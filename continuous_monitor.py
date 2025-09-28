#!/usr/bin/env python3
"""
Continuous monitoring of the transformation progress
"""
import time
import os
from datetime import datetime
import subprocess

def get_process_info():
    """Get process CPU and memory usage"""
    try:
        result = subprocess.run(
            ['ps', '-p', '89895', '-o', 'pid,pcpu,pmem,time,command'],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            return lines[1]  # Return the process info line
        return "Process not found"
    except Exception as e:
        return f"Error: {e}"

def get_database_size():
    """Get current database file size"""
    db_path = "data/test_performance.db"
    if os.path.exists(db_path):
        return os.path.getsize(db_path) / (1024 * 1024)  # Size in MB
    return 0

def monitor_continuously():
    """Monitor progress continuously"""
    print("Starting continuous monitoring...")
    print("Press Ctrl+C to stop\n")
    
    start_time = time.time()
    last_size = get_database_size()
    
    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Get current info
            process_info = get_process_info()
            current_size = get_database_size()
            size_change = current_size - last_size
            
            print(f"\n=== Monitoring Update ===")
            print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
            print(f"Elapsed: {elapsed/60:.1f} minutes")
            print(f"Process: {process_info}")
            print(f"Database Size: {current_size:.1f} MB")
            print(f"Size Change: {size_change:.1f} MB")
            
            last_size = current_size
            time.sleep(30)  # Check every 30 seconds
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

if __name__ == "__main__":
    monitor_continuously()