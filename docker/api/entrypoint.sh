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

# Download ML models if not cached
echo -e "${YELLOW}Initializing ML models...${NC}"
python -c "
import os
from sentence_transformers import SentenceTransformer
from backend.common.embedding_models import get_embedding_model

print('Loading embedding model...')
model = get_embedding_model('BAAI/bge-m3')
print('Embedding model loaded successfully')

print('Loading reranking model...')
reranker = SentenceTransformer('BAAI/bge-reranker-v2-m3')
print('Reranking model loaded successfully')
" || echo -e "${YELLOW}Model initialization failed, will retry at runtime${NC}"

# Wait for OpenSearch to be ready
echo -e "${YELLOW}Waiting for OpenSearch to be ready...${NC}"
while ! curl -k -s -u "${OPENSEARCH_USERNAME}:${OPENSEARCH_PASSWORD}" "https://${OPENSEARCH_HOST}:${OPENSEARCH_PORT}/_cluster/health" > /dev/null; do
    echo "Waiting for OpenSearch..."
    sleep 5
done
echo -e "${GREEN}OpenSearch is ready!${NC}"

# Initialize OpenSearch client and create index if needed
echo -e "${YELLOW}Initializing OpenSearch client...${NC}"
python -c "
from backend.config import Config
from backend.common.opensearch import get_opensearch_client

config = Config('configs/config.yaml')
client = get_opensearch_client(config)
print('OpenSearch client initialized successfully')
" || echo -e "${RED}OpenSearch client initialization failed${NC}"

echo -e "${GREEN}Initialization complete. Starting API server...${NC}"

# Start the API server
exec "$@"