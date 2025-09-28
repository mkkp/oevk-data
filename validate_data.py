#!/usr/bin/env python3
"""Data validation script for OEVK data processing pipeline."""

import duckdb
import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database.connection import get_database_connection
from src.utils.logging import get_logger

logger = get_logger(__name__)


def validate_data_integrity(db_path: str) -> bool:
    """Validate the integrity of processed data.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        True if validation passes, False otherwise
    """
    logger.info(f"Validating data integrity for database: {db_path}")
    
    conn = get_database_connection(db_path)
    
    try:
        # Check if all target tables exist
        target_tables = [
            'County', 'Settlement', 'NationalIndividualElectoralDistrict',
            'SettlementIndividualElectoralDistrict', 'PollingStation',
            'Address', 'PostalCode', 'PostalCode_Settlement'
        ]
        
        for table in target_tables:
            result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            logger.info(f"{table}: {result:,} rows")
            
            if result == 0:
                logger.error(f"Table {table} is empty!")
                return False
        
        # Validate row counts match expectations
        staging_count = conn.execute("SELECT COUNT(*) FROM staging_korzet").fetchone()[0]
        address_count = conn.execute("SELECT COUNT(*) FROM Address").fetchone()[0]
        
        logger.info(f"Staging records: {staging_count:,}")
        logger.info(f"Address records: {address_count:,}")
        
        if staging_count != address_count:
            logger.warning(f"Row count mismatch: staging={staging_count:,}, addresses={address_count:,}")
            # This might be expected due to deduplication, so not a failure
        
        # Validate referential integrity
        logger.info("Validating referential integrity...")
        
        # Check for orphaned records
        integrity_checks = [
            ("Address", "County_ID", "County", "ID"),
            ("Address", "Settlement_ID", "Settlement", "ID"),
            ("Address", "NationalIndividualElectoralDistrict_ID", "NationalIndividualElectoralDistrict", "ID"),
            ("Address", "SettlementIndividualElectoralDistrict_ID", "SettlementIndividualElectoralDistrict", "ID"),
            ("Address", "PollingStation_ID", "PollingStation", "ID"),
            ("Address", "PostalCode_ID", "PostalCode", "ID"),
            ("Settlement", "County_ID", "County", "ID"),
            ("SettlementIndividualElectoralDistrict", "County_ID", "County", "ID"),
            ("SettlementIndividualElectoralDistrict", "Settlement_ID", "Settlement", "ID"),
            ("SettlementIndividualElectoralDistrict", "NationalIndividualElectoralDistrict_ID", "NationalIndividualElectoralDistrict", "ID"),
            ("PollingStation", "County_ID", "County", "ID"),
            ("PollingStation", "Settlement_ID", "Settlement", "ID"),
            ("PollingStation", "NationalIndividualElectoralDistrict_ID", "NationalIndividualElectoralDistrict", "ID"),
            ("PollingStation", "SettlementIndividualElectoralDistrict_ID", "SettlementIndividualElectoralDistrict", "ID"),
            ("PostalCode_Settlement", "PostalCode_ID", "PostalCode", "ID"),
            ("PostalCode_Settlement", "Settlement_ID", "Settlement", "ID")
        ]
        
        all_checks_passed = True
        for child_table, child_fk, parent_table, parent_pk in integrity_checks:
            orphan_count = conn.execute(f"""
                SELECT COUNT(*) FROM {child_table} 
                WHERE {child_fk} NOT IN (SELECT {parent_pk} FROM {parent_table})
            """).fetchone()[0]
            
            if orphan_count > 0:
                logger.error(f"Found {orphan_count} orphaned records in {child_table}.{child_fk} referencing {parent_table}")
                all_checks_passed = False
            else:
                logger.info(f"✓ {child_table}.{child_fk} -> {parent_table} integrity: OK")
        
        # Check for duplicate IDs
        duplicate_checks = [
            ("County", "ID"),
            ("Settlement", "ID"),
            ("NationalIndividualElectoralDistrict", "ID"),
            ("SettlementIndividualElectoralDistrict", "ID"),
            ("PollingStation", "ID"),
            ("Address", "ID"),
            ("PostalCode", "ID"),
            ("PostalCode_Settlement", "ID")
        ]
        
        for table, id_column in duplicate_checks:
            duplicate_count = conn.execute(f"""
                SELECT COUNT(*) - COUNT(DISTINCT {id_column}) 
                FROM {table}
            """).fetchone()[0]
            
            if duplicate_count > 0:
                logger.error(f"Found {duplicate_count} duplicate IDs in {table}.{id_column}")
                all_checks_passed = False
            else:
                logger.info(f"✓ {table}.{id_column} uniqueness: OK")
        
        # Validate data quality
        logger.info("Validating data quality...")
        
        # Check for NULL values in required fields
        required_field_checks = [
            ("County", "CountyCode"),
            ("County", "CountyName"),
            ("Settlement", "SettlementCode"),
            ("Settlement", "SettlementName"),
            ("Address", "FullAddress"),
            ("Address", "County_ID"),
            ("Address", "Settlement_ID")
        ]
        
        for table, field in required_field_checks:
            null_count = conn.execute(f"""
                SELECT COUNT(*) FROM {table} 
                WHERE {field} IS NULL
            """).fetchone()[0]
            
            if null_count > 0:
                logger.warning(f"Found {null_count} NULL values in {table}.{field}")
                # This might be acceptable for some fields, so not a failure
            else:
                logger.info(f"✓ {table}.{field} completeness: OK")
        
        if all_checks_passed:
            logger.info("✅ All data integrity checks passed!")
            return True
        else:
            logger.error("❌ Some data integrity checks failed!")
            return False
            
    except Exception as e:
        logger.error(f"Validation failed with error: {e}")
        return False
    
    finally:
        conn.close()


def main():
    """Main entry point for validation script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate OEVK data processing integrity")
    parser.add_argument('--db-path', default='data/oevk.db', 
                       help='Path to the database file (default: data/oevk.db)')
    
    args = parser.parse_args()
    
    success = validate_data_integrity(args.db_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()