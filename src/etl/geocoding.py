"""Geocoding module for address coordinate resolution using Nominatim."""

import hashlib
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import polars as pl
import requests

from src.utils.config import get_config
from src.utils.pipeline_logging import get_logger

logger = get_logger(__name__)


class GeocodingQuality(Enum):
    """Geocoding result quality levels."""

    EXACT = "exact"  # House-level match (from geocoding service)
    INTERPOLATED = "interpolated"  # House-level match (calculated via interpolation)
    STREET = "street"  # Street-level match
    SETTLEMENT = "settlement"  # Settlement-level match
    FAILED = "failed"  # No match found


@dataclass
class GeocodingResult:
    """Geocoding result for a single address."""

    canonical_address_id: str
    latitude: Optional[float]
    longitude: Optional[float]
    quality: GeocodingQuality
    source: str  # 'nominatim_local', 'nominatim_api', 'cache', etc.
    osm_type: Optional[str]  # 'node', 'way', 'relation'
    osm_id: Optional[int]
    matched_address: Optional[str]  # What Nominatim matched


class NominatimGeocoder:
    """Geocoding service using Nominatim API."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize geocoder with configuration."""
        if config is None:
            config = get_config()

        self.config = config
        self.base_url = config.get("nominatim", {}).get(
            "base_url", "http://localhost:8081"
        )
        self.batch_size = config.get("nominatim", {}).get("batch_size", 100)
        self.rate_limit = config.get("nominatim", {}).get(
            "rate_limit", 0
        )  # 0 = no limit for local
        self.timeout = config.get("nominatim", {}).get("timeout", 30)
        self.max_workers = config.get("nominatim", {}).get(
            "max_workers"
        )  # Number of parallel threads

        # Initialize SQLite cache instead of file-based cache
        # Use cache_dir from config (supports both cache_db and cache_dir for backwards compatibility)
        cache_db_path = config.get("nominatim", {}).get("cache_db") or config.get(
            "nominatim", {}
        ).get("cache_dir", "data/geocoding_cache")
        # If cache_db_path is a directory, append the database filename
        cache_path = Path(cache_db_path)
        if cache_path.suffix != ".db":
            # It's a directory, append the database filename
            self.cache_db_path = cache_path / "geocoding_cache.db"
        else:
            # It's already a full path with .db extension
            self.cache_db_path = cache_path
        self.cache_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_cache_db()

        self.min_quality = config.get("nominatim", {}).get("min_quality", "street")

        # Rate limiting state (not needed for local Nominatim with multi-threading)
        self.last_request_time = 0.0

        # Statistics - using dict for thread-safe updates
        import threading

        self.stats_lock = threading.Lock()
        self.stats = {
            "total": 0,
            "cached": 0,
            "geocoded": 0,
            "exact": 0,
            "interpolated": 0,
            "street": 0,
            "settlement": 0,
            "failed": 0,
        }

        # Start time for ETA calculation
        self.start_time = time.time()

        # Failure log file (thread-safe)
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.failure_log_path = log_dir / f"geocoding_failures_{timestamp}.log"
        self.failure_log = open(self.failure_log_path, "w", encoding="utf-8")
        self.failure_log.write("# Geocoding Failures Log\n")
        self.failure_log.write(
            "# Format: Timestamp | Address ID | Full Address | Settlement | Reason\n"
        )
        self.failure_log.write("=" * 120 + "\n")
        self.failure_log_lock = threading.Lock()
        logger.info(f"Failure log: {self.failure_log_path}")

    def _init_cache_db(self):
        """Initialize SQLite cache database."""
        conn = sqlite3.connect(str(self.cache_db_path))
        cursor = conn.cursor()

        # Create cache table with index on cache_key for fast lookups
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                cache_key TEXT PRIMARY KEY,
                canonical_address_id TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                quality TEXT NOT NULL,
                source TEXT NOT NULL,
                osm_type TEXT,
                osm_id INTEGER,
                matched_address TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_quality
            ON geocoding_cache(quality)
        """)

        conn.commit()
        conn.close()

        logger.info(f"Cache database initialized: {self.cache_db_path}")

    def geocode_addresses(self, addresses_df: pl.DataFrame) -> pl.DataFrame:
        """
        Geocode a DataFrame of canonical addresses.

        Args:
            addresses_df: DataFrame with columns:
                - ID: Canonical address ID
                - CountyCode: County code
                - SettlementName: Settlement name
                - StreetName: Street name (without type)
                - HouseNumber: House number (cleaned)
                - FullAddress: Formatted address

        Returns:
            DataFrame with added columns:
                - Latitude
                - Longitude
                - GeocodingQuality
                - GeocodingSource
                - GeocodedAt
        """
        logger.info(f"Starting geocoding for {len(addresses_df):,} addresses")
        self.start_time = time.time()

        # Process in batches
        results = []
        total_batches = (len(addresses_df) + self.batch_size - 1) // self.batch_size

        for batch_idx in range(total_batches):
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(addresses_df))
            batch = addresses_df[start_idx:end_idx]

            batch_results = self._geocode_batch(batch)
            results.extend(batch_results)

            # Progress reporting every 10 batches
            if (batch_idx + 1) % 10 == 0 or (batch_idx + 1) == total_batches:
                self._log_progress(batch_idx + 1, total_batches)

        # Log final statistics
        self._log_final_stats()

        # Apply post-processing interpolation to improve street-level matches
        logger.info("Applying post-processing interpolation to improve quality...")
        results = self._interpolate_street_addresses(results, addresses_df)

        # Apply HERE geocoding as post-processing fallback for failed/low-quality results
        results = self._apply_here_fallback(results, addresses_df)

        # Convert results to DataFrame
        return self._results_to_dataframe(results)

    def _geocode_batch(self, batch: pl.DataFrame) -> List[GeocodingResult]:
        """Geocode a batch of addresses using multi-threading."""
        results = []

        # Convert batch to list of dictionaries
        addresses = list(batch.iter_rows(named=True))

        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all geocoding tasks
            future_to_address = {
                executor.submit(self._geocode_single, addr): addr for addr in addresses
            }

            # Collect results as they complete
            for future in as_completed(future_to_address):
                result = future.result()
                results.append(result)
                with self.stats_lock:
                    self.stats["total"] += 1

        return results

    def _geocode_single(self, address: Dict) -> GeocodingResult:
        """
        Geocode a single address.

        Uses structured query for better performance (2-3x faster than free text):
        - street: StreetName + HouseNumber
        - city: SettlementName
        - country: hu (Hungary ISO code)
        """
        # Check cache first
        cache_key = self._get_cache_key(address)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            with self.stats_lock:
                self.stats["cached"] += 1
                # Cached results should always be successful (failures are not cached)
                self.stats[cached_result.quality.value] += 1
            return cached_result

        # Build query parameters using structured query (faster than free text)
        params = {
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
        }

        # Use structured query for 2-3x performance improvement
        # Structured queries are faster because they limit search scope to specific fields
        if (
            address.get("StreetName")
            and address.get("HouseNumber")
            and address.get("SettlementName")
        ):
            # Strip leading zeros from house number
            house_num = address["HouseNumber"].lstrip("0") or "0"
            # Structured query: ~20-50ms vs free text: ~60-135ms
            params["street"] = f"{address['StreetName']} {house_num}"
            params["city"] = address["SettlementName"]
            params["country"] = "hu"
        elif address.get("FullAddress") and address.get("SettlementName"):
            # Fallback to free text if components not available
            full_addr = address["FullAddress"].rstrip(".")
            params["q"] = f"{full_addr}, {address['SettlementName']}, Hungary"
            params["countrycodes"] = "hu"
        elif address.get("SettlementName"):
            # Last resort: just settlement
            params["q"] = f"{address['SettlementName']}, Hungary"
            params["countrycodes"] = "hu"
        else:
            # No useful data
            params["q"] = "Hungary"
            params["countrycodes"] = "hu"

        # Rate limiting (disabled for multi-threaded local Nominatim)
        # self._apply_rate_limit()

        try:
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "OEVK-Data-Pipeline/1.0"},
            )
            response.raise_for_status()

            data = response.json()
            result = self._parse_response(data, address, query=params.get("q"))

            # If structured query returned no results, try free-text fallback
            if result.quality == GeocodingQuality.FAILED and "street" in params:
                logger.debug(
                    f"Structured query returned no results for {address.get('FullAddress', 'unknown')}, trying free text fallback"
                )
                # Build free-text fallback query
                fallback_params = {
                    "format": "json",
                    "addressdetails": 1,
                    "limit": 1,
                    "countrycodes": "hu",
                }

                if address.get("FullAddress") and address.get("SettlementName"):
                    full_addr = address["FullAddress"].rstrip(".")
                    fallback_params["q"] = (
                        f"{full_addr}, {address['SettlementName']}, Hungary"
                    )
                elif address.get("SettlementName"):
                    fallback_params["q"] = f"{address['SettlementName']}, Hungary"
                else:
                    fallback_params["q"] = "Hungary"

                try:
                    fallback_response = requests.get(
                        f"{self.base_url}/search",
                        params=fallback_params,
                        timeout=self.timeout,
                        headers={"User-Agent": "OEVK-Data-Pipeline/1.0"},
                    )
                    fallback_response.raise_for_status()
                    fallback_data = fallback_response.json()
                    result = self._parse_response(
                        fallback_data, address, query=fallback_params.get("q")
                    )
                except requests.RequestException:
                    pass  # Keep original failed result

                # If free-text also failed, try settlement centroid as final fallback
                if result.quality == GeocodingQuality.FAILED:
                    settlement_result = self._get_settlement_centroid(
                        address.get("SettlementName")
                    )
                    if settlement_result:
                        logger.debug(
                            f"Using settlement centroid for {address.get('FullAddress', 'unknown')}"
                        )
                        result = GeocodingResult(
                            canonical_address_id=address["ID"],
                            latitude=settlement_result["lat"],
                            longitude=settlement_result["lon"],
                            quality=GeocodingQuality.SETTLEMENT,
                            source="settlement_centroid",
                            osm_type=settlement_result.get("osm_type"),
                            osm_id=settlement_result.get("osm_id"),
                            matched_address=settlement_result.get("display_name"),
                        )

            # Only cache successful results (don't cache failures so they can be retried)
            if result.quality != GeocodingQuality.FAILED:
                self._save_to_cache(cache_key, result)

            with self.stats_lock:
                self.stats["geocoded"] += 1
                self.stats[result.quality.value] += 1

            return result

        except requests.RequestException as e:
            # If structured query failed with 500 error, try fallback to free text
            if (
                hasattr(e, "response")
                and e.response is not None
                and e.response.status_code == 500
                and "street" in params
            ):
                logger.debug(
                    f"Structured query failed for {address.get('FullAddress', 'unknown')}, trying free text fallback"
                )
                try:
                    # Build free-text fallback query
                    fallback_params = {
                        "format": "json",
                        "addressdetails": 1,
                        "limit": 1,
                        "countrycodes": "hu",
                    }

                    if address.get("FullAddress") and address.get("SettlementName"):
                        full_addr = address["FullAddress"].rstrip(".")
                        fallback_params["q"] = (
                            f"{full_addr}, {address['SettlementName']}, Hungary"
                        )
                    elif address.get("SettlementName"):
                        fallback_params["q"] = f"{address['SettlementName']}, Hungary"
                    else:
                        fallback_params["q"] = "Hungary"

                    response = requests.get(
                        f"{self.base_url}/search",
                        params=fallback_params,
                        timeout=self.timeout,
                        headers={"User-Agent": "OEVK-Data-Pipeline/1.0"},
                    )
                    response.raise_for_status()

                    data = response.json()
                    result = self._parse_response(
                        data, address, query=fallback_params.get("q")
                    )

                    if result.quality != GeocodingQuality.FAILED:
                        self._save_to_cache(cache_key, result)

                    with self.stats_lock:
                        self.stats["geocoded"] += 1
                        self.stats[result.quality.value] += 1

                    return result

                except requests.RequestException as fallback_error:
                    logger.warning(
                        f"Fallback geocoding also failed for {address.get('FullAddress', 'unknown')}: {fallback_error}"
                    )
            else:
                logger.warning(
                    f"Geocoding failed for {address.get('FullAddress', 'unknown')}: {e}"
                )

            with self.stats_lock:
                self.stats["failed"] += 1

            # Log failure details
            self._log_failure(address, f"Request error: {e}", query=params.get("q"))

            # Final fallback: Try to get settlement centroid
            settlement_result = self._get_settlement_centroid(
                address.get("SettlementName")
            )
            if settlement_result:
                logger.debug(
                    f"Using settlement centroid for {address.get('FullAddress', 'unknown')}"
                )
                return GeocodingResult(
                    canonical_address_id=address["ID"],
                    latitude=settlement_result["lat"],
                    longitude=settlement_result["lon"],
                    quality=GeocodingQuality.SETTLEMENT,
                    source="settlement_centroid",
                    osm_type=settlement_result.get("osm_type"),
                    osm_id=settlement_result.get("osm_id"),
                    matched_address=settlement_result.get("display_name"),
                )

            return GeocodingResult(
                canonical_address_id=address["ID"],
                latitude=None,
                longitude=None,
                quality=GeocodingQuality.FAILED,
                source="nominatim_local",
                osm_type=None,
                osm_id=None,
                matched_address=None,
            )

    def _parse_response(
        self, data: Dict, original_address: Dict, query: str = None
    ) -> GeocodingResult:
        """Parse Nominatim json response."""
        # data is a list of results for json format
        if not isinstance(data, list) or len(data) == 0:
            # Log failure details
            self._log_failure(
                original_address, "No results returned from Nominatim", query=query
            )

            return GeocodingResult(
                canonical_address_id=original_address["ID"],
                latitude=None,
                longitude=None,
                quality=GeocodingQuality.FAILED,
                source="nominatim_local",
                osm_type=None,
                osm_id=None,
                matched_address=None,
            )

        result = data[0]

        # Extract coordinates (standard json format: lat/lon as strings)
        lat = float(result["lat"])
        lon = float(result["lon"])

        # Determine quality based on OSM type and place_rank
        quality = self._determine_quality(result)

        return GeocodingResult(
            canonical_address_id=original_address["ID"],
            latitude=lat,
            longitude=lon,
            quality=quality,
            source="nominatim_local",
            osm_type=result.get("osm_type"),
            osm_id=result.get("osm_id"),
            matched_address=result.get("display_name"),
        )

    def _determine_quality(self, result: Dict) -> GeocodingQuality:
        """Determine geocoding quality from Nominatim json result."""
        osm_type = result.get("type", "").lower()
        osm_class = result.get("class", "").lower()
        place_rank = result.get("place_rank", 30)

        # Exact match: house-level (place_rank 30 = house number)
        if osm_type == "house" or place_rank == 30:
            return GeocodingQuality.EXACT

        # Street-level match (place_rank 26 = street)
        if osm_class in ["highway", "street"] or place_rank == 26:
            return GeocodingQuality.STREET

        # Settlement-level match (place_rank < 20 = city/town/village)
        if osm_class == "place" or place_rank < 20:
            return GeocodingQuality.SETTLEMENT

        # Default to street level for other matches
        return GeocodingQuality.STREET

    def _get_cache_key(self, address: Dict) -> str:
        """Generate cache key from address components."""
        key_string = f"{address['SettlementName']}|{address['StreetName']}|{address['HouseNumber']}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[GeocodingResult]:
        """Retrieve cached geocoding result from SQLite database."""
        try:
            conn = sqlite3.connect(str(self.cache_db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT canonical_address_id, latitude, longitude, quality,
                       source, osm_type, osm_id, matched_address
                FROM geocoding_cache
                WHERE cache_key = ?
            """,
                (cache_key,),
            )

            row = cursor.fetchone()
            conn.close()

            if row:
                return GeocodingResult(
                    canonical_address_id=row[0],
                    latitude=row[1],
                    longitude=row[2],
                    quality=GeocodingQuality(row[3]),
                    source="cache",
                    osm_type=row[5],
                    osm_id=row[6],
                    matched_address=row[7],
                )
            return None
        except (sqlite3.Error, ValueError) as e:
            logger.warning(f"Cache read error for {cache_key}: {e}")
            return None

    def _save_to_cache(self, cache_key: str, result: GeocodingResult):
        """Save geocoding result to SQLite cache database."""
        try:
            conn = sqlite3.connect(str(self.cache_db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO geocoding_cache
                (cache_key, canonical_address_id, latitude, longitude, quality,
                 source, osm_type, osm_id, matched_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    cache_key,
                    result.canonical_address_id,
                    result.latitude,
                    result.longitude,
                    result.quality.value,
                    result.source,
                    result.osm_type,
                    result.osm_id,
                    result.matched_address,
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.warning(f"Failed to save cache {cache_key}: {e}")

    def _get_settlement_centroid(self, settlement_name: str) -> Optional[Dict]:
        """
        Get settlement centroid from Nominatim as final fallback.

        Args:
            settlement_name: Name of the settlement

        Returns:
            Dictionary with lat, lon, osm_type, osm_id, display_name or None
        """
        if not settlement_name:
            return None

        try:
            params = {
                "q": f"{settlement_name}, Hungary",
                "format": "json",
                "limit": 1,
                "countrycodes": "hu",
            }

            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "OEVK-Data-Pipeline/1.0"},
            )
            response.raise_for_status()

            data = response.json()
            if data and len(data) > 0:
                result = data[0]
                return {
                    "lat": float(result["lat"]),
                    "lon": float(result["lon"]),
                    "osm_type": result.get("osm_type"),
                    "osm_id": result.get("osm_id"),
                    "display_name": result.get("display_name"),
                }
        except Exception as e:
            logger.debug(
                f"Could not get settlement centroid for {settlement_name}: {e}"
            )

        return None

    def _log_failure(self, address: Dict, reason: str, query: str = None):
        """Log failed geocoding attempt to failure log file (thread-safe)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        address_id = address.get("ID", "UNKNOWN")
        full_address = address.get("FullAddress", "")
        settlement = address.get("SettlementName", "")
        street = address.get("StreetName", "")
        house_number = address.get("HouseNumber", "")

        # Include the actual query sent to Nominatim if available
        query_str = f" | Query: {query}" if query else ""

        log_line = f"{timestamp} | {address_id} | {full_address} | {settlement} | {street} {house_number} | {reason}{query_str}\n"

        with self.failure_log_lock:
            self.failure_log.write(log_line)
            # Flush every 10 failures instead of every failure to reduce I/O overhead
            if self.stats.get("failed", 0) % 10 == 0:
                self.failure_log.flush()

    def _apply_rate_limit(self):
        """Apply rate limiting between requests."""
        if self.rate_limit <= 0:
            return

        elapsed = time.time() - self.last_request_time
        required_delay = 1.0 / self.rate_limit

        if elapsed < required_delay:
            time.sleep(required_delay - elapsed)

        self.last_request_time = time.time()

    def __del__(self):
        """Cleanup: close failure log file."""
        if (
            hasattr(self, "failure_log")
            and self.failure_log
            and not self.failure_log.closed
        ):
            self.failure_log.flush()  # Final flush before closing
            self.failure_log.close()
            logger.info(f"Failure log closed: {self.failure_log_path}")

    def _interpolate_street_addresses(
        self, results: List[GeocodingResult], addresses_df: pl.DataFrame
    ) -> List[GeocodingResult]:
        """
        Apply post-processing interpolation to improve street-level matches.

        For each street with multiple addresses:
        1. Find addresses with exact matches (house-level precision)
        2. For street-level matches, interpolate coordinates based on nearby exact matches
        3. Use linear interpolation based on house number positions

        Example:
            Street "Kossuth utca" results:
            - #10: exact (47.500, 19.100)
            - #25: street-level only
            - #50: exact (47.600, 19.200)

            Interpolate #25:
            position = (25-10)/(50-10) = 0.375
            lat = 47.500 + 0.375 * (47.600-47.500) = 47.5375
            lon = 19.100 + 0.375 * (19.200-19.100) = 19.1375

        Args:
            results: List of geocoding results
            addresses_df: Original addresses DataFrame with house numbers

        Returns:
            Updated list of geocoding results with interpolated coordinates
        """
        import re

        # Convert results to dictionary for easy lookup by ID
        results_dict = {r.canonical_address_id: r for r in results}

        # Create a lookup for address metadata (settlement, street, house number)
        address_metadata = {}
        for row in addresses_df.iter_rows(named=True):
            address_metadata[row["ID"]] = {
                "settlement": row["SettlementName"],
                "street": row["StreetName"],
                "house_number": row["HouseNumber"],
            }

        # Group results by settlement and street
        street_groups = {}
        for addr_id, result in results_dict.items():
            if addr_id not in address_metadata:
                continue

            metadata = address_metadata[addr_id]
            settlement = metadata["settlement"]
            street = metadata["street"]

            # Skip if no street name
            if not street:
                continue

            key = (settlement, street)
            if key not in street_groups:
                street_groups[key] = []

            street_groups[key].append(
                {
                    "id": addr_id,
                    "result": result,
                    "house_number": metadata["house_number"],
                }
            )

        # Statistics
        interpolated_count = 0
        skipped_no_exact = 0
        skipped_no_street = 0

        # Process each street group
        for (settlement, street), addresses in street_groups.items():
            # Separate exact matches from street-level matches
            exact_matches = []
            street_matches = []

            for addr_info in addresses:
                result = addr_info["result"]
                if result.quality == GeocodingQuality.EXACT:
                    # Extract numeric part of house number
                    house_num_str = addr_info["house_number"]
                    house_num = self._extract_house_number(house_num_str)
                    if house_num is not None:
                        exact_matches.append(
                            {
                                "id": addr_info["id"],
                                "result": result,
                                "house_number": house_num,
                                "house_number_str": house_num_str,
                            }
                        )
                elif result.quality == GeocodingQuality.STREET:
                    house_num_str = addr_info["house_number"]
                    house_num = self._extract_house_number(house_num_str)
                    if house_num is not None:
                        street_matches.append(
                            {
                                "id": addr_info["id"],
                                "result": result,
                                "house_number": house_num,
                                "house_number_str": house_num_str,
                            }
                        )

            # Need at least 2 exact matches to interpolate
            if len(exact_matches) < 2:
                skipped_no_exact += len(street_matches)
                continue

            # Sort exact matches by house number
            exact_matches.sort(key=lambda x: x["house_number"])

            # Interpolate each street-level match
            for street_match in street_matches:
                target_num = street_match["house_number"]

                # Find two closest exact matches (one below, one above)
                lower_match = None
                upper_match = None

                for exact in exact_matches:
                    if exact["house_number"] <= target_num:
                        lower_match = exact
                    elif exact["house_number"] > target_num and upper_match is None:
                        upper_match = exact
                        break

                # Interpolate if we have both bounds
                if lower_match and upper_match:
                    # Calculate interpolation factor
                    lower_num = lower_match["house_number"]
                    upper_num = upper_match["house_number"]

                    # Avoid division by zero
                    if upper_num == lower_num:
                        continue

                    position = (target_num - lower_num) / (upper_num - lower_num)

                    # Interpolate coordinates
                    lower_lat = lower_match["result"].latitude
                    lower_lon = lower_match["result"].longitude
                    upper_lat = upper_match["result"].latitude
                    upper_lon = upper_match["result"].longitude

                    interpolated_lat = lower_lat + position * (upper_lat - lower_lat)
                    interpolated_lon = lower_lon + position * (upper_lon - lower_lon)

                    # Update result with interpolated coordinates
                    old_result = street_match["result"]
                    results_dict[street_match["id"]] = GeocodingResult(
                        canonical_address_id=old_result.canonical_address_id,
                        latitude=interpolated_lat,
                        longitude=interpolated_lon,
                        quality=GeocodingQuality.INTERPOLATED,  # Mark as interpolated
                        source=f"interpolated ({lower_num}-{upper_num})",
                        osm_type=old_result.osm_type,
                        osm_id=old_result.osm_id,
                        matched_address=old_result.matched_address,
                    )

                    interpolated_count += 1
                    logger.debug(
                        f"Interpolated {settlement} {street} #{target_num}: "
                        f"({lower_lat:.6f}, {lower_lon:.6f}) -> "
                        f"({interpolated_lat:.6f}, {interpolated_lon:.6f}) -> "
                        f"({upper_lat:.6f}, {upper_lon:.6f})"
                    )

                elif lower_match or upper_match:
                    # Use nearest exact match (no interpolation, just use closest)
                    nearest = lower_match if lower_match else upper_match

                    # Calculate a small offset based on distance
                    # This is a simple heuristic: move slightly along the street
                    if lower_match:
                        # Address is beyond the highest known number, extrapolate slightly
                        offset_factor = 0.0001  # ~10 meters
                        lat_offset = offset_factor * (
                            target_num - nearest["house_number"]
                        )
                        lon_offset = offset_factor * (
                            target_num - nearest["house_number"]
                        )
                    else:
                        # Address is below the lowest known number
                        lat_offset = 0
                        lon_offset = 0

                    old_result = street_match["result"]
                    results_dict[street_match["id"]] = GeocodingResult(
                        canonical_address_id=old_result.canonical_address_id,
                        latitude=nearest["result"].latitude + lat_offset,
                        longitude=nearest["result"].longitude + lon_offset,
                        quality=GeocodingQuality.INTERPOLATED,  # Mark as interpolated
                        source=f"extrapolated (nearest: {nearest['house_number']})",
                        osm_type=old_result.osm_type,
                        osm_id=old_result.osm_id,
                        matched_address=old_result.matched_address,
                    )

                    interpolated_count += 1
                else:
                    skipped_no_street += 1

        logger.info(
            f"Interpolation complete: {interpolated_count:,} addresses upgraded to interpolated quality"
        )
        logger.info(f"  - Skipped (no exact matches on street): {skipped_no_exact:,}")
        if skipped_no_street > 0:
            logger.info(f"  - Skipped (no nearby matches): {skipped_no_street:,}")

        # Update stats
        with self.stats_lock:
            # Add interpolated to stats if not present
            if "interpolated" not in self.stats:
                self.stats["interpolated"] = 0
            # Adjust quality counts
            self.stats["interpolated"] += interpolated_count
            self.stats["street"] -= interpolated_count

        # Convert back to list
        return list(results_dict.values())

    def _extract_house_number(self, house_number_str: str) -> Optional[int]:
        """
        Extract numeric part from house number string.

        Examples:
            "10" -> 10
            "10a" -> 10
            "10/A" -> 10
            "10-12" -> 10

        Args:
            house_number_str: House number string

        Returns:
            Numeric part as integer, or None if cannot extract
        """
        import re

        if not house_number_str:
            return None

        # Extract first sequence of digits
        match = re.match(r"^(\d+)", house_number_str.strip())
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None

        return None

    def _apply_here_fallback(
        self, results: List[GeocodingResult], addresses_df: pl.DataFrame
    ) -> List[GeocodingResult]:
        """
        Apply HERE geocoding as fallback for failed or low-quality results.

        This post-processing step uses HERE Geocoding API to improve results for:
        - Failed addresses (no coordinates)
        - Settlement-level matches (low precision)
        - Optionally: Street-level matches (if enabled in config)

        Args:
            results: List of geocoding results from Nominatim
            addresses_df: Original addresses DataFrame

        Returns:
            Updated list of geocoding results with HERE fallback applied
        """
        # Check if HERE geocoding is enabled
        here_config = self.config.get("here", {})
        if not here_config.get("enabled", False):
            logger.info("HERE geocoding fallback disabled in configuration")
            return results

        # Check if API key is available
        if not here_config.get("api_key"):
            logger.warning(
                "HERE geocoding enabled but no API key configured. "
                "Skipping HERE fallback."
            )
            return results

        # Determine which results to retry with HERE
        min_quality = here_config.get("min_quality_to_retry", "settlement")
        retry_street = min_quality in ["street", "exact"]
        retry_settlement = min_quality in ["settlement", "street", "exact"]
        retry_failed = True  # Always retry failed

        logger.info(
            f"Applying HERE geocoding fallback (retry_failed={retry_failed}, "
            f"retry_settlement={retry_settlement}, retry_street={retry_street})"
        )

        # Filter addresses that need HERE fallback
        addresses_to_retry = []
        result_indices = {}

        for idx, result in enumerate(results):
            should_retry = False

            if result.quality == GeocodingQuality.FAILED and retry_failed:
                should_retry = True
            elif result.quality == GeocodingQuality.SETTLEMENT and retry_settlement:
                should_retry = True
            elif result.quality == GeocodingQuality.STREET and retry_street:
                should_retry = True

            if should_retry:
                # Find corresponding address in original DataFrame
                addr_rows = addresses_df.filter(
                    pl.col("ID") == result.canonical_address_id
                )
                if len(addr_rows) > 0:
                    addr_dict = addr_rows.to_dicts()[0]
                    addresses_to_retry.append(addr_dict)
                    result_indices[result.canonical_address_id] = idx

        if len(addresses_to_retry) == 0:
            logger.info("No addresses need HERE fallback")
            return results

        logger.info(
            f"Retrying {len(addresses_to_retry):,} addresses with HERE geocoding..."
        )

        # Initialize HERE geocoder
        try:
            here_geocoder = HereGeocoder(self.config)
        except ValueError as e:
            logger.error(f"Failed to initialize HERE geocoder: {e}")
            return results

        # Geocode with HERE
        retry_df = pl.DataFrame(addresses_to_retry)
        here_results = here_geocoder.geocode_addresses_batch(retry_df)

        # Update results with HERE results (only if HERE quality is better)
        improved_count = 0
        quality_order = {
            GeocodingQuality.EXACT: 3,
            GeocodingQuality.STREET: 2,
            GeocodingQuality.SETTLEMENT: 1,
            GeocodingQuality.FAILED: 0,
        }

        for here_result in here_results:
            addr_id = here_result.canonical_address_id
            if addr_id in result_indices:
                idx = result_indices[addr_id]
                old_result = results[idx]

                # Only update if HERE result is better quality
                old_quality_score = quality_order.get(old_result.quality, 0)
                new_quality_score = quality_order.get(here_result.quality, 0)

                if new_quality_score > old_quality_score:
                    results[idx] = here_result
                    improved_count += 1
                    logger.debug(
                        f"HERE improved {addr_id}: "
                        f"{old_result.quality.value} → {here_result.quality.value}"
                    )

        logger.info(
            f"HERE fallback complete: {improved_count:,} addresses improved "
            f"({improved_count / len(addresses_to_retry) * 100:.1f}% of retried)"
        )

        # Update stats with HERE improvements
        with self.stats_lock:
            # Recalculate quality stats after HERE fallback
            quality_counts = {
                "exact": 0,
                "interpolated": 0,
                "street": 0,
                "settlement": 0,
                "failed": 0,
            }
            for result in results:
                quality_counts[result.quality.value] += 1

            self.stats["exact"] = quality_counts["exact"]
            self.stats["interpolated"] = quality_counts["interpolated"]
            self.stats["street"] = quality_counts["street"]
            self.stats["settlement"] = quality_counts["settlement"]
            self.stats["failed"] = quality_counts["failed"]

        return results

    def _log_progress(self, current_batch: int, total_batches: int):
        """Log current progress statistics."""
        total = self.stats["total"]
        if total == 0:
            return

        # Calculate progress percentage
        progress_pct = (current_batch / total_batches) * 100

        # Calculate processing rate
        elapsed_time = time.time() - self.start_time
        rate = total / elapsed_time if elapsed_time > 0 else 0

        # Calculate ETA
        remaining_batches = total_batches - current_batch
        if rate > 0:
            remaining_addresses = remaining_batches * self.batch_size
            eta_seconds = remaining_addresses / rate
            eta_minutes = int(eta_seconds / 60)
        else:
            eta_minutes = 0

        logger.info(
            f"Batch {current_batch}/{total_batches} ({progress_pct:.1f}%) | "
            f"Progress: {total:,} addresses | "
            f"Rate: {rate:.1f} addr/sec | "
            f"ETA: {eta_minutes} min | "
            f"Cached: {self.stats['cached']:,} ({self.stats['cached'] / total * 100:.1f}%) | "
            f"Exact: {self.stats['exact']:,} ({self.stats['exact'] / total * 100:.1f}%) | "
            f"Interpolated: {self.stats['interpolated']:,} ({self.stats['interpolated'] / total * 100:.1f}%) | "
            f"Street: {self.stats['street']:,} ({self.stats['street'] / total * 100:.1f}%) | "
            f"Settlement: {self.stats['settlement']:,} ({self.stats['settlement'] / total * 100:.1f}%) | "
            f"Failed: {self.stats['failed']:,} ({self.stats['failed'] / total * 100:.1f}%)"
        )

    def _log_final_stats(self):
        """Log final geocoding statistics."""
        total = self.stats["total"]
        elapsed_time = time.time() - self.start_time

        logger.info("=" * 80)
        logger.info("GEOCODING STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total addresses: {total:,}")
        logger.info(f"Total time: {elapsed_time:.1f}s ({elapsed_time / 60:.1f} min)")
        logger.info(
            f"Cached results: {self.stats['cached']:,} ({self.stats['cached'] / total * 100:.1f}%)"
        )
        logger.info(
            f"Newly geocoded: {self.stats['geocoded']:,} ({self.stats['geocoded'] / total * 100:.1f}%)"
        )
        logger.info(
            f"  - Exact match: {self.stats['exact']:,} ({self.stats['exact'] / total * 100:.1f}%)"
        )
        logger.info(
            f"  - Interpolated: {self.stats['interpolated']:,} ({self.stats['interpolated'] / total * 100:.1f}%)"
        )
        logger.info(
            f"  - Street match: {self.stats['street']:,} ({self.stats['street'] / total * 100:.1f}%)"
        )
        logger.info(
            f"  - Settlement match: {self.stats['settlement']:,} ({self.stats['settlement'] / total * 100:.1f}%)"
        )
        logger.info(
            f"Failed: {self.stats['failed']:,} ({self.stats['failed'] / total * 100:.1f}%)"
        )
        logger.info("=" * 80)

    def _results_to_dataframe(self, results: List[GeocodingResult]) -> pl.DataFrame:
        """Convert geocoding results to DataFrame."""
        now = datetime.now()

        return pl.DataFrame(
            {
                "ID": [r.canonical_address_id for r in results],
                "Latitude": [r.latitude for r in results],
                "Longitude": [r.longitude for r in results],
                "GeocodingQuality": [r.quality.value for r in results],
                "GeocodingSource": [r.source for r in results],
                "GeocodedAt": [now for _ in results],
            }
        )


def geocode_canonical_addresses(
    db_connection,
    run_tag: str,
    ignore_geocoded: bool = False,
    update_from_cache: bool = False,
) -> Dict[str, int]:
    """
    Geocode canonical addresses and update the database.

    Args:
        db_connection: DuckDB connection
        run_tag: Current pipeline run tag
        ignore_geocoded: If True, skip addresses with successful coordinates (retry only failures)
        update_from_cache: If True, only update from cache without actual geocoding

    Returns:
        Dictionary with geocoding statistics
    """
    config = get_config()

    # Allow cache updates even when geocoding is disabled
    if not update_from_cache and not config.get("nominatim", {}).get("enabled", True):
        logger.info("Geocoding disabled in configuration, skipping")
        return {"skipped": True}

    logger.info("=" * 80)
    logger.info("GEOCODING STAGE - CANONICAL ADDRESSES")
    logger.info("=" * 80)

    # Fetch canonical addresses based on ignore_geocoded flag
    if ignore_geocoded:
        logger.info(
            "Fetching canonical addresses (ignoring successfully geocoded, retrying failures)..."
        )
        addresses_df = db_connection.execute("""
            SELECT
                ID,
                CountyCode,
                SettlementName,
                StreetName,
                HouseNumber,
                FullAddress
            FROM CanonicalAddress
            WHERE (Latitude IS NULL OR Longitude IS NULL)  -- Only addresses without valid coordinates
        """).pl()
    else:
        logger.info("Fetching canonical addresses...")
        addresses_df = db_connection.execute("""
            SELECT
                ID,
                CountyCode,
                SettlementName,
                StreetName,
                HouseNumber,
                FullAddress
            FROM CanonicalAddress
            WHERE Latitude IS NULL  -- Only geocode addresses without coordinates
        """).pl()

    logger.info(f"Found {len(addresses_df):,} addresses to geocode")

    if len(addresses_df) == 0:
        logger.info("No addresses to geocode")
        return {"total": 0, "skipped": True}

    # Initialize geocoder
    geocoder = NominatimGeocoder(config)

    # Pre-filter: Load cached results directly from SQLite and only geocode non-cached addresses
    logger.info("Pre-filtering cached addresses from SQLite cache...")
    # Use cache_dir from config (supports both cache_db and cache_dir for backwards compatibility)
    cache_db_path = config.get("nominatim", {}).get("cache_db") or config.get(
        "nominatim", {}
    ).get("cache_dir", "data/geocoding_cache")
    # If cache_db_path is a directory, append the database filename
    cache_path = Path(cache_db_path)
    if cache_path.suffix != ".db":
        cache_db_path = str(cache_path / "geocoding_cache.db")
    else:
        cache_db_path = str(cache_path)

    # Load all cached results directly into DuckDB
    try:
        db_connection.execute(f"""
            ATTACH DATABASE '{cache_db_path}' AS cache_db (TYPE SQLITE, READ_ONLY)
        """)

        # Get cached results for addresses we need to geocode
        cached_df = db_connection.execute("""
            SELECT
                a.ID,
                c.latitude as Latitude,
                c.longitude as Longitude,
                c.quality as GeocodingQuality,
                'cache' as GeocodingSource,
                CURRENT_TIMESTAMP as GeocodedAt
            FROM addresses_df a
            INNER JOIN cache_db.geocoding_cache c ON c.cache_key = MD5(a.SettlementName || '|' || a.StreetName || '|' || a.HouseNumber)
            WHERE c.quality != 'failed'  -- Don't use failed results from cache
        """).pl()

        db_connection.execute("DETACH DATABASE cache_db")

        logger.info(f"Found {len(cached_df):,} addresses in cache")

        # Filter out cached addresses from addresses_df
        if len(cached_df) > 0:
            cached_ids = set(cached_df["ID"].to_list())
            addresses_to_geocode = addresses_df.filter(
                pl.col("ID").is_in(cached_ids).not_()
            )
            logger.info(f"Need to geocode {len(addresses_to_geocode):,} new addresses")
        else:
            addresses_to_geocode = addresses_df
            logger.info(
                f"No cached addresses found, geocoding all {len(addresses_to_geocode):,} addresses"
            )

    except Exception as e:
        logger.warning(f"Could not pre-filter from cache: {e}")
        addresses_to_geocode = addresses_df
        cached_df = None

    # Geocode only non-cached addresses (unless update_from_cache is True)
    if update_from_cache:
        logger.info(
            "--update-from-cache enabled: skipping actual geocoding, using cache only"
        )
        new_results_df = None
    elif len(addresses_to_geocode) > 0:
        new_results_df = geocoder.geocode_addresses(addresses_to_geocode)
    else:
        new_results_df = None

    # Combine cached and newly geocoded results
    if cached_df is not None and new_results_df is not None:
        results_df = pl.concat([cached_df, new_results_df])
    elif cached_df is not None:
        results_df = cached_df
    else:
        results_df = new_results_df

    # If update_from_cache is True and no cache results, return early
    if update_from_cache and (results_df is None or len(results_df) == 0):
        logger.warning("No cached results found. Database not updated.")
        return {
            "total": 0,
            "cached": 0,
            "skipped": True,
            "message": "No cache available",
        }

    # Update database
    logger.info("Updating database with geocoding results...")

    # First, deduplicate results (take first row per ID in case of duplicates)
    db_connection.register("geocoding_results", results_df)

    # Create a temporary table with deduplicated results
    db_connection.execute("""
        CREATE OR REPLACE TEMP TABLE geocoding_results_dedup AS
        SELECT DISTINCT ON (ID)
            ID,
            Latitude,
            Longitude,
            GeocodingQuality,
            GeocodingSource,
            GeocodedAt
        FROM geocoding_results
    """)

    # Now use the deduplicated results for update
    # DuckDB's FK constraints prevent ANY UPDATE - we need to drop and recreate FKs
    logger.info("Temporarily dropping foreign key constraints to allow update...")

    # Get count of rows to update
    count_result = db_connection.execute("""
        SELECT COUNT(*) FROM geocoding_results_dedup
    """).fetchone()
    total_updates = count_result[0] if count_result else 0

    if total_updates == 0:
        logger.info("No addresses to update")
    else:
        logger.info(f"Preparing to update {total_updates:,} addresses...")

        # Step 1: Get foreign key information before dropping
        logger.info("Saving foreign key constraints...")
        fk_info = db_connection.execute("""
            SELECT
                table_name,
                constraint_text
            FROM duckdb_constraints()
            WHERE constraint_type = 'FOREIGN KEY'
              AND table_name IN ('AddressMapping', 'AddressPollingStations', 'AddressPIRCodes')
        """).fetchall()

        # Step 2: Drop ALL foreign key constraints to CanonicalAddress
        logger.info("Dropping foreign key constraints from all dependent tables...")

        # AddressMapping
        logger.info("Recreating AddressMapping without FK constraints...")
        db_connection.execute(
            "CREATE TEMP TABLE AddressMapping_temp AS SELECT * FROM AddressMapping"
        )
        db_connection.execute("DROP TABLE AddressMapping")
        db_connection.execute("""
            CREATE TABLE AddressMapping (
                ID TEXT PRIMARY KEY,
                OriginalAddressID TEXT NOT NULL,
                CanonicalAddressID TEXT NOT NULL,
                MappingType TEXT DEFAULT 'deduplication',
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (OriginalAddressID, CanonicalAddressID)
            )
        """)
        db_connection.execute(
            "INSERT INTO AddressMapping SELECT ID, OriginalAddressID, CanonicalAddressID, MappingType, CreatedAt FROM AddressMapping_temp"
        )
        db_connection.execute("DROP TABLE AddressMapping_temp")

        # AddressPollingStations
        logger.info("Recreating AddressPollingStations without FK constraints...")
        db_connection.execute(
            "CREATE TEMP TABLE AddressPollingStations_temp AS SELECT * FROM AddressPollingStations"
        )
        db_connection.execute("DROP TABLE AddressPollingStations")
        db_connection.execute("""
            CREATE TABLE AddressPollingStations (
                ID TEXT PRIMARY KEY,
                CanonicalAddressID TEXT NOT NULL,
                PollingStationID TEXT NOT NULL,
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (CanonicalAddressID, PollingStationID)
            )
        """)
        db_connection.execute(
            "INSERT INTO AddressPollingStations SELECT ID, CanonicalAddressID, PollingStationID, CreatedAt FROM AddressPollingStations_temp"
        )
        db_connection.execute("DROP TABLE AddressPollingStations_temp")

        # AddressPIRCodes
        logger.info("Recreating AddressPIRCodes without FK constraints...")
        db_connection.execute(
            "CREATE TEMP TABLE AddressPIRCodes_temp AS SELECT * FROM AddressPIRCodes"
        )
        db_connection.execute("DROP TABLE AddressPIRCodes")
        db_connection.execute("""
            CREATE TABLE AddressPIRCodes (
                ID TEXT PRIMARY KEY,
                CanonicalAddressID TEXT NOT NULL,
                PIRCode TEXT NOT NULL,
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (CanonicalAddressID, PIRCode)
            )
        """)
        db_connection.execute(
            "INSERT INTO AddressPIRCodes SELECT ID, CanonicalAddressID, PIRCode, CreatedAt FROM AddressPIRCodes_temp"
        )
        db_connection.execute("DROP TABLE AddressPIRCodes_temp")

        # Step 3: Now we can safely update CanonicalAddress
        # Use Python-based merge to avoid DuckDB UPDATE issues
        logger.info(
            "Updating coordinates using Python merge (avoiding DuckDB UPDATE bug)..."
        )

        # Fetch all canonical addresses
        canonical_df = db_connection.execute("SELECT * FROM CanonicalAddress").pl()
        logger.info(f"Loaded {len(canonical_df):,} canonical addresses")

        # Fetch geocoding results
        geocoding_df = db_connection.execute(
            "SELECT * FROM geocoding_results_dedup"
        ).pl()
        logger.info(f"Loaded {len(geocoding_df):,} geocoding results")

        # Merge/update using Polars
        # Rename geocoding columns before join to avoid conflicts
        # Remove timezone from GeocodedAt to avoid supertype mismatch
        geocoding_update = geocoding_df.select(
            [
                pl.col("ID"),
                pl.col("Latitude").alias("Latitude_new"),
                pl.col("Longitude").alias("Longitude_new"),
                pl.col("GeocodingQuality").alias("GeocodingQuality_new"),
                pl.col("GeocodingSource").alias("GeocodingSource_new"),
                pl.col("GeocodedAt").dt.replace_time_zone(None).alias("GeocodedAt_new"),
            ]
        )

        updated_df = canonical_df.join(geocoding_update, on="ID", how="left")

        # Update columns with COALESCE logic (prefer new values over existing)
        updated_df = updated_df.with_columns(
            [
                pl.coalesce(["Latitude_new", "Latitude"]).alias("Latitude"),
                pl.coalesce(["Longitude_new", "Longitude"]).alias("Longitude"),
                pl.coalesce(["GeocodingQuality_new", "GeocodingQuality"]).alias(
                    "GeocodingQuality"
                ),
                pl.coalesce(["GeocodingSource_new", "GeocodingSource"]).alias(
                    "GeocodingSource"
                ),
                pl.coalesce(["GeocodedAt_new", "GeocodedAt"]).alias("GeocodedAt"),
            ]
        )

        # Drop the _new columns
        updated_df = updated_df.select(
            [
                "ID",
                "CountyCode",
                "SettlementName",
                "StreetName",
                "HouseNumber",
                "Building",
                "Staircase",
                "FullAddress",
                "AccessibilityFlag",
                "Latitude",
                "Longitude",
                "GeocodingQuality",
                "GeocodingSource",
                "GeocodedAt",
                "CreatedAt",
            ]
        )

        logger.info("Updating CanonicalAddress table with geocoded data...")

        # Use DELETE+INSERT instead of table swap to avoid dependency issues
        # This preserves the table structure and all constraints/indexes

        # Step 1: Export dependent table data to memory
        logger.info("Exporting dependent table data to memory...")
        address_mapping_df = db_connection.execute("SELECT * FROM AddressMapping").pl()
        address_polling_df = db_connection.execute(
            "SELECT * FROM AddressPollingStations"
        ).pl()
        address_pir_df = db_connection.execute("SELECT * FROM AddressPIRCodes").pl()

        # Step 2: Drop all dependent tables to allow DELETE on CanonicalAddress
        logger.info("Dropping all dependent tables...")
        db_connection.execute("DROP TABLE AddressMapping")
        db_connection.execute("DROP TABLE AddressPollingStations")
        db_connection.execute("DROP TABLE AddressPIRCodes")

        # Step 3: Clear and reload CanonicalAddress data
        logger.info("Deleting all rows from CanonicalAddress...")
        db_connection.execute("DELETE FROM CanonicalAddress")

        logger.info("Inserting updated data into CanonicalAddress...")
        db_connection.register("CanonicalAddress_new_data", updated_df)
        db_connection.execute(
            "INSERT INTO CanonicalAddress SELECT * FROM CanonicalAddress_new_data"
        )
        db_connection.unregister("CanonicalAddress_new_data")

        # Step 4: Recreate ALL foreign key constraints
        logger.info("Recreating foreign key constraints for all dependent tables...")

        # AddressMapping
        logger.info("Recreating AddressMapping WITH FK constraints...")
        db_connection.execute("""
            CREATE TABLE AddressMapping (
                ID TEXT PRIMARY KEY,
                OriginalAddressID TEXT NOT NULL,
                CanonicalAddressID TEXT NOT NULL,
                MappingType TEXT DEFAULT 'deduplication',
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (CanonicalAddressID) REFERENCES CanonicalAddress(ID),
                UNIQUE (OriginalAddressID, CanonicalAddressID)
            )
        """)
        db_connection.register("AddressMapping_data", address_mapping_df)
        db_connection.execute(
            "INSERT INTO AddressMapping SELECT * FROM AddressMapping_data"
        )
        db_connection.unregister("AddressMapping_data")

        # AddressPollingStations
        logger.info("Recreating AddressPollingStations WITH FK constraints...")
        db_connection.execute("""
            CREATE TABLE AddressPollingStations (
                ID TEXT PRIMARY KEY,
                CanonicalAddressID TEXT NOT NULL,
                PollingStationID TEXT NOT NULL,
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (CanonicalAddressID) REFERENCES CanonicalAddress(ID),
                UNIQUE (CanonicalAddressID, PollingStationID)
            )
        """)
        db_connection.register("AddressPollingStations_data", address_polling_df)
        db_connection.execute(
            "INSERT INTO AddressPollingStations SELECT * FROM AddressPollingStations_data"
        )
        db_connection.unregister("AddressPollingStations_data")

        # AddressPIRCodes
        logger.info("Recreating AddressPIRCodes WITH FK constraints...")
        db_connection.execute("""
            CREATE TABLE AddressPIRCodes (
                ID TEXT PRIMARY KEY,
                CanonicalAddressID TEXT NOT NULL,
                PIRCode TEXT NOT NULL,
                CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (CanonicalAddressID) REFERENCES CanonicalAddress(ID),
                UNIQUE (CanonicalAddressID, PIRCode)
            )
        """)
        db_connection.register("AddressPIRCodes_data", address_pir_df)
        db_connection.execute(
            "INSERT INTO AddressPIRCodes SELECT * FROM AddressPIRCodes_data"
        )
        db_connection.unregister("AddressPIRCodes_data")

        logger.info(f"Successfully updated {total_updates:,} addresses")

    db_connection.unregister("geocoding_results")
    db_connection.execute("DROP TABLE IF EXISTS geocoding_results_dedup")

    logger.info("Geocoding complete")

    return geocoder.stats


class HereGeocoder:
    """
    HERE Geocoding API service for post-processing fallback.

    Uses HERE Geocoding & Search API v8 to improve geocoding results
    for addresses that failed or have low-quality results from Nominatim.

    API Documentation: https://www.here.com/docs/bundle/geocoding-and-search-api-developer-guide
    Free Tier: 250,000 queries/month
    Pricing: $1/1000 queries after free tier
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize HERE geocoder with configuration."""
        if config is None:
            config = get_config()

        self.config = config
        here_config = config.get("here", {})

        self.api_key = here_config.get("api_key")
        if not self.api_key:
            raise ValueError(
                "HERE API key not configured. Set 'here.api_key' in config or "
                "HERE_API_KEY environment variable."
            )

        self.base_url = here_config.get(
            "base_url", "https://geocode.search.hereapi.com/v1"
        )
        self.timeout = here_config.get("timeout", 30)
        self.rate_limit = here_config.get("rate_limit", 5)  # 5 req/sec for free tier
        self.max_workers = here_config.get("max_workers", 4)  # Conservative for API

        # Rate limiting state
        self.last_request_time = 0.0

        # Statistics
        import threading

        self.stats_lock = threading.Lock()
        self.stats = {
            "total": 0,
            "success": 0,
            "exact": 0,
            "street": 0,
            "settlement": 0,
            "failed": 0,
        }

        logger.info(f"HERE Geocoder initialized (rate_limit={self.rate_limit} req/sec)")

    def geocode_addresses_batch(
        self, addresses_df: pl.DataFrame
    ) -> List[GeocodingResult]:
        """
        Geocode a batch of addresses using HERE API.

        Args:
            addresses_df: DataFrame with columns ID, SettlementName, StreetName,
                         HouseNumber, FullAddress

        Returns:
            List of GeocodingResult objects
        """
        logger.info(f"Geocoding {len(addresses_df):,} addresses with HERE API")

        results = []
        addresses = list(addresses_df.iter_rows(named=True))

        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_address = {
                executor.submit(self._geocode_single, addr): addr for addr in addresses
            }

            for future in as_completed(future_to_address):
                result = future.result()
                results.append(result)
                with self.stats_lock:
                    self.stats["total"] += 1
                    if result.quality != GeocodingQuality.FAILED:
                        self.stats["success"] += 1
                        self.stats[result.quality.value] += 1
                    else:
                        self.stats["failed"] += 1

        # Log statistics
        total = self.stats["total"]
        if total > 0:
            logger.info(
                f"HERE Geocoding complete: {total:,} addresses | "
                f"Success: {self.stats['success']:,} ({self.stats['success'] / total * 100:.1f}%) | "
                f"Exact: {self.stats['exact']:,} ({self.stats['exact'] / total * 100:.1f}%) | "
                f"Street: {self.stats['street']:,} ({self.stats['street'] / total * 100:.1f}%) | "
                f"Settlement: {self.stats['settlement']:,} ({self.stats['settlement'] / total * 100:.1f}%) | "
                f"Failed: {self.stats['failed']:,} ({self.stats['failed'] / total * 100:.1f}%)"
            )

        return results

    def _geocode_single(self, address: Dict) -> GeocodingResult:
        """
        Geocode a single address using HERE API.

        Uses structured address components for better results:
        - street: StreetName + HouseNumber
        - city: SettlementName
        - country: Hungary
        """
        # Apply rate limiting
        self._apply_rate_limit()

        # Build query string
        query_parts = []

        # Add house number and street
        if address.get("StreetName") and address.get("HouseNumber"):
            house_num = address["HouseNumber"].lstrip("0") or "0"
            query_parts.append(f"{address['StreetName']} {house_num}")
        elif address.get("StreetName"):
            query_parts.append(address["StreetName"])

        # Add settlement
        if address.get("SettlementName"):
            query_parts.append(address["SettlementName"])

        # Add country
        query_parts.append("Hungary")

        query = ", ".join(query_parts)

        # Build request parameters
        params = {
            "q": query,
            "apiKey": self.api_key,
            "limit": 1,
            "lang": "hu",  # Hungarian language
        }

        try:
            response = requests.get(
                f"{self.base_url}/geocode",
                params=params,
                timeout=self.timeout,
                headers={"User-Agent": "OEVK-Data-Pipeline/1.0"},
            )
            response.raise_for_status()

            data = response.json()
            return self._parse_response(data, address)

        except requests.RequestException as e:
            logger.warning(f"HERE API error for {query}: {e}")
            return GeocodingResult(
                canonical_address_id=address["ID"],
                latitude=None,
                longitude=None,
                quality=GeocodingQuality.FAILED,
                source="here_api",
                osm_type=None,
                osm_id=None,
                matched_address=None,
            )

    def _parse_response(self, data: Dict, original_address: Dict) -> GeocodingResult:
        """Parse HERE API response."""
        items = data.get("items", [])

        if not items:
            return GeocodingResult(
                canonical_address_id=original_address["ID"],
                latitude=None,
                longitude=None,
                quality=GeocodingQuality.FAILED,
                source="here_api",
                osm_type=None,
                osm_id=None,
                matched_address=None,
            )

        item = items[0]

        # Extract coordinates
        position = item.get("position", {})
        lat = position.get("lat")
        lon = position.get("lng")

        if lat is None or lon is None:
            return GeocodingResult(
                canonical_address_id=original_address["ID"],
                latitude=None,
                longitude=None,
                quality=GeocodingQuality.FAILED,
                source="here_api",
                osm_type=None,
                osm_id=None,
                matched_address=None,
            )

        # Determine quality based on result type
        quality = self._determine_quality(item)

        # Get matched address
        matched_address = item.get("title") or item.get("address", {}).get("label")

        return GeocodingResult(
            canonical_address_id=original_address["ID"],
            latitude=lat,
            longitude=lon,
            quality=quality,
            source="here_api",
            osm_type=None,
            osm_id=None,
            matched_address=matched_address,
        )

    def _determine_quality(self, item: Dict) -> GeocodingQuality:
        """
        Determine quality from HERE API result.

        HERE returns resultType which indicates precision:
        - houseNumber: exact house-level match
        - street: street-level match
        - locality: settlement-level match
        """
        result_type = item.get("resultType", "").lower()

        # Check resultType
        if result_type == "housenumber":
            return GeocodingQuality.EXACT
        elif result_type == "street":
            return GeocodingQuality.STREET
        elif result_type in ["locality", "administrativearea", "place"]:
            return GeocodingQuality.SETTLEMENT

        # Fallback: check matchLevel in scoring
        scoring = item.get("scoring", {})
        match_level = scoring.get("fieldScore", {})

        # If has houseNumber field, consider it exact
        address = item.get("address", {})
        if address.get("houseNumber"):
            return GeocodingQuality.EXACT
        elif address.get("street"):
            return GeocodingQuality.STREET
        elif address.get("city") or address.get("district"):
            return GeocodingQuality.SETTLEMENT

        # Default to street level
        return GeocodingQuality.STREET

    def _apply_rate_limit(self):
        """Apply rate limiting between requests."""
        if self.rate_limit <= 0:
            return

        elapsed = time.time() - self.last_request_time
        required_delay = 1.0 / self.rate_limit

        if elapsed < required_delay:
            time.sleep(required_delay - elapsed)

        self.last_request_time = time.time()


class PollingStationGeocoder:
    """Geocoder for polling stations with fuzzy search capabilities."""

    def __init__(self, config: Optional[Dict], db_connection):
        """Initialize geocoder with configuration and database access."""
        if config is None:
            config = get_config()

        self.config = config
        self.db_connection = db_connection
        self.nominatim_geocoder = NominatimGeocoder(config)

        # Institution keywords to remove for fuzzy search
        import re

        institution_keywords = [
            "általános iskola",
            "gimnázium",
            "szakközépiskola",
            "művelődési ház",
            "közösségi ház",
            "kultúrház",
            "polgármesteri hivatal",
            "önkormányzat",
            "óvoda",
            "iskola",
            "könyvtár",
            "sportcsarnok",
        ]
        # Compile a single regex for institution keywords
        keywords_pattern = "|".join(re.escape(k) for k in institution_keywords)
        self.institution_regex = re.compile(keywords_pattern, re.IGNORECASE)

        # Statistics
        self.stats = {
            "total": 0,
            "exact_match": 0,
            "fuzzy_nominatim": 0,
            "canonical_match": 0,
            "settlement_fallback": 0,
            "failed": 0,
        }

        # Start time for progress tracking
        self.start_time = time.time()

    def geocode_polling_stations(self, stations_df: pl.DataFrame) -> pl.DataFrame:
        """
        Geocode polling stations with multi-strategy approach.

        Strategy:
        1. Try exact address match with Nominatim
        2. Try fuzzy tokenization and simplified address
        3. Match against CanonicalAddress table with similarity
        4. Fall back to settlement centroid
        """
        logger.info(
            f"Starting polling station geocoding for {len(stations_df):,} stations"
        )
        self.start_time = time.time()

        results = []
        total_batches = (len(stations_df) + 100 - 1) // 100

        for batch_idx in range(total_batches):
            start_idx = batch_idx * 100
            end_idx = min(start_idx + 100, len(stations_df))
            batch = stations_df[start_idx:end_idx]

            for row in batch.iter_rows(named=True):
                result = self._geocode_single_station(row)
                results.append(result)
                self.stats["total"] += 1

            # Progress reporting every 10 batches
            if (batch_idx + 1) % 10 == 0 or (batch_idx + 1) == total_batches:
                self._log_progress(batch_idx + 1, total_batches)

        # Log final statistics
        self._log_final_stats()

        return self._results_to_dataframe(results)

    def _clean_address(self, address: str) -> str:
        """Remove parenthesized text from an address."""
        import re

        return re.sub(r"\s*\([^)]*\)\s*", " ", address).strip()

    def _geocode_single_station(self, station: Dict) -> GeocodingResult:
        """Geocode a single polling station using multi-strategy approach."""

        # Clean address by removing parenthesized text
        cleaned_address = self._clean_address(station["PollingStationAddress"])

        # Strategy 1: Try exact match with Nominatim
        address_dict = {
            "ID": station["ID"],
            "SettlementName": station["SettlementName"],
            "StreetName": "",
            "HouseNumber": "",
            "FullAddress": cleaned_address,
        }

        result = self.nominatim_geocoder._geocode_single(address_dict)
        if result.latitude is not None and result.quality != GeocodingQuality.FAILED:
            self.stats["exact_match"] += 1
            result.source = "nominatim_local"
            result.matched_address = cleaned_address
            return result

        # Strategy 2: Try fuzzy tokenization
        simplified_address = self._extract_address_components(cleaned_address)
        if simplified_address:
            address_dict["FullAddress"] = simplified_address
            address_dict["StreetName"] = simplified_address  # For caching
            result = self.nominatim_geocoder._geocode_single(address_dict)
            if (
                result.latitude is not None
                and result.quality != GeocodingQuality.FAILED
            ):
                self.stats["fuzzy_nominatim"] += 1
                result.source = "nominatim_fuzzy"
                result.matched_address = simplified_address
                return result

        # Strategy 3: Match against CanonicalAddress with similarity
        canonical_match = self._match_canonical_address(
            cleaned_address, station["SettlementName"]
        )
        if canonical_match:
            self.stats["canonical_match"] += 1
            return GeocodingResult(
                canonical_address_id=station["ID"],
                latitude=canonical_match["Latitude"],
                longitude=canonical_match["Longitude"],
                quality=GeocodingQuality(canonical_match["GeocodingQuality"]),
                source="canonical_address",
                osm_type=None,
                osm_id=None,
                matched_address=canonical_match["MatchedAddress"],
            )

        # Strategy 4: Fall back to settlement centroid
        settlement_coords = self._get_settlement_centroid(station["SettlementName"])
        if settlement_coords:
            self.stats["settlement_fallback"] += 1
            return GeocodingResult(
                canonical_address_id=station["ID"],
                latitude=settlement_coords["Latitude"],
                longitude=settlement_coords["Longitude"],
                quality=GeocodingQuality.SETTLEMENT,
                source="settlement_centroid",
                osm_type=None,
                osm_id=None,
                matched_address=station["SettlementName"],
            )

        # All strategies failed
        self.stats["failed"] += 1
        return GeocodingResult(
            canonical_address_id=station["ID"],
            latitude=None,
            longitude=None,
            quality=GeocodingQuality.FAILED,
            source="all_strategies_failed",
            osm_type=None,
            osm_id=None,
            matched_address=None,
        )

    def _extract_address_components(self, address: str) -> Optional[str]:
        """
        Extract clean address components from polling station address.

        Removes institution keywords and extracts street patterns.

        Example:
            "Kossuth Lajos Általános Iskola, Petőfi utca 10."
            → "Petőfi utca 10"
        """
        # Remove institution keywords using pre-compiled regex and convert to lowercase
        # for consistent street pattern matching.
        address_lower = self.institution_regex.sub("", address).lower()

        # Extract street pattern: [Name] [Type] [Number]
        # Hungarian street types: utca, út, tér, köz, körút, sétány, etc.
        street_pattern = r"([a-záéíóöőúüű\s]+(?:utca|út|tér|köz|körút|sétány|park|sor))\s*(\d+[a-z\-/\.]*)"
        match = re.search(street_pattern, address_lower)

        if match:
            street = match.group(1).strip()
            number = match.group(2).strip()
            return f"{street} {number}"

        # If no pattern found, remove common punctuation and extra spaces
        cleaned = re.sub(r"[,;]", " ", address_lower)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned if cleaned != address_lower else None

    def _match_canonical_address(
        self, polling_address: str, settlement_id: str
    ) -> Optional[Dict]:
        """
        Match polling station address against CanonicalAddress using Levenshtein similarity.

        Uses DuckDB's levenshtein function for fuzzy text matching.
        Requires similarity threshold ≥0.6.
        """
        try:
            # Get similarity threshold from config
            similarity_threshold = self.config.get("nominatim", {}).get(
                "similarity_threshold", 0.6
            )

            result = self.db_connection.execute(
                """
                SELECT
                    Latitude,
                    Longitude,
                    GeocodingQuality,
                    FullAddress as MatchedAddress,
                    1.0 - (CAST(levenshtein(LOWER(?), LOWER(FullAddress)) AS REAL) /
                           GREATEST(LENGTH(?), LENGTH(FullAddress))) as similarity
                FROM CanonicalAddress
                WHERE SettlementName = ?
                  AND Latitude IS NOT NULL
                  AND GeocodingQuality IN ('exact', 'street')
                ORDER BY similarity DESC
                LIMIT 1
            """,
                [polling_address, polling_address, settlement_id],
            ).fetchone()

            if result and result[4] >= similarity_threshold:
                return {
                    "Latitude": result[0],
                    "Longitude": result[1],
                    "GeocodingQuality": result[2],
                    "MatchedAddress": result[3],
                }
        except Exception as e:
            logger.warning(f"Canonical address matching failed: {e}")

        return None

    def _get_settlement_centroid(self, settlement_name: str) -> Optional[Dict]:
        """Get settlement centroid coordinates from already geocoded addresses."""
        try:
            result = self.db_connection.execute(
                """
                SELECT
                    AVG(Latitude) as Latitude,
                    AVG(Longitude) as Longitude
                FROM CanonicalAddress
                WHERE SettlementName = ?
                  AND Latitude IS NOT NULL
                  AND GeocodingQuality IN ('exact', 'street')
                GROUP BY SettlementName
            """,
                [settlement_name],
            ).fetchone()

            if result and result[0] is not None:
                return {"Latitude": result[0], "Longitude": result[1]}
        except Exception as e:
            logger.warning(f"Settlement centroid lookup failed: {e}")

        return None

    def _log_progress(self, current_batch: int, total_batches: int):
        """Log current progress statistics."""
        total = self.stats["total"]
        if total == 0:
            return

        # Calculate progress percentage
        progress_pct = (current_batch / total_batches) * 100

        # Calculate processing rate
        elapsed_time = time.time() - self.start_time
        rate = total / elapsed_time if elapsed_time > 0 else 0

        # Calculate ETA
        remaining_batches = total_batches - current_batch
        if rate > 0:
            remaining_stations = remaining_batches * 100
            eta_seconds = remaining_stations / rate
            eta_minutes = int(eta_seconds / 60)
        else:
            eta_minutes = 0

        logger.info(
            f"Batch {current_batch}/{total_batches} ({progress_pct:.1f}%) | "
            f"Progress: {total:,} stations | "
            f"Rate: {rate:.1f} stations/sec | "
            f"ETA: {eta_minutes} min | "
            f"Exact: {self.stats['exact_match']:,} ({self.stats['exact_match'] / total * 100:.1f}%) | "
            f"Fuzzy: {self.stats['fuzzy_nominatim']:,} ({self.stats['fuzzy_nominatim'] / total * 100:.1f}%) | "
            f"Canonical: {self.stats['canonical_match']:,} ({self.stats['canonical_match'] / total * 100:.1f}%) | "
            f"Settlement: {self.stats['settlement_fallback']:,} ({self.stats['settlement_fallback'] / total * 100:.1f}%) | "
            f"Failed: {self.stats['failed']:,} ({self.stats['failed'] / total * 100:.1f}%)"
        )

    def _log_final_stats(self):
        """Log final geocoding statistics."""
        total = self.stats["total"]
        elapsed_time = time.time() - self.start_time

        logger.info("=" * 80)
        logger.info("POLLING STATION GEOCODING STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total stations: {total:,}")
        logger.info(f"Total time: {elapsed_time:.1f}s ({elapsed_time / 60:.1f} min)")
        logger.info(
            f"Exact match (Nominatim): {self.stats['exact_match']:,} ({self.stats['exact_match'] / total * 100:.1f}%)"
        )
        logger.info(
            f"Fuzzy match (Nominatim): {self.stats['fuzzy_nominatim']:,} ({self.stats['fuzzy_nominatim'] / total * 100:.1f}%)"
        )
        logger.info(
            f"Canonical address match: {self.stats['canonical_match']:,} ({self.stats['canonical_match'] / total * 100:.1f}%)"
        )
        logger.info(
            f"Settlement fallback: {self.stats['settlement_fallback']:,} ({self.stats['settlement_fallback'] / total * 100:.1f}%)"
        )
        logger.info(
            f"Failed: {self.stats['failed']:,} ({self.stats['failed'] / total * 100:.1f}%)"
        )
        logger.info("=" * 80)

    def _results_to_dataframe(self, results: List[GeocodingResult]) -> pl.DataFrame:
        """Convert geocoding results to DataFrame."""
        now = datetime.now()

        return pl.DataFrame(
            {
                "ID": [r.canonical_address_id for r in results],
                "Latitude": [r.latitude for r in results],
                "Longitude": [r.longitude for r in results],
                "GeocodingQuality": [r.quality.value for r in results],
                "GeocodingSource": [r.source for r in results],
                "GeocodedAt": [now for _ in results],
                "MatchedAddress": [r.matched_address for r in results],
            }
        )


def geocode_polling_stations(
    db_connection, run_tag: str, update_from_cache: bool = False
) -> Dict[str, int]:
    """
    Geocode polling stations using fuzzy search and canonical address matching.

    Args:
        db_connection: DuckDB connection
        run_tag: Current pipeline run tag
        update_from_cache: If True, only update from cache without actual geocoding

    Returns:
        Dictionary with geocoding statistics
    """
    config = get_config()

    # Allow cache updates even when geocoding is disabled
    if not update_from_cache and not config.get("nominatim", {}).get("enabled", True):
        logger.info("Geocoding disabled in configuration, skipping")
        return {"skipped": True}

    logger.info("=" * 80)
    logger.info("GEOCODING STAGE - POLLING STATIONS")
    logger.info("=" * 80)

    # Fetch polling stations without coordinates
    logger.info("Fetching polling stations...")
    stations_df = db_connection.execute("""
        SELECT
            ps.ID,
            ps.PollingStationAddress,
            s.SettlementName,
            ps.Settlement_ID
        FROM PollingStation ps
        JOIN Settlement s ON ps.Settlement_ID = s.ID
        WHERE ps.Latitude IS NULL  -- Only geocode stations without coordinates
    """).pl()

    logger.info(f"Found {len(stations_df):,} polling stations to geocode")

    if len(stations_df) == 0:
        logger.info("No polling stations to geocode")
        return {"total": 0, "skipped": True}

    # Initialize geocoder with fuzzy search capabilities
    geocoder = PollingStationGeocoder(config, db_connection)

    # Geocode polling stations
    results_df = geocoder.geocode_polling_stations(stations_df)

    # Update database
    logger.info("Updating database with polling station geocoding results...")

    db_connection.register("polling_station_results", results_df)
    db_connection.execute("""
        UPDATE PollingStation
        SET
            Latitude = psr.Latitude,
            Longitude = psr.Longitude,
            GeocodingQuality = psr.GeocodingQuality,
            GeocodingSource = psr.GeocodingSource,
            GeocodedAt = psr.GeocodedAt,
            MatchedAddress = psr.MatchedAddress
        FROM polling_station_results psr
        WHERE PollingStation.ID = psr.ID
    """)
    db_connection.unregister("polling_station_results")

    logger.info("Polling station geocoding complete")

    return geocoder.stats
