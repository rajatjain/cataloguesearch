# CatalogueSearch Developer Onboarding Guide (macOS)

Welcome to CatalogueSearch! This guide will help you get set up and running on macOS to contribute to this multilingual PDF search project.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Project Overview](#project-overview)
  - [Key Components](#key-components)
- [Setup Instructions](#setup-instructions)
  - [1. Clone and Navigate](#1-clone-and-navigate)
  - [2. Python Environment Setup](#2-python-environment-setup)
  - [3. Install System Dependencies](#3-install-system-dependencies)
  - [4. Docker Setup](#4-docker-setup)
  - [5. Google Cloud Vision Setup (Optional)](#5-google-cloud-vision-setup-optional)
  - [6. Configuration](#6-configuration)
  - [7. OpenSearch Setup](#7-opensearch-setup)
- [Running Tests](#running-tests)
- [Development Workflow](#development-workflow)
  - [Starting Development](#starting-development)
  - [Running the Search API](#running-the-search-api)
  - [Stopping Services](#stopping-services)
- [Project Structure](#project-structure)
- [Common Commands](#common-commands)
- [Troubleshooting](#troubleshooting)
  - [Docker Issues](#docker-issues)
  - [Python Environment Issues](#python-environment-issues)
  - [OpenSearch Connection Issues](#opensearch-connection-issues)
  - [Test Failures](#test-failures)

## Prerequisites

- macOS (tested on macOS 10.15+)
- Python 3.9+ (recommended: Python 3.11)
- [Homebrew](https://brew.sh/) package manager
- Docker Desktop for Mac
- Git

## Project Overview

CatalogueSearch is a system for scanning, parsing, and searching PDF files written in Hindi or Gujarati. It supports both lexical and vector search capabilities using OpenSearch as the backend.

### Key Components

- **PDF Processor** (`backend/processor/`): Handles PDF ingestion, OCR, and text extraction
- **Discovery** (`backend/crawler/`): Monitors and discovers new documents
- **Indexing Module** (`backend/index/`): Creates and manages search indices
- **Search API** (`backend/api/`): FastAPI-based search endpoints
- **Search Engine** (`backend/search/`): Language detection, ranking, and highlighting

## Setup Instructions

### 1. Clone and Navigate

```bash
git clone <repository-url>
cd cataloguesearch
```

### 2. Python Environment Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install System Dependencies

```bash
# Install ImageMagick (required for PDF/image conversion)
brew install imagemagick

# Install Tesseract (OCR engine)
brew install tesseract
```

### 4. Docker Setup

1. Install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
2. Start Docker Desktop and ensure it's running
3. Verify installation: `docker --version`

### 5. Google Cloud Vision Setup (Optional)

For advanced OCR capabilities, you'll need to set up Google Cloud Vision API:

#### Create Google Cloud Project and Service Account

1. **Create a Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Click "Select a project" → "New Project"
   - Enter a project name (e.g., "cataloguesearch-ocr")
   - Click "Create"

2. **Enable the Vision API**:
   - In the Google Cloud Console, go to "APIs & Services" → "Library"
   - Search for "Cloud Vision API"
   - Click on it and press "Enable"

3. **Create a Service Account**:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "Service Account"
   - Enter a service account name (e.g., "cataloguesearch-vision")
   - Add description: "Service account for CatalogueSearch Vision API"
   - Click "Create and Continue"

4. **Assign Roles**:
   - Select role: "Cloud Vision" → "Vision API User"
   - Click "Continue" → "Done"

5. **Download Service Account Key**:
   - Click on the created service account
   - Go to "Keys" tab → "Add Key" → "Create new key"
   - Select "JSON" format
   - Click "Create" - the JSON file will be downloaded to your computer

6. **Install Google Cloud SDK and Set Up Authentication**:
   ```bash
   # Install Google Cloud SDK
   brew install --cask google-cloud-sdk
   
   # Set up authentication using the downloaded JSON file
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/downloaded-key.json"
   
   # Alternative: Use gcloud authentication (interactive)
   gcloud auth application-default login
   ```

7. **Store Credentials Securely**:
   ```bash
   # Create a secure directory for credentials
   mkdir -p ~/.config/gcloud
   
   # Move your service account key there
   mv ~/Downloads/your-service-account-key.json ~/.config/gcloud/cataloguesearch-vision.json
   
   # Set environment variable
   export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/cataloguesearch-vision.json"
   
   # Add to your shell profile (.bashrc, .zshrc, etc.)
   echo 'export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/cataloguesearch-vision.json"' >> ~/.zshrc
   ```

8. **Verify Setup**:
   ```bash
   # Test the authentication
   gcloud auth application-default print-access-token
   
   # Or test with Python
   python -c "from google.cloud import vision; print('Google Vision client created successfully')"
   ```


### 6. Configuration
Copy and customize the configuration if needed for more environments:
   ```bash
   cp configs/config.yaml configs/local-config.yaml
   ```

### 7. OpenSearch Setup

Start the OpenSearch containers:

```bash
# For development
python scripts/opensearch_controller.py --start --dev

# For testing
python scripts/opensearch_controller.py --start --test
```

Verify OpenSearch is running:
```bash
curl -k -u 'admin:Admin@Password123!' https://localhost:9200/_cluster/health
```

OpenSearch Dashboards will be available at: https://localhost:5601.

## Running Tests

```bash
# Run basic tests
pytest

# Run all the tests (Require OpenSearch containers to be running)
pytest --run-all
```

## Development Workflow

### Starting Development

1. Activate virtual environment: `source venv/bin/activate`
2. Start OpenSearch: `python scripts/opensearch_controller.py --start --dev`
3. Run tests to verify setup: `pytest`

### Running the Search API

```bash
# From the backend directory
cd backend
uvicorn api.search_api:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: http://localhost:8000

### Stopping Services

```bash
# Stop OpenSearch containers
python scripts/opensearch_controller.py --stop --dev
```