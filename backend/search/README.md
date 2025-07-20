# Catalogue Search API Design

This document outlines the design of an API for querying an OpenSearch index, incorporating both lexical and vector search capabilities, language detection, and category filtering.

## Table of Contents

1. [API Endpoint Definition](#api-endpoint-definition)
2. [Request Payload Structure](#request-payload-structure)
3. [Response Payload Structure](#response-payload-structure)
4. [High-Level Architecture & Flow](#high-level-architecture--flow)
5. [Detailed Component Design](#detailed-component-design)
    - [Language Detection Module](#51-language-detection-module)
    - [OpenSearch Query Builder (Lexical)](#52-opensearch-query-builder-lexical)
    - [Embedding Module (Vector)](#53-embedding-module-vector)
    - [OpenSearch Query Builder (Vector)](#54-opensearch-query-builder-vector)
    - [Result Collation and Ranking Module](#55-result-collation-and-ranking-module)
    - [Highlight Word Extraction](#56-highlight-word-extraction)

---

## 1. API Endpoint Definition

- **Endpoint:** `/search`
- **Method:** `POST`
- **Description:** Performs a search across indexed PDF content based on keywords, categories, and proximity.

---

## 2. Request Payload Structure

The API accepts a JSON payload with the following structure:

```json
{
    "keywords": "string",
    "proximity_distance": "integer",
    "categories": {
        "category_name_1": {"key1":  ["vals1", ... ]},
        "bookmarks": ["keyword_for_bookmark", "another_bookmark_term"]
    },
    "page_size": "integer",
    "page_number": "integer"
}
```

**Field Descriptions:**
  - `keywords` (`string`, required): The main search query containing keywords.
  - `proximity_distance` (`integer`, optional): The maximum word distance between keywords for proximity search. Defaults to 5 if not provided.
  - `categories` (`object`, optional): Dictionary where keys are category names (e.g., `"author"`, `"document_type"`, `"bookmarks"`) and values are arrays of strings representing the specific values to filter for within that category. Documents must match at least one value for each specified category.
  - `page_size` (`integer`, optional): Number of results per page. Default is 10.
  - `page_number` (`integer`, optional): The current page number for pagination. Default is 1.

---

## 3. Response Payload Structure

The API returns a JSON payload structured as follows:

```json
{
    "total_results": "integer",
    "page_size": "integer",
    "page_number": "integer",
    "results": [
        {
            "document_id": "string",
            "page_number": "integer",
            "content_snippet": "string",
            "score": "float",
            "source_file": "string",
            "metadata": {
                "title": "string",
                "author": "string",
                "language": "string",
                "categories": ["string"]
                // ... other relevant metadata fields
            }
        }
    ],
    "highlight_words": ["string"]
}
```

**Field Descriptions:**
- `total_results` (`integer`): The total number of results found.
- `page_size` (`integer`): The number of results per page for the current response.
- `page_number` (`integer`): The current page number.
- `results` (`array of objects`): List of search results, each containing:
    - `document_id` (`string`): Unique identifier for the document.
    - `page_number` (`integer`): Page in the document where the match occurred.
    - `content_snippet` (`string`): Excerpt of content matching the query.
    - `score` (`float`): Combined relevance score.
    - `source_file` (`string`): Path to the original PDF file.
    - `metadata` (`object`): Metadata such as `title`, `author`, `language` (e.g., `"hindi"`, `"gujarati"`, `"english"`), `categories`, and others.
- `highlight_words` (`array of strings`): List of words to highlight in the UI.

---

## 4. High-Level Architecture & Flow

The search API follows these steps:

1. **Receive Request:** Accept the POST request with keywords, proximity, categories, and pagination.
2. **Pre-process Query:**
    - **Language Detection:** Detect the probable language (Hindi, Gujarati, or English) to decide which OpenSearch fields to query.
    - **Keyword Extraction:** Extract individual keywords from the input query.
3. **Perform Lexical Search:**
    - Construct an OpenSearch query using the relevant language field(s) and proximity logic.
    - Apply category filters, including bookmarks.
    - Execute the lexical search.
4. **Perform Vector Search:**
    - Generate a vector embedding for the input keywords.
    - Construct and execute an OpenSearch k-NN (vector) search query.
    - Apply category filters.
5. **Collate and Rank Results:**
    - Combine results from lexical and vector searches.
    - Normalize and rank scores.
    - Apply a ranking algorithm (e.g., Reciprocal Rank Fusion (RRF) or weighted sum).
    - Handle pagination.
6. **Extract Highlight Words:** Identify key terms for UI highlighting.
7. **Return Response:** Return the paginated, ranked results and highlight words.

**Process Diagram (Mermaid):**

```mermaid
graph TD
    A[Client Request] --> B{API Gateway / Load Balancer}
    B --> C[Search API Endpoint]
    C --> D[Request Pre-processing]
    D --> D1{Language Detection}
    D --> D2{Keyword Extraction}
    D1 & D2 --> E[Lexical Search Module]
    D1 & D2 --> F[Vector Embedding Module]
    E --> G[OpenSearch Query Builder (Lexical)]
    F --> H[OpenSearch Query Builder (Vector)]
    G --> I[OpenSearch]
    H --> I
    I --> J[Lexical Search Results]
    I --> K[Vector Search Results]
    J & K --> L[Result Collation & Ranking Module]
    L --> M[Highlight Word Extraction]
    M --> N[Response to Client]
```

---

## 5. Detailed Component Design

### 5.1. Language Detection Module

- **Purpose:** Identify the primary language of the input keywords (Hindi, Gujarati, or English).
- **Approach:**
    - Use a pre-trained language detection library (e.g., `langdetect`, `fasttext`), prioritizing Hindi/Gujarati if model confidence is high.
    - Consider character-based heuristics if libraries are insufficient.
- **Output:** String indicating detected language (e.g., `"hindi"`, `"gujarati"`, `"english"`), mapping to OpenSearch field names.

---

### 5.2. OpenSearch Query Builder (Lexical)

- **Purpose:** Construct the OpenSearch DSL query for lexical search.
- **Logic:**
    - **Proximity Search:** Use `match_phrase` query with `slop` parameter.
    - **Multi-language:** Query detected language field; possibly query multiple fields with boosted scores if detection is uncertain.
    - **Category Filtering:** For `bookmarks`, add a terms/match query; for other categories, add terms queries on corresponding metadata fields, all inside a `bool` filter.
    - **Highlighting:** Include highlight section to get matched snippets.

---

### 5.3. Embedding Module (Vector)

- **Purpose:** Convert input keywords into a vector embedding.
- **Logic:**
    - Load model as specified in `configs/config.yaml`.
    - Encode keywords string to a dense vector using the embedding model.
- **Output:** List of floats (embedding vector).

---

### 5.4. OpenSearch Query Builder (Vector)

- **Purpose:** Construct OpenSearch DSL query for vector (k-NN) search.
- **Logic:**
    - Use OpenSearch k-NN search targeting the `text_vector` field.
    - Use embedding vector as `query_vector`.
    - Apply category filters as in the lexical query.
- **Output:** List of floats (embedding vector).

---

### 5.5. Result Collation and Ranking Module

- **Purpose:** Combine and rank results from lexical and vector searches.
- **Logic:**
    - **Score Normalization:** Normalize lexical (TF-IDF/BM25) and vector (cosine similarity) scores to a common scale.
    - **Combination Strategy:** Use Reciprocal Rank Fusion (RRF) or weighted sum, with possible tuning.
    - **Deduplication:** Remove duplicate documents, keeping the highest combined score.
    - **Pagination:** Apply after ranking.

---

### 5.6. Highlight Word Extraction

- **Purpose:** Provide a list of words to highlight in the UI.
- **Logic:**
    - Start with original keywords.
    - Enhance with significant terms from highlighted content snippets.
    - Clean and deduplicate.