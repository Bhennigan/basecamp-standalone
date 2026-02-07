"""
OSINT Tool Connectors for Digital Persona Protection

This module provides connectors for various OSINT tools used in
digital persona protection and threat intelligence gathering.
"""

from .base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorResult,
    ConnectorStatus,
)
from .manager import ConnectorManager
from .shodan_connector import ShodanConnector
from .zerofox_connector import ZeroFoxConnector
from .sherlock_connector import SherlockConnector
from .harvester_connector import HarvesterConnector

__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorResult",
    "ConnectorStatus",
    "ConnectorManager",
    "ShodanConnector",
    "ZeroFoxConnector",
    "SherlockConnector",
    "HarvesterConnector",
]
