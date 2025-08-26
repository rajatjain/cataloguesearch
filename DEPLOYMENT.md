# CatalogueSearch Deployment Guide

This document outlines the process for deploying the CatalogueSearch application, from running it locally for development to deploying it on a production VM.

## Key Components

The deployment architecture consists of four main services working together:

*   **OpenSearch**: A powerful, open-source search and analytics engine that stores and indexes all the document chunks. It enables fast and complex queries, including both traditional text search and modern vector-based semantic search.

*   **API (cataloguesearch-api)**: The FastAPI-based backend service that handles all business logic, from search queries to metadata retrieval. It communicates with OpenSearch to fetch data and serves it to the frontend application.

*   **Frontend (cataloguesearch-frontend)**: The user-facing web interface that provides the search bar, result display, and all interactive elements. It allows users to easily search for and explore the indexed catalogue documents.

*   **ML Models**: These are the machine learning models responsible for understanding language, creating vector embeddings, and re-ranking search results. We use the ONNX (Open Neural Network Exchange) format because it is optimized for fast inference on CPUs, significantly improving performance and reducing resource usage compared to standard PyTorch ML models.

---

## 1. Local Development

This section describes how to build and run the entire application stack on your local machine for development and testing.

### Building the Docker Images

The `docker-run.sh` script simplifies building the images. The API image will be built with the ONNX models included for immediate use.

```bash
# Build all service images (api, frontend, opensearch)
./docker-run.sh local build

# Or, to build only a specific service (e.g., the API)
./docker-run.sh local build-api
```

### Starting Local Containers

To start all services, use the `up` command. This will also build any images that don't already exist.

```bash
# Start all services in the background
./docker-run.sh local up
```

Once running, you can access the services:
-   **Frontend**: `http://localhost:3000`
-   **API**: `http://localhost:8000`
-   **OpenSearch**: `http://localhost:9200`

To view logs or stop the services:

```bash
# View logs for all running containers
./docker-run.sh local logs

# Stop and remove all containers
./docker-run.sh local down
```

## Configuration

### Environment Variables

#### Laptop Profile (.env.laptop)
Prepare the file `.env.local` and keep it in the home directory. Its contents should be. 

**NOTE: MAKE SURE THAT THESE FILES ARE NOT CHECKED INTO GIT.**

```
➜  cat .env.local
# Laptop Environment Configuration

# Memory settings for local
OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g

# Security
OPENSEARCH_INITIAL_ADMIN_PASSWORD=Admin@Password123!

# Container restart policy
RESTART_POLICY=no

# Environment identifier
ENVIRONMENT=local

# API Configuration
LOG_LEVEL=VERBOSE
API_HOST=0.0.0.0
API_PORT=8000

# For CLI usage against Docker OpenSearch
OPENSEARCH_HOST=localhost
```

#### Production Profile (.env.prod)
```
➜  cat .env.prod
# Production Environment Configuration (GCP ec2-medium)

# Memory settings for production
OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx2g

# Security
OPENSEARCH_INITIAL_ADMIN_PASSWORD=Admin@Password123!

# Container restart policy
RESTART_POLICY=unless-stopped

# Environment identifier
ENVIRONMENT=prod

# API Configuration
LOG_LEVEL=VERBOSE
API_HOST=0.0.0.0
API_PORT=8000

# For CLI usage (not applicable in prod, but kept for consistency)
OPENSEARCH_HOST=opensearch%
```

## GCS Snapshot Management

### How it Works

1. On container startup, the system checks for existing snapshots in the configured GCS bucket
2. If snapshots exist, the latest one is automatically restored
3. If no snapshots exist or restoration fails, OpenSearch starts with an empty cluster

### Manual Snapshot Operations

```bash
# Create a snapshot
curl -k -X PUT \
  "https://localhost:9200/_snapshot/gcs-repository/snapshot_$(date +%Y%m%d_%H%M%S)?wait_for_completion=true"

# List snapshots
curl -k \
  "https://localhost:9200/_snapshot/gcs-repository/_all?pretty"

# Restore a specific snapshot
curl -k -X POST \
  "https://localhost:9200/_snapshot/gcs-repository/snapshot_name/_restore"
```

## Commands

### Start Services
```bash
# Laptop
docker-compose --env-file .env.laptop up -d

# Production
docker-compose --env-file .env.prod up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# API Server only
docker-compose logs -f cataloguesearch-api

# Check snapshot restoration logs
docker logs opensearch-node
```

