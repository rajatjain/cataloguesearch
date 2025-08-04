Application Deployment and Data Management Guide

This document provides a comprehensive guide to deploying and managing the Catalogue Search application. The entire application stack (Frontend, Backend, OpenSearch) is containerized using Docker and orchestrated with Docker Compose.

================================
## Deployment Strategy Overview
================================

The core data management strategy is designed for consistency and reliability:

1.  **Local Indexing**: Data is first processed and indexed into a local OpenSearch instance.
2.  **Cloud Snapshot**: A snapshot of the populated local index is created and uploaded to a private Google Cloud Storage (GCS) bucket.
3.  **Production Restore**: When the application is deployed (either locally for testing or in production), the OpenSearch container automatically downloads and restores this snapshot from GCS on its first startup.

This ensures that the production environment starts with a known, pre-validated dataset.

---

=====================
## Prerequisites
=====================

Before you begin, ensure you have the following:

- **Docker & Docker Compose**: For running the containerized application stack.
- **Google Cloud Platform (GCP) Account**: You will need:
  - A **GCS bucket** to store snapshots.
  - A **Service Account** with the `Storage Object Admin` role on that bucket.
  - The **JSON key file** for the Service Account, downloaded to your local machine.

---

=============================================
## Phase 1: One-Time Setup for Local OpenSearch
=============================================

You must configure the OpenSearch container you use for local development (the one started by `scripts/opensearch_controller.py`) so it can write snapshots to GCS. **This is a one-time setup.**

1.  **Start your local OpenSearch container** using your controller script:

    ```sh
    python scripts/opensearch_controller.py --start
    ```

2.  **Get a shell inside the running container**. Find its name with `docker ps` and run:

    ```sh
    docker exec -it <your-local-opensearch-container-name> bash
    ```

3.  **Install the GCS plugin** (inside the container):

    ```sh
    /usr/share/opensearch/bin/opensearch-plugin install repository-gcs --batch
    ```

4.  **Add GCS credentials to the keystore** (inside the container). This securely stores your key.

    ```sh
    # Replace /path/to/your/key.json with the actual path on your local machine
    (cat /path/to/your/gcs-credentials.json | /usr/share/opensearch/bin/opensearch-keystore add-file --stdin gcs.client.default.credentials_file)
    ```

5.  **Restart your local OpenSearch container** for the changes to take effect.

    ```sh
    docker restart <your-local-opensearch-container-name>
    ```

6.  **Register the GCS repository** with your local OpenSearch. Run this `curl` command from your laptop's terminal (not inside the container). **Replace `your-gcs-bucket-name` with your actual bucket name.**

    ```sh
    curl -k -X PUT "https://admin:Admin@Password123!@localhost:9200/_snapshot/gcs_local_repository" \
         -H 'Content-Type: application/json' \
         -d '{"type": "gcs", "settings": {"bucket": "your-gcs-bucket-name", "base_path": "snapshots"}}'
    ```

Your local OpenSearch instance is now fully configured to save snapshots to the cloud.

---

================================================
## Phase 2: Data Management Workflow (Repeatable)
================================================

Whenever you want to update the data that the application uses, follow this two-step process.

### Step 1: Index Data Locally

Run your `discovery_cli.py` scripts to populate your local OpenSearch index with the latest data.

```sh
# Example: Crawl for new files and create the index
python scripts/discovery_cli.py discover --crawl --index
```

### Step 2: Create and Upload Snapshot to GCS

Execute the `snapshot_to_gcs.sh` script. This takes a snapshot of the `cataloguesearch_prod` index from your local OpenSearch and saves it as `latest_snapshot` in your GCS bucket.

```sh
# Make the script executable (only need to do this once)
chmod +x scripts/snapshot_to_gcs.sh

# Run the script to create the snapshot
./scripts/snapshot_to_gcs.sh
```

---

===========================================
## Phase 3: Running the Full Application Stack
===========================================

This process uses Docker Compose to build and run the entire application. It works for both local testing and production deployment on a server.

### Step 1: Create the `.env` File

This file securely provides the GCS credentials to the Docker Compose environment. Create a file named `.env` in the project root with the following content.

**Important:** Replace placeholder values and ensure `.env` is in your `.gitignore`.

```
# .env
GCS_BUCKET_NAME="your-gcs-bucket-name"
GCS_CREDENTIALS_JSON='{"type":"service_account","project_id":"...","private_key_id":"...","private_key":"...","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}'
```

### Step 2: Build and Run the Containers

From the project root directory, run:

```sh
# Build all container images
docker-compose build

# Start all services in the background
docker-compose up -d
```

### Step 3: Accessing and Managing the Application

- **Access the Frontend:** `http://localhost`
- **View Logs:** `docker-compose logs -f`
- **Stop the Application:** `docker-compose down`