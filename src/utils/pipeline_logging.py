"""Enhanced logging for OEVK data transformation pipeline."""

import logging
import logging.config
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    log_format: str = "detailed",
    max_file_size: str = "10MB",
    backup_count: int = 5,
) -> None:
    """
    Setup structured logging for the OEVK data transformation application.

    Args:
        log_dir: Directory where log files will be stored
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format (simple, detailed, pipeline)
        max_file_size: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
    """
    # Create log directory if it doesn't exist
    Path(log_dir).mkdir(parents=True, exist_ok=True)

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
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple": {"format": "%(levelname)s: %(message)s"},
            "pipeline": {
                "format": "%(asctime)s - %(levelname)s - [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": log_format,
                "filename": log_file,
                "maxBytes": _parse_size(max_file_size),
                "backupCount": backup_count,
                "encoding": "utf-8",
            },
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "": {  # root logger
                "level": log_level,
                "handlers": ["file", "console"],
            },
            "src.etl": {
                "level": log_level,
                "handlers": ["file", "console"],
                "propagate": False,
            },
            "src.database": {
                "level": log_level,
                "handlers": ["file", "console"],
                "propagate": False,
            },
            "pipeline": {
                "level": log_level,
                "handlers": ["file", "console"],
                "propagate": False,
                "formatter": "pipeline",
            },
        },
    }

    # Apply logging configuration
    logging.config.dictConfig(logging_config)

    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized")
    logger.info("Log file: %s", log_file)
    logger.info("Log level: %s", log_level)
    logger.info("Log format: %s", log_format)


def _parse_size(size_str: str) -> int:
    """Parse size string like '10MB' to bytes."""
    # Check longer units first to avoid partial matches
    if size_str.upper().endswith("GB"):
        number = size_str[:-2].strip()
        return int(float(number) * 1024 * 1024 * 1024)
    elif size_str.upper().endswith("MB"):
        number = size_str[:-2].strip()
        return int(float(number) * 1024 * 1024)
    elif size_str.upper().endswith("KB"):
        number = size_str[:-2].strip()
        return int(float(number) * 1024)
    elif size_str.upper().endswith("B"):
        number = size_str[:-1].strip()
        return int(float(number))
    # Handle single letter abbreviations
    elif size_str.upper().endswith("G"):
        number = size_str[:-1].strip()
        return int(float(number) * 1024 * 1024 * 1024)
    elif size_str.upper().endswith("M"):
        number = size_str[:-1].strip()
        return int(float(number) * 1024 * 1024)
    elif size_str.upper().endswith("K"):
        number = size_str[:-1].strip()
        return int(float(number) * 1024)
    else:
        # Default to bytes if no unit specified
        return int(size_str)


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


class PipelineMetrics:
    """
    Track and log pipeline performance metrics.
    """

    def __init__(self, pipeline_name: str):
        self.pipeline_name = pipeline_name
        self.logger = get_logger(f"pipeline.metrics.{pipeline_name}")
        self.start_time: Optional[float] = None
        self.step_times: Dict[str, float] = {}

    def start_pipeline(self) -> None:
        """Start pipeline timing."""
        self.start_time = time.time()
        self.logger.info(f"Pipeline {self.pipeline_name} started")

    def log_step_start(self, step_name: str, **kwargs) -> None:
        """Log the start of a pipeline step."""
        step_start = time.time()
        self.step_times[step_name] = step_start
        message = f"Step {step_name} started"
        if kwargs:
            details = " ".join([f"{k}={v}" for k, v in kwargs.items()])
            message += f" - {details}"
        self.logger.info(message)

    def log_step_completion(self, step_name: str, row_count: int = 0, **kwargs) -> None:
        """Log the completion of a pipeline step with timing and row count."""
        if step_name in self.step_times:
            duration = time.time() - self.step_times[step_name]
            message = f"Step {step_name} completed in {duration:.2f}s"
            if row_count > 0:
                message += f" - processed {row_count} rows"
            if kwargs:
                details = " ".join([f"{k}={v}" for k, v in kwargs.items()])
                message += f" - {details}"
            self.logger.info(message)

    def end_pipeline(self, total_rows: int = 0) -> None:
        """End pipeline timing and log summary."""
        if self.start_time:
            total_duration = time.time() - self.start_time
            message = (
                f"Pipeline {self.pipeline_name} completed in {total_duration:.2f}s"
            )
            if total_rows > 0:
                message += f" - processed {total_rows} total rows"
            self.logger.info(message)

    def get_metrics(self) -> Dict[str, Any]:
        """Get current pipeline metrics."""
        metrics = {
            "pipeline_name": self.pipeline_name,
            "total_duration": 0,
            "steps": {},
        }

        if self.start_time:
            metrics["total_duration"] = time.time() - self.start_time

        # Calculate step durations
        current_time = time.time()
        for step_name, step_start in self.step_times.items():
            step_duration = current_time - step_start
            metrics["steps"][step_name] = {
                "start_time": step_start,
                "duration": step_duration,
            }

        return metrics
