#!/bin/bash
set -e

# --- Configuration ---
GCS_BUCKET="jaincatalogue-opensearch"
SNAPSHOT_REPO="gcs_repo" # The logical name for the repository in OpenSearch
SNAPSHOT_NAME="latest_snapshot" # A fixed name for easy restoration in production

# OpenSearch connection details for the local instance started by opensearch_controller.py
# Using https and credentials because the controller enables the security plugin.
OPENSEARCH_HOST="https://localhost:9200"
OPENSEARCH_USER="admin"
OPENSEARCH_PASS="Admin@Password123!"
CURL_OPTS=(-k -s -u "${OPENSEARCH_USER}:${OPENSEARCH_PASS}")

# --- Functions ---

# Function to register the GCS snapshot repository if it doesn't exist.
# This is a one-time setup per OpenSearch cluster.
register_repository() {
    echo "--> Checking if snapshot repository '${SNAPSHOT_REPO}' is registered..."
    
    # Check if the repository already exists
    http_code=$(curl "${CURL_OPTS[@]}" -o /dev/null -w "%{http_code}" "${OPENSEARCH_HOST}/_snapshot/${SNAPSHOT_REPO}")

    if [ "$http_code" -eq 200 ]; then
        echo "Repository '${SNAPSHOT_REPO}' already exists. Skipping registration."
    elif [ "$http_code" -eq 404 ]; then
        echo "Repository not found. Registering '${SNAPSHOT_REPO}'..."
        
        # Using a here-document for a cleaner and more readable JSON payload
        JSON_PAYLOAD=$(cat <<EOF
{
          "type": "gcs",
          "settings": {
            "bucket": "${GCS_BUCKET}",
            "base_path": "snapshots"
          }
}
EOF
)
        
        # Register the repository with the JSON payload
        curl "${CURL_OPTS[@]}" -XPUT "${OPENSEARCH_HOST}/_snapshot/${SNAPSHOT_REPO}" -H 'Content-Type: application/json' -d "${JSON_PAYLOAD}"
        
        echo -e "\nRepository '${SNAPSHOT_REPO}' registered successfully."
    else
        echo "Error: Failed to check repository status. HTTP status: $http_code." >&2
        echo "Please ensure OpenSearch is running and the 'repository-gcs' plugin is installed in the container." >&2
        exit 1
    fi
}

create_snapshot() {
    echo "--> Creating/updating snapshot: ${SNAPSHOT_NAME} in repository ${SNAPSHOT_REPO}"
    # This command will create a new incremental snapshot. If a snapshot with the
    # same name exists, its definition in the repository metadata will be updated.
    curl "${CURL_OPTS[@]}" -XPUT "${OPENSEARCH_HOST}/_snapshot/${SNAPSHOT_REPO}/${SNAPSHOT_NAME}?wait_for_completion=true"
    echo "Snapshot '${SNAPSHOT_NAME}' created successfully."
}

# Function to list all snapshots in the repository.
list_snapshots() {
    echo "--> Listing all snapshots in repository '${SNAPSHOT_REPO}':"
    curl "${CURL_OPTS[@]}" -XGET "${OPENSEARCH_HOST}/_snapshot/${SNAPSHOT_REPO}/_all" | python3 -m json.tool
}

# --- Main Logic ---
ACTION=${1:-create} # Default action is 'create' if no argument is provided

echo "=================================================================="
echo "OpenSearch Snapshot Manager"
echo "=================================================================="
echo "GCS Bucket:      ${GCS_BUCKET}"
echo "Repository Name: ${SNAPSHOT_REPO}"
echo "Action:          ${ACTION}"
echo "------------------------------------------------------------------"

# Always ensure the repository is registered before performing any action.
# The function is idempotent and will skip if the repo already exists.
register_repository

if [ "$ACTION" == "create" ]; then
    create_snapshot
elif [ "$ACTION" == "list" ]; then
    list_snapshots
else
    echo "Error: Invalid action '${ACTION}'. Use 'create' or 'list'." >&2
    exit 1
fi

echo "Process complete."
