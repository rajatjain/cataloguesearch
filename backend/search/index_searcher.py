import logging
import os
import string
import time
import traceback
from typing import List, Dict, Any, Tuple

from opensearchpy import NotFoundError

from backend.common.opensearch import get_opensearch_config, get_opensearch_client
from backend.common.embedding_models import get_embedding_model_factory
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
            "hindi": "text_content_hindi",
            "gujarati": "text_content_gujarati",
            "hi": "text_content_hindi",
            "gu": "text_content_gujarati",
        }
        self._vector_field = "vector_embedding"
        self._bookmark_field = "bookmarks"
        self._metadata_prefix = "metadata"
        try:
            embedding_model = get_embedding_model_factory(self._config)
            self._reranker = embedding_model.get_reranking_model()
            log_handle.info(
                f"Using embedding model type '{self._config.EMBEDDING_MODEL_TYPE}' for reranking")
        except Exception:
            traceback.print_exc()
            self._reranker = None

        log_handle.info("Initialized IndexSearcher")

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
                log_handle.debug(
                    f"Added bookmark filter: {self._bookmark_field} with values {values}")
            else:
                field_name = f"{self._metadata_prefix}.{category_key}.keyword"
                filters.append({
                    "terms": {
                        field_name: values
                    }
                })
                log_handle.debug(f"Added metadata filter: {field_name} with values {values}")
        return filters

    def _build_language_filter(self, language: str) -> Dict[str, Any]:
        """Build language filter that works for both indexes using metadata.language"""
        if not language or language == 'all':
            return None
        
        # Convert language name to code
        language_code_map = {"hindi": "hi", "gujarati": "gu",
                             "gu": "gu", "hi": "hi"}
        language_code = language_code_map.get(language, language)
        
        # Same filter works for both indexes since both have metadata.language
        return {
            "term": {
                "metadata.language": language_code
            }
        }

    def _build_multi_field_lexical_query(
            self, index_name: str, search_fields: List[str], keywords: str,
            exact_match: bool, exclude_words: List[str],
            categories: Dict[str, List[str]], language: str) -> Dict[str, Any]:
        """
        Builds the OpenSearch DSL query for multi-field lexical search.
        Works with both search_index and granth_index.
        """
        log_handle.verbose(
            f"Multi-field lexical search on index: {index_name}, "
            f"fields: {search_fields}, language: {language}, "
            f"exact_match: {exact_match}, exclude_words: {exclude_words}")

        # Check if we're searching the granth index (which has nested verses)
        is_nested_search = index_name == self._config.OPENSEARCH_GRANTH_INDEX_NAME

        # Build the main query based on exact_match and nested structure
        if is_nested_search:
            # For granth index with nested verses field
            if exact_match:
                inner_query = {
                    "multi_match": {
                        "query": keywords,
                        "fields": search_fields,
                        "type": "phrase"
                    }
                }
            else:
                inner_query = {
                    "multi_match": {
                        "query": keywords,
                        "fields": search_fields,
                        "type": "best_fields",
                        "operator": "or"
                    }
                }

            # Build highlight configuration for nested fields
            highlight_fields = {}
            for field in search_fields:
                highlight_fields[field] = {}

            main_query = {
                "nested": {
                    "path": "verses",
                    "query": inner_query,
                    "inner_hits": {
                        "highlight": {
                            "fields": highlight_fields
                        }
                    }
                }
            }
            # For nested queries, we don't need root-level highlighting
            highlight_config = None
        else:
            # For regular search index (non-nested fields)
            if exact_match:
                # Exact phrase match across all fields
                main_query = {
                    "multi_match": {
                        "query": keywords,
                        "fields": search_fields,
                        "type": "phrase"
                    }
                }
            else:
                # Regular match with all terms across all fields
                main_query = {
                    "multi_match": {
                        "query": keywords,
                        "fields": search_fields,
                        "type": "best_fields",
                        "operator": "and"
                    }
                }

            # Build highlight configuration for all search fields
            highlight_fields = {}
            for field in search_fields:
                highlight_fields[field] = {
                    "pre_tags": ["<em>"],
                    "post_tags": ["</em>"],
                    "number_of_fragments": 0,
                    "type": "unified",
                    "highlight_query": main_query
                }

            highlight_config = {
                "fields": highlight_fields
            }

        # Build the final query body
        bool_query = {
            "must": [main_query]
        }

        # Add exclude words as must_not clauses
        if exclude_words:
            must_not_clauses = []
            for word in exclude_words:
                must_not_clauses.append({
                    "multi_match": {
                        "query": word,
                        "fields": search_fields
                    }
                })
            bool_query["must_not"] = must_not_clauses
            log_handle.debug(f"Added {len(exclude_words)} exclude words to multi-field lexical query.")

        query_body = {
            "query": {
                "bool": bool_query
            },
            "track_total_hits": 1000
        }

        # Only add root-level highlight for non-nested queries
        if highlight_config:
            query_body["highlight"] = highlight_config

        # Add filters
        filters = []
        
        # Add category filters
        category_filters = self._build_category_filters(categories)
        if category_filters:
            filters.extend(category_filters)
            
        # Add language filter
        language_filter = self._build_language_filter(language)
        if language_filter:
            filters.append(language_filter)
            
        if filters:
            query_body["query"]["bool"]["filter"] = filters
            log_handle.debug(f"Added {len(filters)} filters to multi-field lexical query.")

        log_handle.verbose(f"Multi-field lexical query: {json_dumps(query_body)}")

        return query_body

    def _build_lexical_query(
            self, keywords: str, exact_match: bool, exclude_words: List[str],
            categories: Dict[str, List[str]], detected_language: str) -> Dict[str, Any]:
        """
        Builds the OpenSearch DSL query for lexical search.
        exact_match determines if exact phrase match is used.
        exclude_words are terms to exclude from results.
        """
        query_field = self._text_fields.get(detected_language)
        if not query_field:
            log_handle.warning(
                f"Detected language '{detected_language}' not supported. "
                f"Defaulting to Hindi field.")
            query_field = 'text_content_hindi'

        log_handle.verbose(
            f"Lexical search targeting field: {query_field} for language: {detected_language}, "
            f"exact_match: {exact_match}, exclude_words: {exclude_words}")

        # Build the main query based on exact_match
        if exact_match:
            # Exact phrase match
            main_query = {
                "match_phrase": {
                    query_field: {
                        "query": keywords
                    }
                }
            }
        else:
            # Regular match with all terms
            main_query = {
                "match": {
                    query_field: {
                        "query": keywords,
                        "operator": "and"
                    }
                }
            }

        # Build highlight configuration
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

        # Build the final query body
        bool_query = {
            "must": [main_query]
        }

        # Add exclude words as must_not clauses
        if exclude_words:
            must_not_clauses = []
            for word in exclude_words:
                must_not_clauses.append({
                    "match": {
                        query_field: word
                    }
                })
            bool_query["must_not"] = must_not_clauses
            log_handle.debug(f"Added {len(exclude_words)} exclude words to lexical query.")
        query_body = {
            "query": {
                "bool": bool_query
            },
            "highlight": highlight_config,
            "track_total_hits": 1000
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
            categories: Dict[str, List[str]], size: int, language: str = None) -> Dict[str, Any]:
        knn_query = {
            self._vector_field: {
                "vector": embedding,
                "k": size
            }
        }

        # Build category filters
        category_filters = self._build_category_filters(categories)
        
        # Add language filter if specified
        all_filters = category_filters[:]
        if language and language != 'all':
            # Convert language name to language code for filtering
            language_code_map = {"hindi": "hi", "gujarati": "gu"}
            language_code = language_code_map.get(language, language)
            
            language_filter = {
                "term": {
                    "language": language_code
                }
            }
            all_filters.append(language_filter)
            log_handle.debug(f"Added language filter for: {language} (code: {language_code})")
        
        if all_filters:
            # For filtered vector search, add filters directly to the knn query
            knn_query[self._vector_field]["filter"] = {
                "bool": {
                    "filter": all_filters
                }
            }
            log_handle.debug(f"Added {len(all_filters)} total filters to vector query.")
        query_body = {
            "size": size,
            "query": {
                "knn": knn_query
            }
        }

        log_handle.verbose(
            f"Vector query: {json_dumps(query_body, truncate_fields=['vector'])}")
        return query_body

    def _extract_results(
            self, hits: List[Dict[str, Any]],
            is_lexical: bool = True, language=None) -> List[Dict[str, Any]]:
        extracted = []
        for hit in hits:
            source = hit.get('_source', {})
            document_id = hit.get('_id')
            score = hit.get("rerank_score", hit.get("_score"))
            content_snippet = ""

            if is_lexical:
                if language is None:
                    language = 'hi'
                field = self._text_fields.get(language)

                # Prioritise the highlighted content if available
                highlighted_fragment = hit.get('highlight', {}).get(field, [])
                if highlighted_fragment:
                    content_snippet = "...".join(highlighted_fragment)
            elif not is_lexical:
                # For vector search, we might just take a snippet of the content
                field = self._text_fields.get(language or 'hi', 'text_content_hindi')
                content_snippet = source.get(field)

            metadata = source.get(self._metadata_prefix, {})
            metadata_categories = metadata.get('categories', [])
            if not isinstance(metadata_categories, list):
                metadata_categories = [str(metadata_categories)]

            original_filename = source.get('original_filename')
            filename = os.path.basename(original_filename)

            result = {
                "document_id": document_id,
                "original_filename": source.get('original_filename'),
                "filename": filename,
                "page_number": source.get('page_number'),
                "paragraph_id": source.get('paragraph_id'),
                "content_snippet": content_snippet,
                "score": float(score) if score is not None else 0.0,
                "bookmarks": source.get(self._bookmark_field, {}),
                "metadata": source.get(self._metadata_prefix, {}),
                "file_url": metadata.get("file_url", "")
            }
            if "Kanji" in metadata.get("Pravachankar", {}):
                # Set Pravachankar text based on language
                if language in ['gujarati', 'gu']:
                    result["Pravachankar"] = "પૂજ્ય ગુરુદેવશ્રી કાંજી સ્વામી, સોનગઢ"
                else:
                    result["Pravachankar"] = "पूज्य गुरुदेव श्री कांजी स्वामी, सोनगढ़"
            extracted.append(result)
        return extracted

    def perform_multi_field_lexical_search(
            self, index_name: str, search_fields: List[str], keywords: str, 
            exact_match: bool, exclude_words: List[str],
            categories: Dict[str, List[str]], language: str,
            page_size: int, page_number: int) -> Tuple[List[Dict[str, Any]], int]:
        """
        Generalized multi-field lexical search that works with both search_index and granth_index.
        
        Args:
            index_name: Target index (OPENSEARCH_INDEX_NAME or OPENSEARCH_GRANTH_INDEX_NAME)
            search_fields: List of fields to search across
            keywords: Search terms
            exact_match: Whether to use exact phrase matching
            exclude_words: Words to exclude from results
            categories: Filters for metadata categories and bookmarks
            language: Language for filtering (hi, gu, or 'all')
            page_size: Number of results per page
            page_number: Page number for pagination
            
        Returns:
            Tuple of (results_list, total_hits_count)
        """
        query_body = self._build_multi_field_lexical_query(
            index_name, search_fields, keywords, exact_match,
            exclude_words, categories, language)
        from_ = (page_number - 1) * page_size

        try:
            response = self._opensearch_client.search(
                index=index_name,
                body=query_body,
                size=page_size,
                from_=from_
            )
            hits = response.get('hits', {}).get('hits', [])
            total_hits = response.get('hits', {}).get('total', {}).get('value', 0)
            log_handle.info(
                f"Multi-field lexical search executed on index '{index_name}'. Total hits: {total_hits}.")
            log_handle.info(
                f"Multi-field lexical search response: "
                f"{json_dumps(response, truncate_fields=['content_snippet', 'vector_embedding'])}")
            
            # Use appropriate result extraction based on index
            if index_name == self._config.OPENSEARCH_GRANTH_INDEX_NAME:
                extracted_results = self._extract_granth_results(hits, search_fields, language)
                return extracted_results, total_hits
            else:
                # For search index, use existing extraction logic
                return (self._extract_results(hits, is_lexical=True, language=language),
                        total_hits)
            
        except Exception as e:
            log_handle.error(f"Error during multi-field lexical search: {e}", exc_info=True)
            return [], 0

    def _extract_granth_results(
            self, hits: List[Dict[str, Any]], search_fields: List[str],
            language: str) -> List[Dict[str, Any]]:
        """Extract and format results for granth index search"""
        extracted = []
        for hit in hits:
            source = hit.get('_source', {})
            document_id = hit.get('_id')
            score = hit.get("rerank_score", hit.get("_score"))

            # Extract matching verses from inner_hits (if available from nested query)
            matching_verses = []
            inner_hits = hit.get('inner_hits', {})

            # Handle content snippet from highlighting in inner_hits
            content_snippet = ""
            highlighted_fragments = []

            if inner_hits and 'verses' in inner_hits:
                # Get the matching nested documents from inner_hits
                verse_hits = inner_hits['verses'].get('hits', {}).get('hits', [])
                for verse_hit in verse_hits:
                    matching_verses.append(verse_hit.get('_source', {}))

                    # Get highlights from inner_hits
                    verse_highlight = verse_hit.get('highlight', {})
                    if verse_highlight:
                        for field in search_fields:
                            if field in verse_highlight:
                                highlighted_fragments.extend(verse_highlight[field])
            else:
                # Fallback: if no inner_hits, use all verses (shouldn't happen with nested query)
                matching_verses = source.get('verses', [])

            if highlighted_fragments:
                content_snippet = "...".join(highlighted_fragments)

            # If no highlighting, fall back to extracting content from matching verses
            if not content_snippet and matching_verses:
                # Take content from the first matching verse
                first_verse = matching_verses[0]
                verse_text = first_verse.get('verse', '')
                translation = first_verse.get('translation', '')
                content_snippet = f"{verse_text} {translation}".strip()

            metadata = source.get(self._metadata_prefix, {})
            original_filename = source.get('original_filename')
            filename = os.path.basename(original_filename) if original_filename else ""

            result = {
                "document_id": document_id,
                "original_filename": original_filename,
                "filename": filename,
                "content_snippet": content_snippet,
                "score": float(score) if score is not None else 0.0,
                "metadata": metadata,
                "file_url": metadata.get("file_url", ""),
                # Granth-specific fields
                "granth_id": source.get('granth_id'),
                "name": source.get('name', ''),
                "verses": matching_verses  # Only return matching verses, not all verses
            }

            extracted.append(result)
        return extracted

    def perform_pravachan_search(
            self, keywords: str, exact_match: bool, exclude_words: List[str],
            categories: Dict[str, List[str]], detected_language: str,
            page_size: int, page_number: int) -> Tuple[List[Dict[str, Any]], int]:
        """
        Performs lexical search on the pravachan/document search index.
        Wrapper around perform_multi_field_lexical_search for pravachan documents.
        """
        # Map detected language to appropriate search field
        search_fields = []
        if detected_language in ['hindi', 'hi']:
            search_fields = ['text_content_hindi']
        elif detected_language in ['gujarati', 'gu']:
            search_fields = ['text_content_gujarati']
        else:
            # Default to Hindi if language not recognized
            search_fields = ['text_content_hindi']
            log_handle.warning(
                f"Detected language '{detected_language}' not supported. "
                f"Defaulting to Hindi field.")
        
        return self.perform_multi_field_lexical_search(
            index_name=self._config.OPENSEARCH_INDEX_NAME,
            search_fields=search_fields,
            keywords=keywords,
            exact_match=exact_match,
            exclude_words=exclude_words,
            categories=categories,
            language=detected_language,
            page_size=page_size,
            page_number=page_number
        )

    def perform_granth_search(
            self, keywords: str, exact_match: bool, exclude_words: List[str],
            categories: Dict[str, List[str]], language: str,
            page_size: int, page_number: int,
            search_fields: List[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Performs lexical search on the granth index.
        Wrapper around perform_multi_field_lexical_search for granth documents.
        
        Args:
            search_fields: Fields to search in granth index. 
                          Defaults to ['verses.verse', 'verses.translation', 'verses.meaning', 'verses.teeka', 'verses.bhavarth']
        """
        if search_fields is None:
            search_fields = [
                'verses.verse', 
                'verses.translation', 
                'verses.meaning', 
                'verses.teeka', 
                'verses.bhavarth'
            ]
        
        return self.perform_multi_field_lexical_search(
            index_name=self._config.OPENSEARCH_GRANTH_INDEX_NAME,
            search_fields=search_fields,
            keywords=keywords,
            exact_match=exact_match,
            exclude_words=exclude_words,
            categories=categories,
            language=language,
            page_size=page_size,
            page_number=page_number
        )

    def perform_lexical_search(
            self, keywords: str, exact_match: bool, exclude_words: List[str],
            categories: Dict[str, List[str]], detected_language: str,
            page_size: int, page_number: int) -> Tuple[List[Dict[str, Any]], int]:
        """
        Legacy function - delegates to perform_pravachan_search for backward compatibility.
        """
        return self.perform_pravachan_search(
            keywords, exact_match, exclude_words, categories, 
            detected_language, page_size, page_number
        )

    def perform_vector_search(
            self, keywords: str, embedding: List[float], categories: Dict[str, List[str]],
            page_size: int, page_number: int, language: str, rerank: bool = True,
            rerank_top_k: int = 40) -> Tuple[List[Dict[str, Any]], int]:
        initial_fetch_size = rerank_top_k
        from_ = 0 if rerank else (page_number - 1) * page_size

        query_body = self._build_vector_query(embedding, categories, initial_fetch_size, language)
        log_handle.debug(f"Vector query: {query_body}")
        try:
            response = self._opensearch_client.search(
                index=self._index_name,
                body=query_body,
                size=initial_fetch_size,
                from_=from_
            )
            hits = response.get('hits', {}).get('hits', [])
            total_hits = response.get('hits', {}).get('total', {}).get('value', 0)
            log_handle.info(f"Vector search executed. Total hits: {total_hits}.")

            # Rerank, if required
            if not rerank or not self._reranker or not hits:
                log_handle.info(f"Vector search executed (no reranking). Total hits: {total_hits}")
                return self._extract_results(hits, is_lexical=False, language=language), total_hits

            text_field = self._text_fields.get(language, "text_content_hindi")
            log_handle.info(
                f"Performing reranking on {len(hits)} documents for query: '{keywords}'")

            # Create pairs of [query, document_text] for the reranker
            sentence_pairs = []
            for hit in hits:
                doc_text = hit["_source"].get(text_field, "")
                # Only apply text truncation - safest optimization
                truncated_text = doc_text[:1000] if len(doc_text) > 1000 else doc_text
                sentence_pairs.append([keywords, truncated_text])

            log_handle.info("--- Starting expensive reranker.predict() call... ---")
            rerank_start_time = time.time()
            # Use very small batch size for e2-medium
            rerank_scores = self._reranker.predict(
                sentence_pairs)
            rerank_duration = time.time() - rerank_start_time
            log_handle.info(
                f"--- Reranker.predict() finished. Took {rerank_duration:.2f} seconds. ---")

            for hit, score in zip(hits, rerank_scores):
                hit["rerank_score"] = score

            # Sort results based on the new reranked score
            reranked_hits = sorted(hits, key=lambda x: x["rerank_score"], reverse=True)

            # Paginate the final, sorted results
            start_index = (page_number - 1) * page_size
            end_index = start_index + page_size
            paginated_hits = reranked_hits[start_index:end_index]

            return (self._extract_results(paginated_hits, is_lexical=False, language=language),
                    total_hits)
        except Exception as e:
            log_handle.error(f"Error during vector search: {e}", exc_info=True)
            return [], 0

    def find_similar_by_id(self, doc_id: str, language: str, size: int = 10) \
            -> Tuple[List[Dict[str, Any]], int]:
        """
        Finds documents similar to the one with the given doc_id.
        """
        try:
            # 1. Fetch the source document to get its vector
            source_doc = self._opensearch_client.get(index=self._index_name, id=doc_id)
            source_vector = source_doc['_source'].get(self._vector_field)

            if not source_vector:
                log_handle.warning(
                    f"Document {doc_id} does not have a vector embedding. "
                    f"Cannot find similar documents.")
                return [], 0

            # 2. Build a k-NN query to find similar vectors, excluding the source document itself
            query_body = {
                "size": size,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "knn": {
                                    self._vector_field: {
                                        "vector": source_vector,
                                        "k": size + 1
                                    }
                                }
                            }
                        ],
                        "must_not": [
                            {
                                "ids": {
                                    "values": [doc_id]
                                }
                            }
                        ]
                    }
                }
            }

            # 3. Execute the search
            log_handle.info(f"Finding similar documents for doc_id: {doc_id}")
            response = self._opensearch_client.search(
                index=self._index_name,
                body=query_body
            )
            hits = response.get('hits', {}).get('hits', [])

            # The total will be for the whole index, so we cap it at the number of results returned.
            effective_total = len(hits)

            log_handle.info(f"Found {effective_total} similar documents for doc_id: {doc_id}")
            return self._extract_results(hits, is_lexical=False, language=language), effective_total

        except NotFoundError:
            log_handle.error(f"Document with id '{doc_id}' not found.")
            return [], 0
        except Exception as exc:
            log_handle.error(
                f"Error finding similar documents for doc_id {doc_id}: {exc}", exc_info=True)
            return [], 0

    def get_paragraph_context(self, chunk_id: str, language: str) -> Dict[str, Any]:
        """
        Fetches the context for a given paragraph (previous, current, next)
        using a simplified and more robust two-step query process.
        """
        try:
            # Step 1: Directly fetch the current document by its unique chunk_id.
            # This is a fast lookup and avoids fragile string parsing.
            current_doc_response = self._opensearch_client.get(index=self._index_name, id=chunk_id)

            source = current_doc_response.get('_source', {})
            document_id = source.get('document_id')
            current_para_id = source.get('paragraph_id')

            if document_id is None or current_para_id is None:
                raise ValueError(
                    f"Source document for chunk_id {chunk_id} is missing "
                    f"'document_id' or 'paragraph_id'")

            current_para_id = int(current_para_id)

            # Initialize the context with the current document we already have.
            context = {
                "previous": None,
                "current": self._extract_results(
                    [current_doc_response], is_lexical=False, language=language)[0],
                "next": None
            }

            # Step 2: Build a single query to fetch only the previous and next paragraphs.
            para_ids_to_fetch = [current_para_id - 1, current_para_id + 1]
            query_body = {
                "size": 2,
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"document_id": document_id}},
                            {"terms": {"paragraph_id": para_ids_to_fetch}}
                        ]
                    }
                }
            }

            response = self._opensearch_client.search(index=self._index_name, body=query_body)
            neighbor_hits = self._extract_results(
                response.get('hits', {}).get('hits', []), is_lexical=False, language=language)
            log_handle.info(
                f"response: {json_dumps(response, truncate_fields=['vector_embedding'])}")
            log_handle.info(
                f"neighbor_hits: {json_dumps(neighbor_hits, truncate_fields=['vector_embedding'])}")
            # Step 3: Populate the context with the neighbors.
            for doc in neighbor_hits:
                para_id = int(doc.get('paragraph_id', 0))
                if para_id == current_para_id - 1:
                    context['previous'] = doc
                elif para_id == current_para_id + 1:
                    context['next'] = doc

            log_handle.info(f"Context: {json_dumps(context, truncate_fields=['vector_embedding'])}")
            return context

        except Exception as exc:
            log_handle.error(
                f"An unexpected error occurred getting paragraph context for {chunk_id}: {exc}",
                exc_info=True)
            return {}

    def get_spelling_suggestions(
            self, index_name: str, text: str, language: str,
            min_score: float = 0.6, num_suggestions: int = 3):
        """
        Gets spelling suggestions for a given text and returns a list of corrected query strings.

        Args:
            client: An instance of the OpenSearch client.
            index_name: The name of the index to query.
            text: The input string to get spelling suggestions for.
            min_score: The minimum score for a suggestion to be considered valid.
            num_suggestions: The number of alternative queries to generate.

        Returns:
            A list of corrected query strings. Returns an empty list if no corrections are found.
        """
        log_handle.info(f"Getting spelling suggestions for {text} on index {index_name}")
        if not text:
            return []

        client = get_opensearch_client(self._config)
        suggester_name = "spell-check"
        text_field = self._text_fields.get(language)

        query_body = {
            "size": 0,
            "suggest": {
                suggester_name: {
                    "text": text,
                    "term": {
                        "field": text_field,
                        "size": num_suggestions,  # Get up to N suggestions per term.
                        "sort": "score",
                        "min_word_length": 3,
                        "prefix_length": 1,
                    }
                }
            }
        }

        try:
            log_handle.info(f"Querying index '{index_name}' for suggestions on: '{text}'")
            response = client.search(
                index=index_name,
                body=query_body
            )

            # This will hold lists of suggestions for each token.
            # e.g., [['कुंदकुंदाचार्य'], ['सीमंधर', 'सीमंघर']]
            token_suggestions = []
            has_any_correction = False

            if "suggest" in response and suggester_name in response["suggest"]:
                for suggestion_part in response["suggest"][suggester_name]:
                    original_token = suggestion_part["text"]

                    # Filter suggestions by score
                    valid_options = [
                        opt['text'] for opt in suggestion_part.get("options", [])
                        if opt['score'] >= min_score
                    ]

                    if valid_options:
                        token_suggestions.append(valid_options)
                        has_any_correction = True
                    else:
                        # If no valid suggestions, use the original token
                        token_suggestions.append([original_token])

            if not has_any_correction:
                return []

            # Construct the final list of suggested queries
            final_suggestions = []
            for i in range(num_suggestions):
                new_query_tokens = []
                for suggestions_for_token in token_suggestions:
                    # Use the i-th suggestion if available, otherwise fall back to the best one (0).
                    suggestion_index = min(i, len(suggestions_for_token) - 1)
                    new_query_tokens.append(suggestions_for_token[suggestion_index])

                new_query = " ".join(new_query_tokens)
                if new_query not in final_suggestions:
                    final_suggestions.append(new_query)

            return final_suggestions

        except Exception as e:
            traceback.print_exc()
            return []

    def is_lexical_query(self, query_string: str) -> bool:
        """
        Checks if a query is "lexical," with special handling for Hindi.
        """
        # Define a set of punctuation including standard English and Hindi marks.
        # The "।" (danda/purna viram) is the Hindi full stop.
        # The "॥" (double danda) is also included for completeness.
        all_punctuation = set(string.punctuation) | {"।", "॥"}

        has_punctuation = any(char in all_punctuation for char in query_string)
        if has_punctuation:
            return False

        word_count = len(query_string.split())
        if word_count >= 4:
            return False

        return True
