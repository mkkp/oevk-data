"""Data models for address deduplication."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CanonicalAddress:
    """Represents a deduplicated canonical address."""

    id: str  # xxhash64(CountyCode|SettlementName|StreetName|HouseNumber)
    county_code: str
    settlement_name: str
    street_name: str
    house_number: str
    accessibility_flag: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class AddressMapping:
    """Maps original addresses to canonical addresses."""

    id: str  # xxhash64(OriginalAddressID|CanonicalAddressID)
    original_address_id: str
    canonical_address_id: str
    mapping_type: str = "deduplication"  # deduplication, manual_override, etc.
    created_at: Optional[datetime] = None


@dataclass
class AddressPollingStations:
    """Preserves polling station assignments for canonical addresses."""

    id: str  # xxhash64(CanonicalAddressID|PollingStationID)
    canonical_address_id: str
    polling_station_id: str
    created_at: Optional[datetime] = None


@dataclass
class AddressPIRCodes:
    """Preserves PIR code relationships for canonical addresses."""

    id: str  # xxhash64(CanonicalAddressID|PIRCode)
    canonical_address_id: str
    pir_code: str
    created_at: Optional[datetime] = None


@dataclass
class DeduplicationReport:
    """Report of deduplication operations for audit and verification."""

    id: str  # xxhash64(RunID)
    run_id: str
    total_addresses: int
    duplicates_found: int
    canonical_addresses_created: int
    processing_time_ms: int
    status: str  # completed, failed, partial
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class DeduplicationConfig:
    """Configuration for deduplication operations."""

    hash_seed: int = 20241012
    chunk_size: int = 100000
    enable_logging: bool = True
    enable_validation: bool = True
    preserve_relationships: bool = True

    # Matching thresholds
    street_name_similarity_threshold: float = 0.95
    house_number_similarity_threshold: float = 0.95

    # Performance settings
    max_memory_mb: int = 4096
    parallel_processing: bool = True

    # Output settings
    generate_reports: bool = True
    export_mappings: bool = True
