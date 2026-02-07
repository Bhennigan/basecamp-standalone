"""Base connector class for OSINT tools"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class ConnectorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


class ConnectorConfig(BaseModel):
    name: str
    connector_type: str
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    enabled: bool = True
    poll_interval_seconds: int = 3600
    config: Dict[str, Any] = {}


class ConnectorResult(BaseModel):
    connector_name: str
    timestamp: datetime
    success: bool
    records_count: int
    data: List[Dict[str, Any]]
    errors: List[str] = []


class BaseConnector(ABC):
    """Abstract base class for all OSINT connectors"""
    
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.status = ConnectorStatus.INACTIVE
        self.last_run: Optional[datetime] = None
        
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection/verify credentials"""
        pass
    
    @abstractmethod
    async def fetch(self, query: Optional[str] = None) -> ConnectorResult:
        """Fetch data from the source"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check connector health"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.config.name,
            "type": self.config.connector_type,
            "status": self.status,
            "last_run": self.last_run,
            "enabled": self.config.enabled
        }
