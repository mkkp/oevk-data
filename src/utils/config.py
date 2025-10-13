"""Configuration management for OEVK data transformation application."""

import os
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """Configuration class for managing application settings."""

    def __init__(self):
        # Default configuration values
        self._config = {
            # Source URLs
            "source_urls": {
                "oevk_json": "https://static.valasztas.hu/dyn/oevk_data/oevk.json",
                "korzet_zip": "https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip",
            },
            # File paths
            "paths": {
                "data_dir": "data",
                "staging_dir": "data/staging",
                "export_dir": "data/export",
                "database_dir": "data/database",
                "logs_dir": "logs",
                "database_file": "data/database/oevk.db",
            },
            # Processing settings
            "processing": {
                "chunk_size": 100000,  # Number of rows to process at once
                "max_workers": 4,  # Maximum number of parallel workers
                "sample_size": -1,  # Sample size for testing (-1 for all data)
            },
            # Database settings
            "database": {
                "memory_limit": "2GB",  # DuckDB memory limit
                "threads": 4,  # Number of database threads
                "temp_directory": "data/temp",  # Temporary directory for DuckDB
            },
            # Logging settings
            "logging": {
                "level": "INFO",  # Log level: DEBUG, INFO, WARNING, ERROR
                "format": "detailed",  # Log format: simple, detailed
                "max_file_size": "10MB",  # Maximum log file size
                "backup_count": 5,  # Number of backup log files
            },
            # Export settings
            "export": {
                "include_partitioned_addresses": True,
                "include_consolidated_addresses": True,
                "partition_by_settlement": True,
                "csv_delimiter": ",",
                "csv_header": True,
                "max_workers": 8,  # Maximum number of parallel workers for export
            },
            # Deduplication settings
            "deduplication": {
                "hash_seed": 20241012,
                "chunk_size": 100000,
                "enable_logging": True,
                "enable_validation": True,
                "preserve_relationships": True,
                "street_name_similarity_threshold": 0.95,
                "house_number_similarity_threshold": 0.95,
                "max_memory_mb": 4096,
                "parallel_processing": True,
                "generate_reports": True,
                "export_mappings": True,
            },
        }

        # Load environment variables
        self._load_environment_variables()

        # Create required directories
        self._create_directories()

    def _load_environment_variables(self) -> None:
        """Load configuration from environment variables."""
        # Source URLs
        oevk_json_url = os.getenv("OEVK_JSON_URL")
        if oevk_json_url:
            self._config["source_urls"]["oevk_json"] = oevk_json_url

        korzet_zip_url = os.getenv("KORZET_ZIP_URL")
        if korzet_zip_url:
            self._config["source_urls"]["korzet_zip"] = korzet_zip_url

        # Paths
        data_dir = os.getenv("DATA_DIR")
        if data_dir:
            self._config["paths"]["data_dir"] = data_dir
            self._config["paths"]["staging_dir"] = os.path.join(data_dir, "staging")
            self._config["paths"]["export_dir"] = os.path.join(data_dir, "export")
            self._config["paths"]["database_dir"] = os.path.join(data_dir, "database")
            self._config["paths"]["database_file"] = os.path.join(
                data_dir, "database", "oevk.db"
            )

        logs_dir = os.getenv("LOGS_DIR")
        if logs_dir:
            self._config["paths"]["logs_dir"] = logs_dir

        # Processing settings
        chunk_size = os.getenv("CHUNK_SIZE")
        if chunk_size:
            self._config["processing"]["chunk_size"] = int(chunk_size)

        max_workers = os.getenv("MAX_WORKERS")
        if max_workers:
            self._config["processing"]["max_workers"] = int(max_workers)

        sample_size = os.getenv("SAMPLE_SIZE")
        if sample_size:
            self._config["processing"]["sample_size"] = int(sample_size)

        # Database settings
        db_memory_limit = os.getenv("DB_MEMORY_LIMIT")
        if db_memory_limit:
            self._config["database"]["memory_limit"] = db_memory_limit

        db_threads = os.getenv("DB_THREADS")
        if db_threads:
            self._config["database"]["threads"] = int(db_threads)

        # Logging settings
        log_level = os.getenv("LOG_LEVEL")
        if log_level:
            self._config["logging"]["level"] = log_level

        # Export settings
        include_partitioned = os.getenv("INCLUDE_PARTITIONED_ADDRESSES")
        if include_partitioned:
            self._config["export"]["include_partitioned_addresses"] = (
                include_partitioned.lower() == "true"
            )

        include_consolidated = os.getenv("INCLUDE_CONSOLIDATED_ADDRESSES")
        if include_consolidated:
            self._config["export"]["include_consolidated_addresses"] = (
                include_consolidated.lower() == "true"
            )

        # Deduplication settings
        deduplication_hash_seed = os.getenv("DEDUPLICATION_HASH_SEED")
        if deduplication_hash_seed:
            self._config["deduplication"]["hash_seed"] = int(deduplication_hash_seed)

        deduplication_chunk_size = os.getenv("DEDUPLICATION_CHUNK_SIZE")
        if deduplication_chunk_size:
            self._config["deduplication"]["chunk_size"] = int(deduplication_chunk_size)

        deduplication_enable_logging = os.getenv("DEDUPLICATION_ENABLE_LOGGING")
        if deduplication_enable_logging:
            self._config["deduplication"]["enable_logging"] = (
                deduplication_enable_logging.lower() == "true"
            )

        deduplication_max_memory = os.getenv("DEDUPLICATION_MAX_MEMORY_MB")
        if deduplication_max_memory:
            self._config["deduplication"]["max_memory_mb"] = int(
                deduplication_max_memory
            )

    def _create_directories(self) -> None:
        """Create required directories if they don't exist."""
        paths = self._config["paths"]

        directories = [
            paths["data_dir"],
            paths["staging_dir"],
            paths["export_dir"],
            paths["database_dir"],
            paths["logs_dir"],
            self._config["database"]["temp_directory"],
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation.

        Args:
            key: Configuration key in dot notation (e.g., 'source_urls.oevk_json')
            default: Default value if key is not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value using dot notation.

        Args:
            key: Configuration key in dot notation (e.g., 'source_urls.oevk_json')
            value: Value to set
        """
        keys = key.split(".")
        config = self._config

        # Navigate to the parent of the final key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the final key
        config[keys[-1]] = value

    def get_source_urls(self) -> Dict[str, str]:
        """Get source URLs configuration."""
        return self._config["source_urls"]

    def get_paths(self) -> Dict[str, str]:
        """Get file paths configuration."""
        return self._config["paths"]

    def get_processing_settings(self) -> Dict[str, Any]:
        """Get processing settings."""
        return self._config["processing"]

    def get_database_settings(self) -> Dict[str, Any]:
        """Get database settings."""
        return self._config["database"]

    def get_logging_settings(self) -> Dict[str, Any]:
        """Get logging settings."""
        return self._config["logging"]

    def get_export_settings(self) -> Dict[str, Any]:
        """Get export settings."""
        return self._config["export"]

    def get_deduplication_settings(self) -> Dict[str, Any]:
        """Get deduplication settings."""
        return self._config["deduplication"]

    def to_dict(self) -> Dict[str, Any]:
        """Get the complete configuration as a dictionary."""
        return self._config.copy()


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        Configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reload_config() -> Config:
    """Reload configuration from environment variables.

    Returns:
        Updated configuration instance
    """
    global _config_instance
    _config_instance = Config()
    return _config_instance
