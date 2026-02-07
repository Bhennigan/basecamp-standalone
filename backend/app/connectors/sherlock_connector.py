"""Sherlock OSINT Connector for username searches across social networks"""
import asyncio
import logging
import json
import subprocess
import tempfile
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseConnector, ConnectorConfig, ConnectorResult, ConnectorStatus

logger = logging.getLogger(__name__)


class SherlockConnector(BaseConnector):
    """
    Connector for Sherlock CLI tool.
    
    Sherlock hunts down social media accounts by username across many
    social networks. This connector wraps the CLI tool for automated
    username reconnaissance in digital persona protection.
    """
    
    CONNECTOR_TYPE = "sherlock"
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.sherlock_path = config.config.get("sherlock_path", "sherlock")
        self.timeout_seconds = config.config.get("timeout_seconds", 300)
        self._sherlock_available = False
        
    async def connect(self) -> bool:
        """Verify Sherlock CLI is available"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [self.sherlock_path, "--version"],
                    capture_output=True, text=True, timeout=10
                )
            )
            
            if result.returncode == 0 or "sherlock" in result.stdout.lower():
                self._sherlock_available = True
                self.status = ConnectorStatus.ACTIVE
                logger.info("Sherlock CLI available")
                return True
            else:
                logger.error(f"Sherlock not found or error: {result.stderr}")
                self.status = ConnectorStatus.ERROR
                return False
                
        except FileNotFoundError:
            logger.error("Sherlock CLI not found. Install with: pip install sherlock-project")
            self.status = ConnectorStatus.ERROR
            return False
        except Exception as e:
            logger.error(f"Sherlock connection check failed: {str(e)}")
            self.status = ConnectorStatus.ERROR
            return False
    
    async def fetch(self, query: Optional[str] = None) -> ConnectorResult:
        """Search for username across social networks."""
        self.last_run = datetime.utcnow()
        errors: List[str] = []
        data: List[Dict[str, Any]] = []
        
        if not query:
            return ConnectorResult(
                connector_name=self.config.name, timestamp=datetime.utcnow(),
                success=False, records_count=0, data=[],
                errors=["Username query is required"]
            )
        
        try:
            if not self._sherlock_available:
                await self.connect()
                if not self._sherlock_available:
                    return ConnectorResult(
                        connector_name=self.config.name, timestamp=datetime.utcnow(),
                        success=False, records_count=0, data=[],
                        errors=["Sherlock CLI not available"]
                    )
            
            results = await self._run_sherlock(query)
            data.extend(results)
            self.status = ConnectorStatus.ACTIVE
            
        except asyncio.TimeoutError:
            errors.append(f"Sherlock search timed out after {self.timeout_seconds}s")
            self.status = ConnectorStatus.ERROR
        except Exception as e:
            errors.append(str(e))
            logger.error(f"Sherlock fetch error: {str(e)}")
            self.status = ConnectorStatus.ERROR
        
        return ConnectorResult(
            connector_name=self.config.name, timestamp=datetime.utcnow(),
            success=len(errors) == 0, records_count=len(data), data=data, errors=errors
        )
    
    async def _run_sherlock(self, username: str) -> List[Dict[str, Any]]:
        """Run Sherlock CLI and parse results"""
        results = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, f"{username}.json")
            
            cmd = [self.sherlock_path, username, "--output", output_file, "--json", output_file, "--print-found", "--timeout", "30"]
            
            sites = self.config.config.get("sites", [])
            if sites:
                for site in sites:
                    cmd.extend(["--site", site])
            
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: subprocess.run(cmd, capture_output=True, text=True)),
                timeout=self.timeout_seconds
            )
            
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    json_results = json.load(f)
                    for site_name, site_data in json_results.items():
                        if site_data.get("status") == "Claimed":
                            results.append(self._normalize_result(username, site_name, site_data))
            else:
                results.extend(self._parse_stdout(username, result.stdout))
        
        return results
    
    def _parse_stdout(self, username: str, stdout: str) -> List[Dict[str, Any]]:
        """Parse Sherlock stdout for found accounts"""
        results = []
        for line in stdout.split('\n'):
            line = line.strip()
            if line and ':' in line and 'http' in line.lower():
                parts = line.split(':', 1)
                if len(parts) == 2:
                    site_name = parts[0].strip()
                    url = parts[1].strip()
                    results.append({
                        "entity_type": "social_account", "source": "sherlock",
                        "username": username, "platform": site_name, "url": url,
                        "status": "found", "timestamp": datetime.utcnow().isoformat()
                    })
        return results
    
    def _normalize_result(self, username: str, site_name: str, site_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Sherlock result to standard format"""
        return {
            "entity_type": "social_account", "source": "sherlock",
            "username": username, "platform": site_name,
            "url": site_data.get("url_user"), "status": site_data.get("status", "unknown"),
            "response_time": site_data.get("response_time_s"),
            "http_status": site_data.get("http_status"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Sherlock connector health"""
        try:
            connected = await self.connect()
            return {
                "healthy": connected, "status": self.status.value,
                "sherlock_path": self.sherlock_path,
                "sherlock_available": self._sherlock_available,
                "last_run": self.last_run.isoformat() if self.last_run else None
            }
        except Exception as e:
            return {"healthy": False, "status": "error", "message": str(e)}
