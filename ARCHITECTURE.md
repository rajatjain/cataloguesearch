# Discovery Module

## Overview

The Discovery module is the core data processing pipeline of CatalogueSearch, responsible for discovering, processing, and indexing multilingual PDF documents into a searchable format. It implements a sophisticated ETL (Extract, Transform, Load) pipeline optimized for Hindi and Gujarati documents with advanced OCR capabilities and intelligent text processing.

## Architecture Overview

The Crawler module follows a modular, pipeline-based architecture with clear separation of concerns:

```
┌─────────────┐    ┌───────────────┐    ┌──────────────┐    ┌─────────────┐
│  Discovery  │───▶│      PDF      │───▶│ Paragraph    │───▶│   Index     │
│   Module    │    │   Processor   │    │  Generator   │    │ Generator   │
└─────────────┘    └───────────────┘    └──────────────┘    └─────────────┘
       │                    │                   │                   │
       ▼                    ▼                   ▼                   ▼
┌─────────────┐    ┌───────────────┐    ┌──────────────┐    ┌─────────────┐
│ Index State │    │  OCR Engine   │    │ Language     │    │ OpenSearch  │
│ Management  │    │ (Tesseract/   │    │ Processors   │    │   Index     │
│             │    │ Google Vision)│    │ (Hi / Gu)    │    │             │
└─────────────┘    └───────────────┘    └──────────────┘    └─────────────┘
```

Discovery Module and PDF Processing Engine are self-explanatory. 

## Paragraph Generator

Paragraph Generator is the heart of the system. Without efficient paragraph generation, quality of indices & search results will be poor.
Hence, paragraph generation is carefully written to extract the paragraphs as accurately as they are present in the original PDF files.

This involves multiple strategies including

* Accurate detection of headers & footers and ignoring them from the index designed specially to handle indic languages and the type of source PDF documents
* Extensible framework to specify generic rules and extensible rules per category of PDF files
* Efficient chunking of paragraphs to ensure Q&A chunks occur in a single paragraph 
* Ensuring that paragraphs that span multiple pages are part of the same chunk

More details here: [https://github.com/rajatjain/cataloguesearch/issues/24](https://github.com/rajatjain/cataloguesearch/issues/24) and [https://github.com/rajatjain/cataloguesearch/issues/30](https://github.com/rajatjain/cataloguesearch/issues/30).

## OpenSearch Index
OpenSearch Index is also carefully designed to handle hybrid search tailored for indic content

* Allows proximity search
* Liberal with typos
* Handling of indic nuances like Anusvar & Halant (eg. शांति and शान्ति)

Vector Embeddings are part of the same index to allow
* Hybrid Search
* Support for using `reranker` models for higher quality of search results.
