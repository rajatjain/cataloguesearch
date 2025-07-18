# **PDF Chatbot Search System**

This repository contains the design and future implementation of a PDF search chatbot system. The system is designed to index and search content within PDF files, primarily in Hindi and Gujarati languages, leveraging OCR for text extraction, OpenSearch for indexing and vector embeddings, and a Large Language Model (LLM) for transforming user queries. The chatbot will provide paginated search results with highlighted keywords.

## **Table of Contents**

1. [Introduction](https://www.google.com/search?q=%231-introduction)  
2. [Overall Architecture](https://www.google.com/search?q=%232-overall-architecture)  
3. [Modules](https://www.google.com/search?q=%233-modules)  
   * [Discovery Module](https://www.google.com/search?q=%2331-discovery-module)  
   * [Indexing and Embedding Module](https://www.google.com/search?q=%2332-indexing-and-embedding-module)  
   * [LLM Chatbot and Search Module](https://www.google.com/search?q=%2333-llm-chatbot-and-search-module)  
   * [UI Module](https://www.google.com/search?q=%2334-ui-module)  
4. [Technology Stack](https://www.google.com/search?q=%234-technology-stack)  
5. [Setup and Installation](https://www.google.com/search?q=%235-setup-and-installation)  
   * [Prerequisites](https://www.google.com/search?q=%2351-prerequisites)  
   * [OpenSearch Setup](https://www.google.com/search?q=%2352-opensearch-setup)  
   * [Backend Setup](https://www.google.com/search?q=%2353-backend-setup)  
   * [Frontend Setup](https://www.google.com/search?q=%2354-frontend-setup)  
6. [Usage](https://www.google.com/search?q=%236-usage)  
   * [Discovery Module Execution](https://www.google.com/search?q=%2361-discovery-module-execution)  
   * [Chatbot Interaction](https://www.google.com/search?q=%2362-chatbot-interaction)  
7. [Logging](https://www.google.com/search?q=%237-logging)  
8. [Testing](https://www.google.com/search?q=%238-testing)  
9. [Future Enhancements](https://www.google.com/search?q=%239-future-enhancements)  
10. [Contributing](https://www.google.com/search?q=%2310-contributing)  
11. [License](https://www.google.com/search?q=%2311-license)

## **1\. Introduction**

The PDF Chatbot Search System aims to provide an intelligent way to search and retrieve information from a collection of PDF documents. It's particularly focused on handling content in Hindi and Gujarati, making it a valuable tool for multilingual document repositories.

## **2\. Overall Architecture**

The system is structured into four main modules:

* **Discovery Module:** Scans, OCRs, and prepares PDF content and metadata.  
* **Indexing & Embedding Module:** Chunks text, generates vector embeddings, and indexes data into OpenSearch.  
* **LLM Chatbot & Search Module:** Processes user queries, performs searches, and formats results.  
* **UI Module:** Provides the interactive user interface.

```

graph TD  
    subgraph Data Ingestion  
        A [Base PDF Folder] --> B{Discovery Module};  
        B --> C [PDF Files (Hindi/Gujarati)];  
        B --> D [Config Files (.json)];  
        C --> E [OCR Processor];  
        E --> F [Text Files (Page-wise)];  
        D --> F;  
        F --> G{Indexing & Embedding Module};  
    end

    subgraph Search & Chatbot  
        H [User Input (Hindi/Gujarati)] --> I{UI Module};  
        I --> J{LLM Chatbot & Search Module};  
        J --> K [OpenSearch Cluster];  
        K --> J;  
        J --> I;  
        I --> L [Paginated Search Results];  
    end

    G --> K;
```

## **3. Modules**

### **3.1. Discovery Module**

This module is responsible for scanning the designated base folder for PDF files, performing OCR to extract text, processing associated metadata from JSON config files, and preparing the data for indexing. It also handles detecting changes in files or configurations to trigger re-indexing.

**Key Features:**

* Recursive folder scanning.  
* OCR for Hindi and Gujarati PDFs.  
* Recursive config file merging.  
* PDF bookmark extraction.  
* Page-wise text file conversion.  
* Change detection for files and configurations.

### **3.2. Indexing and Embedding Module**

This module takes the processed text and metadata from the Discovery Module, chunks the text, generates vector embeddings, and stores everything in OpenSearch. It's designed to be modular, allowing for different chunking and embedding algorithms.

**Key Features:**

* Configurable text chunking.  
* Pluggable vector embedding algorithms.  
* OpenSearch integration for indexing.  
* Stop word filtering for text indexing.  
* Tracking of `last_indexed_timestamp`.

### **3.3. LLM Chatbot and Search Module**

This is the core intelligence module, handling user queries. It uses an LLM (Gemini API) to transform natural language queries into vector search queries, performs searches in OpenSearch (both vector and optionally lexical), and formats the results for the UI.

**Key Features:**

* Hindi and Gujarati query language detection.  
* LLM-powered query transformation.  
* Combined vector and lexical search capabilities.  
* Dynamic result count determination (up to 50).  
* Formatted search snippets with highlighted keywords.  
* Pagination support.

### **3.4. UI Module**

The user interface provides a simple and intuitive way for users to interact with the chatbot. It displays a search bar, a search button, and paginated search results with highlighted keywords.

**Key Features:**

* Top banner and informational text.  
* Search input field and button.  
* Paginated search results display.  
* Highlighting of keywords in snippets.  
* Results grouped by file and page number.  
* **Light theme for the UI.**

## **4. Technology Stack**

* **Backend (Python 3.9+):**  
  * pytesseract (for OCR)  
  * PyPDF2 or pdfminer.six (for PDF parsing)  
  * opensearch-py (OpenSearch client)  
  * requests or httpx (for Gemini API calls)  
  * logging (for logging)  
  * json (for config files)  
* **Database/Search Engine:** OpenSearch  
* **Frontend:**  
  * React  
  * Tailwind CSS  
  * lucide-react or inline SVGs (for icons)  
* **Containerization for Testing:** Docker / Testcontainers

## **5. Setup and Installation**

### **5.1. Prerequisites**

* Python 3.9+  
* Docker (for OpenSearch and testing)  
* Tesseract OCR engine installed on your system (ensure it supports Hindi and Gujarati language packs).  
  * For Debian/Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-guj  
  * For macOS (using Homebrew): brew install tesseract tesseract-lang (then download hin.traineddata and guj.traineddata and place them in Tesseract's tessdata directory).

### **5.2. OpenSearch Setup**

The easiest way to run OpenSearch for development and testing is using Docker.

1. **Create a docker-compose.yml file:**
```
   version: '3.8'  
   services:  
     opensearch:  
       image: opensearchproject/opensearch:2.11.0  
       container_name: opensearch-chatbot  
       environment:  
         - discovery.type=single-node  
         - plugins.security.disabled=true # Disable security for local development  
         - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m" # Adjust memory as needed  
       ports:  
         - "9200:9200"  
         - "9600:9600" # For Performance Analyzer  
       volumes:  
         - opensearch_data:/usr/share/opensearch/data  
       ulimits:  
         memlock:  
           soft: -1  
           hard: -1  
       healthcheck:  
         test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health?wait_for_status=yellow || exit 1"]  
         interval: 10s  
         timeout: 10s  
         retries: 5  
   volumes:  
     opensearch_data:
```

2. **Start OpenSearch:**  
 
   ```
   docker-compose up -d
   ```

    Wait for OpenSearch to be healthy before proceeding. You can check its status with `docker-compose ps` or `docker-compose logs opensearch`.

### **5.3. Backend Setup**

1. **Clone the repository:**
```
   git clone git@github.com:rajatjain/cataloguesearch.git  
   cd cataloguesearch
```

2. **Create a virtual environment:**  
```
   python3 -m venv venv  
   source venv/bin/activate
```

3. **Install dependencies:**  
```
   pip install -r requirements.txt
```
   
4. Configuration:  
   Create a `config.ini` or `config.json` file to configure paths, OpenSearch connection details, and Gemini API key.

### **5.4. Frontend Setup**

1. **Navigate to the frontend directory:**  
```
   cd frontend
```

3. **Install Node.js dependencies:**  
```
   npm install  
   # or yarn install
```

4. **Start the frontend development server:**  
```
   npm start  
   # or yarn start
```

  This will typically open the application in your browser at `http://localhost:3000`.

## **6. Usage**

### **6.1. Discovery Module Execution**

The Discovery Module is designed to be run manually.

1. **Prepare your PDF files:** Place your Hindi and Gujarati PDF files within the `base_pdf_folder` (as configured in your backend settings). Create sub-folders and corresponding `config.json` files as needed.  
   * Example structure:
```
     data/  
     ├── config.json  
     ├── folder_a/  
     │   ├── config.json  
     │   ├── doc_a.pdf  
     │   └── doc_a_config.json  
     └── folder_b/  
         ├── config.json  
         └── doc_b.pdf
```

2. **Run the Discovery script:**  
```
   python backend/discovery_module/run_discovery.py
```

   This will scan for new files, perform OCR, generate page-wise text files, and trigger indexing into OpenSearch. Subsequent runs will detect changes and re-index only what's necessary.

### **6.2. Chatbot Interaction**

1. Ensure both the OpenSearch container and the backend server are running.  
2. Access the UI in your web browser (e.g., `http://localhost:3000`).  
3. Enter your search query in Hindi or Gujarati into the search bar and click "Search".  
4. The results will be displayed below, paginated, with relevant keywords highlighted.

## **7. Logging**

The system uses Python's standard logging module. Logging levels (INFO, WARNING, ERROR, CRITICAL, DEBUG) and output destinations (console, file) can be configured. Refer to the `logging_config.py` file in the backend for details.

## **8. Testing**

Unit tests are provided for each module. These tests utilize Docker/Testcontainers for OpenSearch integration tests and programmatic file system setup for the Discovery Module, avoiding the use of mock objects.

To run tests:

```
python -m pytest
```

## **9. Future Enhancements**

* **Scalability:** Implement distributed processing for large datasets.  
* **Advanced OCR:** Integrate with more robust commercial or open-source OCR solutions for improved accuracy.  
* **Fine-tuned Embeddings:** Explore domain-specific embedding model fine-tuning.  
* **User Authentication:** Add user authentication and authorization features.  
* **Monitoring:** Implement comprehensive monitoring and alerting for system health and performance.

## **10. Contributing**

Contributions are welcome! Please refer to CONTRIBUTING.md (to be created) for guidelines.

## **11. License**

This project is licensed under the [MIT License](https://www.google.com/search?q=LICENSE) (to be created).
