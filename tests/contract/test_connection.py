"""
Contract tests for the database connection module.

These tests verify that the database connection module implements the contract
defined in the project requirements.
"""

import pytest
import tempfile
import os

# Import the module under test
from src.database.connection import get_database_connection, apply_schema, close_connection, test_connection


class TestDatabaseConnection:
    """Test the database connection functionality."""
    
    def test_get_database_connection_in_memory(self):
        """Test that get_database_connection works with in-memory database."""
        conn = get_database_connection()
        assert conn is not None
        
        # Test that we can execute a query
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1
        
        close_connection(conn)
    
    def test_get_database_connection_file(self):
        """Test that get_database_connection works with file-based database."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, 'test.db')
            conn = get_database_connection(db_path)
            assert conn is not None
            
            # Test that we can execute a query
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
            
            close_connection(conn)
            
            # Verify the database file was created
            assert os.path.exists(db_path)
    
    def test_apply_schema(self):
        """Test that apply_schema creates all required tables."""
        conn = get_database_connection()
        
        # Verify all 8 target tables exist
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
        
        close_connection(conn)
    
    def test_test_connection(self):
        """Test that test_connection returns True for a valid connection."""
        result = test_connection()
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])