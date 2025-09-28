import logging
import logging.config
import os
from datetime import datetime
from typing import Dict, Any


def setup_logging(log_dir: str = "logs", log_level: str = "INFO") -> None:
    """
    Setup structured logging for the OEVK data transformation application.
    
    Args:
        log_dir: Directory where log files will be stored
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"oevk_transform_{timestamp}.log")
    
    # Logging configuration
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(levelname)s: %(message)s"
            }
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "level": log_level,
                "formatter": "detailed",
                "filename": log_file,
                "encoding": "utf-8"
            },
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout"
            }
        },
        "loggers": {
            "": {  # root logger
                "level": log_level,
                "handlers": ["file", "console"]
            },
            "src.etl": {
                "level": log_level,
                "handlers": ["file", "console"],
                "propagate": False
            },
            "src.database": {
                "level": log_level,
                "handlers": ["file", "console"],
                "propagate": False
            }
        }
    }
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)
    
    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized")
    logger.info("Log file: %s", log_file)
    logger.info("Log level: %s", log_level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class PipelineLogger:
    """
    A specialized logger for ETL pipeline operations with structured logging.
    """
    
    def __init__(self, component_name: str):
        self.logger = get_logger(f"pipeline.{component_name}")
        self.component_name = component_name
        
    def log_start(self, operation: str, **kwargs) -> None:
        """Log the start of an operation."""
        message = f"Starting {operation}"
        if kwargs:
            details = " ".join([f"{k}={v}" for k, v in kwargs.items()])
            message += f" - {details}"
        self.logger.info(message)
        
    def log_completion(self, operation: str, duration: float, **kwargs) -> None:
        """Log the completion of an operation with duration."""
        message = f"Completed {operation} in {duration:.2f}s"
        if kwargs:
            details = " ".join([f"{k}={v}" for k, v in kwargs.items()])
            message += f" - {details}"
        self.logger.info(message)
        
    def log_error(self, operation: str, error: Exception, **kwargs) -> None:
        """Log an error during an operation."""
        message = f"Error in {operation}: {str(error)}"
        if kwargs:
            details = " ".join([f"{k}={v}" for k, v in kwargs.items()])
            message += f" - {details}"
        self.logger.error(message, exc_info=True)
        
    def log_data_stats(self, operation: str, row_count: int, **kwargs) -> None:
        """Log data statistics for an operation."""
        message = f"{operation} processed {row_count} rows"
        if kwargs:
            details = " ".join([f"{k}={v}" for k, v in kwargs.items()])
            message += f" - {details}"
        self.logger.info(message)