# **LLM/Chatbot Backend for PDF Search (Hindi & Gujarati)**

This repository contains the backend modules for an LLM/chatbot system designed to search data within PDF files, specifically supporting Hindi and Gujarati languages. The system automates the discovery, text extraction (including OCR), metadata management, and indexing of PDF documents into an OpenSearch cluster.

## **Table of Contents**

* [1. Features](https://www.google.com/search?q=%231-features)  
* [2. High-Level Architecture](https://www.google.com/search?q=%232-high-level-architecture)  
* [3. Setup](https://www.google.com/search?q=%233-setup)  
  * [3.1. Prerequisites](https://www.google.com/search?q=%2331-prerequisites)  
  * [3.2. Installation](https://www.google.com/search?q=%2332-installation)  
  * [3.3. OpenSearch Setup (for running discovery_module.py directly)](https://www.google.com/search?q=%2333-opensearch-setup-for-running-discovery_modulepy-directly)  
* [4. Usage](https://www.google.com/search?q=%234-usage)  
  * [4.1. Directory Structure for PDFs and Configs](https://www.google.com/search?q=%2341-directory-structure-for-pdfs-and-configs)  
  * [4.2. Running the Discovery Module](https://www.google.com/search?q=%2342-running-the-discovery-module)  
  * [4.3. Output Directories](https://www.google.com/search?q=%2343-output-directories)  
* [5. Testing](https://www.google.com/search?q=%235-testing)  
  * [5.1. Running Tests](https://www.google.com/search?q=%2351-running-tests)  
* [6. Project Structure](https://www.google.com/search?q=%236-project-structure)  
* [7. Future Enhancements](https://www.google.com/search?q=%237-future-enhancements)

## **1. Features**

* **Discovery Module**:  
  * Scans a base folder and its sub-folders for PDF files.  
  * Detects new PDF files and changes in existing PDF content.  
  * Identifies changes in document-specific or folder-level configurations.  
  * Orchestrates OCR and text extraction for PDF pages.  
  * Extracts PDF bookmarks as additional metadata.  
  * Manages a persistent state to track indexed files and their configurations for incremental updates.  
* **Indexing & Embedding Module**:  
  * Connects to OpenSearch 3.0 for both text indexing and vector embeddings.  
  * Supports pluggable text chunking algorithms.  
  * Supports pluggable vector embedding algorithms (using Sentence Transformers).  
  * Performs full-text indexing with language-specific stop word removal (Hindi, Gujarati).  
  * Generates and stores vector embeddings for semantic search.  
  * Handles metadata-only re-indexing for configuration changes, optimizing performance.  
* **Configuration Management**:  
  * Recursively merges config.json files from root, sub-folders, and file-specific JSONs, with deeper configurations overriding shallower ones.  
* **Logging**:  
  * Centralized logging setup with separate log files for each module and optional console output.

## **2. High-Level Architecture**

The system operates in a pipeline fashion:

1. **PDF Storage**: PDF files are stored in a designated base folder with a hierarchical structure, potentially alongside config.json files.  
2. **Discovery Module**: Scans the PDF folder, performs OCR on PDFs to extract text, extracts bookmarks, and merges configuration data. It determines if a file is new, its content has changed, or its configuration has changed.  
3. **Indexing & Embedding Module**: Receives processed text and metadata from the Discovery Module. It chunks the text, generates vector embeddings, and indexes both the text content and embeddings into OpenSearch.  
4. **OpenSearch 3.0**: Serves as the primary data store for all indexed text, metadata, and vector embeddings, enabling efficient search and retrieval.

```
graph TD  
    A[Base PDF Folder --> B{Discovery Module};  
    B -- New/Updated PDFs --> C[OCR Processing ;  
    C --> D[Page-wise Text Files ;  
    B -- Metadata (from config.json & Bookmarks) --> E[Metadata Processor ;  
    D & E --> F{Indexing & Embedding Module};  
    F -- Text & Vectors --> G[OpenSearch 3.0 ;  
    F -- Last Index Timestamp Update --> H[Tracking Database/File ;  
    G -- Indexed Data & Embeddings --> I[LLM/Chatbot (Future Module) ;
```

## **3. Setup**

### **3.1. Prerequisites**

* **Python 3.9+**: The project is developed using Python.  
* **Docker**: Required for running the OpenSearch 3.0 container, especially for testing with Testcontainers.  
* **Tesseract OCR**:  
  * Install Tesseract OCR engine on your system.  
  * Install Hindi (hin) and Gujarati (guj) language packs for Tesseract.  
  * **Windows**: You might need to add Tesseract to your system's PATH, or specify the path to tesseract.exe in the DiscoveryModule initialization (e.g., tesseract_cmd_path=r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe').  
  * **Linux/macOS**: Typically installed via package managers (e.g., sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-guj on Debian/Ubuntu, brew install tesseract tesseract-lang on macOS).

### **3.2. Installation**

1. **Clone the repository**:  
```
   git clone <repository_url>  
   cd <repository_name>
```

2. **Create a virtual environment (recommended)**:  
```
   python -m venv venv  
   source venv/bin/activate
```

3. **Install dependencies**:  
```
   pip install -r requirements.txt
```

### **3.3. OpenSearch Setup (for running discovery_module.py directly)**

For direct execution of discovery_module.py, you'll need a running OpenSearch instance. You can use Docker:

```
docker run -p 9200:9200 -p 9600:9600 \  
  -e "discovery.type=single-node" \  
  -e "OPENSEARCH_USERNAME=admin" \  
  -e "OPENSEARCH_PASSWORD=admin" \  
  -e "OPENSEARCH_INITIAL_ADMIN_PASSWORD=admin" \  
  --name opensearch-test \  
  opensearchproject/opensearch:3.0.0
```

Wait for OpenSearch to start (it might take a minute or two). You can check its health at `https://localhost:9200` (use admin/admin credentials).

## **4. Usage**

The `discovery_module.py` file can be run directly to initiate the scanning and indexing process.

### **4.1. Directory Structure for PDFs and Configs**

Organize your PDF files and config.json files as follows:

```
<base_pdf_folder>/  
├── config.json             # Global config  
├── subfolder1/  
│   ├── config.json         # Subfolder1 config (overrides global)  
│   ├── documentA.pdf  
│   └── documentA_config.json # Document A specific config (overrides subfolder1 and global)  
├── subfolder2/  
│   ├── config.json         # Subfolder2 config  
│   └── documentB.pdf  
└── documentC.pdf
```

### **4.2. Running the Discovery Module**

You can run the `discovery_module.py` directly. Ensure your OpenSearch instance is running and accessible.

```
python discovery_module.py
```

The if `__name__ == "__main__":` block in `discovery_module.py` provides a demonstration of:

* **Initial Scan**: Indexes new PDFs.  
* **No Change Scan**: Skips re-indexing if no changes are detected.  
* **Content Change Scan**: Triggers full re-indexing if PDF content changes.  
* **Config Change Scan**: Triggers metadata-only re-indexing if a config file changes.  
* **New PDF Scan**: Indexes newly added PDFs.

Environment Variables (Optional but Recommended):  
For production or more flexible local setup, you can set OpenSearch connection details as environment variables:  
```
export OPENSEARCH_HOST="localhost"  
export OPENSEARCH_PORT="9200"  
export OPENSEARCH_USER="admin"  
export OPENSEARCH_PASSWORD="admin"  
```

Now run

```
python discovery_module.py
```

### **4.3. Output Directories**

* **discovery_test_pdfs/**: This is the example `BASE_PDF_FOLDER` where you place your PDF files and config files.  
* **discovery_extracted_texts/**: This is the `OUTPUT_TEXT_BASE_DIR` where the page-wise text files extracted from PDFs will be stored, mirroring the original folder structure.  
* **discovery_state/state.json**: This file stores the internal state of the Discovery Module, tracking which files have been indexed, their checksums, and config hashes.

## **5. Testing**

Unit tests are provided for each module and utilize pytest and testcontainers to spin up a clean OpenSearch 3.0 instance for each test run, ensuring isolated and reliable testing.

### **5.1. Running Tests**

1. **Ensure Docker is running** on your system.  
2. **Run pytest** from the root of the repository:  
   pytest

This will automatically:

* Spin up an OpenSearch 3.0 Docker container.  
* Run all tests, including those that interact with OpenSearch.  
* Tear down the OpenSearch container after tests are complete.  
* Generate log files in the test_logs/ directory.

**Note on Tesseract for Tests**: If your tests involve OCR (e.g., test_pdf_processor.py), ensure Tesseract OCR and its Hindi/Gujarati language packs are correctly installed and accessible in your environment. Tests that require Tesseract will be skipped if it's not detected.

## **6. Project Structure**

```
.  
├── requirements.txt                # Python dependencies  
├── logger_config.py                # Centralized logging configuration  
├── config_parser.py                # Handles recursive config merging  
├── pdf_processor.py                # Extracts text from PDFs (with OCR) and bookmarks  
├── indexing_embedding_module.py    # Chunks text, generates embeddings, indexes into OpenSearch  
├── discovery_module.py             # Orchestrates scanning, change detection, and indexing  
├── test_config_parser.py           # Unit tests for config_parser.py  
├── test_pdf_processor.py           # Unit tests for pdf_processor.py  
├── test_indexing_embedding_module.py # Unit tests for indexing_embedding_module.py (uses Testcontainers)  
├── test_discovery_module.py        # Unit tests for discovery_module.py (uses Testcontainers)  
└── logs/                           # Directory for module-specific log files (created on run)
```

## **7. Future Enhancements**

* **Document Deletion**: Implement logic in DiscoveryModule and IndexingEmbeddingModule to remove documents from OpenSearch if they are deleted from the file system.  
* **Scheduled Scans**: Automate the scan_and_index process to run periodically.  
* **REST API**: Develop a RESTful API to expose indexing and search functionalities.  
* **LLM/Chatbot Integration**: Integrate with a frontend LLM/chatbot application for natural language querying.  
* **Advanced Chunking/Embedding**: Explore more sophisticated chunking strategies (e.g., semantic chunking) and fine-tuned embedding models for Hindi/Gujarati.  
* **Monitoring and Alerting**: Add metrics and alerts for indexing failures or performance issues.
