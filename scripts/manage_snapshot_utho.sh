#!/bin/bash
set -e

# --- Configuration for Utho Cloud S3-compatible Object Storage ---
S3_BUCKET="your-utho-bucket-name"
S3_ENDPOINT="your-utho-s3-endpoint"
SNAPSHOT_REPO="utho_s3_repo"
SNAPSHOT_NAME="latest_snapshot"

# OpenSearch connection details for the local instance without security
OPENSEARCH_HOST="http://localhost:9200"
# NOTE: The following line is commented out because no authentication is used
# CURL_OPTS=(-k -s -u "${OPENSEARCH_USER}:${OPENSEARCH_PASS}")

# --- Functions ---

register_repository() {
    echo "--> Checking if snapshot repository '${SNAPSHOT_REPO}' is registered..."

    # The curl command no longer needs the -u flag for credentials
    http_code=$(curl -o /dev/null -w "%{http_code}" "${OPENSEARCH_HOST}/_snapshot/${SNAPSHOT_REPO}")

    if [ "$http_code" -eq 200 ]; then
        echo "Repository '${SNAPSHOT_REPO}' already exists. Skipping registration."
    elif [ "$http_code" -eq 404 ]; then
        echo "Repository not found. Registering '${SNAPSHOT_REPO}'..."

        # Ensure the 'repository-s3' plugin is installed and configured with credentials
        # in the OpenSearch keystore.

        JSON_PAYLOAD=$(cat <<EOF
{
          "type": "s3",
          "settings": {
            "bucket": "${S3_BUCKET}",
            "endpoint": "${S3_ENDPOINT}"
          }
}
EOF
)

        # The curl command is simplified
        curl -XPUT "${OPENSEARCH_HOST}/_snapshot/${SNAPSHOT_REPO}" -H 'Content-Type: application/json' -d "${JSON_PAYLOAD}"

        echo -e "\nRepository '${SNAPSHOT_REPO}' registered successfully."
    else
        echo "Error: Failed to check repository status. HTTP status: $http_code." >&2
        echo "Please ensure OpenSearch is running and the 'repository-s3' plugin is installed." >&2
        exit 1
    fi
}

create_snapshot() {
    echo "--> Creating/updating snapshot: ${SNAPSHOT_NAME} in repository ${SNAPSHOT_REPO}"
    # The curl command is simplified
    curl -XPUT "${OPENSEARCH_HOST}/_snapshot/${SNAPSHOT_REPO}/${SNAPSHOT_NAME}?wait_for_completion=true"
    echo "Snapshot '${SNAPSHOT_NAME}' created successfully."
}

list_snapshots() {
    echo "--> Listing all snapshots in repository '${SNAPSHOT_REPO}':"
    # The curl command is simplified
    curl -XGET "${OPENSEARCH_HOST}/_snapshot/${SNAPSHOT_REPO}/_all" | python3 -m json.tool
}

# --- Main Logic ---
ACTION=${1:-create}

echo "=================================================================="
echo "OpenSearch Snapshot Manager for Utho Cloud (Unsecured HTTP)"
echo "=================================================================="
echo "S3 Bucket:       ${S3_BUCKET}"
echo "S3 Endpoint:     ${S3_ENDPOINT}"
echo "Repository Name: ${SNAPSHOT_REPO}"
echo "Action:          ${ACTION}"
echo "------------------------------------------------------------------"

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