"""Shodan OSINT Connector for infrastructure reconnaissance"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseConnector, ConnectorConfig, ConnectorResult, ConnectorStatus

logger = logging.getLogger(__name__)


class ShodanConnector(BaseConnector):
    """Connector for Shodan API for infrastructure reconnaissance."""
    CONNECTOR_TYPE = "shodan"
    DEFAULT_API_URL = "https://api.shodan.io"
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.api_url = config.api_url or self.DEFAULT_API_URL
        self._client = None
        
    async def connect(self) -> bool:
        """Establish connection and verify API credentials"""
        try:
            try:
                import shodan
            except ImportError:
                logger.error("Shodan library not installed. Run: pip install shodan")
                self.status = ConnectorStatus.ERROR
                return False
            
            if not self.api_key:
                logger.error("Shodan API key not configured")
                self.status = ConnectorStatus.ERROR
                return False
            
            self._client = shodan.Shodan(self.api_key)
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self._client.info)
            logger.info(f"Shodan connected. Query credits: {info.get('query_credits', 0)}")
            self.status = ConnectorStatus.ACTIVE
            return True
            
        except Exception as e:
            logger.error(f"Shodan connection failed: {str(e)}")
            self.status = ConnectorStatus.ERROR
            return False
    
    async def fetch(self, query: Optional[str] = None) -> ConnectorResult:
        """Fetch data from Shodan."""
        self.last_run = datetime.utcnow()
        errors: List[str] = []
        data: List[Dict[str, Any]] = []
        
        try:
            if not self._client:
                await self.connect()
                if not self._client:
                    return ConnectorResult(
                        connector_name=self.config.name,
                        timestamp=datetime.utcnow(),
                        success=False, records_count=0, data=[],
                        errors=["Failed to connect to Shodan"]
                    )
            
            loop = asyncio.get_event_loop()
            
            if not query:
                info = await loop.run_in_executor(None, self._client.info)
                data.append(self._normalize_info(info))
            elif self._is_ip(query):
                result = await loop.run_in_executor(None, self._client.host, query)
                data.append(self._normalize_host(result))
            elif self._is_domain(query):
                result = await loop.run_in_executor(None, self._client.dns.domain_info, query)
                data.append(self._normalize_domain(result))
            else:
                results = await loop.run_in_executor(None, lambda: self._client.search(query, limit=100))
                for match in results.get('matches', []):
                    data.append(self._normalize_match(match))
            
            self.status = ConnectorStatus.ACTIVE
            
        except Exception as e:
            error_msg = str(e)
            errors.append(error_msg)
            logger.error(f"Shodan fetch error: {error_msg}")
            if "rate limit" in error_msg.lower():
                self.status = ConnectorStatus.RATE_LIMITED
            else:
                self.status = ConnectorStatus.ERROR
        
        return ConnectorResult(
            connector_name=self.config.name, timestamp=datetime.utcnow(),
            success=len(errors) == 0, records_count=len(data), data=data, errors=errors
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Shodan connector health and API status"""
        try:
            if not self._client:
                return {"healthy": False, "status": "disconnected", "message": "Client not initialized"}
            
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self._client.info)
            
            return {
                "healthy": True, "status": self.status.value,
                "query_credits": info.get("query_credits", 0),
                "scan_credits": info.get("scan_credits", 0),
                "plan": info.get("plan", "unknown"),
                "last_run": self.last_run.isoformat() if self.last_run else None
            }
        except Exception as e:
            return {"healthy": False, "status": "error", "message": str(e)}
    
    def _is_ip(self, query: str) -> bool:
        """Check if query is an IP address"""
        import re
        return bool(re.match(r'^(\d{1,3}\.){3}\d{1,3}$', query))
    
    def _is_domain(self, query: str) -> bool:
        """Check if query is a domain name"""
        import re
        pattern = r'^[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+$'
        return bool(re.match(pattern, query)) and not self._is_ip(query)
    
    def _normalize_info(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize API info response"""
        return {
            "entity_type": "api_info", "source": "shodan",
            "query_credits": info.get("query_credits"),
            "scan_credits": info.get("scan_credits"),
            "plan": info.get("plan"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _normalize_host(self, host: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize host lookup result"""
        return {
            "entity_type": "host", "source": "shodan",
            "ip": host.get("ip_str"), "hostnames": host.get("hostnames", []),
            "country": host.get("country_code"), "city": host.get("city"),
            "org": host.get("org"), "asn": host.get("asn"), "isp": host.get("isp"),
            "ports": host.get("ports", []), "vulns": host.get("vulns", []),
            "services": [{"port": s.get("port"), "protocol": s.get("transport"), "product": s.get("product"), "version": s.get("version"), "banner": s.get("data", "")[:500]} for s in host.get("data", [])],
            "last_update": host.get("last_update"),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _normalize_domain(self, domain: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize domain info result"""
        return {
            "entity_type": "domain", "source": "shodan",
            "domain": domain.get("domain"), "subdomains": domain.get("subdomains", []),
            "dns_records": {
                "A": domain.get("data", {}).get("A", []),
                "AAAA": domain.get("data", {}).get("AAAA", []),
                "MX": domain.get("data", {}).get("MX", []),
                "NS": domain.get("data", {}).get("NS", []),
                "TXT": domain.get("data", {}).get("TXT", [])
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _normalize_match(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize search match result"""
        return {
            "entity_type": "search_result", "source": "shodan",
            "ip": match.get("ip_str"), "port": match.get("port"),
            "protocol": match.get("transport"), "hostnames": match.get("hostnames", []),
            "country": match.get("location", {}).get("country_code"),
            "org": match.get("org"), "product": match.get("product"),
            "version": match.get("version"), "banner": match.get("data", "")[:500],
            "timestamp": datetime.utcnow().isoformat()
        }
