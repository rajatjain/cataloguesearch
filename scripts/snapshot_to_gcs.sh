#!/bin/bash
set -e

# --- Configuration ---
# This script uses environment variables for configuration.
# You can set them directly or use a .env file with `source .env`

# Your LOCAL OpenSearch instance details
OPENSEARCH_HOST=${OPENSEARCH_HOST:-"localhost"}
OPENSEARCH_PORT=${OPENSEARCH_PORT:-9200}
OPENSEARCH_USER=${OPENSEARCH_USER:-"admin"}
OPENSEARCH_PASSWORD=${OPENSEARCH_PASSWORD:-"Admin@Password123!"}

# The name of the index you want to snapshot
INDEX_NAME=${INDEX_NAME:-"cataloguesearch_prod"}

# The name for the snapshot repository you configured in your local OpenSearch
SNAPSHOT_REPO_NAME=${SNAPSHOT_REPO_NAME:-"gcs_local_repository"}

# The name of the snapshot to create in GCS. 'latest_snapshot' is recommended.
SNAPSHOT_NAME=${SNAPSHOT_NAME:-"latest_snapshot"}

# --- Script Logic ---
echo "Starting snapshot process for index '${INDEX_NAME}'..."

# Construct the curl command
CURL_URL="https://_:${OPENSEARCH_PASSWORD}@${OPENSEARCH_HOST}:${OPENSEARCH_PORT}/_snapshot/${SNAPSHOT_REPO_NAME}/${SNAPSHOT_NAME}?wait_for_completion=true"

# Add the index to the request body to only snapshot the specific index
REQUEST_BODY=$(cat <<EOF
{
  "indices": "${INDEX_NAME}",
  "ignore_unavailable": true,
  "include_global_state": false
}
EOF
)

echo "Taking snapshot '${SNAPSHOT_NAME}' and storing it in repository '${SNAPSHOT_REPO_NAME}'..."

curl -k -X PUT "${CURL_URL}" \
     -H 'Content-Type: application/json' \
     --user "${OPENSEARCH_USER}:${OPENSEARCH_PASSWORD}" \
     -d "${REQUEST_BODY}"

echo "" # for a newline
echo "✅ Snapshot successfully created and uploaded to GCS."