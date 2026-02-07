"""Structured JSON logging setup for Base Camp OS."""

import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

from pythonjsonlogger import jsonlogger

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get the current correlation ID or generate a new one."""
    cid = correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current context."""
    correlation_id_var.set(cid)


class BaseCampJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with Base Camp specific fields."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        
        # Add service name
        log_record["service"] = "basecamp-os"
        
        # Add correlation ID if available
        cid = correlation_id_var.get()
        if cid:
            log_record["correlation_id"] = cid
        
        # Add log level
        log_record["level"] = record.levelname.lower()
        
        # Add logger name
        log_record["logger"] = record.name
        
        # Add source location
        log_record["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName
        }
        
        # Remove default fields we're replacing
        for field in ["levelname", "asctime"]:
            if field in log_record:
                del log_record[field]


def setup_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging for the application.
    
    Args:
        level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create formatter
    formatter = BaseCampJsonFormatter(
        fmt="%(timestamp)s %(level)s %(name)s %(message)s"
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.
    
    Args:
        name: The logger name, typically __name__
        
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding extra context to log messages."""
    
    def __init__(self, **kwargs):
        self.extra = kwargs
        self.old_factory = None
    
    def __enter__(self):
        old_factory = logging.getLogRecordFactory()
        extra = self.extra
        
        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            for key, value in extra.items():
                setattr(record, key, value)
            return record
        
        self.old_factory = old_factory
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)
        return False
