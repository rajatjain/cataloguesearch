#!/bin/bash

# Script to restore OpenSearch snapshots using bind-mounted directory
# Usage: ./restore_snapshots.sh (run from cataloguesearch project root)

set -e  # Exit on any error

SNAPSHOTS_DIR="./snapshots"

# Check that we're in the right directory and snapshots folder exists
if [ ! -d "$SNAPSHOTS_DIR" ]; then
    echo "Error: './snapshots' directory not found"
    echo "Make sure you're running this script from the cataloguesearch project root"
    echo "and that the snapshots directory exists with your snapshot files"
    exit 1
fi

# Check if snapshots folder is readable
echo "Checking snapshots folder accessibility..."
if [ ! -r "$SNAPSHOTS_DIR" ]; then
    echo "Error: Cannot read snapshots folder '$SNAPSHOTS_DIR'"
    echo "Make sure the folder is readable"
    exit 1
fi
echo "Snapshots folder is accessible"

# Check for required snapshot files
REQUIRED_FILES=("index-1" "index.latest" "indices")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -e "$SNAPSHOTS_DIR/$file" ]; then
        echo "Error: Required snapshot file '$file' not found in '$SNAPSHOTS_DIR'"
        exit 1
    fi
done

# Check if any .dat files exist
if ! ls "$SNAPSHOTS_DIR"/*.dat 1> /dev/null 2>&1; then
    echo "Error: No snapshot .dat files found in '$SNAPSHOTS_DIR'"
    echo "This doesn't appear to be a valid OpenSearch snapshot directory"
    exit 1
fi

echo "✅ Valid snapshots directory found with required files"

echo "Starting OpenSearch snapshot management..."

# Function to wait for user confirmation
wait_for_confirmation() {
    local step_name="$1"
    echo ""
    echo "=========================================="
    echo "Executing step: $step_name"
    echo "Should I continue? (y/N)"
    echo "=========================================="
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Aborted by user."
        exit 0
    fi
}

# Function to check command success
check_status() {
    local step_name="$1"
    local exit_code=$2
    if [ $exit_code -eq 0 ]; then
        echo "✅ SUCCESS: $step_name completed successfully"
        echo "Press any key to continue..."
        read -r
    else
        echo "❌ FAILED: $step_name failed with exit code $exit_code"
        echo "Do you want to continue anyway? (y/N)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "Aborted due to failure."
            exit 1
        fi
    fi
}

# Step 1: Restart OpenSearch container to ensure bind mount is refreshed
wait_for_confirmation "Step 1: Restarting OpenSearch container"
echo "Restarting opensearch-node container to refresh bind mount..."
docker restart opensearch-node
echo "Waiting for OpenSearch to be ready..."
sleep 10
# Wait for OpenSearch to be accessible
until curl -s "localhost:9200/_cluster/health" > /dev/null; do
    echo "Waiting for OpenSearch to start..."
    sleep 5
done
echo "OpenSearch is ready"
check_status "Step 1: Restarting OpenSearch container" 0

# Step 2: Fix permissions in the bind-mounted directory
wait_for_confirmation "Step 2: Fixing permissions in container"
echo "Setting ownership and permissions on bind-mounted snapshots..."
echo "Current directory contents:"
docker exec opensearch-node ls -la /tmp/snapshots/
docker exec -u root opensearch-node chown -R opensearch:opensearch /tmp/snapshots/
CHOWN_EXIT=$?
docker exec -u root opensearch-node chmod -R 775 /tmp/snapshots/
CHMOD_EXIT=$?
echo "After permission fix:"
docker exec opensearch-node ls -la /tmp/snapshots/
check_status "Step 2: Fixing permissions in container" $((CHOWN_EXIT + CHMOD_EXIT))

# Step 3: Delete existing repository if it exists
wait_for_confirmation "Step 3: Removing existing repository (if any)"
echo "Deleting any existing repository..."
curl -s -X DELETE "localhost:9200/_snapshot/local_backup" > /dev/null 2>&1 || echo "No existing repository to delete"
check_status "Step 3: Removing existing repository" 0

# Step 4: Create new repository
wait_for_confirmation "Step 4: Creating new snapshot repository"
echo "Creating repository pointing to /tmp/snapshots..."
REPO_RESPONSE=$(curl -s -X PUT "localhost:9200/_snapshot/local_backup" -H 'Content-Type: application/json' -d'{
  "type": "fs",
  "settings": {
    "location": "/tmp/snapshots"
  }
}')

if echo "$REPO_RESPONSE" | grep -q '"acknowledged":true'; then
    echo "Repository created successfully"
    check_status "Step 4: Creating new snapshot repository" 0
else
    echo "Error creating repository: $REPO_RESPONSE"
    check_status "Step 4: Creating new snapshot repository" 1
fi

# Step 5: Verify snapshots are visible before restoring
wait_for_confirmation "Step 5: Verifying snapshots are accessible"
echo "Checking if snapshots are visible in repository..."
SNAPSHOTS_LIST=$(curl -s "localhost:9200/_snapshot/local_backup/_all")

if echo "$SNAPSHOTS_LIST" | grep -q '"snapshots" : \[ \]'; then
    echo "Error: No snapshots found in repository. Check if files copied correctly."
    check_status "Step 5: Verifying snapshots are accessible" 1
elif ! echo "$SNAPSHOTS_LIST" | grep -q '"cataloguesearch_prod"'; then
    echo "Error: cataloguesearch_prod snapshot not found in repository"
    check_status "Step 5: Verifying snapshots are accessible" 1
elif ! echo "$SNAPSHOTS_LIST" | grep -q '"cataloguesearch_prod_metadata"'; then
    echo "Error: cataloguesearch_prod_metadata snapshot not found in repository"
    check_status "Step 5: Verifying snapshots are accessible" 1
else
    echo "Both required snapshots found in repository"
    check_status "Step 5: Verifying snapshots are accessible" 0
fi

# Step 6: Delete existing indices (if they exist)
wait_for_confirmation "Step 6: Deleting existing indices"
echo "Deleting any existing indices..."
curl -s -X DELETE "localhost:9200/cataloguesearch_prod" > /dev/null || echo "cataloguesearch_prod index may not exist, continuing..."
curl -s -X DELETE "localhost:9200/cataloguesearch_prod_metadata" > /dev/null || echo "cataloguesearch_prod_metadata index may not exist, continuing..."
check_status "Step 6: Deleting existing indices" 0

# Step 7: Restore the snapshots with error checking
wait_for_confirmation "Step 7: Restoring snapshots"
echo "Initiating restoration of both indices..."

echo "Restoring cataloguesearch_prod..."
RESTORE_RESPONSE=$(curl -s -X POST "localhost:9200/_snapshot/local_backup/cataloguesearch_prod/_restore" -H 'Content-Type: application/json' -d'{
  "indices": "cataloguesearch_prod",
  "ignore_unavailable": true,
  "include_global_state": false
}')

if echo "$RESTORE_RESPONSE" | grep -q '"accepted":true'; then
    echo "cataloguesearch_prod restore initiated successfully"
    RESTORE1_SUCCESS=0
elif echo "$RESTORE_RESPONSE" | grep -q "error"; then
    echo "Error restoring cataloguesearch_prod: $RESTORE_RESPONSE"
    RESTORE1_SUCCESS=1
else
    echo "Unexpected response from cataloguesearch_prod restore: $RESTORE_RESPONSE"
    RESTORE1_SUCCESS=1
fi

echo "Restoring cataloguesearch_prod_metadata..."
RESTORE_RESPONSE=$(curl -s -X POST "localhost:9200/_snapshot/local_backup/cataloguesearch_prod_metadata/_restore" -H 'Content-Type: application/json' -d'{
  "indices": "cataloguesearch_prod_metadata",
  "ignore_unavailable": true,
  "include_global_state": false
}')

if echo "$RESTORE_RESPONSE" | grep -q '"accepted":true'; then
    echo "cataloguesearch_prod_metadata restore initiated successfully"
    RESTORE2_SUCCESS=0
elif echo "$RESTORE_RESPONSE" | grep -q "error"; then
    echo "Error restoring cataloguesearch_prod_metadata: $RESTORE_RESPONSE"
    RESTORE2_SUCCESS=1
else
    echo "Unexpected response from cataloguesearch_prod_metadata restore: $RESTORE_RESPONSE"
    RESTORE2_SUCCESS=1
fi

check_status "Step 7: Restoring snapshots" $((RESTORE1_SUCCESS + RESTORE2_SUCCESS))

# Print curl commands to check restoration status
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
