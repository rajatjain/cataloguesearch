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

# Check permissions on snapshots folder
echo "Checking permissions on snapshots folder..."
if [ ! -r "$SNAPSHOTS_PATH" ]; then
    echo "Error: Cannot read snapshots folder '$SNAPSHOTS_PATH'"
    echo "Fix permissions with: sudo chown -R 1000:1000 '$SNAPSHOTS_PATH'"
    exit 1
fi

# Check if snapshots directory is owned by user 1000 (opensearch container user)
OWNER_UID=$(stat -c '%u' "$SNAPSHOTS_PATH" 2>/dev/null || stat -f '%u' "$SNAPSHOTS_PATH" 2>/dev/null)
if [ "$OWNER_UID" != "1000" ]; then
    echo "Error: Snapshots folder '$SNAPSHOTS_PATH' is not owned by user 1000 (current owner: $OWNER_UID)"
    echo "Fix permissions with: sudo chown -R 1000:1000 '$SNAPSHOTS_PATH'"
    exit 1
fi
echo "Permissions check passed - snapshots directory is owned by user 1000"

# Check for required snapshot files
REQUIRED_FILES=("index-1" "index.latest" "indices")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -e "$SNAPSHOTS_PATH/$file" ]; then
        echo "Error: Required snapshot file '$file' not found in '$SNAPSHOTS_PATH'"
        exit 1
    fi
done

# Check if any .dat files exist
if ! ls "$SNAPSHOTS_PATH"/*.dat 1> /dev/null 2>&1; then
    echo "Error: No snapshot .dat files found in '$SNAPSHOTS_PATH'"
    echo "This doesn't appear to be a valid OpenSearch snapshot directory"
    exit 1
fi

echo "Starting OpenSearch snapshot management..."

# Step 1: Copy snapshots folder to opensearch-node:/tmp
echo "Step 1: Copying snapshots folder to opensearch-node:/tmp..."
docker cp "$SNAPSHOTS_PATH/." opensearch-node:/tmp/snapshots/

# Fix permissions inside the container
echo "Fixing permissions inside container..."
docker exec -u root opensearch-node chown -R opensearch:opensearch /tmp/snapshots/

# Step 2: Check if repository exists, create only if needed
echo "Step 2: Checking snapshot repository..."
REPO_EXISTS=$(curl -s "localhost:9200/_snapshot/local_backup" | grep -o '"local_backup"' || echo "")

if [ -z "$REPO_EXISTS" ]; then
    echo "Repository doesn't exist, creating new one..."
    REPO_RESPONSE=$(curl -s -X PUT "localhost:9200/_snapshot/local_backup" -H 'Content-Type: application/json' -d'{
      "type": "fs",
      "settings": {
        "location": "/tmp/snapshots"
      }
    }')
    
    if echo "$REPO_RESPONSE" | grep -q '"acknowledged":true'; then
        echo "Repository created successfully"
    else
        echo "Error creating repository: $REPO_RESPONSE"
        exit 1
    fi
else
    echo "Repository already exists, skipping creation"
fi

# Step 3: Verify snapshots are visible before restoring
echo "Step 3: Verifying snapshots are accessible..."
SNAPSHOTS_LIST=$(curl -s "localhost:9200/_snapshot/local_backup/_all")

if echo "$SNAPSHOTS_LIST" | grep -q '"snapshots" : \[ \]'; then
    echo "Error: No snapshots found in repository. Check if files copied correctly."
    exit 1
fi

if ! echo "$SNAPSHOTS_LIST" | grep -q '"cataloguesearch_prod"'; then
    echo "Error: cataloguesearch_prod snapshot not found in repository"
    exit 1
fi

if ! echo "$SNAPSHOTS_LIST" | grep -q '"cataloguesearch_prod_metadata"'; then
    echo "Error: cataloguesearch_prod_metadata snapshot not found in repository"
    exit 1
fi

echo "Both required snapshots found in repository"

# Step 4: Delete existing indices (if they exist)
echo "Step 4: Deleting existing indices..."

echo "Deleting cataloguesearch_prod index..."
curl -s -X DELETE "localhost:9200/cataloguesearch_prod" > /dev/null || echo "cataloguesearch_prod index may not exist, continuing..."

echo "Deleting cataloguesearch_prod_metadata index..."
curl -s -X DELETE "localhost:9200/cataloguesearch_prod_metadata" > /dev/null || echo "cataloguesearch_prod_metadata index may not exist, continuing..."

# Step 5: Restore the snapshots with error checking
echo "Step 5: Restoring snapshots..."

echo "Restoring cataloguesearch_prod..."
RESTORE_RESPONSE=$(curl -s -X POST "localhost:9200/_snapshot/local_backup/cataloguesearch_prod/_restore" -H 'Content-Type: application/json' -d'{
  "indices": "cataloguesearch_prod",
  "ignore_unavailable": true,
  "include_global_state": false
}')

if echo "$RESTORE_RESPONSE" | grep -q '"accepted":true'; then
    echo "cataloguesearch_prod restore initiated successfully"
elif echo "$RESTORE_RESPONSE" | grep -q "error"; then
    echo "Error restoring cataloguesearch_prod: $RESTORE_RESPONSE"
    exit 1
else
    echo "Unexpected response from cataloguesearch_prod restore: $RESTORE_RESPONSE"
fi

echo "Restoring cataloguesearch_prod_metadata..."
RESTORE_RESPONSE=$(curl -s -X POST "localhost:9200/_snapshot/local_backup/cataloguesearch_prod_metadata/_restore" -H 'Content-Type: application/json' -d'{
  "indices": "cataloguesearch_prod_metadata",
  "ignore_unavailable": true,
  "include_global_state": false
}')

if echo "$RESTORE_RESPONSE" | grep -q '"accepted":true'; then
    echo "cataloguesearch_prod_metadata restore initiated successfully"
elif echo "$RESTORE_RESPONSE" | grep -q "error"; then
    echo "Error restoring cataloguesearch_prod_metadata: $RESTORE_RESPONSE"
    exit 1
else
    echo "Unexpected response from cataloguesearch_prod_metadata restore: $RESTORE_RESPONSE"
fi

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