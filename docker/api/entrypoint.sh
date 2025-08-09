#!/bin/bash
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting CatalogueSearch API initialization...${NC}"

# Create necessary directories
mkdir -p /app/data/pdf /app/data/text /app/data/db /app/logs

# Download Indic NLP resources if not present
if [ ! -d "/app/indic_nlp_resources" ]; then
    echo -e "${YELLOW}Downloading Indic NLP resources...${NC}"
    cd /app
    git clone https://github.com/anoopkunchukuttan/indic_nlp_resources.git
    echo -e "${GREEN}Indic NLP resources downloaded successfully${NC}"
fi

# Wait for OpenSearch to be ready
echo -e "${YELLOW}Waiting for OpenSearch to be ready...${NC}"
while ! curl -f -s "http://${OPENSEARCH_HOST}:${OPENSEARCH_PORT}/_cluster/health" > /dev/null; do
    echo "Waiting for OpenSearch..."
    sleep 5
done
echo -e "${GREEN}OpenSearch is ready!${NC}"

echo -e "${GREEN}Initialization complete. Starting API server...${NC}"

# Start the API server
exec "$@"