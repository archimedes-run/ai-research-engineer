#!/usr/bin/env bash
# Usage: wait-for-port.sh <port> <timeout_seconds> <name>
port=$1; timeout=$2; name=$3
echo "  Waiting for $name on :$port..."
for i in $(seq 1 "$timeout"); do
    nc -z 127.0.0.1 "$port" 2>/dev/null && echo "  ✓ $name ready" && exit 0
    sleep 1
done
echo "  ✗ $name did not start on port $port within ${timeout}s"
exit 1
