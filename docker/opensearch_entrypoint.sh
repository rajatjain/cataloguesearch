#!/bin/bash
set -e

# --- Configuration (from environment variables) ---
OPENSEARCH_HOST=${OPENSEARCH_HOST:-"localhost"}
OPENSEARCH_PORT=${OPENSEARCH_PORT:-9200}
OPENSEARCH_USER=${OPENSEARCH_USER:-"admin"}
OPENSEARCH_PASSWORD=${OPENSEARCH_PASSWORD:-"Admin@Password123!"}
INDEX_NAME=${INDEX_NAME:-"cataloguesearch_prod"}

# These variables MUST be provided when running the container
GCS_BUCKET_NAME=${GCS_BUCKET_NAME:?"GCS_BUCKET_NAME must be set"}
GCS_CREDENTIALS_JSON=${GCS_CREDENTIALS_JSON:?"GCS_CREDENTIALS_JSON must be set"}

# Optional variables
GCS_BASE_PATH=${GCS_BASE_PATH:-"snapshots"} # Sub-folder in the bucket
SNAPSHOT_REPO_NAME=${SNAPSHOT_REPO_NAME:-"gcs_prod_repository"}
SNAPSHOT_NAME=${SNAPSHOT_NAME:-"latest_snapshot"}

CURL_USER_AUTH="${OPENSEARCH_USER}:${OPENSEARCH_PASSWORD}"
CURL_BASE_URL="https://${OPENSEARCH_HOST}:${OPENSEARCH_PORT}"
CURL_OPTS="-s -k" # -s for silent, -k to ignore self-signed certs

# --- Helper Functions ---
_curl() {
    local method="$1"
    local path="$2"
    shift 2
    curl ${CURL_OPTS} -u "${CURL_USER_AUTH}" -X "${method}" "${CURL_BASE_URL}${path}" "$@"
}

wait_for_opensearch() {
    echo "Waiting for OpenSearch to be available..."
    until _curl "GET" "/_cluster/health?wait_for_status=yellow&timeout=50s" > /dev/null; do
        echo -n '.'
        sleep 2
    done
    echo "OpenSearch is up and running!"
}

register_gcs_repo() {
    echo "Registering GCS snapshot repository '${SNAPSHOT_REPO_NAME}'..."
    _curl "PUT" "/_snapshot/${SNAPSHOT_REPO_NAME}" -H 'Content-Type: application/json' -d"
    {
      \"type\": \"gcs\",
      \"settings\": {
        \"bucket\": \"${GCS_BUCKET_NAME}\",
        \"base_path\": \"${GCS_BASE_PATH}\",
        \"compress\": true
      }
    }
    "
    echo "Repository registration command sent."
}

check_index_exists() {
    echo "Checking if index '${INDEX_NAME}' exists..."
    status_code=$(_curl "HEAD" "/${INDEX_NAME}" --write-out %{http_code} --silent --output /dev/null)
    if [ "$status_code" -eq 200 ]; then
        return 0 # True, index exists
    else
        return 1 # False, index does not exist
    fi
}

restore_snapshot() {
    echo "Index '${INDEX_NAME}' not found. Restoring from snapshot '${SNAPSHOT_NAME}'..."
    _curl "POST" "/_snapshot/${SNAPSHOT_REPO_NAME}/${SNAPSHOT_NAME}/_restore?wait_for_completion=true" -H 'Content-Type: application/json' -d"
    {
      \"indices\": \"${INDEX_NAME}\",
      \"ignore_unavailable\": true,
      \"include_global_state\": false
    }
    "
    echo "Restore completed successfully."
}

# --- Main Execution ---

# 1. Add GCS credentials to the OpenSearch keystore for secure access.
echo "Adding GCS credentials to OpenSearch keystore..."
(echo "${GCS_CREDENTIALS_JSON}" | /usr/share/opensearch/bin/opensearch-keystore add-file --stdin gcs.client.default.credentials_file) || echo "gcs credentials already in keystore."

# 2. Start the original OpenSearch entrypoint in the background
echo "Starting OpenSearch server in the background..."
unset GCS_CREDENTIALS_JSON # Unset credentials so they are not exposed
/usr/share/opensearch/opensearch-docker-entrypoint.sh &
OPENSEARCH_PID=$!

# 3. Wait for OpenSearch to become ready
wait_for_opensearch

# 4. Register the GCS snapshot repository
register_gcs_repo

# 5. Check if the index exists and restore if it doesn't
if check_index_exists; then
    echo "Index '${INDEX_NAME}' already exists. Skipping restore."
else
    restore_snapshot
fi

# 6. Bring the OpenSearch process to the foreground to keep the container running
echo "Initialization complete. OpenSearch is running."
wait $OPENSEARCH_PID