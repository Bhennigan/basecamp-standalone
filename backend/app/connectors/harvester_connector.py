"""TheHarvester OSINT Connector for email and domain reconnaissance"""
import asyncio
import logging
import subprocess
import tempfile
import os
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseConnector, ConnectorConfig, ConnectorResult, ConnectorStatus

logger = logging.getLogger(__name__)


class HarvesterConnector(BaseConnector):
    """
    Connector for TheHarvester CLI tool.
    
    TheHarvester gathers emails, subdomains, hosts, employee names, open ports
    and banners from different public sources like search engines and PGP key
    servers. Essential for digital persona protection reconnaissance.
    """
    
    CONNECTOR_TYPE = "harvester"
    DEFAULT_SOURCES = ["google", "bing", "linkedin", "twitter", "dnsdumpster"]
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.harvester_path = config.config.get("harvester_path", "theHarvester")
        self.timeout_seconds = config.config.get("timeout_seconds", 600)
        self.sources = config.config.get("sources", self.DEFAULT_SOURCES)
        self._harvester_available = False
        
    async def connect(self) -> bool:
        """Verify TheHarvester CLI is available"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [self.harvester_path, "-h"],
                    capture_output=True, text=True, timeout=10
                )
            )
            
            if "theHarvester" in result.stdout or "theHarvester" in result.stderr:
                self._harvester_available = True
                self.status = ConnectorStatus.ACTIVE
                logger.info("TheHarvester CLI available")
                return True
            else:
                logger.error(f"TheHarvester not found: {result.stderr}")
                self.status = ConnectorStatus.ERROR
                return False
                
        except FileNotFoundError:
            logger.error("TheHarvester CLI not found. Install with: pip install theHarvester")
            self.status = ConnectorStatus.ERROR
            return False
        except Exception as e:
            logger.error(f"TheHarvester connection check failed: {str(e)}")
            self.status = ConnectorStatus.ERROR
            return False
    
    async def fetch(self, query: Optional[str] = None) -> ConnectorResult:
        """
        Run TheHarvester against a domain.
        
        Query should be the domain to investigate.
        """
        self.last_run = datetime.utcnow()
        errors: List[str] = []
        data: List[Dict[str, Any]] = []
        
        if not query:
            return ConnectorResult(
                connector_name=self.config.name, timestamp=datetime.utcnow(),
                success=False, records_count=0, data=[],
                errors=["Domain query is required"]
            )
        
        try:
            if not self._harvester_available:
                await self.connect()
                if not self._harvester_available:
                    return ConnectorResult(
                        connector_name=self.config.name, timestamp=datetime.utcnow(),
                        success=False, records_count=0, data=[],
                        errors=["TheHarvester CLI not available"]
                    )
            
            results = await self._run_harvester(query)
            data.extend(results)
            self.status = ConnectorStatus.ACTIVE
            
        except asyncio.TimeoutError:
            errors.append(f"TheHarvester search timed out after {self.timeout_seconds}s")
            self.status = ConnectorStatus.ERROR
        except Exception as e:
            errors.append(str(e))
            logger.error(f"TheHarvester fetch error: {str(e)}")
            self.status = ConnectorStatus.ERROR
        
        return ConnectorResult(
            connector_name=self.config.name, timestamp=datetime.utcnow(),
            success=len(errors) == 0, records_count=len(data), data=data, errors=errors
        )
    
    async def _run_harvester(self, domain: str) -> List[Dict[str, Any]]:
        """Run TheHarvester CLI and parse results"""
        results = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, f"{domain.replace('.', '_')}")
            sources_str = ",".join(self.sources)
            
            cmd = [
                self.harvester_path,
                "-d", domain,
                "-b", sources_str,
                "-f", output_file,
                "-l", "500"
            ]
            
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: subprocess.run(cmd, capture_output=True, text=True)),
                timeout=self.timeout_seconds
            )
            
            xml_file = output_file + ".xml"
            if os.path.exists(xml_file):
                results.extend(self._parse_xml_output(domain, xml_file))
            else:
                results.extend(self._parse_stdout(domain, result.stdout))
        
        return results
    
    def _parse_xml_output(self, domain: str, xml_file: str) -> List[Dict[str, Any]]:
        """Parse TheHarvester XML output"""
        results = []
        
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            for email_elem in root.findall(".//email"):
                if email_elem.text:
                    results.append({
                        "entity_type": "email", "source": "harvester",
                        "domain": domain, "email": email_elem.text.strip(),
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            for host_elem in root.findall(".//host"):
                if host_elem.text:
                    host_text = host_elem.text.strip()
                    ip = host_elem.get("ip", "")
                    results.append({
                        "entity_type": "subdomain", "source": "harvester",
                        "domain": domain, "subdomain": host_text, "ip": ip,
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            for ip_elem in root.findall(".//ip"):
                if ip_elem.text:
                    results.append({
                        "entity_type": "ip_address", "source": "harvester",
                        "domain": domain, "ip": ip_elem.text.strip(),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
        except ET.ParseError as e:
            logger.warning(f"Failed to parse XML output: {e}")
        
        return results
    
    def _parse_stdout(self, domain: str, stdout: str) -> List[Dict[str, Any]]:
        """Parse TheHarvester stdout for results"""
        results = []
        current_section = None
        
        for line in stdout.split('\n'):
            line = line.strip()
            
            if "Emails found:" in line:
                current_section = "emails"
                continue
            elif "Hosts found:" in line:
                current_section = "hosts"
                continue
            elif "IPs found:" in line:
                current_section = "ips"
                continue
            elif line.startswith("[*]") or line.startswith("[-]"):
                current_section = None
                continue
            
            if not line or line.startswith("-"):
                continue
                
            if current_section == "emails" and "@" in line:
                results.append({
                    "entity_type": "email", "source": "harvester",
                    "domain": domain, "email": line,
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif current_section == "hosts":
                parts = line.split(":")
                subdomain = parts[0].strip()
                ip = parts[1].strip() if len(parts) > 1 else ""
                results.append({
                    "entity_type": "subdomain", "source": "harvester",
                    "domain": domain, "subdomain": subdomain, "ip": ip,
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif current_section == "ips":
                results.append({
                    "entity_type": "ip_address", "source": "harvester",
                    "domain": domain, "ip": line,
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Check TheHarvester connector health"""
        try:
            connected = await self.connect()
            return {
                "healthy": connected, "status": self.status.value,
                "harvester_path": self.harvester_path,
                "harvester_available": self._harvester_available,
                "sources": self.sources,
                "last_run": self.last_run.isoformat() if self.last_run else None
            }
        except Exception as e:
            return {"healthy": False, "status": "error", "message": str(e)}
