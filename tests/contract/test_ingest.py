"""
Contract tests for the ingestion module.

These tests verify that the ingestion module implements the contract defined in
`specs/001-initial-oevk-transformation/contracts/ingest-contract.json`.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import os
import inspect

# Import the module under test
from src.etl.ingest import download_sources, load_staging_data


class TestDownloadSources:
    """Test the download_sources function."""
    
    def test_download_sources_exists(self):
        """Test that download_sources function exists and has correct signature."""
        assert callable(download_sources)
        sig = inspect.signature(download_sources)
        assert 'sources' in sig.parameters
        assert 'staging_dir' in sig.parameters
        # Check that return annotation is a Dict type
        assert 'Dict' in str(sig.return_annotation)
    
    def test_download_sources_returns_file_paths(self):
        """Test that download_sources returns dictionary with file paths."""
        # Mock the download to avoid actual HTTP requests
        with patch('src.etl.ingest.requests.get') as mock_get, \
             patch('src.etl.ingest.zipfile.ZipFile') as mock_zip, \
             patch('src.etl.ingest.os.listdir') as mock_listdir, \
             patch('src.etl.ingest.os.path.exists') as mock_exists:
            
            # Mock the HTTP response
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.iter_content.return_value = [b'test data']
            mock_get.return_value = mock_response
            
            # Mock the zip file extraction
            mock_zip_instance = Mock()
            mock_zip.return_value.__enter__.return_value = mock_zip_instance
            
            # Mock the file listing to return a CSV file
            mock_listdir.return_value = ['korzet_data.csv']
            
            # Mock file existence checks
            mock_exists.return_value = True
            
            sources = {
                'oevk_json': 'https://static.valasztas.hu/dyn/oevk_data/oevk.json',
                'korzet_zip': 'https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip'
            }
            
            with tempfile.TemporaryDirectory() as staging_dir:
                result = download_sources(sources, staging_dir)
                assert isinstance(result, dict)
                assert 'oevk_json' in result
                assert 'korzet_csv' in result
                # The files should be reported as existing due to our mock
                assert mock_exists.called


class TestLoadStagingData:
    """Test the load_staging_data function."""
    
    def test_load_staging_data_exists(self):
        """Test that load_staging_data function exists and has correct signature."""
        assert callable(load_staging_data)
        sig = inspect.signature(load_staging_data)
        assert 'db_connection' in sig.parameters
        assert 'file_paths' in sig.parameters
        assert 'run_tag' in sig.parameters
        assert sig.return_annotation is None
    
    def test_load_staging_data_populates_tables(self):
        """Test that load_staging_data creates staging tables."""
        import duckdb
        
        # Create a proper database file path
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, 'test.db')
            conn = duckdb.connect(db_path)
            file_paths = {
                'oevk_json': 'path/to/oevk.json',
                'korzet_csv': 'path/to/korzet.csv'
            }
            run_tag = 'test_run'
            
            # Mock the file existence checks to prevent actual file reading
            with patch('src.etl.ingest.os.path.exists') as mock_exists:
                mock_exists.return_value = False  # Files don't exist, so no data loading
                
                load_staging_data(conn, file_paths, run_tag)
            
            # Verify tables exist (they should be created by create_staging_tables)
            tables = conn.execute("SELECT table_name FROM duckdb_tables()").fetchall()
            table_names = [t[0] for t in tables]
            assert 'staging_oevk' in table_names
            assert 'staging_korzet' in table_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])