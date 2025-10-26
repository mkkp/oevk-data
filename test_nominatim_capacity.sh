#!/bin/bash
# Test Nominatim with different concurrency levels

echo "Testing Nominatim capacity..."
echo "================================"

for concurrent in 4 8 16 32; do
    echo ""
    echo "Testing with $concurrent concurrent requests:"
    
    # Run concurrent requests and measure time
    start=$(date +%s.%N)
    for i in $(seq 1 $concurrent); do
        curl -s "http://localhost:8081/search?q=Test+Street+$i,+Budapest,+Hungary&format=json&limit=1" > /dev/null &
    done
    wait
    end=$(date +%s.%N)
    
    duration=$(echo "$end - $start" | bc)
    throughput=$(echo "$concurrent / $duration" | bc -l)
    
    printf "  Duration: %.3f seconds\n" $duration
    printf "  Throughput: %.1f req/sec\n" $throughput
done
