
import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Add src directory to Python path
sys.path.insert(0, str(project_root / "src"))

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

import argparse
from src.cli import export_data, setup_logging

# Setup logging
setup_logging(log_level="INFO", log_format="simple")


args = argparse.Namespace(
    db_path="data/oevk.db",
    output_dir="exports",
    run_tag=None,
    skip_postgresql_export=False,
    export_original_addresses=False,
    max_workers=8,
    tables_only=False,
    addresses_only=False,
    use_copies=False,
    use_symlinks=False,
    verbose=False,
)

export_data(args)
