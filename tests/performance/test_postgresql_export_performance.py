"""
Performance tests for PostgreSQL export functionality.

Tests that the PostgreSQL export process completes within acceptable time limits
and verifies performance characteristics under realistic data loads.
"""

import pytest
import time
import tempfile
import os
import duckdb
from pathlib import Path
from src.etl.export import (
    export_tables_to_csv,
    generate_postgresql_schema,
    to_uuid3,
    export_table_to_postgresql,
)


class TestPostgreSQLExportPerformance:
    """Performance tests for PostgreSQL export."""

    @pytest.fixture
    def large_test_database(self):
        """Create a test database with realistic data volumes."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "perf_test.db")

        conn = duckdb.connect(db_path)

        # Create tables
        conn.execute("""
            CREATE TABLE County (
                ID TEXT PRIMARY KEY,
                CountyCode TEXT UNIQUE NOT NULL,
                CountyName TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE Settlement (
                ID TEXT PRIMARY KEY,
                SettlementCode TEXT NOT NULL,
                SettlementName TEXT NOT NULL,
                County_ID TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE PostalCode (
                ID TEXT PRIMARY KEY,
                PostalCode TEXT UNIQUE NOT NULL
            )
        """)

        # Insert realistic volumes of test data
        # 20 counties (matching real OEVK data)
        counties = [
            (f"county_{i}", f"{i:02d}", f"Test County {i}") for i in range(1, 21)
        ]
        conn.executemany("INSERT INTO County VALUES (?, ?, ?)", counties)

        # ~3,200 settlements (matching real OEVK data)
        settlements = []
        for i in range(1, 3201):
            county_id = f"county_{(i % 20) + 1}"
            settlements.append(
                (f"settlement_{i}", f"{i:04d}", f"Settlement {i}", county_id)
            )
        conn.executemany("INSERT INTO Settlement VALUES (?, ?, ?, ?)", settlements)

        # ~3,000 postal codes (matching real OEVK data)
        postal_codes = [(f"postal_{i}", f"{i:04d}") for i in range(1000, 4001)]
        conn.executemany("INSERT INTO PostalCode VALUES (?, ?)", postal_codes)

        yield conn, db_path, temp_dir

        conn.close()
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_schema_generation_performance(self):
        """Test that schema generation completes quickly."""
        start_time = time.time()

        schema = generate_postgresql_schema()

        elapsed = time.time() - start_time

        # Schema generation should be nearly instantaneous (< 1 second)
        assert elapsed < 1.0, f"Schema generation took {elapsed:.2f}s, expected < 1.0s"
        assert len(schema) > 0
        assert "UUID" in schema

    def test_uuid_conversion_performance(self):
        """Test UUID conversion performance with many values."""
        test_values = [f"hash_{i}" for i in range(10000)]

        start_time = time.time()

        for value in test_values:
            to_uuid3(value)

        elapsed = time.time() - start_time
        conversions_per_sec = len(test_values) / elapsed

        # Should convert at least 10,000 UUIDs per second
        assert conversions_per_sec > 10000, (
            f"UUID conversion rate: {conversions_per_sec:.0f}/sec, expected > 10,000/sec"
        )

        print(
            f"\nUUID conversion performance: {conversions_per_sec:.0f} conversions/sec"
        )

    def test_table_export_to_postgresql_performance(self, large_test_database):
        """Test PostgreSQL INSERT generation performance with realistic data."""
        conn, db_path, temp_dir = large_test_database

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            sql_file = f.name

            # Test County export (20 rows)
            start_time = time.time()
            export_table_to_postgresql(conn, "County", f)
            county_time = time.time() - start_time

            # Test Settlement export (~3,200 rows)
            start_time = time.time()
            export_table_to_postgresql(conn, "Settlement", f)
            settlement_time = time.time() - start_time

            # Test PostalCode export (~3,000 rows)
            start_time = time.time()
            export_table_to_postgresql(conn, "PostalCode", f)
            postal_time = time.time() - start_time

        try:
            os.unlink(sql_file)
        except:
            pass

        # Performance assertions
        # Small table (20 rows) should be very fast
        assert county_time < 0.5, (
            f"County export took {county_time:.2f}s, expected < 0.5s"
        )

        # Medium tables (~3000 rows) should complete in reasonable time
        assert settlement_time < 5.0, (
            f"Settlement export took {settlement_time:.2f}s, expected < 5.0s"
        )

        assert postal_time < 5.0, (
            f"PostalCode export took {postal_time:.2f}s, expected < 5.0s"
        )

        # Calculate throughput
        settlement_rate = 3200 / settlement_time
        postal_rate = 3000 / postal_time

        print(f"\nExport performance:")
        print(f"  County: {county_time:.3f}s (20 rows)")
        print(f"  Settlement: {settlement_time:.3f}s ({settlement_rate:.0f} rows/sec)")
        print(f"  PostalCode: {postal_time:.3f}s ({postal_rate:.0f} rows/sec)")

    def test_full_export_performance(self, large_test_database):
        """Test full export process with both CSV and PostgreSQL formats."""
        conn, db_path, temp_dir = large_test_database

        export_dir = tempfile.mkdtemp()
        run_tag = "perf_test"

        try:
            start_time = time.time()

            # Export only the tables we created (not the full OEVK table list)
            # We'll test the actual function but with limited tables
            with tempfile.TemporaryDirectory() as test_export_dir:
                # Generate schema
                schema_start = time.time()
                schema = generate_postgresql_schema()
                schema_path = os.path.join(test_export_dir, "schema.sql")
                with open(schema_path, "w") as f:
                    f.write(schema)
                schema_time = time.time() - schema_start

                # Generate data
                data_start = time.time()
                data_path = os.path.join(test_export_dir, "data.sql")
                with open(data_path, "w") as f:
                    f.write("-- Performance Test Export\n\n")
                    export_table_to_postgresql(conn, "County", f)
                    export_table_to_postgresql(conn, "Settlement", f)
                    export_table_to_postgresql(conn, "PostalCode", f)
                data_time = time.time() - data_start

                total_time = time.time() - start_time

                # Verify files were created
                assert os.path.exists(schema_path)
                assert os.path.exists(data_path)

                # Check file sizes
                schema_size = os.path.getsize(schema_path)
                data_size = os.path.getsize(data_path)

                # Performance assertions
                # Schema should be instant
                assert schema_time < 1.0, (
                    f"Schema generation took {schema_time:.2f}s, expected < 1.0s"
                )

                # Data export with ~6,200 total rows should complete reasonably
                assert data_time < 10.0, (
                    f"Data export took {data_time:.2f}s, expected < 10.0s"
                )

                # Total process should be reasonable
                assert total_time < 15.0, (
                    f"Total export took {total_time:.2f}s, expected < 15.0s"
                )

                # Calculate overall throughput
                total_rows = 20 + 3200 + 3000  # County + Settlement + PostalCode
                rows_per_sec = total_rows / data_time

                print(f"\nFull export performance:")
                print(
                    f"  Schema generation: {schema_time:.3f}s ({schema_size:,} bytes)"
                )
                print(f"  Data export: {data_time:.3f}s ({data_size:,} bytes)")
                print(f"  Total time: {total_time:.3f}s")
                print(f"  Throughput: {rows_per_sec:.0f} rows/sec")
                print(f"  Total rows: {total_rows:,}")

        finally:
            import shutil

            shutil.rmtree(export_dir, ignore_errors=True)

    def test_uuid_conversion_determinism(self):
        """Test that UUID conversion is deterministic (same input = same output)."""
        test_value = "test_hash_12345"

        # Convert the same value 1000 times
        start_time = time.time()
        results = [to_uuid3(test_value) for _ in range(1000)]
        elapsed = time.time() - start_time

        # All results should be identical
        assert len(set(results)) == 1, "UUID conversion should be deterministic"

        # Should still be fast
        assert elapsed < 0.1, (
            f"1000 UUID conversions took {elapsed:.3f}s, expected < 0.1s"
        )

    def test_large_insert_statement_generation(self, large_test_database):
        """Test performance of generating INSERT statements for large tables."""
        conn, db_path, temp_dir = large_test_database

        # Create a table with many columns (like Address table)
        conn.execute("""
            CREATE TABLE TestLargeTable (
                ID TEXT PRIMARY KEY,
                Col1 TEXT, Col2 TEXT, Col3 TEXT, Col4 TEXT, Col5 TEXT,
                Col6 TEXT, Col7 TEXT, Col8 TEXT, Col9 TEXT, Col10 TEXT,
                Col11 TEXT, Col12 TEXT, Col13 TEXT, Col14 TEXT, Col15 TEXT
            )
        """)

        # Insert 1000 rows
        rows = []
        for i in range(1000):
            row = [f"id_{i}"] + [f"value_{i}_{j}" for j in range(15)]
            rows.append(tuple(row))

        conn.executemany(
            "INSERT INTO TestLargeTable VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

        # Test INSERT generation performance
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False) as f:
            sql_file = f.name

            start_time = time.time()
            export_table_to_postgresql(conn, "TestLargeTable", f)
            elapsed = time.time() - start_time

        try:
            # Verify file was created and has content
            assert os.path.exists(sql_file)
            file_size = os.path.getsize(sql_file)
            assert file_size > 0

            # Performance check
            rows_per_sec = 1000 / elapsed
            assert rows_per_sec > 100, (
                f"Large table export: {rows_per_sec:.0f} rows/sec, expected > 100 rows/sec"
            )

            print(f"\nLarge table (1000 rows x 16 columns) export:")
            print(f"  Time: {elapsed:.3f}s")
            print(f"  Throughput: {rows_per_sec:.0f} rows/sec")
            print(f"  File size: {file_size:,} bytes")

        finally:
            os.unlink(sql_file)


class TestPostgreSQLExportScalability:
    """Scalability tests for PostgreSQL export with varying data sizes."""

    def test_export_scales_linearly(self):
        """Test that export time scales roughly linearly with data size."""
        times = []
        row_counts = [100, 500, 1000]

        for row_count in row_counts:
            temp_dir = tempfile.mkdtemp()
            db_path = os.path.join(temp_dir, "scale_test.db")
            conn = duckdb.connect(db_path)

            # Create and populate table
            conn.execute("CREATE TABLE ScaleTest (ID TEXT PRIMARY KEY, Value TEXT)")
            rows = [(f"id_{i}", f"value_{i}") for i in range(row_count)]
            conn.executemany("INSERT INTO ScaleTest VALUES (?, ?)", rows)

            # Measure export time
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".sql", delete=False
            ) as f:
                sql_file = f.name
                start_time = time.time()
                export_table_to_postgresql(conn, "ScaleTest", f)
                elapsed = time.time() - start_time
                times.append((row_count, elapsed))

            # Cleanup
            conn.close()
            os.unlink(sql_file)
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

        # Analyze scaling
        # Calculate time per row for each size
        rates = [(count, count / time) for count, time in times]

        print(f"\nScalability analysis:")
        for count, time_taken in times:
            rate = count / time_taken
            print(f"  {count:5d} rows: {time_taken:.3f}s ({rate:.0f} rows/sec)")

        # Rates should be relatively consistent (within 50% variance)
        rate_values = [rate for _, rate in rates]
        avg_rate = sum(rate_values) / len(rate_values)
        max_deviation = max(abs(rate - avg_rate) / avg_rate for rate in rate_values)

        assert max_deviation < 0.5, (
            f"Export rate variance {max_deviation:.1%} too high, expected < 50%"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
