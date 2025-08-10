#!/bin/bash

# Configuration
OPENSEARCH_URL="http://localhost:9200"
REPOSITORY_NAME="${SNAPSHOT_REPOSITORY_NAME:-gcs-repository}"
GCS_BUCKET="${GCS_BUCKET_NAME:-opensearch-snapshots}"
GCS_KEY_PATH="${GCS_SERVICE_ACCOUNT_KEY_PATH:-/usr/share/opensearch/config/gcs-key.json}"

echo "Configuring GCS repository..."

# Check if GCS key file exists
if [ ! -f "$GCS_KEY_PATH" ]; then
    echo "Warning: GCS service account key not found at $GCS_KEY_PATH"
    echo "Skipping snapshot restoration"
    exit 0
fi

# Create GCS repository
echo "Creating GCS repository: $REPOSITORY_NAME"
curl -f -s -X PUT "$OPENSEARCH_URL/_snapshot/$REPOSITORY_NAME" \
    -H 'Content-Type: application/json' \
    -d "{
        \"type\": \"gcs\",
        \"settings\": {
            \"bucket\": \"$GCS_BUCKET\",
            \"service_account\": \"$GCS_KEY_PATH\",
            \"compress\": true
        }
    }"

echo ""
echo "Waiting for repository to be configured..."
sleep 5

# List available snapshots
echo "Checking for available snapshots..."
SNAPSHOTS=$(curl -f -s "$OPENSEARCH_URL/_snapshot/$REPOSITORY_NAME/_all" | jq -r '.snapshots[].snapshot' 2>/dev/null)

if [ -z "$SNAPSHOTS" ]; then
    echo "No snapshots found in GCS bucket: $GCS_BUCKET"
    exit 0
fi

# Get the latest snapshot (last in the list)
LATEST_SNAPSHOT=$(echo "$SNAPSHOTS" | tail -n 1)
echo "Found snapshots. Latest: $LATEST_SNAPSHOT"

# Check if indices already exist
EXISTING_INDICES=$(curl -f -s "$OPENSEARCH_URL/_cat/indices" | wc -l)

if [ "$EXISTING_INDICES" -gt 1 ]; then
    echo "Indices already exist. Skipping restoration."
    exit 0
fi

# Restore the latest snapshot
echo "Restoring snapshot: $LATEST_SNAPSHOT"
RESTORE_RESPONSE=$(curl -f -s -X POST "$OPENSEARCH_URL/_snapshot/$REPOSITORY_NAME/$LATEST_SNAPSHOT/_restore" \
    -H 'Content-Type: application/json' \
    -d '{
        "indices": "*",
        "ignore_unavailable": true,
        "include_global_state": false,
        "include_aliases": true
    }')

echo "Restore response: $RESTORE_RESPONSE"

# Wait for restoration to complete
echo "Waiting for restoration to complete..."
while true; do
    RECOVERY_STATUS=$(curl -f -s "$OPENSEARCH_URL/_recovery" | jq -r '.[].shards[].stage' 2>/dev/null | grep -v "DONE" | wc -l)
    
    if [ "$RECOVERY_STATUS" -eq 0 ]; then
        echo "Snapshot restoration completed successfully!"
        break
    fi
    
    echo "Restoration in progress... ($RECOVERY_STATUS shards remaining)"
    sleep 5
done

echo "Snapshot restoration process finished."
