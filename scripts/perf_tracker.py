#!/usr/bin/env python3
"""Performance tracker for OEVK ETL pipeline - tracks step execution times and frequencies."""

import re
from collections import defaultdict
from pathlib import Path


def analyze_log():
    """Analyze log file and generate comprehensive performance report."""
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
    print(f"\n{'=' * 100}")
    print(f"OEVK ETL PIPELINE PERFORMANCE ANALYSIS")
    print(f"{'=' * 100}")
    print(f"Log file: {log_file.name}\n")

    with open(log_file, "r") as f:
        lines = f.readlines()

    # Data structures
    steps = {}
    transforms = []
    chunk_times = []
    current_step = None

    # Parse log lines
    for line in lines:
        line = line.strip()
        if not line.startswith("INFO:"):
            continue

        message = line[6:]  # Remove "INFO: " prefix

        # Step started: "Step ingest started"
        if match := re.search(r"Step (\w+) started", message):
            step_name = match.group(1)
            current_step = step_name
            if step_name not in steps:
                steps[step_name] = {
                    "name": step_name,
                    "duration": None,
                    "rows": 0,
                    "substeps": [],
                }

        # Step completed: "Step ingest completed in 17.20s - processed 3336202 rows"
        elif match := re.search(
            r"Step (\w+) completed in ([\d.]+)s - processed ([\d,]+) rows", message
        ):
            step_name = match.group(1)
            duration = float(match.group(2))
            rows = int(match.group(3).replace(",", ""))
            if step_name in steps:
                steps[step_name]["duration"] = duration
                steps[step_name]["rows"] = rows

        # Transform completed: "Transformed 8547 polling stations"
        elif match := re.search(r"Transformed ([\d,]+) (.+)", message):
            count = int(match.group(1).replace(",", ""))
            entity = match.group(2)
            transforms.append({"entity": entity, "count": count})
            if current_step and current_step in steps:
                steps[current_step]["substeps"].append(
                    {"type": "transform", "entity": entity, "count": count}
                )

        # Processing start: "Processing 3,336,202 addresses using Polars in 67 chunks of 50,000"
        elif match := re.search(
            r"Processing ([\d,]+) (.+?) using .+ in (\d+) chunks", message
        ):
            total = int(match.group(1).replace(",", ""))
            entity = match.group(2)
            num_chunks = int(match.group(3))
            if current_step and current_step in steps:
                steps[current_step]["substeps"].append(
                    {
                        "type": "processing",
                        "entity": entity,
                        "total": total,
                        "chunks": num_chunks,
                    }
                )

        # Chunk progress: "Polars Chunk 10/67: 500,000/3,336,202 (15.0%) - Chunk: 2.4s, Elapsed: 22.7s, ETA: 2.1m"
        elif match := re.search(
            r"Polars Chunk (\d+)/(\d+): ([\d,]+)/([\d,]+) \(([\d.]+)%\) - Chunk: ([\d.]+)s, Elapsed: ([\d.]+[ms]), ETA: ([\d.]+[ms])",
            message,
        ):
            chunk_num = int(match.group(1))
            total_chunks = int(match.group(2))
            chunk_time = float(match.group(6))
            chunk_times.append(
                {
                    "chunk": chunk_num,
                    "total_chunks": total_chunks,
                    "time": chunk_time,
                }
            )

        # Polars transformation complete: "Polars transformation complete: 3,336,202 addresses in 3.3m (16979 addr/sec)"
        elif match := re.search(
            r"Polars transformation complete: ([\d,]+) addresses in ([\d.]+)m \(([\d,]+) addr/sec\)",
            message,
        ):
            count = int(match.group(1).replace(",", ""))
            duration_min = float(match.group(2))
            throughput = int(match.group(3).replace(",", ""))
            if current_step and current_step in steps:
                steps[current_step]["substeps"].append(
                    {
                        "type": "polars_complete",
                        "count": count,
                        "duration": duration_min * 60,
                        "throughput": throughput,
                    }
                )

        # Deduplication completed (correct timing): "Deduplication complete in 3.0m: 3,336,202 addresses → 3,315,609 canonical (0.6% reduction)"
        elif match := re.search(
            r"Deduplication complete in ([\d.]+)m: ([\d,]+) addresses → ([\d,]+) canonical",
            message,
        ):
            duration_min = float(match.group(1))
            original = int(match.group(2).replace(",", ""))
            canonical = int(match.group(3).replace(",", ""))
            if current_step and current_step in steps:
                steps[current_step]["substeps"].append(
                    {
                        "type": "deduplication",
                        "duration": duration_min * 60,  # Convert to seconds
                        "canonical": canonical,
                        "original": original,
                        "reduction": ((original - canonical) / original * 100)
                        if original > 0
                        else 0,
                    }
                )

        # Filtered invalid addresses: "Filtered out 7,550 invalid addresses (house number is all zeros, e.g., '0000', '00000')"
        elif match := re.search(r"Filtered out ([\d,]+) invalid addresses", message):
            filtered = int(match.group(1).replace(",", ""))
            if current_step and current_step in steps:
                steps[current_step]["substeps"].append(
                    {
                        "type": "filtered",
                        "count": filtered,
                        "reason": "all-zero house numbers",
                    }
                )

    # Generate report
    print(f"{'=' * 100}")
    print("STEP PERFORMANCE SUMMARY")
    print(f"{'=' * 100}\n")

    print(f"{'Step':<20} {'Duration':<15} {'Rows Processed':<20} {'Throughput':<20}")
    print("-" * 75)

    total_duration = 0
    total_rows = 0

    for step_name, data in steps.items():
        duration = data["duration"]
        rows = data["rows"]

        if duration:
            total_duration += duration
            total_rows += rows
            throughput = rows / duration if duration > 0 else 0
            print(
                f"{step_name:<20} {duration:>12.2f}s   {rows:>15,}   {throughput:>15,.0f} rows/s"
            )
        else:
            print(f"{step_name:<20} {'In progress...':<15} {rows:>15,}")

    print("-" * 75)
    print(
        f"{'TOTAL':<20} {total_duration:>12.2f}s   {total_rows:>15,}   {total_rows / total_duration:>15,.0f} rows/s\n"
    )

    # Detailed substep analysis
    print(f"{'=' * 100}")
    print("DETAILED STEP ANALYSIS")
    print(f"{'=' * 100}\n")

    for step_name, data in steps.items():
        if data["substeps"]:
            print(f"Step: {step_name}")
            print("-" * 80)

            for substep in data["substeps"]:
                if substep["type"] == "polars_complete":
                    print(f"  • Polars transformation: {substep['count']:,} addresses")
                    print(
                        f"    Duration: {substep['duration']:.1f}s ({substep['duration'] / 60:.1f} min)"
                    )
                    print(f"    Throughput: {substep['throughput']:,} addr/sec")

                elif substep["type"] == "deduplication":
                    print(f"  • Address deduplication:")
                    print(
                        f"    Duration: {substep['duration']:.1f}s ({substep['duration'] / 60:.1f} min)"
                    )
                    print(f"    Original addresses: {substep['original']:,}")
                    print(f"    Canonical addresses: {substep['canonical']:,}")
                    print(
                        f"    Duplicates removed: {substep['original'] - substep['canonical']:,} ({substep['reduction']:.2f}%)"
                    )

                elif substep["type"] == "filtered":
                    print(
                        f"  • Filtered {substep['count']:,} invalid addresses ({substep['reason']})"
                    )

                elif substep["type"] == "processing":
                    print(
                        f"  • Processing {substep['total']:,} {substep['entity']} in {substep['chunks']} chunks"
                    )

            print()

    # Transform details
    if transforms:
        print(f"{'=' * 100}")
        print("TRANSFORM OPERATIONS")
        print(f"{'=' * 100}\n")

        print(f"{'Entity':<60} {'Count':<20}")
        print("-" * 80)

        for t in transforms:
            print(f"{t['entity']:<60} {t['count']:>15,}")

        print()

    # Chunk performance
    if chunk_times:
        print(f"{'=' * 100}")
        print("CHUNK PROCESSING PERFORMANCE")
        print(f"{'=' * 100}\n")

        times = [c["time"] for c in chunk_times]
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(
            f"Total chunks processed: {len(chunk_times)}/{chunk_times[-1]['total_chunks'] if chunk_times else 0}"
        )
        print(f"Average chunk time:     {avg_time:.2f}s")
        print(f"Min chunk time:         {min_time:.2f}s")
        print(f"Max chunk time:         {max_time:.2f}s")
        print(f"Time variance:          {max_time - min_time:.2f}s")

        # Show distribution
        print(f"\nChunk time distribution:")
        print(f"  {'Range':<20} {'Count':<10} {'Percentage'}")
        print("-" * 50)

        buckets = [0, 2.0, 2.5, 3.0, 3.5, 4.0, 100]
        for i in range(len(buckets) - 1):
            lower, upper = buckets[i], buckets[i + 1]
            count = sum(1 for t in times if lower <= t < upper)
            pct = (count / len(times)) * 100
            range_str = (
                f"{lower:.1f}s - {upper:.1f}s" if upper < 100 else f"{lower:.1f}s+"
            )
            bar = "█" * int(pct / 2)
            print(f"  {range_str:<20} {count:<10} {pct:5.1f}% {bar}")

        print()

    # Execution frequency analysis
    print(f"{'=' * 100}")
    print("STEP EXECUTION FREQUENCY")
    print(f"{'=' * 100}\n")

    print(f"Step execution: Each step runs once per pipeline execution")
    print(
        f"Transform operations within steps: {len(transforms)} total transform operations"
    )

    if chunk_times:
        print(
            f"Chunk processing: {len(chunk_times)} chunks processed out of {chunk_times[-1]['total_chunks']}"
        )
        completion_pct = (len(chunk_times) / chunk_times[-1]["total_chunks"]) * 100
        print(f"Progress: {completion_pct:.1f}% complete")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    try:
        analyze_log()
    except KeyboardInterrupt:
        print("\n\nAnalysis stopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
