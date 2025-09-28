#!/usr/bin/env python3
"""
Monitor the progress of the ongoing address transformation
"""
import sqlite3
import time
import os
from datetime import datetime

def monitor_progress():
    db_path = "data/test_performance.db"
    
    if not os.path.exists(db_path):
        print("Database file not found")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current address count
        cursor.execute("SELECT COUNT(*) FROM Address")
        current_count = cursor.fetchone()[0]
        
        # Get total expected count
        cursor.execute("SELECT COUNT(*) FROM Korzet")
        total_count = cursor.fetchone()[0]
        
        # Get database file size
        file_size = os.path.getsize(db_path)
        
        # Calculate progress
        progress_pct = (current_count / total_count) * 100 if total_count > 0 else 0
        
        print(f"=== Address Transformation Progress ===")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"Current Address Count: {current_count:,}")
        print(f"Total Expected: {total_count:,}")
        print(f"Progress: {progress_pct:.1f}%")
        print(f"Database Size: {file_size / (1024*1024):.1f} MB")
        
        conn.close()
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print("Database is locked - transformation in progress")
            print("Unable to get current count due to active processing")
        else:
            print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    monitor_progress()