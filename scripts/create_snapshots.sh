#!/bin/bash

# Script to create OpenSearch snapshots and store them locally
# Usage: ./create_snapshots.sh <local_directory_path>

set -e  # Exit on any error

# Check if local directory path is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <local_directory_path>"
    echo "Example: $0 /home/user/opensearch_snapshots"
    exit 1
fi

LOCAL_SNAPSHOTS_DIR="$1"

# Create local directory if it doesn't exist
mkdir -p "$LOCAL_SNAPSHOTS_DIR"

# Validate that the local directory is writable
if [ ! -w "$LOCAL_SNAPSHOTS_DIR" ]; then
    echo "Error: Local directory '$LOCAL_SNAPSHOTS_DIR' is not writable"
    exit 1
fi

echo "Starting OpenSearch snapshot creation..."
echo "Local snapshots directory: $LOCAL_SNAPSHOTS_DIR"

# Step 1: Clean up existing repository and directory
echo "Step 1: Cleaning up existing repository..."
curl -s -X DELETE "localhost:9200/_snapshot/local_backup" || echo "Repository didn't exist or already deleted"

echo "Step 2: Preparing container snapshot directory..."
docker exec opensearch-node rm -rf /tmp/snapshots 2>/dev/null || echo "Directory cleanup skipped (permission issue)"
docker exec opensearch-node mkdir -p /tmp/snapshots

# Step 3: Register snapshot repository
echo "Step 3: Registering snapshot repository..."
REPO_RESPONSE=$(curl -s -X PUT "localhost:9200/_snapshot/local_backup" -H 'Content-Type: application/json' -d'{
  "type": "fs",
  "settings": {
    "location": "/tmp/snapshots"
  }
}' || echo '{"error": "repository_exception"}')

if echo "$REPO_RESPONSE" | grep -q "repository_exception"; then
    echo "Repository may already exist or there was an error. Checking existing repository..."
    curl -s -X GET "localhost:9200/_snapshot/local_backup" || echo "Continuing with existing repository..."
else
    echo "Repository registered successfully."
fi

# Step 4: Create timestamp for unique snapshot names
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Step 5: Create snapshot for cataloguesearch_prod
echo "Step 4: Creating snapshot for cataloguesearch_prod..."
SNAPSHOT_NAME_PROD="cataloguesearch_prod"

curl -X PUT "localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_PROD}?wait_for_completion=true" -H 'Content-Type: application/json' -d'{
  "indices": "cataloguesearch_prod",
  "ignore_unavailable": true,
  "include_global_state": false,
  "metadata": {
    "description": "Snapshot of cataloguesearch_prod index",
    "created_by": "create_snapshots.sh"
  }
}'

echo "Snapshot created: $SNAPSHOT_NAME_PROD"

# Step 6: Create snapshot for metadata_index
echo "Step 5: Creating snapshot for cataloguesearch_prod_metadata..."
SNAPSHOT_NAME_META="cataloguesearch_prod_metadata"

curl -X PUT "localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_META}?wait_for_completion=true" -H 'Content-Type: application/json' -d'{
  "indices": "cataloguesearch_prod_metadata",
  "ignore_unavailable": true,
  "include_global_state": false,
  "metadata": {
    "description": "Snapshot of metadata_index",
    "created_by": "create_snapshots.sh"
  }
}'

echo "Snapshot created: $SNAPSHOT_NAME_META"

# Step 7: Copy snapshots from container to local directory
echo "Step 6: Copying snapshots to local directory..."
docker cp opensearch-node:/tmp/snapshots/. "$LOCAL_SNAPSHOTS_DIR/"

echo "Snapshots copied to: $LOCAL_SNAPSHOTS_DIR"

# Step 8: List created snapshots
echo "Step 7: Listing created snapshots..."
echo ""
echo "=========================================="
echo "Snapshots created successfully!"
echo "=========================================="
echo ""
echo "Created snapshots:"
echo "- $SNAPSHOT_NAME_PROD"
echo "- $SNAPSHOT_NAME_META"
echo ""
echo "Local storage location: $LOCAL_SNAPSHOTS_DIR"
echo ""

# Step 8: Print useful commands for verification
echo "Use the following curl commands to verify snapshots:"
echo ""
echo "1. List all snapshots in repository:"
echo "curl -X GET \"localhost:9200/_snapshot/local_backup/_all?pretty\""
echo ""
echo "2. Get specific snapshot info:"
echo "curl -X GET \"localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_PROD}?pretty\""
echo "curl -X GET \"localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_META}?pretty\""
echo ""
echo "3. Check snapshot repository status:"
echo "curl -X GET \"localhost:9200/_snapshot/local_backup?pretty\""
echo ""
echo "4. Verify snapshot integrity:"
echo "curl -X POST \"localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_PROD}/_verify\""
echo "curl -X POST \"localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_META}/_verify\""
echo ""
echo "5. Check index document counts:"
echo "curl -X GET \"localhost:9200/cataloguesearch_prod/_count\""
echo "curl -X GET \"localhost:9200/cataloguesearch_prod_metadata/_count\""

echo ""
echo "Script completed successfully!"
echo "Snapshots are available in: $LOCAL_SNAPSHOTS_DIR"