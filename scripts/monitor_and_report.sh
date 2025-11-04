#!/bin/bash
# Monitor ETL pipeline and generate final performance report

echo "Monitoring OEVK ETL Pipeline..."
echo "Press Ctrl+C to stop monitoring"
echo ""

PID=$(ps aux | grep "python src/cli.py run" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "No running pipeline found. Generating report from last run..."
    python perf_tracker.py
    exit 0
fi

echo "Found process PID: $PID"
echo ""

# Monitor every 30 seconds
while ps -p $PID > /dev/null 2>&1; do
    clear
    echo "Pipeline is running (PID: $PID)..."
    echo ""
    python perf_tracker.py
    echo ""
    echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
    sleep 30
done

echo ""
echo "Pipeline completed! Generating final report..."
echo ""
python perf_tracker.py
