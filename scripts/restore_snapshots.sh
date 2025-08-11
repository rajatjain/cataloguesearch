#!/bin/bash

# Script to manage OpenSearch snapshots on VM instance
# Usage: ./restore_snapshots.sh <snapshots_folder_path>

set -e  # Exit on any error

# Check if snapshots folder path is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <snapshots_folder_path>"
    echo "Example: $0 /local/path/to/snapshots"
    exit 1
fi

SNAPSHOTS_PATH="$1"

# Validate that the snapshots folder exists
if [ ! -d "$SNAPSHOTS_PATH" ]; then
    echo "Error: Snapshots folder '$SNAPSHOTS_PATH' does not exist"
    exit 1
fi

echo "Starting OpenSearch snapshot management..."

# Step 1: Delete existing snapshots
echo "Step 1: Deleting existing snapshots..."

echo "Deleting cataloguesearch_prod snapshot..."
curl -X DELETE "localhost:9200/_snapshot/local_backup/cataloguesearch_prod" || echo "cataloguesearch_prod snapshot may not exist, continuing..."

echo "Deleting cataloguesearch_prod_metadata snapshot..."
curl -X DELETE "localhost:9200/_snapshot/local_backup/cataloguesearch_prod_metadata" || echo "cataloguesearch_prod_metadata snapshot may not exist, continuing..."

# Step 2: Copy snapshots folder to opensearch-node:/tmp
echo "Step 2: Copying snapshots folder to opensearch-node:/tmp..."
docker cp "$SNAPSHOTS_PATH/." opensearch-node:/tmp/snapshots/

# Step 3: Create/update snapshot repository
echo "Step 3: Creating snapshot repository..."
curl -X PUT "localhost:9200/_snapshot/local_backup" -H 'Content-Type: application/json' -d'{
  "type": "fs",
  "settings": {
    "location": "/tmp/snapshots"
  }
}' || echo "Repository may already exist, continuing..."

# Step 4: Delete existing indices (if they exist)
echo "Step 4: Deleting existing indices..."

echo "Deleting cataloguesearch_prod index..."
curl -X DELETE "localhost:9200/cataloguesearch_prod" || echo "cataloguesearch_prod index may not exist, continuing..."

echo "Deleting cataloguesearch_prod_metadata index..."
curl -X DELETE "localhost:9200/cataloguesearch_prod_metadata" || echo "cataloguesearch_prod_metadata index may not exist, continuing..."

# Step 5: Restore the snapshot
echo "Step 5: Restoring snapshots..."

echo "Restoring cataloguesearch_prod..."
curl -X POST "localhost:9200/_snapshot/local_backup/cataloguesearch_prod/_restore" -H 'Content-Type: application/json' -d'{
  "indices": "cataloguesearch_prod",
  "ignore_unavailable": true,
  "include_global_state": false
}'

echo "Restoring cataloguesearch_prod_metadata..."
curl -X POST "localhost:9200/_snapshot/local_backup/cataloguesearch_prod_metadata/_restore" -H 'Content-Type: application/json' -d'{
  "indices": "cataloguesearch_prod_metadata",
  "ignore_unavailable": true,
  "include_global_state": false
}'

# Step 6: Print curl commands to check restoration status
echo ""
echo "=========================================="
echo "Restoration initiated!"
echo "=========================================="
echo ""
echo "Use the following curl commands to check restoration status:"
echo ""
echo "1. Check overall restoration status:"
echo "curl -X GET \"localhost:9200/_cat/recovery?v\""
echo ""
echo "2. Check cataloguesearch_prod restoration status:"
echo "curl -X GET \"localhost:9200/_cat/recovery/cataloguesearch_prod?v\""
echo ""
echo "3. Check cataloguesearch_prod_metadata restoration status:"
echo "curl -X GET \"localhost:9200/_cat/recovery/cataloguesearch_prod_metadata?v\""
echo ""
echo "4. Check document count in cataloguesearch_prod:"
echo "curl -X GET \"localhost:9200/cataloguesearch_prod/_count\""
echo ""
echo "5. Check document count in cataloguesearch_prod_metadata:"
echo "curl -X GET \"localhost:9200/cataloguesearch_prod_metadata/_count\""
echo ""
echo "6. Check cluster health:"
echo "curl -X GET \"localhost:9200/_cluster/health?pretty\""
echo ""
echo "7. List all snapshots:"
echo "curl -X GET \"localhost:9200/_snapshot/local_backup/_all?pretty\""

echo ""
echo "Script completed successfully!"