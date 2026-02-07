"""REST API endpoints for Tracecat integration"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Any

from app.tracecat.client import get_tracecat_client, TracecatClient

router = APIRouter()


class WorkflowTriggerRequest(BaseModel):
    workflow_id: str
    payload: dict


class CaseCreateRequest(BaseModel):
    title: str
    description: str
    data: dict


class TracecatStatus(BaseModel):
    connected: bool
    tracecat_url: str
    error: Optional[str] = None


@router.get("/status", response_model=TracecatStatus)
async def get_tracecat_status():
    """Check Tracecat connection status"""
    client = get_tracecat_client()
    result = await client.health_check()
    return TracecatStatus(
        connected=result["status"] == "connected",
        tracecat_url=client.config.api_url,
        error=result.get("error"),
    )


@router.post("/workflows/trigger")
async def trigger_workflow(request: WorkflowTriggerRequest):
    """Trigger a Tracecat workflow with Base Camp data"""
    client = get_tracecat_client()
    try:
        result = await client.trigger_workflow(request.workflow_id, request.payload)
        return {"status": "triggered", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/{workflow_id}/runs/{run_id}")
async def get_workflow_run_status(workflow_id: str, run_id: str):
    """Get status of a workflow run"""
    client = get_tracecat_client()
    try:
        return await client.get_workflow_status(workflow_id, run_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cases")
async def create_case(request: CaseCreateRequest):
    """Create a case in Tracecat from Base Camp data"""
    client = get_tracecat_client()
    try:
        result = await client.create_case(
            request.title, request.description, request.data
        )
        return {"status": "created", "case": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
