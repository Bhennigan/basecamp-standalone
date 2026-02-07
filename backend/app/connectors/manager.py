"""Connector Manager for orchestrating OSINT tool connectors"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Type
from datetime import datetime

from .base import BaseConnector, ConnectorConfig, ConnectorResult, ConnectorStatus
from .shodan_connector import ShodanConnector
from .zerofox_connector import ZeroFoxConnector
from .sherlock_connector import SherlockConnector
from .harvester_connector import HarvesterConnector

logger = logging.getLogger(__name__)


class ConnectorManager:
    """
    Manages registration, lifecycle, and scheduling of OSINT connectors.
    
    This manager provides a centralized interface for:
    - Registering and configuring connectors
    - Managing connector lifecycle (connect, disconnect)
    - Scheduling periodic polling
    - Aggregating results from multiple connectors
    """
    
    CONNECTOR_TYPES: Dict[str, Type[BaseConnector]] = {
        "shodan": ShodanConnector,
        "zerofox": ZeroFoxConnector,
        "sherlock": SherlockConnector,
        "harvester": HarvesterConnector,
    }
    
    def __init__(self):
        self._connectors: Dict[str, BaseConnector] = {}
        self._polling_tasks: Dict[str, asyncio.Task] = {}
        self._results_callback = None
        self._running = False
        
    def register_connector(self, config: ConnectorConfig) -> BaseConnector:
        """Register a new connector with the manager"""
        if config.name in self._connectors:
            raise ValueError(f"Connector {config.name} already registered")
        
        connector_class = self.CONNECTOR_TYPES.get(config.connector_type)
        if not connector_class:
            raise ValueError(f"Unknown connector type: {config.connector_type}")
        
        connector = connector_class(config)
        self._connectors[config.name] = connector
        logger.info(f"Registered connector: {config.name} ({config.connector_type})")
        
        return connector
    
    def unregister_connector(self, name: str) -> bool:
        """Unregister a connector and stop its polling"""
        if name not in self._connectors:
            return False
        
        if name in self._polling_tasks:
            self._polling_tasks[name].cancel()
            del self._polling_tasks[name]
        
        del self._connectors[name]
        logger.info(f"Unregistered connector: {name}")
        return True
    
    def get_connector(self, name: str) -> Optional[BaseConnector]:
        """Get a connector by name"""
        return self._connectors.get(name)
    
    def list_connectors(self) -> List[Dict[str, Any]]:
        """List all registered connectors with their status"""
        return [conn.get_status() for conn in self._connectors.values()]
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connect all registered connectors"""
        results = {}
        tasks = []
        
        for name, connector in self._connectors.items():
            if connector.config.enabled:
                tasks.append((name, connector.connect()))
        
        for name, task in tasks:
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Failed to connect {name}: {e}")
                results[name] = False
        
        return results
    
    async def fetch_from(self, name: str, query: Optional[str] = None) -> ConnectorResult:
        """Fetch data from a specific connector"""
        connector = self._connectors.get(name)
        if not connector:
            raise ValueError(f"Connector not found: {name}")
        
        result = await connector.fetch(query)
        
        if self._results_callback:
            await self._results_callback(result)
        
        return result
    
    async def fetch_all(self, query: Optional[str] = None) -> List[ConnectorResult]:
        """Fetch data from all enabled connectors"""
        results = []
        tasks = []
        
        for name, connector in self._connectors.items():
            if connector.config.enabled:
                tasks.append(self.fetch_from(name, query))
        
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
            except Exception as e:
                logger.error(f"Fetch error: {e}")
        
        return results
    
    def set_results_callback(self, callback):
        """Set callback function to process results (e.g., enrichment pipeline)"""
        self._results_callback = callback
    
    async def start_polling(self):
        """Start polling for all enabled connectors"""
        self._running = True
        
        for name, connector in self._connectors.items():
            if connector.config.enabled and connector.config.poll_interval_seconds > 0:
                task = asyncio.create_task(self._polling_loop(name))
                self._polling_tasks[name] = task
                logger.info(f"Started polling for {name} every {connector.config.poll_interval_seconds}s")
    
    async def stop_polling(self):
        """Stop all polling tasks"""
        self._running = False
        
        for name, task in self._polling_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._polling_tasks.clear()
        logger.info("Stopped all polling tasks")
    
    async def _polling_loop(self, name: str):
        """Polling loop for a single connector"""
        connector = self._connectors.get(name)
        if not connector:
            return
        
        while self._running:
            try:
                if connector.status != ConnectorStatus.ACTIVE:
                    await connector.connect()
                
                if connector.status == ConnectorStatus.ACTIVE:
                    result = await connector.fetch()
                    
                    if self._results_callback:
                        await self._results_callback(result)
                    
                    logger.info(f"Polled {name}: {result.records_count} records")
                
                await asyncio.sleep(connector.config.poll_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error for {name}: {e}")
                await asyncio.sleep(60)
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Run health checks on all connectors"""
        results = {}
        
        for name, connector in self._connectors.items():
            try:
                results[name] = await connector.health_check()
            except Exception as e:
                results[name] = {"healthy": False, "error": str(e)}
        
        return results
    
    async def test_connector(self, name: str, test_query: Optional[str] = None) -> Dict[str, Any]:
        """Test a connector with an optional test query"""
        connector = self._connectors.get(name)
        if not connector:
            raise ValueError(f"Connector not found: {name}")
        
        result = {
            "connector": name,
            "type": connector.config.connector_type,
            "tests": {}
        }
        
        # Test connection
        try:
            connected = await connector.connect()
            result["tests"]["connection"] = {"success": connected, "status": connector.status.value}
        except Exception as e:
            result["tests"]["connection"] = {"success": False, "error": str(e)}
        
        # Test health check
        try:
            health = await connector.health_check()
            result["tests"]["health"] = health
        except Exception as e:
            result["tests"]["health"] = {"success": False, "error": str(e)}
        
        # Test fetch if query provided
        if test_query:
            try:
                fetch_result = await connector.fetch(test_query)
                result["tests"]["fetch"] = {
                    "success": fetch_result.success,
                    "records": fetch_result.records_count,
                    "errors": fetch_result.errors
                }
            except Exception as e:
                result["tests"]["fetch"] = {"success": False, "error": str(e)}
        
        return result
    
    @classmethod
    def get_available_types(cls) -> List[str]:
        """Get list of available connector types"""
        return list(cls.CONNECTOR_TYPES.keys())


# Global manager instance
_manager: Optional[ConnectorManager] = None


def get_connector_manager() -> ConnectorManager:
    """Get or create the global connector manager"""
    global _manager
    if _manager is None:
        _manager = ConnectorManager()
    return _manager
