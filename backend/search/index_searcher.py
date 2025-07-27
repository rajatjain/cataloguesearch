import logging
from opensearchpy import OpenSearch, RequestsHttpConnection
import os
from typing import List, Dict, Any, Tuple

from backend.common.opensearch import get_opensearch_config, get_opensearch_client
from backend.search.highlight_extractor import HighlightExtractor
from backend.utils import json_dumps

log_handle = logging.getLogger(__name__)

class IndexSearcher:
    def __init__(self, config):
        """
        Initializes the IndexSearcher with OpenSearch client and configuration.

        Args:
            config: Configuration object containing OpenSearch settings.
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

    def _build_category_filters(self, categories: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        filters = []
        for category_key, values in categories.items():
            if not values:
                continue

            if category_key == "bookmarks":
                filters.append({
                    "bool": {
                        "should": [{"match": {self._bookmark_field: value}} for value in values],
                        "minimum_should_match": 1
                    }
                })
                log_handle.debug(f"Added bookmark filter: {self._bookmark_field} with values {values}")
            else:
                field_name = f"{self._metadata_prefix}.{category_key}.keyword"
                filters.append({
                    "terms": {
                        field_name: values
                    }
                })
                log_handle.debug(f"Added metadata filter: {field_name} with values {values}")
        return filters

    def _build_lexical_query(
            self, keywords: str, proximity_distance: int, allow_typos: bool,
            categories: Dict[str, List[str]], detected_language: str) -> Dict[str, Any]:
        """
        Builds the OpenSearch DSL query for lexical search.
        When proximity_distance is 0, performs exact phrase match.
        allow_typos determines if fuzzy matching is allowed.
        """
        query_field = self._text_fields.get(detected_language, 'text_content')
        if not query_field:
            log_handle.warning(f"Detected language '{detected_language}' not supported. Defaulting to English field.")
            query_field = 'text_content'

        is_exact_phrase = proximity_distance == 0

        # Determine which analyzer to use for highlighting
        analyzer_name = None
        if detected_language == "hi":
            analyzer_name = "hindi_analyzer"
        elif detected_language == "gu":
            analyzer_name = "gujarati_analyzer"

        log_handle.verbose(f"Lexical search targeting field: {query_field} for language: {detected_language}, "
                           f"exact_phrase: {is_exact_phrase}, allow_typos: {allow_typos}")

        # Build the main query based on allow_typos and proximity
        if allow_typos:
            if is_exact_phrase:
                # Fuzzy exact phrase match - prioritize exact matches strongly
                main_query = {
                    "bool": {
                        "should": [
                            {
                                "match_phrase": {
                                    query_field: {
                                        "query": keywords,
                                        "slop": 0,
                                        "boost": 10  # Very high boost for exact matches
                                    }
                                }
                            },
                            {
                                "match": {
                                    query_field: {
                                        "query": keywords,
                                        "fuzziness": "AUTO",
                                        "operator": "and",
                                        "boost": 1  # Standard boost for fuzzy fallback
                                    }
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                }
            else:
                # Fuzzy proximity match
                main_query = {
                    "bool": {
                        "should": [
                            {
                                "match_phrase": {
                                    query_field: {
                                        "query": keywords,
                                        "slop": proximity_distance,
                                        "boost": 2
                                    }
                                }
                            },
                            {
                                "match": {
                                    query_field: {
                                        "query": keywords,
                                        "fuzziness": "AUTO",
                                        "operator": "and"
                                    }
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                }
        else:  # strict
            # Strict phrase match (with or without proximity)
            main_query = {
                "match_phrase": {
                    query_field: {
                        "query": keywords,
                        "slop": proximity_distance
                    }
                }
            }

        # Build highlight configuration
        if is_exact_phrase and not allow_typos:
            # For exact phrase without typos, highlight the entire phrase together
            highlight_config = {
                "fields": {
                    query_field: {
                        "pre_tags": ["<em>"],
                        "post_tags": ["</em>"],
                        "number_of_fragments": 0,
                        "type": "unified",
                        "highlight_query": {
                            "match_phrase": {
                                query_field: {
                                    "query": keywords,
                                    "slop": 0
                                }
                            }
                        }
                    }
                }
            }
        else:
            # For proximity/fuzzy search
            if allow_typos:
                # For fuzzy search, use the main query for highlighting
                highlight_config = {
                    "fields": {
                        query_field: {
                            "pre_tags": ["<em>"],
                            "post_tags": ["</em>"],
                            "number_of_fragments": 0,
                            "type": "unified",
                            "highlight_query": main_query
                        }
                    }
                }
            else:
                # For strict proximity search, simple highlighting
                highlight_config = {
                    "fields": {
                        query_field: {
                            "pre_tags": ["<em>"],
                            "post_tags": ["</em>"],
                            "number_of_fragments": 0,
                            "type": "unified"
                        }
                    }
                }

        # Build the final query body
        query_body = {
            "query": {
                "bool": {
                    "must": [main_query]
                }
            },
            "highlight": highlight_config
        }

        # Add category filters
        category_filters = self._build_category_filters(categories)
        if category_filters:
            query_body["query"]["bool"]["filter"] = category_filters
            log_handle.debug(f"Added {len(category_filters)} category filters to lexical query.")

        log_handle.verbose(f"Lexical query: {json_dumps(query_body)}")

        return query_body

    def _build_vector_query(
            self, embedding: List[float],
            categories: Dict[str, List[str]]) -> Dict[str, Any]:
        query_body = {
            "size": 10,
            "query": {
                "knn": {
                    self._vector_field: {
                        "vector": embedding,
                        "k": 10
                    }
                }
            }
        }
        log_handle.verbose(
            f"Vector query: {json_dumps(query_body, truncate_fields=['vector'])}")

        category_filters = self._build_category_filters(categories)
        if category_filters:
            query_body["query"] = {
                "bool": {
                    "must": [
                        query_body["query"]
                    ],
                    "filter": category_filters
                }
            }
            log_handle.debug(f"Added {len(category_filters)} category filters to vector query.")
        return query_body

    def _extract_results(
            self, hits: List[Dict[str, Any]],
            is_lexical: bool = True, language=None) -> List[Dict[str, Any]]:
        extracted = []
        for hit in hits:
            source = hit.get('_source', {})
            document_id = hit.get('_id')
            score = hit.get('_score')
            content_snippet = ""

            if is_lexical:
                if language is None:
                    language = 'hi'
                field = self._text_fields.get(language)

                # Prioritise the highlighted content if available
                highlighted_fragment = hit.get('highlight', {}).get(field, '')
                if highlighted_fragment:
                    content_snippet = "...".join(highlighted_fragment)
            elif not is_lexical:
                # For vector search, we might just take a snippet of the content
                field = self._text_fields.get(language or 'hi')
                content_snippet = source.get(field)

            metadata = source.get(self._metadata_prefix, {})
            metadata_categories = metadata.get('categories', [])
            if not isinstance(metadata_categories, list):
                metadata_categories = [str(metadata_categories)]

            extracted.append({
                "document_id": document_id,
                "original_filename": source.get('original_filename'),
                "page_number": source.get('page_number'),
                "content_snippet": content_snippet,
                "score": score,
                "bookmarks": source.get(self._bookmark_field, {}),
                "metadata": source.get(self._metadata_prefix, {}),
            })
        return extracted

    def perform_lexical_search(
            self, keywords: str, proximity_distance: int, allow_typos: bool,
            categories: Dict[str, List[str]], detected_language: str,
            page_size: int, page_number: int) -> Tuple[List[Dict[str, Any]], int]:
        query_body = self._build_lexical_query(keywords, proximity_distance,
                                               allow_typos, categories, detected_language)
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
            log_handle.info(
                f"Lexical search response: {json_dumps(response, truncate_fields=['content_snippet'])}")
            return self._extract_results(hits, is_lexical=True, language=detected_language), total_hits
        except Exception as e:
            log_handle.error(f"Error during lexical search: {e}", exc_info=True)
            return [], 0

    def perform_vector_search(
            self, embedding: List[float], categories: Dict[str, List[str]],
            page_size: int, page_number: int, language) -> Tuple[List[Dict[str, Any]], int]:
        query_body = self._build_vector_query(embedding, categories)
        from_ = (page_number - 1) * page_size
        log_handle.debug(f"Vector query: {query_body}")
        try:
            response = self._opensearch_client.search(
                index=self._index_name,
                body=query_body,
                size=page_size,
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
