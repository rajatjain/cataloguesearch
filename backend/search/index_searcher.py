import logging
from opensearchpy import OpenSearch, RequestsHttpConnection
import os
from typing import List, Dict, Any, Tuple

from backend.common.opensearch import get_opensearch_config, get_opensearch_client
from backend.utils import json_dumps

log_handle = logging.getLogger(__name__)

class IndexSearcher:
    def __init__(self, config):
        """
        Initializes the IndexSearcher with OpenSearch client and configuration.

        Args:
            config: Configuration object containing OpenSearch settings.
            opensearch_config: Dictionary containing OpenSearch index settings.
        """
        self._config = config
        self._index_name = config.OPENSEARCH_INDEX_NAME
        self._opensearch_config = get_opensearch_config(self._config)
        self._opensearch_client = get_opensearch_client(self._config)
        log_handle.info(f"Initialized IndexSearcher for index: {self._index_name}")

        self._text_fields = {
            "english": "text_content",
            "hindi": "text_content_hindi",
            "gujarati": "text_content_gujarati",
            "en": "text_content",
            "hi": "text_content_hindi",
            "gu": "text_content_gujarati",
        }
        self._vector_field = "vector_embedding"
        self._bookmark_field = "bookmarks"
        self._metadata_prefix = "metadata"

        log_handle.info(f"Initialized IndexSearcher")

    def _build_category_filters(self, categories: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Builds OpenSearch filter clauses for categories.

        Args:
            categories (Dict[str, List[str]]): Dictionary of category names and their values.

        Returns:
            List[Dict[str, Any]]: A list of OpenSearch query clauses for filtering.
        """
        filters = []
        for category_key, values in categories.items():
            if not values:
                continue

            if category_key == "bookmarks":
                # Search in the dedicated bookmark field
                # Using 'match' for text search within bookmarks, 'terms' if bookmarks are exact keywords
                # Assuming bookmarks are text, so using match query
                filters.append({
                    "bool": {
                        "should": [{"match": {self._bookmark_field: value}} for value in values],
                        "minimum_should_match": 1
                    }
                })
                log_handle.debug(f"Added bookmark filter: {self._bookmark_field} with values {values}")
            else:
                # Search in metadata fields using .keyword for exact matching
                field_name = f"{self._metadata_prefix}.{category_key}.keyword"
                filters.append({
                    "terms": {
                        field_name: values
                    }
                })
                log_handle.debug(f"Added metadata filter: {field_name} with values {values}")
        return filters

    def _build_lexical_query(
            self, keywords: str, proximity_distance: int,
            categories: Dict[str, List[str]], detected_language: str) -> Dict[str, Any]:
        """
        Builds the OpenSearch DSL query for lexical search.

        Args:
            keywords (str): The search keywords.
            proximity_distance (int): The maximum word distance for proximity search.
            categories (Dict[str, List[str]]): Category filters.
            detected_language (str): The detected language of the keywords.

        Returns:
            Dict[str, Any]: The OpenSearch query body.
        """
        query_field = self._text_fields.get(detected_language) # Fallback to English
        if not query_field:
            log_handle.warning(f"Detected language '{detected_language}' not supported. Defaulting to English field.")
            return {}
        log_handle.verbose(f"Lexical search targeting field: {query_field} for language: {detected_language}")

        query_body = {
            "query": {
                "bool": {
                    "must": [{
                        "match_phrase": {
                            query_field: {
                                "query": keywords,
                                "slop": proximity_distance,
                            }
                        }
                    }]
                }
            },
            "highlight": {
                "fields": {
                    query_field: {
                        "pre_tags": ["<em>"],
                        "post_tags": ["</em>"],
                        "fragment_size": 150,
                        "number_of_fragments": 1
                    }
                }
            }
        }

        category_filters = self._build_category_filters(categories)
        if category_filters:
            query_body["query"]["bool"]["filter"] = category_filters
            log_handle.debug(f"Added {len(category_filters)} category filters to lexical query.")

        log_handle.verbose(f"Lexical query: {json_dumps(query_body)}")

        return query_body

    def _build_vector_query(
            self, embedding: List[float],
            categories: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Builds the OpenSearch DSL query for vector (k-NN) search.

        Args:
            embedding (List[float]): The query vector embedding.
            categories (Dict[str, List[str]]): Category filters.

        Returns:
            Dict[str, Any]: The OpenSearch query body.
        """
        # Ensure k-NN plugin is enabled and vector field is mapped correctly in OpenSearch
        # This assumes the vector field is configured for k-NN search.
        query_body = {
            "size": 10, # k-NN typically requires a size parameter
            "query": {
                "knn": {
                    self._vector_field: {
                        "vector": embedding,
                        "k": 10 # Number of nearest neighbors to return from the vector search
                    }
                }
            }
        }
        log_handle.verbose(
            f"Vector query: {json_dumps(query_body, truncate_fields=['vector'])}")

        category_filters = self._build_category_filters(categories)
        log_handle.verbose(f"Category filters: {category_filters}")
        if category_filters:
            # k-NN with filters requires a 'post_filter' or combining with a 'bool' query
            # For simplicity, we'll use a bool query with filter.
            # Note: The exact structure for combining KNN with filters might vary based on OpenSearch version
            # and k-NN plugin configuration. This is a common pattern.
            query_body["query"] = {
                "bool": {
                    "must": [
                        query_body["query"] # The KNN query itself
                    ],
                    "filter": category_filters
                }
            }
            log_handle.debug(f"Added {len(category_filters)} category filters to vector query.")
        return query_body

    def _extract_results(
            self, hits: List[Dict[str, Any]],
            is_lexical: bool = True, language=None) -> List[Dict[str, Any]]:
        """
        Extracts relevant information from OpenSearch hits.

        Args:
            hits (List[Dict[str, Any]]): List of hit dictionaries from OpenSearch response.
            is_lexical (bool): True if results are from lexical search (for highlight extraction).

        Returns:
            List[Dict[str, Any]]: A list of simplified result dictionaries.
        """
        extracted = []
        for hit in hits:
            source = hit.get('_source', {})
            document_id = hit.get('_id')
            score = hit.get('_score')
            content_snippet = None

            if is_lexical:
                if language is None:
                    language = 'en'
                field = self._text_fields.get(language)
                content_snippet = source.get(field, '')
            elif not is_lexical:
                # For vector search, we might just take a snippet of the content
                field = self._text_fields.get('en')
                content_snippet = source.get(field)

            # TODO(rajatjain): Disable highlights for now. Just share the snippet
            """
            if is_lexical and 'highlight' in hit and self._text_fields['en'] in hit['highlight']:
                # Assuming English field is a good fallback for highlights if language-specific isn't present
                # Or, ideally, use the detected language field from the original query
                highlight_field_name = None
                for lang_key in self._text_fields.values():
                    if lang_key in hit['highlight']:
                        highlight_field_name = lang_key
                        break
                if highlight_field_name:
                    content_snippet = " ... ".join(hit['highlight'][highlight_field_name])
                else:
                    log_handle.warning(f"No highlight found for expected text fields in hit {document_id}. Using raw content.")
                    content_snippet = source.get(self._text_fields.get('en'), '') + '...' # Fallback to raw snippet
            """

            # Extract metadata, handling potential missing 'metadata' key
            metadata = source.get(self._metadata_prefix, {})
            # Ensure 'categories' in metadata is a list of strings
            metadata_categories = metadata.get('categories', [])
            if not isinstance(metadata_categories, list):
                metadata_categories = [str(metadata_categories)] # Ensure it's a list

            extracted.append({
                "document_id": document_id,
                "original_filename": source.get('original_filename'),
                "page_number": source.get('page_number'),
                "content_snippet": content_snippet,
                "score": score,
                "bookmarks": source.get(self._bookmark_field, {}),
                "metadata": source.get(self._metadata_prefix, {})
            })
        return extracted

    def perform_lexical_search(
            self, keywords: str, proximity_distance: int, categories: Dict[str, List[str]],
            detected_language: str, page_size: int, page_number: int) -> Tuple[List[Dict[str, Any]], int]:
        """
        Performs a lexical search in OpenSearch.

        Args:
            keywords (str): The search keywords.
            proximity_distance (int): The maximum word distance for proximity search.
            categories (Dict[str, List[str]]): Category filters.
            detected_language (str): The detected language of the keywords.
            page_size (int): Number of results per page.
            page_number (int): Page number for pagination.

        Returns:
            Tuple[List[Dict[str, Any]], int]: A tuple containing the list of lexical results and total hits.
        """
        query_body = self._build_lexical_query(keywords, proximity_distance, categories, detected_language)
        from_ = (page_number - 1) * page_size
        log_handle.verbose(f"Lexical query: {json_dumps(query_body)}")
        try:
            response = self._opensearch_client.search(
                index=self._index_name,
                body=query_body,
                size=page_size,
                from_=from_
            )
            hits = response.get('hits', {}).get('hits', [])
            total_hits = response.get('hits', {}).get('total', {}).get('value', 0)
            log_handle.info(f"Lexical search executed. Total hits: {total_hits}.")
            return self._extract_results(hits, is_lexical=True, language=detected_language), total_hits
        except Exception as e:
            log_handle.error(f"Error during lexical search: {e}", exc_info=True)
            return [], 0

    def perform_vector_search(
            self, embedding: List[float], categories: Dict[str, List[str]],
            page_size: int, page_number: int, language) -> Tuple[List[Dict[str, Any]], int]:
        """
        Performs a vector (k-NN) search in OpenSearch.

        Args:
            embedding (List[float]): The query vector embedding.
            categories (Dict[str, List[str]]): Category filters.
            page_size (int): Number of results per page.
            page_number (int): Page number for pagination.

        Returns:
            Tuple[List[Dict[str, Any]], int]: A tuple containing the list of vector results and total hits.
        """
        query_body = self._build_vector_query(embedding, categories)
        from_ = (page_number - 1) * page_size # k-NN often ignores 'from' for ranking, but include for consistency
        log_handle.debug(f"Vector query: {query_body}")
        try:
            response = self._opensearch_client.search(
                index=self._index_name,
                body=query_body,
                size=page_size, # k-NN 'k' param is for number of nearest neighbors, 'size' is for results returned
                from_=from_
            )
            hits = response.get('hits', {}).get('hits', [])
            log_handle.verbose(f"Vector search response: {json_dumps(response, truncate_fields=['vector_embedding'])}")
            total_hits = response.get('hits', {}).get('total', {}).get('value', 0)
            log_handle.info(f"Vector search executed. Total hits: {total_hits}.")
            return self._extract_results(hits, is_lexical=False, language=language), total_hits
        except Exception as e:
            log_handle.error(f"Error during vector search: {e}", exc_info=True)
            return [], 0

