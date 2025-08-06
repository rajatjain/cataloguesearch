# Docker Deployment Guide

This guide covers running CatalogueSearch using Docker containers with OpenSearch and the API service.

## Quick Start

### Local Development
```bash
./docker-run.sh local up
```

### Production
```bash
./docker-run.sh prod up
```

## Services

The Docker setup includes:

1. **OpenSearch** - Search engine and document indexing (port 9200)
2. **CatalogueSearch API** - FastAPI backend (port 8000)  
3. **OpenSearch Dashboards** - Web UI for OpenSearch (port 5601)

## Environment Configuration

The setup uses the existing `configs/config.yaml` with environment variable substitution to work in both local and container environments.

### Local (.env.local)
- Reduced memory allocation (1GB for OpenSearch)
- Verbose logging for development
- No container restart policy
- Uses development GCS credentials
- Container paths: `/app/data`, `/app`
- OpenSearch hostname: `opensearch`

### Production (.env.prod)
- Increased memory allocation (2GB for OpenSearch)  
- Verbose logging
- Automatic container restart (`unless-stopped`)
- Uses production GCS credentials
- Container paths: `/app/data`, `/app`
- OpenSearch hostname: `opensearch`

### Configuration File
The system uses the existing `configs/config.yaml` with these environment variables:
- `{HOME}` → `/app/data` (container data directory)
- `{BASE_DIR}` → `/app` (container app directory) 
- `{OPENSEARCH_HOST}` → `opensearch` (Docker service name)

## Usage

### Starting Services
```bash
# Local development
./docker-run.sh local up

# Production
./docker-run.sh prod up
```

### Viewing Logs
```bash
./docker-run.sh local logs
```

### Stopping Services
```bash
./docker-run.sh local down
```

### Rebuilding Images
```bash
./docker-run.sh local build
```

## API Endpoints

Once running, the API will be available at `http://localhost:8000`:

- `GET /metadata` - Get document metadata
- `POST /search` - Perform search queries
- `GET /similar-documents/{doc_id}` - Find similar documents
- `GET /context/{chunk_id}` - Get paragraph context

## Data Persistence

The setup uses Docker volumes for data persistence:

- `opensearch-data` - OpenSearch index data
- `cataloguesearch-data` - PDF files, extracted text, SQLite database
- `cataloguesearch-logs` - Application logs

## Health Checks

Both OpenSearch and the API include health checks:

- OpenSearch: Cluster health endpoint
- API: Metadata endpoint availability

## Troubleshooting

### API Won't Start
- Check if OpenSearch is healthy: `docker logs opensearch-node`
- Verify environment variables in the .env file
- Check API logs: `docker logs cataloguesearch-api`

### Memory Issues
- Adjust `OPENSEARCH_JAVA_OPTS` in .env files
- Monitor container memory usage: `docker stats`

### Network Issues
- All services use the `opensearch-net` network
- API connects to OpenSearch via hostname `opensearch`
- Ports are exposed to host for external access

## Prerequisites

- Docker and Docker Compose installed
- At least 2GB RAM available for containers
- Valid GCS credentials (if using cloud storage)

## File Structure

```
docker/
├── api/
│   ├── Dockerfile          # API container definition
│   └── entrypoint.sh       # Initialization script
└── opensearch/
    ├── Dockerfile          # OpenSearch container
    └── entrypoint.sh       # OpenSearch setup

configs/
├── config.yaml             # Main config (works for both local & containers)
└── opensearch-config.yaml  # OpenSearch index mapping

.env.local                  # Local development settings
.env.prod                   # Production settings
docker-compose.yml          # Service definitions
docker-run.sh              # Convenience script
```