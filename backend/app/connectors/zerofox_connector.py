"""ZeroFox OSINT Connector for impersonation and threat alerts"""
import asyncio
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseConnector, ConnectorConfig, ConnectorResult, ConnectorStatus

logger = logging.getLogger(__name__)


class ZeroFoxConnector(BaseConnector):
    """
    Connector for ZeroFox API.
    
    ZeroFox provides digital risk protection including impersonation detection,
    brand protection, and threat intelligence for digital persona protection.
    """
    
    CONNECTOR_TYPE = "zerofox"
    DEFAULT_API_URL = "https://api.zerofox.com/1.0"
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.api_url = config.api_url or self.DEFAULT_API_URL
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None
        
    async def connect(self) -> bool:
        """Establish connection and verify API credentials"""
        try:
            if not self.api_key:
                logger.error("ZeroFox API key not configured")
                self.status = ConnectorStatus.ERROR
                return False
            
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={"Authorization": f"Token {self.api_key}"},
                timeout=30.0
            )
            
            # Verify credentials by fetching account info
            response = await self._client.get("/accounts/")
            if response.status_code == 200:
                logger.info("ZeroFox connected successfully")
                self.status = ConnectorStatus.ACTIVE
                return True
            elif response.status_code == 401:
                logger.error("ZeroFox authentication failed")
                self.status = ConnectorStatus.ERROR
                return False
            else:
                logger.error(f"ZeroFox connection error: {response.status_code}")
                self.status = ConnectorStatus.ERROR
                return False
                
        except Exception as e:
            logger.error(f"ZeroFox connection failed: {str(e)}")
            self.status = ConnectorStatus.ERROR
            return False
    
    async def fetch(self, query: Optional[str] = None) -> ConnectorResult:
        """
        Fetch alerts and threat data from ZeroFox.
        
        Query can specify alert type or search criteria.
        """
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
                        errors=["Failed to connect to ZeroFox"]
                    )
            
            # Fetch alerts
            alerts = await self._fetch_alerts(query)
            data.extend(alerts)
            
            # Fetch entities if configured
            if self.config.config.get("fetch_entities", True):
                entities = await self._fetch_entities()
                data.extend(entities)
            
            self.status = ConnectorStatus.ACTIVE
            
        except Exception as e:
            error_msg = str(e)
            errors.append(error_msg)
            logger.error(f"ZeroFox fetch error: {error_msg}")
            
            if "429" in error_msg or "rate" in error_msg.lower():
                self.status = ConnectorStatus.RATE_LIMITED
            else:
                self.status = ConnectorStatus.ERROR
        
        return ConnectorResult(
            connector_name=self.config.name, timestamp=datetime.utcnow(),
            success=len(errors) == 0, records_count=len(data), data=data, errors=errors
        )
    
    async def _fetch_alerts(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch alerts from ZeroFox"""
        alerts = []
        params = {"limit": 100, "status": "open"}
        
        if query:
            params["search"] = query
        
        response = await self._client.get("/alerts/", params=params)
        if response.status_code == 200:
            result = response.json()
            for alert in result.get("alerts", []):
                alerts.append(self._normalize_alert(alert))
        
        return alerts
    
    async def _fetch_entities(self) -> List[Dict[str, Any]]:
        """Fetch protected entities from ZeroFox"""
        entities = []
        
        response = await self._client.get("/entities/", params={"limit": 100})
        if response.status_code == 200:
            result = response.json()
            for entity in result.get("entities", []):
                entities.append(self._normalize_entity(entity))
        
        return entities
    
    async def health_check(self) -> Dict[str, Any]:
        """Check ZeroFox connector health"""
        try:
            if not self._client:
                return {"healthy": False, "status": "disconnected", "message": "Client not initialized"}
            
            response = await self._client.get("/accounts/")
            
            return {
                "healthy": response.status_code == 200,
                "status": self.status.value,
                "api_status": response.status_code,
                "last_run": self.last_run.isoformat() if self.last_run else None
            }
            
        except Exception as e:
            return {"healthy": False, "status": "error", "message": str(e)}
    
    def _normalize_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize ZeroFox alert to standard format"""
        return {
            "entity_type": "alert",
            "source": "zerofox",
            "alert_id": alert.get("id"),
            "alert_type": alert.get("alert_type"),
            "severity": alert.get("severity"),
            "status": alert.get("status"),
            "rule_name": alert.get("rule_name"),
            "entity": alert.get("entity", {}).get("name"),
            "offending_content": {
                "url": alert.get("offending_content_url"),
                "type": alert.get("content_type"),
                "created_at": alert.get("content_created_at")
            },
            "perpetrator": {
                "username": alert.get("perpetrator", {}).get("username"),
                "url": alert.get("perpetrator", {}).get("url"),
                "network": alert.get("perpetrator", {}).get("network")
            },
            "timestamp": alert.get("timestamp"),
            "fetched_at": datetime.utcnow().isoformat()
        }
    
    def _normalize_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize ZeroFox entity to standard format"""
        return {
            "entity_type": "protected_entity",
            "source": "zerofox",
            "entity_id": entity.get("id"),
            "name": entity.get("name"),
            "type": entity.get("type_id"),
            "policy_id": entity.get("policy_id"),
            "labels": entity.get("labels", []),
            "strict_name_matching": entity.get("strict_name_matching"),
            "timestamp": datetime.utcnow().isoformat()
        }
