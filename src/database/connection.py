"""Database connection management for the OEVK data transformation pipeline."""

import os
from typing import Optional
import duckdb
from src.utils.logging import get_logger

logger = get_logger(__name__)


def get_database_connection(db_path: Optional[str] = None) -> duckdb.DuckDBPyConnection:
    """Get a database connection, creating the database and schema if needed.
    
    Args:
        db_path: Path to the database file. If None, uses in-memory database.
        
    Returns:
        An active DuckDB connection with the schema applied.
    """
    if db_path is None:
        db_path = ':memory:'
        logger.info("Using in-memory database")
    elif db_path != ':memory:' and os.path.dirname(db_path):
        # Ensure the directory exists (only if path has a directory component)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        logger.info(f"Using database at {db_path}")
    
    # Connect to the database
    conn = duckdb.connect(db_path)
    
    # Apply the schema if this is a new database
    apply_schema(conn)
    
    return conn


def apply_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply the database schema to the connection.
    
    Args:
        conn: An active DuckDB connection.
    """
    # Read the schema file
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    
    if not os.path.exists(schema_path):
        logger.error(f"Schema file not found at {schema_path}")
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
    
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    # Execute the schema
    conn.execute(schema_sql)
    logger.info("Database schema applied successfully")


def close_connection(conn: duckdb.DuckDBPyConnection) -> None:
    """Close a database connection.
    
    Args:
        conn: The database connection to close.
    """
    if conn:
        conn.close()
        logger.info("Database connection closed")


def test_connection() -> bool:
    """Test that the database connection works correctly.
    
    Returns:
        True if the connection test passes, False otherwise.
    """
    try:
        with get_database_connection(':memory:') as conn:
            # Test that we can execute a simple query
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
            
            # Test that all tables exist
            target_tables = [
                'County', 'Settlement', 'NationalIndividualElectoralDistrict',
                'SettlementIndividualElectoralDistrict', 'PostalCode',
                'PostalCode_Settlement', 'PollingStation', 'Address'
            ]
            
            for table in target_tables:
                result = conn.execute(f"""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_name = '{table}'
                """).fetchone()
                assert result[0] == 1, f"Table {table} should exist"
            
            logger.info("Database connection test passed")
            return True
            
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False