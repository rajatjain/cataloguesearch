# CatalogueSearch — Multi-Lingual PDF Document Processor and Search Engine

## Table of Contents

- [Introduction](#introduction)
- [High Level Architecture and Components](#high-level-architecture-and-components)
- [Installation Instructions on macOS](#installation-instructions-on-macos)
- [Technologies Used](#technologies-used)
- [LICENSE](#license)

## Introduction

CatalogueSearch is a advanced document processing and search system specifically designed for multilingual PDF documents, with specialized support for Hindi and Gujarati texts. The system provides intelligent paragraph generation, semantic text processing, and powerful search capabilities combining both lexical and vector-based search methods.

The system uses OCR technology, natural language processing, and vector embeddings to create searchable document indexes from complex multilingual PDF content.

## High Level Architecture and Components

### PDF Processor
Handles PDF document ingestion and processing. Converts PDF files to processable text and images, manages OCR operations, and preprocesses documents for further analysis.

### Discovery Module
Responsible for document discovery and crawling operations. This module can monitor directories, receive files from various endpoints, and manage the document intake pipeline to ensure the system stays updated with new content.

### Paragraph Generator
Advanced text processing system with language-specific implementations for Hindi and Gujarati. Features intelligent paragraph combination, text normalization, header/footer detection, and contextual text chunking. The system handles OCR correction, punctuation normalization, and semantic paragraph boundary detection.

### Search Engine
Provides dual-mode search capabilities:
- **Lexical Search**: Traditional keyword-based search using OpenSearch
- **Vector Search**: Semantic search using sentence transformers and vector embeddings
- **Hybrid Search**: Combines both approaches for optimal search results

### API Layer
FastAPI-based REST API providing search endpoints and document management capabilities. Includes result ranking, search result aggregation, and response formatting.

### Frontend Interface
React-based web application with Tailwind CSS styling, providing an intuitive user interface for document search and management.

## Installation Instructions on macOS

### Prerequisites
Python 3.11+.

### Python Environment Setup
1. Create and activate a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2. Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Docker Installation
Docker is required for OpenSearch and testing components.

1. Install Docker Desktop for Mac from [Docker's official website](https://www.docker.com/products/docker-desktop/)
2. Start Docker Desktop and ensure it's running

### Tesseract OCR Installation
Tesseract is required for optical character recognition with multilingual support.

1. Install Tesseract using Homebrew:
    ```bash
    brew install tesseract
    ```

2. Install language data for Hindi and Gujarati:
    ```bash
    brew install tesseract-lang
    ```

3. Verify installation and check available languages:
    ```bash
    tesseract --list-langs
    ```
    You should see `hin` (Hindi) and `guj` (Gujarati) in the list.

### Poppler Installation
Poppler is required for PDF to image conversion.

```bash
brew install poppler
```

### Indic NLP Resources Setup
Download and set up the Indic NLP resources for advanced language processing.

1. Clone the Indic NLP resources repository:
    ```bash
    git clone https://github.com/anoopkunchukuttan/indic_nlp_resources.git
    ```

2. Set the environment variable to point to the resources:
    ```bash
    export INDIC_RESOURCES_PATH="/path/to/indic_nlp_resources"
    ```

3. Add this to your shell profile (`.bashrc`, `.zshrc`, etc.) for persistence:
    ```bash
    echo 'export INDIC_RESOURCES_PATH="/path/to/indic_nlp_resources"' >> ~/.zshrc
    ```

### Google Vision API Setup
For advanced OCR capabilities:

1. Install Google Cloud SDK following the [official installation guide](https://cloud.google.com/sdk/docs/install)
2. Set up authentication:
    ```bash
    export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-file.json"
    ```

### OpenSearch Setup
Start the required OpenSearch containers:

```bash
python scripts/opensearch_controller.py --start
```

To stop the containers:
```bash
python scripts/opensearch_controller.py --stop
```

### Frontend Setup
Navigate to the frontend directory and install Node.js dependencies:

```bash
cd frontend
npm install
npm start
```

### Running Tests
Execute the test suite:

```bash
pytest
```

**Note**: Ensure Docker containers are running before executing tests that require OpenSearch.

## Technologies Used

- **OpenSearch** - Search engine and document indexing
- **Tesseract OCR** - Optical character recognition
- **Indic NLP Library** - Specialized processing for Indic languages
- **Sentence Transformers** - Vector embeddings generation
- **Python 3.11+** - Core runtime environment
- **Docker** - Containerization and deployment

## LICENSE

This project is licensed under the MIT License.

```
MIT License

Copyright (c) 2025 Rajat Jain

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```