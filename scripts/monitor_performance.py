#!/usr/bin/env python3
"""Monitor CLI performance and generate comprehensive metrics."""

import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_log_line(line: str) -> dict | None:
    """Parse a log line and extract timestamp, level, and message."""
    # Pattern: 2025-10-29 01:39:01,234 - ETL - INFO - Message
    pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - .* - (\w+) - (.+)"
    match = re.match(pattern, line)
    if match:
        timestamp_str, level, message = match.groups()
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
        return {"timestamp": timestamp, "level": level, "message": message}
    return None


def extract_step_info(message: str) -> dict | None:
    """Extract step information from log message."""
    # Pattern for step start: "Starting step X/Y: Step Name"
    start_pattern = r"Starting step (\d+)/(\d+): (.+)"
    # Pattern for step completion: "Completed step X/Y: Step Name (duration)"
    complete_pattern = r"Completed step (\d+)/(\d+): (.+?) \((.+?)\)"
    # Pattern for progress updates
    progress_pattern = r"(\d+(?:,\d+)*) (?:rows?|records?|addresses?|items?)"

    start_match = re.search(start_pattern, message)
    if start_match:
        step_num, total_steps, step_name = start_match.groups()
        return {
            "type": "step_start",
            "step": int(step_num),
            "total": int(total_steps),
            "name": step_name.strip(),
        }

    complete_match = re.search(complete_pattern, message)
    if complete_match:
        step_num, total_steps, step_name, duration = complete_match.groups()
        return {
            "type": "step_complete",
            "step": int(step_num),
            "total": int(total_steps),
            "name": step_name.strip(),
            "duration": duration,
        }

    progress_match = re.search(progress_pattern, message)
    if progress_match:
        count = progress_match.group(1).replace(",", "")
        return {"type": "progress", "count": int(count), "message": message}

    return None


def monitor_process(pid: int):
    """Monitor process and collect performance metrics."""
    log_file = Path("logs/oevk_data.log")

    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return

    print(f"Monitoring process PID {pid}")
    print(f"Log file: {log_file}")
    print("=" * 80)

    steps = {}
    step_counts = defaultdict(list)
    current_step = None
    start_time = None

    # Read existing log lines
    with open(log_file, "r") as f:
        lines = f.readlines()

    # Find the start of current run
    run_start_idx = 0
    for i in range(len(lines) - 1, -1, -1):
        if "Starting ETL pipeline" in lines[i] or "run --run-tag" in lines[i]:
            run_start_idx = i
            break

    # Process existing lines
    for line in lines[run_start_idx:]:
        parsed = parse_log_line(line.strip())
        if not parsed:
            continue

        if start_time is None:
            start_time = parsed["timestamp"]

        step_info = extract_step_info(parsed["message"])
        if not step_info:
            continue

        if step_info["type"] == "step_start":
            step_key = (step_info["step"], step_info["name"])
            current_step = step_key
            if step_key not in steps:
                steps[step_key] = {
                    "step_num": step_info["step"],
                    "name": step_info["name"],
                    "start_time": parsed["timestamp"],
                    "end_time": None,
                    "duration": None,
                    "count": 0,
                }
                print(
                    f"\n[{parsed['timestamp'].strftime('%H:%M:%S')}] Step {step_info['step']}: {step_info['name']}"
                )

        elif step_info["type"] == "step_complete":
            step_key = (step_info["step"], step_info["name"])
            if step_key in steps:
                steps[step_key]["end_time"] = parsed["timestamp"]
                steps[step_key]["duration"] = step_info["duration"]
                elapsed = (
                    parsed["timestamp"] - steps[step_key]["start_time"]
                ).total_seconds()
                print(f"  ✓ Completed in {step_info['duration']} ({elapsed:.1f}s)")

        elif step_info["type"] == "progress" and current_step:
            step_counts[current_step].append(step_info["count"])
            steps[current_step]["count"] = step_info["count"]

    # Check if process is still running
    try:
        subprocess.run(["ps", "-p", str(pid)], check=True, capture_output=True)
        process_running = True
    except subprocess.CalledProcessError:
        process_running = False

    if not process_running:
        print("\n" + "=" * 80)
        print("Process has completed. Generating performance report...")
        generate_report(steps, step_counts, start_time)
    else:
        print("\n" + "=" * 80)
        print("Process is still running. Current progress:")
        generate_report(steps, step_counts, start_time)
        print("\nRun this script again to see final results.")


def generate_report(steps, step_counts, start_time):
    """Generate comprehensive performance report."""
    print("\n" + "=" * 80)
    print("PERFORMANCE REPORT")
    print("=" * 80)

    if not steps:
        print("No step data collected yet.")
        return

    # Sort steps by step number
    sorted_steps = sorted(steps.values(), key=lambda x: x["step_num"])

    print(f"\n{'Step':<5} {'Name':<40} {'Duration':<15} {'Count':<15}")
    print("-" * 80)

    total_duration = 0
    for step in sorted_steps:
        step_num = step["step_num"]
        name = step["name"][:38]
        duration = step["duration"] or "In progress..."
        count = f"{step['count']:,}" if step["count"] > 0 else "-"

        print(f"{step_num:<5} {name:<40} {duration:<15} {count:<15}")

        # Track total duration
        if step["end_time"] and step["start_time"]:
            elapsed = (step["end_time"] - step["start_time"]).total_seconds()
            total_duration += elapsed

    print("-" * 80)

    if start_time:
        now = datetime.now()
        total_elapsed = (now - start_time).total_seconds()
        print(
            f"\nTotal elapsed time: {total_elapsed:.1f}s ({total_elapsed / 60:.1f} minutes)"
        )
        print(
            f"Total step time: {total_duration:.1f}s ({total_duration / 60:.1f} minutes)"
        )

    # Step frequency analysis
    print("\n" + "=" * 80)
    print("STEP EXECUTION FREQUENCY")
    print("=" * 80)

    step_freq = defaultdict(int)
    for step_num, name in steps.keys():
        step_freq[name] += 1

    print(f"\n{'Step Name':<40} {'Count':<10}")
    print("-" * 50)
    for name, count in sorted(step_freq.items(), key=lambda x: -x[1]):
        print(f"{name[:38]:<40} {count:<10}")

    # Row/item processing counts
    if step_counts:
        print("\n" + "=" * 80)
        print("DATA PROCESSING COUNTS")
        print("=" * 80)

        for (step_num, name), counts in sorted(step_counts.items()):
            if counts:
                max_count = max(counts)
                print(f"\nStep {step_num}: {name}")
                print(f"  Max items processed: {max_count:,}")


if __name__ == "__main__":
    # Find running Python process
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True,
        )

        pid = None
        for line in result.stdout.split("\n"):
            if "python src/cli.py run" in line and "grep" not in line:
                parts = line.split()
                pid = int(parts[1])
                break

        if pid:
            monitor_process(pid)
        else:
            print("No running CLI process found.")
            print("Checking most recent log file...")
            monitor_process(0)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
