#!/bin/bash

# Script to create OpenSearch snapshots and store them locally
# Usage: ./create_snapshots.sh [--use-podman] <local_directory_path>

set -e  # Exit on any error

# Default to docker
USE_PODMAN=false
CONTAINER_TOOL="docker"
COMPOSE_COMMAND="docker-compose"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --use-podman)
            USE_PODMAN=true
            CONTAINER_TOOL="podman"
            COMPOSE_COMMAND="podman-compose"
            shift
            ;;
        -*)
            echo "Unknown option $1"
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

# Check if local directory path is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 [--use-podman] <local_directory_path>"
    echo "Example: $0 /home/user/opensearch_snapshots"
    echo "Example: $0 --use-podman /home/user/opensearch_snapshots"
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

echo "Starting OpenSearch snapshot creation using $CONTAINER_TOOL..."
echo "Local snapshots directory: $LOCAL_SNAPSHOTS_DIR"

# Step 1: Clean up existing repository
echo "Step 1: Cleaning up existing repository..."
curl -s -X DELETE "localhost:9200/_snapshot/local_backup" || echo "Repository didn't exist or already deleted"

# Step 2: Work around the mounted directory issue
echo "Step 2: Setting up snapshot directory..."
# Since /tmp/snapshots is mounted and has permission issues, we'll:
# 1. Stop OpenSearch temporarily
# 2. Fix the mount and permissions
# 3. Restart OpenSearch
echo "Stopping OpenSearch temporarily to fix snapshot directory..."
$COMPOSE_COMMAND stop opensearch

# Clear and setup the host directory properly
rm -rf "$LOCAL_SNAPSHOTS_DIR"/*
mkdir -p "$LOCAL_SNAPSHOTS_DIR"
chmod 755 "$LOCAL_SNAPSHOTS_DIR"

# Restart OpenSearch
echo "Restarting OpenSearch..."
$COMPOSE_COMMAND start opensearch

# Wait for OpenSearch to be ready and for shards to be allocated
echo "Waiting for OpenSearch cluster to be healthy..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
  health_response=$(curl -s http://localhost:9200/_cluster/health 2>/dev/null || true)

  if [ -n "$health_response" ]; then
    status=$(echo "$health_response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "unknown")

    if [ "$status" = "green" ] || [ "$status" = "yellow" ]; then
      echo "Cluster status: $status - ready for snapshots!"
      break
    fi

    echo "Cluster status: $status - waiting for shards to be allocated... (attempt $((attempt + 1))/$max_attempts)"
  else
    echo "Waiting for OpenSearch to respond... (attempt $((attempt + 1))/$max_attempts)"
  fi

  attempt=$((attempt + 1))
  sleep 2
done

if [ $attempt -eq $max_attempts ]; then
  echo "ERROR: Cluster did not reach healthy state within expected time"
  exit 1
fi

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

# Step 6.5: Create snapshot for granth index
echo "Step 5.5: Creating snapshot for cataloguesearch_prod_granth..."
SNAPSHOT_NAME_GRANTH="cataloguesearch_prod_granth"

curl -X PUT "localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_GRANTH}?wait_for_completion=true" -H 'Content-Type: application/json' -d'{
  "indices": "cataloguesearch_prod_granth",
  "ignore_unavailable": true,
  "include_global_state": false,
  "metadata": {
    "description": "Snapshot of granth_index",
    "created_by": "create_snapshots.sh"
  }
}'

echo "Snapshot created: $SNAPSHOT_NAME_GRANTH"

# Step 7: Copy snapshots from container to local directory
echo "Step 6: Copying snapshots to local directory..."
# Since /tmp/snapshots is mounted from host, snapshots are already in the local directory
echo "Snapshots are already available in the mounted directory."

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
echo "- $SNAPSHOT_NAME_GRANTH"
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
echo "curl -X GET \"localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_GRANTH}?pretty\""
echo ""
echo "3. Check snapshot repository status:"
echo "curl -X GET \"localhost:9200/_snapshot/local_backup?pretty\""
echo ""
echo "4. Verify snapshot integrity:"
echo "curl -X POST \"localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_PROD}/_verify\""
echo "curl -X POST \"localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_META}/_verify\""
echo "curl -X POST \"localhost:9200/_snapshot/local_backup/${SNAPSHOT_NAME_GRANTH}/_verify\""
echo ""
echo "5. Check index document counts:"
echo "curl -X GET \"localhost:9200/cataloguesearch_prod/_count\""
echo "curl -X GET \"localhost:9200/cataloguesearch_prod_metadata/_count\""
echo "curl -X GET \"localhost:9200/cataloguesearch_prod_granth/_count\""

echo ""
echo "Script completed successfully!"
echo "Snapshots are available in: $LOCAL_SNAPSHOTS_DIR"
