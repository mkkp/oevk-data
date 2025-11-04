#!/usr/bin/env python3
"""Real-time performance tracker for ETL pipeline."""

import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_log_line(line: str) -> tuple:
    """Parse log line and extract timestamp and message."""
    # Pattern: INFO: Message (simple format, no timestamp in log line)
    pattern = r"(\w+): (.+)"
    match = re.match(pattern, line)
    if match:
        level, message = match.groups()
        # We'll use file modification time for timing
        return None, level, message
    return None, None, None


def extract_metrics(message: str) -> dict:
    """Extract performance metrics from message."""
    metrics = {}

    # Chunk processing: "Polars Chunk 10/67: 500,000/3,336,202 (15.0%) - Chunk: 2.4s, Elapsed: 22.7s, ETA: 2.1m"
    chunk_pattern = r"Polars Chunk (\d+)/(\d+): ([\d,]+)/([\d,]+) \(([\d.]+)%\) - Chunk: ([\d.]+)s, Elapsed: ([\d.]+[ms]), ETA: ([\d.]+[ms])"
    chunk_match = re.search(chunk_pattern, message)
    if chunk_match:
        metrics["type"] = "chunk_progress"
        metrics["chunk_num"] = int(chunk_match.group(1))
        metrics["total_chunks"] = int(chunk_match.group(2))
        metrics["processed"] = int(chunk_match.group(3).replace(",", ""))
        metrics["total"] = int(chunk_match.group(4).replace(",", ""))
        metrics["percent"] = float(chunk_match.group(5))
        metrics["chunk_time"] = float(chunk_match.group(6))
        metrics["elapsed"] = chunk_match.group(7)
        metrics["eta"] = chunk_match.group(8)
        return metrics

    # Transform completion: "Transformed 8547 polling stations"
    transform_pattern = r"Transformed ([\d,]+) (.+)"
    transform_match = re.search(transform_pattern, message)
    if transform_match:
        metrics["type"] = "transform_complete"
        metrics["count"] = int(transform_match.group(1).replace(",", ""))
        metrics["entity"] = transform_match.group(2)
        return metrics

    # Processing start: "Processing 3,336,202 addresses using Polars in 67 chunks"
    processing_pattern = r"Processing ([\d,]+) (.+?) using .+ in (\d+) chunks"
    processing_match = re.search(processing_pattern, message)
    if processing_match:
        metrics["type"] = "processing_start"
        metrics["total"] = int(processing_match.group(1).replace(",", ""))
        metrics["entity"] = processing_match.group(2)
        metrics["chunks"] = int(processing_match.group(3))
        return metrics

    # Step start: "Step transform started"
    step_start_pattern = r"Step (\w+) started"
    step_start_match = re.search(step_start_pattern, message)
    if step_start_match:
        metrics["type"] = "step_start"
        metrics["step"] = step_start_match.group(1)
        return metrics

    # Step complete: "Step ingest completed in 17.20s - processed 3336202 rows"
    step_complete_pattern = (
        r"Step (\w+) completed in ([\d.]+)s - processed ([\d,]+) rows"
    )
    step_complete_match = re.search(step_complete_pattern, message)
    if step_complete_match:
        metrics["type"] = "step_complete"
        metrics["step"] = step_complete_match.group(1)
        metrics["duration"] = float(step_complete_match.group(2))
        metrics["rows"] = int(step_complete_match.group(3).replace(",", ""))
        return metrics

    return metrics


