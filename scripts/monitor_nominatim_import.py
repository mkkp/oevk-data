#!/usr/bin/env python3
"""Monitor Nominatim import progress in real-time."""

import argparse
import re
import subprocess
import sys
import time


def monitor_nominatim_import(container_name="oevk-nominatim"):
    """Monitor Nominatim import progress from Docker logs."""

    print(f"Monitoring Nominatim import progress for container: {container_name}\n")

    # Check if container exists
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True,
        )
        if container_name not in result.stdout:
            print(f"❌ Container '{container_name}' not found")
            print("\nAvailable containers:")
            subprocess.run(["docker", "ps", "-a", "--format", "table {{.Names}}\t{{.Status}}"])
            sys.exit(1)
    except subprocess.CalledProcessError:
        print("❌ Docker is not running or accessible")
        sys.exit(1)

    process = subprocess.Popen(
        ["docker", "logs", "-f", container_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    stages = {
        "download": False,
        "import": False,
        "indexing": False,
        "ready": False,
    }

    last_progress_time = time.time()
    start_time = time.time()

    try:
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            current_time = time.time()
            elapsed = int(current_time - start_time)

            # Download progress
            if "Downloading" in line or "PBF_URL" in line or "downloading" in line.lower():
                if not stages["download"]:
                    print(f"📥 Stage 1/3: Downloading OSM data... ({elapsed}s)")
                    stages["download"] = True

            # Download completion
            if "download" in line.lower() and "complete" in line.lower():
                print(f"   ✓ Download complete ({elapsed}s)")

            # Import progress (osm2pgsql)
            if "osm2pgsql" in line.lower() or "importing" in line.lower():
                if not stages["import"]:
                    print(f"🔄 Stage 2/3: Importing to PostgreSQL... ({elapsed}s)")
                    print("   This typically takes 30-60 minutes for Hungary dataset")
                    stages["import"] = True

                # Parse osm2pgsql progress - nodes/ways/relations
                match = re.search(r"(\d+)k\s+.*\((\d+)k/s\)", line)
                if match:
                    processed = match.group(1)
                    rate = match.group(2)
                    if current_time - last_progress_time > 10:  # Update every 10 seconds
                        print(f"   Processing: {processed}k items ({rate}k/s) - {elapsed//60}m {elapsed%60}s")
                        last_progress_time = current_time

                # Progress percentage if available
                percent_match = re.search(r"(\d+)%", line)
                if percent_match:
                    percent = percent_match.group(1)
                    if current_time - last_progress_time > 10:
                        print(f"   Progress: {percent}% - {elapsed//60}m {elapsed%60}s")
                        last_progress_time = current_time

            # Import completion
            if "import" in line.lower() and ("done" in line.lower() or "complete" in line.lower()):
                print(f"   ✓ Import complete ({elapsed//60}m {elapsed%60}s)")

            # Indexing progress
            if "index" in line.lower() and not stages["indexing"]:
                print(f"📊 Stage 3/3: Creating indexes... ({elapsed//60}m)")
                print("   This typically takes 20-40 minutes")
                stages["indexing"] = True

            if stages["indexing"] and ("index" in line.lower() or "analyzing" in line.lower()):
                # Show index creation progress
                if "creating" in line.lower() or "building" in line.lower():
                    index_match = re.search(r"index\s+(\w+)", line, re.IGNORECASE)
                    if index_match:
                        index_name = index_match.group(1)
                        print(f"   Building index: {index_name} ({elapsed//60}m)")

            # Ready signals
            if any(
                marker in line.lower()
                for marker in ["server started", "ready to accept", "nominatim is ready", "listening on"]
            ):
                if not stages["ready"]:
                    stages["ready"] = True
                    total_time = elapsed // 60
                    print(f"\n✅ Nominatim is ready! (Total time: {total_time} minutes)")
                    print(f"   Service URL: http://localhost:8081")
                    break

            # Error detection
            if "error" in line.lower() or "failed" in line.lower():
                if "fatal" in line.lower() or "cannot" in line.lower():
                    print(f"\n❌ Error detected: {line}")

    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoring stopped by user")
        print("Note: Nominatim import continues in background")
        print(f"Resume monitoring with: docker logs -f {container_name}")
    finally:
        process.terminate()

    # Final status check
    if not stages["ready"]:
        print("\n⏳ Import still in progress")
        print(f"   Continue monitoring with: docker logs -f {container_name}")
        print(f"   Or run this script again: python scripts/monitor_nominatim_import.py")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor Nominatim Docker import progress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor default container
  python scripts/monitor_nominatim_import.py

  # Monitor custom container
  python scripts/monitor_nominatim_import.py --container my-nominatim

  # Check status without following logs
  docker logs oevk-nominatim | tail -50
        """,
    )
    parser.add_argument(
        "--container",
        default="oevk-nominatim",
        help="Docker container name (default: oevk-nominatim)",
    )

    args = parser.parse_args()
    monitor_nominatim_import(args.container)


if __name__ == "__main__":
    main()
