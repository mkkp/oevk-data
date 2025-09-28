"""
Contract tests for the database schema.

These tests verify that the database schema can be created and follows the contract
defined in `specs/001-initial-oevk-transformation/data-model.md`.
"""

import pytest
import tempfile
import duckdb
import os


class TestDatabaseSchema:
    """Test the database schema creation and structure."""
    
    def test_schema_file_exists(self):
        """Test that the schema file exists."""
        schema_path = "src/database/schema.sql"
        assert os.path.exists(schema_path), f"Schema file {schema_path} does not exist"
    
    def test_schema_can_be_executed(self):
        """Test that the schema SQL can be executed without errors."""
        schema_path = "src/database/schema.sql"
        
        # Read the schema file
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Execute the schema in a temporary database
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, 'test.db')
            conn = duckdb.connect(db_path)
            
            # Execute the schema
            conn.execute(schema_sql)
            
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
    
    def test_schema_has_correct_columns(self):
        """Test that the schema has the correct columns for each table."""
        schema_path = "src/database/schema.sql"
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, 'test.db')
            conn = duckdb.connect(db_path)
            conn.execute(schema_sql)
            
            # Test County table columns
            county_columns = conn.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'County' 
                ORDER BY column_name
            """).fetchall()
            
            expected_county_columns = ['CountyCode', 'CountyName', 'ID']
            actual_county_columns = [col[0] for col in county_columns]
            assert set(actual_county_columns) == set(expected_county_columns)
            
            # Test that ID is primary key
            pk_info = conn.execute("""
                SELECT constraint_type FROM information_schema.table_constraints 
                WHERE table_name = 'County' AND constraint_type = 'PRIMARY KEY'
            """).fetchone()
            assert pk_info is not None, "County table should have a primary key"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])