def monitor_log_file():
    """Monitor log file and collect performance data."""
    log_dir = Path("logs")
    log_files = sorted(
        log_dir.glob("oevk_transform_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not log_files:
        print("No log files found")
        return

    log_file = log_files[0]
    print(f"Monitoring: {log_file.name}")
    print("=" * 100)

    steps = {}
    chunk_times = defaultdict(list)
    step_counts = defaultdict(int)
    current_step = None
    start_time = None

    # Read existing content
    with open(log_file, "r") as f:
        lines = f.readlines()

    print("\n Processing Performance Data...\n")

    for line in lines:
        timestamp, level, message = parse_log_line(line.strip())
        if not timestamp:
            continue

        if start_time is None:
            start_time = timestamp

        metrics = extract_metrics(message)
        if not metrics:
            continue

        if metrics["type"] == "step_start":
            current_step = metrics["step"]
            if current_step not in steps:
                steps[current_step] = {
                    "start_time": timestamp,
                    "end_time": None,
                    "count": 0,
                    "chunks": 0,
                }
                print(f"📊 Step: {current_step}")

        elif metrics["type"] == "processing_start":
            if current_step:
                steps[current_step]["total"] = metrics["total"]
                steps[current_step]["chunks"] = metrics["chunks"]
                print(
                    f"   Total: {metrics['total']:,} items in {metrics['chunks']} chunks"
                )

        elif metrics["type"] == "chunk_progress":
            if current_step:
                chunk_times[current_step].append(metrics["chunk_time"])
                steps[current_step]["count"] = metrics["processed"]
                steps[current_step]["percent"] = metrics["percent"]
                steps[current_step]["eta"] = metrics["eta"]

                # Print progress every 10 chunks
                if metrics["chunk_num"] % 10 == 0:
                    avg_chunk = sum(chunk_times[current_step]) / len(
                        chunk_times[current_step]
                    )
                    print(
                        f"   Chunk {metrics['chunk_num']}/{metrics['total_chunks']}: "
                        f"{metrics['processed']:,}/{metrics['total']:,} ({metrics['percent']:.1f}%) - "
                        f"Avg: {avg_chunk:.2f}s/chunk, ETA: {metrics['eta']}"
                    )

        elif metrics["type"] == "transform_complete":
            if current_step:
                steps[current_step]["end_time"] = timestamp
                steps[current_step]["count"] = metrics["count"]
                duration = (
                    timestamp - steps[current_step]["start_time"]
                ).total_seconds()
                print(
                    f"   ✓ Completed: {metrics['count']:,} items in {duration:.1f}s\n"
                )
                step_counts[current_step] = metrics["count"]

    # Generate report
    print("\n" + "=" * 100)
    print("PERFORMANCE SUMMARY")
    print("=" * 100)

    print(f"\n{'Step':<45} {'Count':<15} {'Duration':<15} {'Throughput':<20}")
    print("-" * 100)

    total_duration = 0
    total_items = 0

    for step, data in steps.items():
        if data["end_time"]:
            duration = (data["end_time"] - data["start_time"]).total_seconds()
            total_duration += duration
            total_items += data.get("count", 0)

            throughput = data.get("count", 0) / duration if duration > 0 else 0

            print(
                f"{step[:43]:<45} {data.get('count', 0):>12,}   "
                f"{duration:>12.1f}s   {throughput:>15,.0f} items/s"
            )
        else:
            status = "In progress..." if data.get("percent") else "Running..."
            if data.get("percent"):
                status = f"{data['percent']:.1f}%, ETA: {data.get('eta', 'N/A')}"
            print(f"{step[:43]:<45} {data.get('count', 0):>12,}   {status}")

    print("-" * 100)

    if start_time:
        now = datetime.now()
        total_elapsed = (now - start_time).total_seconds()
        print(f"\nTotal elapsed: {total_elapsed:.1f}s ({total_elapsed / 60:.1f} min)")
        print(f"Total items processed: {total_items:,}")
        if total_duration > 0:
            print(f"Overall throughput: {total_items / total_duration:,.0f} items/s")

    # Chunk performance analysis
    if chunk_times:
        print("\n" + "=" * 100)
        print("CHUNK PERFORMANCE ANALYSIS")
        print("=" * 100)

        for step, times in chunk_times.items():
            if times:
                avg = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                print(f"\n{step}:")
                print(f"  Chunks processed: {len(times)}")
                print(f"  Avg time: {avg:.2f}s")
                print(f"  Min time: {min_time:.2f}s")
                print(f"  Max time: {max_time:.2f}s")
                print(f"  Time range: {max_time - min_time:.2f}s")

    # Step frequency
    print("\n" + "=" * 100)
    print("STEP EXECUTION COUNT")
    print("=" * 100)

    print(f"\n{'Step':<45} {'Count':<15}")
    print("-" * 60)
    for step, count in sorted(step_counts.items(), key=lambda x: -x[1]):
        print(f"{step[:43]:<45} {count:>12,}")


if __name__ == "__main__":
    try:
        monitor_log_file()
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
