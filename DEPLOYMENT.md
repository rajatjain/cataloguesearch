# OpenSearch 3.0.0 Docker Setup

This repository contains a unified Docker setup for OpenSearch 3.0.0 that works on both laptop and production (GCP ec2-medium) environments.

## Features

- **OpenSearch 3.0.0** with single-node configuration
- **HTTPS enabled** on port 9200
- **Installed plugins:**
  - analysis-icu (International Components for Unicode)
  - repository-gcs (Google Cloud Storage for snapshots)
- **Automatic GCS snapshot restoration** on startup
- **OpenSearch Dashboards** on port 5601
- **Unified configuration** for both laptop and production

## Directory Structure

```
.
├── docker/
│   └── opensearch/
│       ├── Dockerfile          # Custom OpenSearch image with plugins
│       ├── entrypoint.sh       # Custom entrypoint script
│       └── restore-snapshot.sh # GCS snapshot restoration script
├── docker-compose.yml          # Main compose file
├── .env.laptop                 # Laptop environment variables
├── .env.prod                   # Production environment variables
├── setup.sh                    # Setup and deployment script
├── certs/                      # SSL certificates (generated)
└── credentials/                # GCS service account keys (you provide)
```

## Prerequisites

1. **Docker & Docker Compose** installed
2. **GCS Service Account** with permissions to read/write snapshots
3. **OpenSSL** (for certificate generation)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <your-repo>
cd <your-repo>

# Make setup script executable
chmod +x setup.sh

# Run setup
./setup.sh
```

### 2. Add GCS Credentials

Place your GCS service account JSON keys in the `credentials/` directory:

- `credentials/gcs-key-dev.json` - For laptop profile
- `credentials/gcs-key-prod.json` - For production profile

### 3. Run OpenSearch

#### Option A: Using the setup script

```bash
./setup.sh
# Select option 1 for laptop or option 2 for production
```

#### Option B: Manual Docker Compose

```bash
# For laptop profile
docker-compose --env-file .env.laptop up -d --build

# For production profile
docker-compose --env-file .env.prod up -d --build
```

## Access Points

- **OpenSearch API:** https://localhost:9200
- **OpenSearch Dashboards:** https://localhost:5601

**Default Credentials:**
- Username: `admin`
- Password: `Admin@123456`

## Configuration

### Environment Variables

#### Laptop Profile (.env.laptop)
- Memory: 512MB
- GCS Bucket: opensearch-snapshots-dev
- Restart Policy: no

#### Production Profile (.env.prod)
- Memory: 2GB
- GCS Bucket: opensearch-snapshots-prod
- Restart Policy: unless-stopped

## GCS Snapshot Management

### How it Works

1. On container startup, the system checks for existing snapshots in the configured GCS bucket
2. If snapshots exist, the latest one is automatically restored
3. If no snapshots exist or restoration fails, OpenSearch starts with an empty cluster

### Manual Snapshot Operations

```bash
# Create a snapshot
curl -k -u admin:Admin@123456 -X PUT \
  "https://localhost:9200/_snapshot/gcs-repository/snapshot_$(date +%Y%m%d_%H%M%S)?wait_for_completion=true"

# List snapshots
curl -k -u admin:Admin@123456 \
  "https://localhost:9200/_snapshot/gcs-repository/_all?pretty"

# Restore a specific snapshot
curl -k -u admin:Admin@123456 -X POST \
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

# OpenSearch only
docker-compose logs -f opensearch

# Check snapshot restoration logs
docker logs opensearch-node
```

### Rebuild Image
```bash
docker-compose build --no-cache
```

## Production Deployment on GCP

1. **SSH into your GCP instance:**
```bash
gcloud compute ssh [INSTANCE_NAME] --zone=[ZONE]
```

2. **Install Docker:**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker $USER
newgrp docker
```

3. **Set system parameters:**
```bash
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

4. **Clone and setup:**
```bash
git clone <your-repo>
cd <your-repo>
./setup.sh
# Select option 2 for production
```

5. **Configure firewall (if needed):**
```bash
gcloud compute firewall-rules create opensearch-allow \
  --allow tcp:9200,tcp:5601 \
  --source-ranges=[YOUR_IP_RANGE] \
  --target-tags=opensearch
```

## Troubleshooting

### Certificate Issues
If you encounter SSL certificate errors, regenerate certificates:
```bash
rm -rf certs/*
./setup.sh
```

### GCS Connection Issues
- Verify service account key is valid
- Check GCS bucket permissions
- Ensure bucket name in `.env` file is correct

### Memory Issues
If OpenSearch fails to start due to memory:
```bash
# Increase vm.max_map_count
sudo sysctl -w vm.max_map_count=262144
```

### Check Health
```bash
curl -k -u admin:Admin@123456 \
  https://localhost:9200/_cluster/health?pretty
```

## Security Notes

- Default setup uses self-signed certificates (suitable for development)
- For production, replace with proper SSL certificates
- Change default admin password in production
- Secure GCS service account keys properly
- Consider network policies and firewall rules in production

## Support

For issues or questions, check:
- OpenSearch logs: `docker logs opensearch-node`
- Dashboards logs: `docker logs opensearch-dashboards`
- Cluster health: https://localhost:9200/_cluster/health
