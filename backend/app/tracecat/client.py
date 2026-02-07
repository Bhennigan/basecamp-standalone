"""Tracecat API Client for Base Camp integration"""
import os
import httpx
from typing import Optional, Any
from dataclasses import dataclass


@dataclass
class TracecatConfig:
    api_url: str
    api_key: Optional[str]
    workspace_id: str
    
    @classmethod
    def from_env(cls) -> "TracecatConfig":
        return cls(
            api_url=os.getenv("TRACECAT_API_URL", "http://localhost:80/api"),
            api_key=os.getenv("TRACECAT_API_KEY"),
            workspace_id=os.getenv("TRACECAT_WORKSPACE_ID", "default"),
        )


class TracecatClient:
    """Client for communicating with Tracecat API"""
    
    def __init__(self, config: Optional[TracecatConfig] = None):
        self.config = config or TracecatConfig.from_env()
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.api_url,
                headers=self.headers,
                timeout=30.0,
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    # Workflow Integration
    async def trigger_workflow(self, workflow_id: str, payload: dict) -> dict:
        """Trigger a Tracecat workflow with data from Base Camp"""
        client = await self._get_client()
        response = await client.post(
            f"/workflows/{workflow_id}/trigger",
            json={"data": payload, "workspace_id": self.config.workspace_id},
        )
        response.raise_for_status()
        return response.json()
    
    async def get_workflow_status(self, workflow_id: str, run_id: str) -> dict:
        """Get status of a workflow run"""
        client = await self._get_client()
        response = await client.get(
            f"/workflows/{workflow_id}/runs/{run_id}",
            params={"workspace_id": self.config.workspace_id},
        )
        response.raise_for_status()
        return response.json()
    
    # Case Management
    async def create_case(self, title: str, description: str, data: dict) -> dict:
        """Create a case in Tracecat from Base Camp data"""
        client = await self._get_client()
        response = await client.post(
            "/cases",
            json={
                "title": title,
                "description": description,
                "data": data,
                "workspace_id": self.config.workspace_id,
            },
        )
        response.raise_for_status()
        return response.json()
    
    # Health Check
    async def health_check(self) -> dict:
        """Check if Tracecat API is reachable"""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return {"status": "connected", "tracecat_status": response.json()}
        except Exception as e:
            return {"status": "disconnected", "error": str(e)}


# Global client instance
_tracecat_client: Optional[TracecatClient] = None


def get_tracecat_client() -> TracecatClient:
    global _tracecat_client
    if _tracecat_client is None:
        _tracecat_client = TracecatClient()
    return _tracecat_client
