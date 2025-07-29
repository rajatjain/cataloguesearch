# CatalogueSearch for Multi Lingual PDF Documents

## Table of Contents

- [Project Description](#project-description)
- [Project Structure](#project-structure)
  - [PDF Processor](#pdf-processor)
  - [Discovery](#discovery)
  - [Indexing Module](#indexing-module)
- [Installation (macOS)](#installation-macos)
  - [Python Dependencies](#python-dependencies)
  - [Docker](#docker)
  - [ImageMagick](#imagemagick)
  - [Google Vision Libraries](#google-vision-libraries)
- [OpenSearch](#opensearch)
- [Running Tests](#running-tests)
- [License](#license)

## Project Description

CatalogueSearch is designed for scanning & parsing PDF files written in hindi or gujarati and then indexing them so they can be used for text search (lexical search as well as vector search).

## Project Structure

### PDF Processor

Handles ingestion and processing of PDF documents. Converts and preprocesses documents for further analysis, including text extraction and image handling.

### Discovery

Responsible for discovering new documents or data sources. This module can crawl, monitor, or receive files from various endpoints, ensuring the system stays updated with the latest content.

### Indexer

Indexes processed data to enable efficient and rapid search. Supports updating, querying, and maintaining the search index for all ingested documents.

## Installation

Follow these instructions to set up the project. These are specifically for macOS laptop, but similar instructions will work for linux.

### Python Dependencies

1. This project is tested with Python 3.11. But it should work with Python 3.9+.
2. Install dependencies:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

### Docker

Some components and tests require Docker.

1. [Install Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/).
2. Start Docker Desktop and ensure it is running.

### ImageMagick

ImageMagick is required for PDF/image conversion.

```bash
brew install imagemagick
```

### Google Vision Libraries

Google Vision is used for advanced OCR.

1. Install the Google Cloud SDK:  
   [Google Cloud SDK Installation](https://cloud.google.com/sdk/docs/install)
2. Install the Vision client library:
    ```bash
    pip install google-cloud-vision
    ```
3. Set up authentication by exporting your Google credentials:
    ```bash
    export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-file.json"
    ```

## OpenSearch

CatalogueSearch uses OpenSearch for indexing and searching documents. You can use the `opensearch_controller.py` script to manage the OpenSearch Docker containers required for development and testing.

### Starting OpenSearch Containers

To start the OpenSearch and supporting containers:

```bash
python opensearch_controller.py --start
```

This script will launch the necessary OpenSearch services using Docker. Make sure Docker Desktop is running before you execute this command.

### Stopping OpenSearch Containers

To stop and remove the OpenSearch containers:

```bash
python opensearch_controller.py --stop
```

You may need to run these commands from the root directory of the project, depending on how your Python environment and Docker are configured.

## Running Tests

Pytest is used for testing.

```bash
pytest
```

> **Note:** Some tests require a Docker container to be running. Make sure Docker is running and the required containers are up before executing the tests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.


```mermaid
graph TD
    A[Agent] -->|Actual/Natural Language Query| B[MCP Server]
    B --> C[Semantic Layer]
    C -->|Converts to SQL, identifies DB| D[Data API Gateway]
    D -->|Validates Security (DCS, Credentials)| E[Security Check]
    D -->|Validates Safety (SafeDB)| F[Safety Check]
    D --> G[WJC (Walmart Java Client)]
    G -->|Executes Query| H[Database]
    H -->|Results| G
    G --> D
    D --> C
    C --> B
    B --> A

```