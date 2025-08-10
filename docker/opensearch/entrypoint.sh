#!/bin/bash
set -e

echo "Starting OpenSearch with custom entrypoint..."

# Start OpenSearch in the background
/usr/share/opensearch/opensearch-docker-entrypoint.sh &
OPENSEARCH_PID=$!

# Function to check if OpenSearch is ready
wait_for_opensearch() {
    echo "Waiting for OpenSearch to be ready..."
    while ! curl -f -s http://localhost:9200/_cluster/health > /dev/null 2>&1; do
        sleep 5
        echo "Still waiting for OpenSearch..."
    done
    echo "OpenSearch is ready!"
}

# Wait for OpenSearch to be fully started
sleep 10
wait_for_opensearch

# Run snapshot restoration script
echo "Checking for GCS snapshots..."
/usr/local/bin/restore-snapshot.sh

# Keep the container running
wait $OPENSEARCH_PID
