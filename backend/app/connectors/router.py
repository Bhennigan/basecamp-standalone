"""FastAPI Router for OSINT Connector endpoints"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import ConnectorConfig, ConnectorResult
from .manager import get_connector_manager, ConnectorManager

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


class ConnectorCreateRequest(BaseModel):
    """Request model for creating a new connector"""
    name: str
    connector_type: str
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    enabled: bool = True
    poll_interval_seconds: int = 3600
    config: Dict[str, Any] = {}


class ConnectorResponse(BaseModel):
    """Response model for connector information"""
    name: str
    type: str
    status: str
    enabled: bool
    last_run: Optional[datetime] = None


class FetchRequest(BaseModel):
    """Request model for fetching data"""
    query: Optional[str] = None


class TestRequest(BaseModel):
    """Request model for testing a connector"""
    test_query: Optional[str] = None


def get_manager() -> ConnectorManager:
    """Dependency to get the connector manager"""
    return get_connector_manager()


@router.get("", response_model=List[ConnectorResponse])
async def list_connectors(manager: ConnectorManager = Depends(get_manager)):
    """
    List all registered connectors.
    
    Returns a list of all connectors with their current status.
    """
    connectors = manager.list_connectors()
    return [
        ConnectorResponse(
            name=c["name"],
            type=c["type"],
            status=c["status"].value if hasattr(c["status"], "value") else c["status"],
            enabled=c["enabled"],
            last_run=c.get("last_run")
        )
        for c in connectors
    ]


@router.get("/types")
async def list_connector_types():
    """
    List available connector types.
    
    Returns the types of connectors that can be registered.
    """
    return {
        "types": ConnectorManager.get_available_types(),
        "descriptions": {
            "shodan": "Shodan API for infrastructure reconnaissance",
            "zerofox": "ZeroFox API for impersonation and threat alerts",
            "sherlock": "Sherlock CLI for username searches",
            "harvester": "TheHarvester CLI for email and domain reconnaissance",
            "netcraft": "Netcraft API for takedown intelligence and brand protection"
        }
    }


@router.post("", response_model=ConnectorResponse)
async def create_connector(
    request: ConnectorCreateRequest,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Register a new connector.
    
    Creates and registers a new OSINT connector with the provided configuration.
    """
    try:
        config = ConnectorConfig(
            name=request.name,
            connector_type=request.connector_type,
            api_key=request.api_key,
            api_url=request.api_url,
            enabled=request.enabled,
            poll_interval_seconds=request.poll_interval_seconds,
            config=request.config
        )
        
        connector = manager.register_connector(config)
        status = connector.get_status()
        
        return ConnectorResponse(
            name=status["name"],
            type=status["type"],
            status=status["status"].value,
            enabled=status["enabled"],
            last_run=status.get("last_run")
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}")
async def delete_connector(
    name: str,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Unregister a connector.
    
    Removes a connector and stops any polling tasks.
    """
    if not manager.unregister_connector(name):
        raise HTTPException(status_code=404, detail=f"Connector not found: {name}")
    
    return {"message": f"Connector {name} unregistered successfully"}


@router.get("/{name}/status")
async def get_connector_status(
    name: str,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Get connector status.
    
    Returns detailed status information for a specific connector.
    """
    connector = manager.get_connector(name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector not found: {name}")
    
    status = connector.get_status()
    status["status"] = status["status"].value if hasattr(status["status"], "value") else status["status"]
    
    return status


@router.get("/{name}/health")
async def get_connector_health(
    name: str,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Get connector health.
    
    Performs a health check on the connector and returns detailed health info.
    """
    connector = manager.get_connector(name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector not found: {name}")
    
    try:
        health = await connector.health_check()
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/fetch")
async def fetch_from_connector(
    name: str,
    request: FetchRequest,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Trigger manual fetch from connector.
    
    Fetches data from the specified connector with an optional query.
    """
    try:
        result = await manager.fetch_from(name, request.query)
        return {
            "connector_name": result.connector_name,
            "timestamp": result.timestamp.isoformat(),
            "success": result.success,
            "records_count": result.records_count,
            "data": result.data,
            "errors": result.errors
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/test")
async def test_connector(
    name: str,
    request: TestRequest,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Test connector.
    
    Runs connection, health, and optionally fetch tests on the connector.
    """
    try:
        result = await manager.test_connector(name, request.test_query)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/connect")
async def connect_connector(
    name: str,
    manager: ConnectorManager = Depends(get_manager)
):
    """
    Connect a connector.
    
    Establishes connection/verifies credentials for the connector.
    """
    connector = manager.get_connector(name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector not found: {name}")
    
    try:
        success = await connector.connect()
        return {
            "connector": name,
            "connected": success,
            "status": connector.status.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/all")
async def health_check_all(manager: ConnectorManager = Depends(get_manager)):
    """
    Health check all connectors.
    
    Performs health checks on all registered connectors.
    """
    return await manager.health_check_all()


@router.post("/polling/start")
async def start_polling(manager: ConnectorManager = Depends(get_manager)):
    """
    Start polling for all connectors.
    
    Begins scheduled polling for all enabled connectors.
    """
    await manager.start_polling()
    return {"message": "Polling started for all enabled connectors"}


@router.post("/polling/stop")
async def stop_polling(manager: ConnectorManager = Depends(get_manager)):
    """
    Stop polling for all connectors.
    
    Stops all scheduled polling tasks.
    """
    await manager.stop_polling()
    return {"message": "Polling stopped"}
