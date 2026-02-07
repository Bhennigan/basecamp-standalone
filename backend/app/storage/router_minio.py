"""REST API endpoints for MinIO storage operations"""
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Path
from fastapi.responses import Response, StreamingResponse
import io

from .minio_client import get_minio_client, MinIOClient

router = APIRouter()

VALID_BUCKETS = ["raw", "enriched", "reports", "audit"]


def validate_bucket(bucket: str) -> None:
    """Validate bucket name"""
    if bucket not in VALID_BUCKETS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid bucket. Must be one of: {VALID_BUCKETS}"
        )


@router.post("/upload/{bucket}")
async def upload_file(
    bucket: str = Path(..., description="Target bucket name"),
    file: UploadFile = File(...),
    path_prefix: Optional[str] = Query(None, description="Optional path prefix")
):
    """Upload file to specified bucket"""
    validate_bucket(bucket)
    
    try:
        client = get_minio_client()
        
        # Build object name with optional prefix
        object_name = file.filename
        if path_prefix:
            object_name = f"{path_prefix.strip('/')}/{file.filename}"
        
        # Read file content
        content = await file.read()
        
        # Upload to MinIO
        result_path = client.upload_bytes(
            bucket=bucket,
            object_name=object_name,
            data=content,
            content_type=file.content_type or "application/octet-stream"
        )
        
        return {
            "success": True,
            "bucket": bucket,
            "object_name": object_name,
            "path": result_path,
            "size": len(content),
            "content_type": file.content_type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/download/{bucket}/{path:path}")
async def download_file(
    bucket: str = Path(..., description="Source bucket name"),
    path: str = Path(..., description="Object path in bucket")
):
    """Download file from bucket"""
    validate_bucket(bucket)
    
    try:
        client = get_minio_client()
        data = client.download_file(bucket, path)
        
        # Determine content type from extension
        content_type = "application/octet-stream"
        if path.endswith(".json"):
            content_type = "application/json"
        elif path.endswith(".csv"):
            content_type = "text/csv"
        elif path.endswith(".xlsx"):
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif path.endswith(".pdf"):
            content_type = "application/pdf"
        elif path.endswith(".txt"):
            content_type = "text/plain"
        
        # Get filename from path
        filename = path.split("/")[-1]
        
        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")


@router.get("/list/{bucket}")
async def list_objects(
    bucket: str = Path(..., description="Bucket name"),
    prefix: Optional[str] = Query(None, description="Filter by prefix")
):
    """List objects in bucket with optional prefix filter"""
    validate_bucket(bucket)
    
    try:
        client = get_minio_client()
        objects = client.list_objects(bucket, prefix=prefix or "")
        
        return {
            "bucket": bucket,
            "prefix": prefix,
            "objects": objects,
            "count": len(objects)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List failed: {str(e)}")


@router.delete("/{bucket}/{path:path}")
async def delete_object(
    bucket: str = Path(..., description="Bucket name"),
    path: str = Path(..., description="Object path to delete")
):
    """Delete object from bucket"""
    validate_bucket(bucket)
    
    try:
        client = get_minio_client()
        client.delete_object(bucket, path)
        
        return {
            "success": True,
            "bucket": bucket,
            "deleted": path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.get("/url/{bucket}/{path:path}")
async def get_presigned_url(
    bucket: str = Path(..., description="Bucket name"),
    path: str = Path(..., description="Object path"),
    expires_hours: int = Query(1, ge=1, le=168, description="URL expiry in hours (max 7 days)")
):
    """Get presigned URL for direct object access"""
    validate_bucket(bucket)
    
    try:
        client = get_minio_client()
        url = client.get_presigned_url(bucket, path, expires_hours)
        
        return {
            "bucket": bucket,
            "object": path,
            "url": url,
            "expires_hours": expires_hours
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Object not found: {str(e)}")


@router.get("/buckets")
async def list_buckets():
    """List all available buckets"""
    return {
        "buckets": VALID_BUCKETS,
        "descriptions": {
            "raw": "Raw ingested data files",
            "enriched": "Processed and enriched data",
            "reports": "Generated reports and exports",
            "audit": "Audit logs and compliance records"
        }
    }
