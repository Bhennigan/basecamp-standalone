"""Netcraft Connector for takedown intelligence and brand protection"""
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseConnector, ConnectorConfig, ConnectorResult, ConnectorStatus

logger = logging.getLogger(__name__)


class NetcraftConnector(BaseConnector):
    """
    Connector for Netcraft Takedown / Threat Intelligence API.

    Provides access to:
    - Takedown operations (phishing, malware, brand abuse)
    - Attack reports and threat intelligence
    - Submission of new attacks for takedown
    - Brand-specific monitoring via configured brand name
    """

    CONNECTOR_TYPE = "netcraft"
    DEFAULT_API_URL = "https://takedown.netcraft.com/api/v1"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.api_url = config.api_url or self.DEFAULT_API_URL
        self.brand = config.config.get("brand", "")
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> bool:
        """Establish connection and verify API credentials"""
        try:
            if not self.api_key:
                logger.error("Netcraft API key not configured")
                self.status = ConnectorStatus.ERROR
                return False

            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            # Verify credentials by listing takedowns
            response = await self._client.get(
                "/attacks", params={"count": 1}
            )
            if response.status_code == 200:
                logger.info(
                    f"Netcraft connected successfully | brand={self.brand}"
                )
                self.status = ConnectorStatus.ACTIVE
                return True
            elif response.status_code == 401 or response.status_code == 403:
                logger.error("Netcraft authentication failed")
                self.status = ConnectorStatus.ERROR
                return False
            else:
                logger.error(
                    f"Netcraft connection error: {response.status_code}"
                )
                self.status = ConnectorStatus.ERROR
                return False

        except Exception as e:
            logger.error(f"Netcraft connection failed: {str(e)}")
            self.status = ConnectorStatus.ERROR
            return False

    async def fetch(self, query: Optional[str] = None) -> ConnectorResult:
        """
        Fetch takedown and attack data from Netcraft.

        Query types:
        - None / empty: fetch recent attacks for configured brand
        - URL: report/search for a specific URL
        - domain: search attacks related to a domain
        - "takedowns": fetch active takedown requests
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
                        success=False,
                        records_count=0,
                        data=[],
                        errors=["Failed to connect to Netcraft"],
                    )

            if query and query.strip().lower() == "takedowns":
                takedowns = await self._fetch_takedowns()
                data.extend(takedowns)
            elif query and (
                query.startswith("http://") or query.startswith("https://")
            ):
                # Search by URL
                attacks = await self._search_attacks(url=query)
                data.extend(attacks)
            elif query:
                # Search by domain/keyword
                attacks = await self._search_attacks(domain=query)
                data.extend(attacks)
            else:
                # Default: fetch recent attacks for our brand
                attacks = await self._fetch_attacks()
                data.extend(attacks)

                # Also fetch active takedowns
                takedowns = await self._fetch_takedowns()
                data.extend(takedowns)

            self.status = ConnectorStatus.ACTIVE

        except Exception as e:
            error_msg = str(e)
            errors.append(error_msg)
            logger.error(f"Netcraft fetch error: {error_msg}")

            if "429" in error_msg or "rate" in error_msg.lower():
                self.status = ConnectorStatus.RATE_LIMITED
            else:
                self.status = ConnectorStatus.ERROR

        return ConnectorResult(
            connector_name=self.config.name,
            timestamp=datetime.utcnow(),
            success=len(errors) == 0,
            records_count=len(data),
            data=data,
            errors=errors,
        )

    async def _fetch_attacks(self) -> List[Dict[str, Any]]:
        """Fetch recent attacks/threats reported against our brand"""
        attacks = []
        params: Dict[str, Any] = {"count": 100}
        if self.brand:
            params["brand"] = self.brand

        response = await self._client.get("/attacks", params=params)
        if response.status_code == 200:
            result = response.json()
            for attack in result if isinstance(result, list) else result.get("attacks", result.get("results", [])):
                attacks.append(self._normalize_attack(attack))
        else:
            logger.warning(f"Netcraft attacks endpoint returned {response.status_code}")

        return attacks

    async def _fetch_takedowns(self) -> List[Dict[str, Any]]:
        """Fetch active takedown requests"""
        takedowns = []
        params: Dict[str, Any] = {"count": 100}
        if self.brand:
            params["brand"] = self.brand

        response = await self._client.get("/takedowns", params=params)
        if response.status_code == 200:
            result = response.json()
            for td in result if isinstance(result, list) else result.get("takedowns", result.get("results", [])):
                takedowns.append(self._normalize_takedown(td))
        else:
            logger.warning(f"Netcraft takedowns endpoint returned {response.status_code}")

        return takedowns

    async def _search_attacks(
        self,
        url: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for attacks by URL or domain"""
        attacks = []
        params: Dict[str, Any] = {"count": 100}
        if url:
            params["url"] = url
        if domain:
            params["domain"] = domain
        if self.brand:
            params["brand"] = self.brand

        response = await self._client.get("/attacks", params=params)
        if response.status_code == 200:
            result = response.json()
            for attack in result if isinstance(result, list) else result.get("attacks", result.get("results", [])):
                attacks.append(self._normalize_attack(attack))

        return attacks

    async def submit_attack(
        self, attack_url: str, comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a new URL for takedown"""
        if not self._client:
            await self.connect()

        payload: Dict[str, Any] = {"attack": attack_url}
        if self.brand:
            payload["brand"] = self.brand
        if comment:
            payload["comment"] = comment

        response = await self._client.post("/attacks", json=payload)
        if response.status_code in (200, 201, 202):
            return {
                "success": True,
                "response": response.json(),
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
            }

    async def health_check(self) -> Dict[str, Any]:
        """Check Netcraft connector health"""
        try:
            if not self._client:
                return {
                    "healthy": False,
                    "status": "disconnected",
                    "message": "Client not initialized",
                }

            response = await self._client.get(
                "/attacks", params={"count": 1}
            )

            return {
                "healthy": response.status_code == 200,
                "status": self.status.value,
                "api_status": response.status_code,
                "brand": self.brand,
                "last_run": self.last_run.isoformat() if self.last_run else None,
            }

        except Exception as e:
            return {"healthy": False, "status": "error", "message": str(e)}

    def _normalize_attack(self, attack: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Netcraft attack report to standard format"""
        return {
            "entity_type": "attack",
            "source": "netcraft",
            "attack_id": attack.get("id"),
            "attack_url": attack.get("url") or attack.get("attack_url"),
            "attack_type": attack.get("attack_type") or attack.get("type"),
            "status": attack.get("status"),
            "country": attack.get("country") or attack.get("country_code"),
            "ip": attack.get("ip"),
            "domain": attack.get("domain"),
            "brand": attack.get("brand") or self.brand,
            "hostname": attack.get("hostname"),
            "certificate": attack.get("certificate"),
            "first_seen": attack.get("first_seen") or attack.get("date_reported"),
            "last_updated": attack.get("last_updated") or attack.get("date_updated"),
            "region": attack.get("region"),
            "registrar": attack.get("registrar"),
            "hosting_provider": attack.get("hosting_provider") or attack.get("hoster"),
            "target_brand": attack.get("target_brand") or attack.get("brand"),
            "evidence_url": attack.get("evidence_url"),
            "screenshot_url": attack.get("screenshot_url"),
            "fetched_at": datetime.utcnow().isoformat(),
        }

    def _normalize_takedown(self, td: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Netcraft takedown record to standard format"""
        return {
            "entity_type": "takedown",
            "source": "netcraft",
            "takedown_id": td.get("id"),
            "attack_url": td.get("url") or td.get("attack_url"),
            "status": td.get("status"),
            "date_submitted": td.get("date_submitted") or td.get("submitted"),
            "date_resolved": td.get("date_resolved") or td.get("resolved"),
            "attack_type": td.get("attack_type") or td.get("type"),
            "brand": td.get("brand") or self.brand,
            "domain": td.get("domain"),
            "ip": td.get("ip"),
            "country": td.get("country") or td.get("country_code"),
            "hostname": td.get("hostname"),
            "hosting_provider": td.get("hosting_provider") or td.get("hoster"),
            "registrar": td.get("registrar"),
            "resolution": td.get("resolution"),
            "fetched_at": datetime.utcnow().isoformat(),
        }
