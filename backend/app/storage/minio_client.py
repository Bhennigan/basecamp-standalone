"""MinIO client for object storage"""
import os
from typing import Optional, BinaryIO
from minio import Minio
from minio.error import S3Error
import io

class MinIOClient:
    """Client for MinIO object storage with /raw, /enriched, /reports buckets"""
    
    BUCKETS = ["raw", "enriched", "reports", "audit"]
    
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
    async def ensure_buckets(self):
        """Create buckets if they don't exist"""
        for bucket in self.BUCKETS:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                
    def upload_file(self, bucket: str, object_name: str, data: BinaryIO, 
                    content_type: str = "application/octet-stream") -> str:
        """Upload file to bucket, return object path"""
        data.seek(0, 2)
        size = data.tell()
        data.seek(0)
        
        self.client.put_object(
            bucket, object_name, data, size, content_type=content_type
        )
        return f"{bucket}/{object_name}"
    
    def upload_bytes(self, bucket: str, object_name: str, data: bytes,
                     content_type: str = "application/octet-stream") -> str:
        """Upload bytes to bucket"""
        stream = io.BytesIO(data)
        return self.upload_file(bucket, object_name, stream, content_type)
    
    def download_file(self, bucket: str, object_name: str) -> bytes:
        """Download file from bucket"""
        response = self.client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    
    def list_objects(self, bucket: str, prefix: str = "") -> list:
        """List objects in bucket with optional prefix"""
        objects = self.client.list_objects(bucket, prefix=prefix, recursive=True)
        return [{"name": obj.object_name, "size": obj.size, "modified": obj.last_modified} 
                for obj in objects]
    
    def delete_object(self, bucket: str, object_name: str):
        """Delete object from bucket"""
        self.client.remove_object(bucket, object_name)
        
    def get_presigned_url(self, bucket: str, object_name: str, expires_hours: int = 1) -> str:
        """Get presigned URL for object access"""
        from datetime import timedelta
        return self.client.presigned_get_object(
            bucket, object_name, expires=timedelta(hours=expires_hours)
        )

# Global instance
_minio_client: Optional[MinIOClient] = None

def get_minio_client() -> MinIOClient:
    global _minio_client
    if _minio_client is None:
        _minio_client = MinIOClient()
    return _minio_client
