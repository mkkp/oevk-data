#!/bin/bash
# Wait for pipeline completion and generate final comprehensive report

PID=$(ps aux | grep "python src/cli.py run" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "Pipeline already completed. Generating final report..."
    python perf_tracker.py
    exit 0
fi

echo "Waiting for pipeline (PID: $PID) to complete..."
echo "Started at: $(date)"
echo ""

# Wait for process to complete
while ps -p $PID > /dev/null 2>&1; do
    sleep 10
done

echo ""
echo "Pipeline completed at: $(date)"
echo ""
echo "Generating final comprehensive performance report..."
echo ""

python perf_tracker.py
