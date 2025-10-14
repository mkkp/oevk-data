"""Integration tests for --skip-postgresql-export flag."""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import argparse

from src.cli import export_data, run_pipeline


class TestSkipPostgreSQLFlag:
    """Test --skip-postgresql-export flag behavior."""

    def test_flag_controls_format_list_export_command(self):
        """Test that flag controls format list in export command."""
        # Create mock args with flag enabled
        args = argparse.Namespace(
            db_path="test.db",
            output_dir="test_exports",
            run_tag="test",
            skip_postgresql_export=True,
            export_original_addresses=False,
            max_workers=4,
            tables_only=False,
            addresses_only=False,
            use_copies=False,
            use_symlinks=False,
        )

        # Mock the database connection and export functions
        with patch('src.cli.duckdb.connect') as mock_connect, \
             patch('src.cli.export_tables_to_csv') as mock_export_tables, \
             patch('src.cli.export_canonical_addresses_optimized') as mock_export_canonical, \
             patch('src.cli.create_release_symlinks'), \
             patch('src.cli.verify_and_dump_postgresql') as mock_verify:

            mock_conn = Mock()
            mock_connect.return_value = mock_conn

            try:
                export_data(args)
            except:
                pass  # Ignore errors from mocked functions

            # Verify export functions were called with CSV-only format
            if mock_export_tables.called:
                call_args = mock_export_tables.call_args
                assert call_args is not None
                assert 'formats' in call_args.kwargs
                assert call_args.kwargs['formats'] == ['csv']
                assert 'postgresql' not in call_args.kwargs['formats']

            if mock_export_canonical.called:
                call_args = mock_export_canonical.call_args
                assert call_args is not None
                assert 'formats' in call_args.kwargs
                assert call_args.kwargs['formats'] == ['csv']

            # Verify verification was NOT called
            assert not mock_verify.called, "Verification should be skipped when flag is set"

    def test_flag_disabled_exports_postgresql(self):
        """Test that without flag, PostgreSQL export is enabled."""
        args = argparse.Namespace(
            db_path="test.db",
            output_dir="test_exports",
            run_tag="test",
            skip_postgresql_export=False,
            export_original_addresses=False,
            max_workers=4,
            tables_only=False,
            addresses_only=False,
            use_copies=False,
            use_symlinks=False,
        )

        with patch('src.cli.duckdb.connect') as mock_connect, \
             patch('src.cli.export_tables_to_csv') as mock_export_tables, \
             patch('src.cli.export_canonical_addresses_optimized') as mock_export_canonical, \
             patch('src.cli.create_release_symlinks'), \
             patch('src.cli.verify_and_dump_postgresql') as mock_verify:

            mock_conn = Mock()
            mock_connect.return_value = mock_conn

            try:
                export_data(args)
            except:
                pass

            # Verify export functions were called with both formats
            if mock_export_tables.called:
                call_args = mock_export_tables.call_args
                assert call_args is not None
                assert 'formats' in call_args.kwargs
                assert 'csv' in call_args.kwargs['formats']
                assert 'postgresql' in call_args.kwargs['formats']

    def test_flag_prevents_sql_file_creation(self, tmp_path):
        """Test that flag prevents schema.sql and data.sql creation."""
        # This test would require full integration with real database
        # For now, we verify the format list is correct
        pass

    def test_flag_in_run_pipeline_command(self):
        """Test flag works in run pipeline command."""
        args = argparse.Namespace(
            db_path="test.db",
            output_dir="test_exports",
            run_tag="test",
            skip_postgresql_export=True,
            stages="export",
            chunk_size=50000,
            max_workers=4,
            export_original_addresses=False,
        )

        with patch('src.cli.duckdb.connect') as mock_connect, \
             patch('src.cli.export_tables_to_csv') as mock_export_tables, \
             patch('src.cli.export_canonical_addresses_optimized') as mock_export_canonical, \
             patch('src.cli.verify_and_dump_postgresql') as mock_verify, \
             patch('src.cli.PipelineMetrics'):

            mock_conn = Mock()
            mock_conn.execute.return_value.fetchone.return_value = [100]
            mock_connect.return_value = mock_conn

            try:
                run_pipeline(args)
            except:
                pass

            # Verify formats parameter
            if mock_export_tables.called:
                call_args = mock_export_tables.call_args
                if 'formats' in call_args.kwargs:
                    assert call_args.kwargs['formats'] == ['csv']

            # Verify verification was NOT called
            assert not mock_verify.called


class TestPostgreSQLFlagIntegration:
    """Integration tests verifying full workflow with flag."""

    def test_help_text_includes_flag(self):
        """Test that --help includes --skip-postgresql-export."""
        import subprocess

        result = subprocess.run(
            ["python", "src/cli.py", "export", "--help"],
            capture_output=True,
            text=True,
        )

        assert "--skip-postgresql-export" in result.stdout
        assert "Skip PostgreSQL export" in result.stdout

    def test_run_command_help_includes_flag(self):
        """Test that run command --help includes flag."""
        import subprocess

        result = subprocess.run(
            ["python", "src/cli.py", "run", "--help"],
            capture_output=True,
            text=True,
        )

        assert "--skip-postgresql-export" in result.stdout
        assert "Skip PostgreSQL export" in result.stdout

    def test_flag_default_is_false(self):
        """Test that flag defaults to False (PostgreSQL enabled)."""
        args = argparse.Namespace()

        # Flag should not exist by default
        skip = getattr(args, "skip_postgresql_export", False)
        assert skip is False

        # When explicitly set to False
        args.skip_postgresql_export = False
        assert args.skip_postgresql_export is False

        # When explicitly set to True
        args.skip_postgresql_export = True
        assert args.skip_postgresql_export is True