### Rebuild Image
```bash
docker-compose build --no-cache
```

## Production Deployment

### Prerequisites
- Cloud instance (GCP, AWS, Azure, etc.) with SSH access
- Port 80 open for web access
- At least 4GB RAM and 20GB disk space

### Step 1: Prepare the VM
```bash
# Ensure you have these files ready for transfer
scripts/install-docker.sh
docker-compose.prod.yml
snapshots/  # If you have OpenSearch snapshots to restore
```

### Step 2: Copy Files to Cloud Instance
```bash
# Copy installation script and production config to your cloud instance
gcloud compute scp scripts/install-docker.sh user@your-instance-ip:. --zone=<zone>
gcloud compute scp docker-compose.prod.yml user@your-instance-ip:. --zone=<zone>
gcloud compute scp -r snapshots/ user@your-instance-ip:.  # Optional: if you have snapshots
```

### Step 3: SSH and Install Docker
```bash
# SSH into your cloud instance
gcloud compute ssh root@your-instance-ip

# Make install script executable and run it
chmod +x install-docker.sh
sudo ./install-docker.sh

# Log out and log back in (or run newgrp docker) for group changes to take effect
newgrp docker
```

### Step 4: Set System Parameters
```bash
# Required for OpenSearch
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Step 5: Start Services
```bash
# Start all services using the production configuration
docker-compose -f docker-compose.prod.yml up -d

# Check that all services are running
docker-compose -f docker-compose.prod.yml ps

# View logs if needed
docker-compose -f docker-compose.prod.yml logs -f
```

### Step 6: Verify Deployment
```bash
# Check that the frontend is accessible
curl -I http://localhost

# Check that the API is responding
curl http://localhost/api/metadata

# Check OpenSearch health
curl http://localhost:9200/_cluster/health
```

### Step 7: Restore Snapshots (Optional)
If you have OpenSearch snapshots to restore:
```bash
# Copy snapshot files into the OpenSearch container
docker cp snapshots/ opensearch-node:/tmp/snapshots/

# Create snapshot repository
curl -X PUT "localhost:9200/_snapshot/my_backup" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/tmp/snapshots"
  }
}'

# Restore from snapshot
curl -X POST "localhost:9200/_snapshot/my_backup/snapshot_1/_restore" -H 'Content-Type: application/json' -d'
{
  "indices": "cataloguesearch_prod",
  "ignore_unavailable": true,
  "include_global_state": false
}'
```

## Troubleshooting

### Memory Issues
If OpenSearch fails to start due to memory:
```bash
# Increase vm.max_map_count
sudo sysctl -w vm.max_map_count=262144
```

### OpenSearch Index Management
```bash
# Delete index (if needed for fresh start)
curl -X DELETE "localhost:9200/cataloguesearch_prod"

# Check snapshot status
curl -X GET "localhost:9200/_snapshot/my_backup/_all"

# Check restore status
curl -X GET "localhost:9200/_cat/recovery/cataloguesearch_prod?v"

# Check index document count
curl -X GET "localhost:9200/cataloguesearch_prod/_count"
```

### Docker Container Management
```bash
# Check running containers
docker ps

# Check container logs with follow
docker logs container_name -f

# Execute command in container
docker exec -it container_name /bin/bash

# Copy files from host to container
docker cp /local/path/file container_name:/container/path/

# Copy files from container to host
docker cp container_name:/container/path/file /local/path/

# Check disk usage
docker system df

# Clean up unused images/containers
docker system prune -a
```

### Performance Monitoring
```bash
# Real-time container stats (CPU, Memory, Network, Disk I/O)
docker stats

# Stats for specific container
docker stats cataloguesearch-api

# One-time stats snapshot
docker stats --no-stream

# Detailed memory usage inside container
docker exec -it container_name free -h

# Check disk usage inside container
docker exec -it container_name df -h

# Check disk usage of specific directory (e.g., model cache)
docker exec -it cataloguesearch-api du -sh /app/data/.cache/huggingface/

# Check container processes
docker exec -it container_name ps aux

# Monitor container logs during query execution
docker logs cataloguesearch-api --tail 100 -f

# Check container resource limits
docker inspect container_name | grep -i memory
docker inspect container_name | grep -i cpu
```

### System Monitoring (on host)
```bash
# Monitor disk I/O during query execution
sudo iotop -a -o -d 1

# Monitor system resources during query
htop
```

### Check Health
```bash
curl -k  \
  https://localhost:9200/_cluster/health?pretty
```
