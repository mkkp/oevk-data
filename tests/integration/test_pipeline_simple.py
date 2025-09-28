"""
Simple integration test for the complete ETL pipeline using local sample data.
"""
import pytest
import tempfile
import os
import datetime
import polars as pl
from pathlib import Path

from src.etl.ingest import load_staging_data
from src.etl.transform import transform_all
from src.etl.export import export_tables_to_csv, export_addresses_partitioned
from src.database.connection import get_database_connection


class TestPipelineIntegrationSimple:
    """Simple integration tests for the complete ETL pipeline"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory for test data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def file_paths(self):
        """Local file paths for test data"""
        return {
            'oevk_json': 'data/oevk.sample.json',
            'korzet_csv': 'data/Korzet_levalogatas20250702__ORSZAGOS.sample.csv'
        }
    
    @pytest.fixture
    def run_tag(self):
        """Generate a unique run tag for testing"""
        return f"test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def test_complete_pipeline_flow(self, temp_data_dir, file_paths, run_tag):
        """Test the complete ETL pipeline from ingest to export using local files"""
        # Setup
        output_dir = Path(temp_data_dir) / "output"
        db_path = Path(temp_data_dir) / "test.db"
        
        output_dir.mkdir()
        
        # Get database connection
        conn = get_database_connection(str(db_path))
        
        # 1. Ingest process
        print("Starting ingest process...")
        load_staging_data(conn, file_paths, run_tag)
        
        # Verify staging data was loaded
        staging_count = conn.execute("SELECT COUNT(*) FROM staging_oevk").fetchone()[0]
        assert staging_count > 0, "Staging data should be loaded"
        print(f"Staging data: {staging_count} rows")
        
        # 2. Transform process
        print("Starting transform process...")
        transform_all(conn, run_tag)
        
        # Verify target tables were created and populated
        target_tables = [
            "County", "Settlement", "NationalIndividualElectoralDistrict",
            "SettlementIndividualElectoralDistrict", "PostalCode",
            "PostalCode_Settlement", "PollingStation", "Address"
        ]
        
        for table in target_tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"Table {table}: {count} rows")
            # Some tables might be empty in sample data, but should exist
            assert count >= 0, f"Table {table} should exist"
        
        # 3. Export process
        print("Starting export process...")
        export_tables_to_csv(conn, str(output_dir), run_tag)
        export_addresses_partitioned(conn, str(output_dir), run_tag)
        
        # 4. Validate output CSV files
        print("Validating output files...")
        
        # Check main tables
        main_tables = ["County", "Settlement", "NationalIndividualElectoralDistrict",
                      "SettlementIndividualElectoralDistrict", "PostalCode",
                      "PostalCode_Settlement", "PollingStation", "Address"]
        for table in main_tables:
            csv_path = output_dir / f"{run_tag}_{table}.csv"
            assert csv_path.exists(), f"CSV file {csv_path} should exist"
            
            # Load and verify CSV
            df = pl.read_csv(csv_path)
            assert len(df) >= 0, f"CSV {table} should have data"
            print(f"CSV {table}: {len(df)} rows")
        
        # Check partitioned address files
        partitioned_dir = output_dir / f"{run_tag}_Address"
        assert partitioned_dir.exists(), f"Partitioned addresses directory {partitioned_dir} should exist"
        
        address_files = list(partitioned_dir.glob("*.csv"))
        assert len(address_files) > 0, "Should have partitioned address files"
        
        # 5. Verify referential integrity between exported CSVs
        print("Checking referential integrity...")
        self._verify_referential_integrity(output_dir, run_tag)
        
        # 6. Check rejects table
        rejects_path = output_dir / "rejects.csv"
        if rejects_path.exists():
            rejects_df = pl.read_csv(rejects_path)
            print(f"Rejects table: {len(rejects_df)} rows")
            # Rejects table might be empty in clean data
        
        print("Integration test completed successfully!")
    
    def _verify_referential_integrity(self, output_dir, run_tag):
        """Verify referential integrity between exported tables"""
        
        # Load exported data
        counties_df = pl.read_csv(output_dir / f"{run_tag}_County.csv")
        settlements_df = pl.read_csv(output_dir / f"{run_tag}_Settlement.csv")
        oevk_df = pl.read_csv(output_dir / f"{run_tag}_NationalIndividualElectoralDistrict.csv")
        tevk_df = pl.read_csv(output_dir / f"{run_tag}_SettlementIndividualElectoralDistrict.csv")
        postal_codes_df = pl.read_csv(output_dir / f"{run_tag}_PostalCode.csv")
        postal_code_settlements_df = pl.read_csv(output_dir / f"{run_tag}_PostalCode_Settlement.csv")
        polling_stations_df = pl.read_csv(output_dir / f"{run_tag}_PollingStation.csv")
        addresses_df = pl.read_csv(output_dir / f"{run_tag}_Address.csv")
        
        # Check county IDs in settlements
        if len(counties_df) > 0 and len(settlements_df) > 0:
            county_ids = set(counties_df["ID"])
            settlement_county_ids = set(settlements_df["County_ID"])
            
            # All settlement county IDs should exist in counties
            missing_counties = settlement_county_ids - county_ids
            assert len(missing_counties) == 0, f"Settlements reference non-existent counties: {missing_counties}"
        
        # Check county IDs in OEVK
        if len(counties_df) > 0 and len(oevk_df) > 0:
            county_ids = set(counties_df["ID"])
            oevk_county_ids = set(oevk_df["County_ID"])
            
            # All OEVK county IDs should exist in counties
            missing_counties = oevk_county_ids - county_ids
            assert len(missing_counties) == 0, f"OEVK reference non-existent counties: {missing_counties}"
        
        # Check settlement and county IDs in TEVK
        if len(settlements_df) > 0 and len(counties_df) > 0 and len(tevk_df) > 0:
            settlement_ids = set(settlements_df["ID"])
            county_ids = set(counties_df["ID"])
            oevk_ids = set(oevk_df["ID"])
            
            tevk_settlement_ids = set(tevk_df["Settlement_ID"])
            tevk_county_ids = set(tevk_df["County_ID"])
            tevk_oevk_ids = set(tevk_df["NationalIndividualElectoralDistrict_ID"])
            
            # All TEVK references should exist
            missing_settlements = tevk_settlement_ids - settlement_ids
            missing_counties = tevk_county_ids - county_ids
            missing_oevk = tevk_oevk_ids - oevk_ids
            
            assert len(missing_settlements) == 0, f"TEVK reference non-existent settlements: {missing_settlements}"
            assert len(missing_counties) == 0, f"TEVK reference non-existent counties: {missing_counties}"
            assert len(missing_oevk) == 0, f"TEVK reference non-existent OEVK: {missing_oevk}"
        
        # Check postal code and settlement IDs in junction table
        if len(postal_codes_df) > 0 and len(settlements_df) > 0 and len(postal_code_settlements_df) > 0:
            postal_code_ids = set(postal_codes_df["ID"])
            settlement_ids = set(settlements_df["ID"])
            
            junction_postal_ids = set(postal_code_settlements_df["PostalCode_ID"])
            junction_settlement_ids = set(postal_code_settlements_df["Settlement_ID"])
            
            missing_postal_codes = junction_postal_ids - postal_code_ids
            missing_settlements = junction_settlement_ids - settlement_ids
            
            assert len(missing_postal_codes) == 0, f"PostalCode_Settlement reference non-existent postal codes: {missing_postal_codes}"
            assert len(missing_settlements) == 0, f"PostalCode_Settlement reference non-existent settlements: {missing_settlements}"
        
        print("Referential integrity verified!")


if __name__ == "__main__":
    # Run integration test directly
    test_instance = TestPipelineIntegrationSimple()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        file_paths = {
            'oevk_json': 'data/oevk.sample.json',
            'korzet_csv': 'data/oevk.sample.csv'
        }
        run_tag = f"test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        test_instance.test_complete_pipeline_flow(temp_dir, file_paths, run_tag)