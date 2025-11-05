"""
Transliteration utilities for romanized text to native scripts.

This module provides functionality to:
1. Convert romanized text to native scripts (e.g., Hindi romanized to Devanagari)
2. Validate transliterations against OpenSearch corpus
3. Handle disambiguation when multiple valid variants exist
4. Use a three-phase approach for finding the best matches
"""

import logging
import requests
from typing import List, Dict, Tuple, Optional
from itertools import product
from opensearchpy import OpenSearch

log = logging.getLogger(__name__)


def get_field_name_for_language(lang: str) -> str:
    """
    Map language code to OpenSearch field name.

    Args:
        lang: Language code (e.g., "hi", "sa", "gu")

    Returns:
        OpenSearch field name for the language

    Example:
        >>> get_field_name_for_language("hi")
        'text_content_hindi'
        >>> get_field_name_for_language("sa")
        'text_content_sanskrit'
    """
    language_field_map = {
        "hi": "text_content_hindi",
        "sa": "text_content_sanskrit",
        "gu": "text_content_gujarati",
        "pa": "text_content_punjabi",
        "bn": "text_content_bengali",
        "ta": "text_content_tamil",
        "te": "text_content_telugu",
        "ml": "text_content_malayalam",
        "kn": "text_content_kannada",
        "or": "text_content_oriya",
        "mr": "text_content_marathi"
    }

    field_name = language_field_map.get(lang)
    if not field_name:
        log.warning(f"Unknown language code '{lang}', defaulting to 'text_content_hindi'")
        return "text_content_hindi"

    return field_name


def get_transliteration_variants(
    romanized_word: str,
    lang: str = "hi",
    topk: int = 5,
    api_url: str = "http://localhost:8500",
    timeout: int = 10
) -> List[str]:
    """
    Generate multiple transliteration variants for a romanized word using the Transliteration API.

    Args:
        romanized_word: Romanized text (e.g., "bhagwan", "aatma")
        lang: Language code (e.g., "hi" for Hindi, "sa" for Sanskrit)
        topk: Number of top predictions to return
        api_url: Base URL of the transliteration API
        timeout: Request timeout in seconds

    Returns:
        List of transliteration variants in the target script

    Example:
        >>> get_transliteration_variants("ram", lang="hi", topk=3)
        ['राम', 'रम', 'रामा']
    """
    url = f"{api_url}/tl/{lang}/{romanized_word}"
    params = {"topk": topk}

    try:
        log.debug(f"Requesting transliteration for '{romanized_word}' (lang={lang}, topk={topk})")
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()

        variants = response.json()

        if not isinstance(variants, list):
            log.error(f"Unexpected response format from API: {variants}")
            return []

        log.debug(f"Received {len(variants)} variants for '{romanized_word}': {variants}")
        return variants

    except requests.exceptions.Timeout:
        log.error(f"Transliteration API request timed out for '{romanized_word}'")
        return []
    except requests.exceptions.ConnectionError:
        log.error(f"Could not connect to transliteration API at {api_url}")
        return []
    except requests.exceptions.HTTPError as e:
        log.error(f"HTTP error from transliteration API: {e}")
        return []
    except Exception as e:
        log.error(f"Unexpected error during transliteration: {e}", exc_info=True)
        return []


def query_opensearch_for_word(
    opensearch_client: OpenSearch,
    index_name: str,
    word: str,
    field_name: str = "text_content_hindi"
) -> int:
    """
    Query OpenSearch to check if a word exists and get its frequency.

    Args:
        opensearch_client: OpenSearch client instance
        index_name: Name of the OpenSearch index to query
        word: The word to search for
        field_name: The field name to search in (default: "text_content_hindi")

    Returns:
        Total hit count (number of occurrences in the corpus)

    Example:
        >>> query_opensearch_for_word(client, "my_index", "राम")
        1234
    """
    query_body = {
        "size": 1,
        "query": {
            "match": {
                field_name: {
                    "query": word,
                    "operator": "and"
                }
            }
        }
    }

    try:
        response = opensearch_client.search(
            index=index_name,
            body=query_body
        )

        hits = response.get('hits', {}).get('hits', [])
        total_hits = response.get('hits', {}).get('total', {}).get('value', 0)

        if hits:
            score = hits[0].get('_score', 0.0)
            log.debug(f"Word '{word}' found: {total_hits} occurrences, relevance score: {score}")
            return total_hits
        else:
            log.debug(f"Word '{word}' not found in index (0 hits)")
            return 0
    except Exception as e:
        log.error(f"Error querying OpenSearch for '{word}': {e}")
        import traceback
        log.error(traceback.format_exc())
        return 0


def query_variants(
    opensearch_client: OpenSearch,
    index_name: str,
    variants: List[str],
    field_name: str = "text_content_hindi"
) -> List[Tuple[str, int]]:
    """
    Query OpenSearch for a list of variants and return those that exist.

    Args:
        opensearch_client: OpenSearch client instance
        index_name: Name of the OpenSearch index to query
        variants: List of variant words to check
        field_name: The field name to search in (default: "text_content_hindi")

    Returns:
        List of (variant, frequency) tuples for variants with frequency > 0,
        sorted by frequency descending

    Example:
        >>> query_variants(client, "my_index", ["राम", "रम", "रामा"])
        [("राम", 1234), ("रामा", 56)]
    """
    found_variants = []

    for variant in variants:
        frequency = query_opensearch_for_word(opensearch_client, index_name, variant, field_name)
        log.info(f"  - '{variant}': {frequency} occurrences")

        if frequency > 0:
            found_variants.append((variant, frequency))

    # Sort by frequency descending
    found_variants.sort(key=lambda x: x[1], reverse=True)
    return found_variants


def find_best_matches(
    romanized_word: str,
    opensearch_client: OpenSearch,
    index_name: str,
    index_searcher,
    lang: str = "hi",
    field_name: Optional[str] = None,
    api_url: str = "http://localhost:8500",
    timeout: int = 10
) -> List[Tuple[str, int]]:
    """
    Find all variants that exist in OpenSearch using a three-phase approach.

    Phase 1: Try top-5 transliteration variants
    Phase 2: If nothing found, expand to top-10
    Phase 3: If still nothing, use OpenSearch's spelling suggester

    Args:
        romanized_word: The romanized word to transliterate
        opensearch_client: OpenSearch client instance
        index_name: Name of the OpenSearch index to query
        index_searcher: IndexSearcher instance for spelling suggestions
        lang: Language code (e.g., "hi" for Hindi, "sa" for Sanskrit, "gu" for Gujarati)
        field_name: The field name to search in (auto-determined from lang if not provided)
        api_url: Base URL of the transliteration API
        timeout: Request timeout in seconds

    Returns:
        List of (variant, frequency) tuples for all variants that exist
        in the index (frequency > 0), sorted by frequency (descending)

    Example:
        >>> find_best_matches("ram", client, "my_index", searcher, lang="hi")
        [("राम", 1234), ("रामा", 56)]
    """
    # Auto-determine field name from language if not provided
    if field_name is None:
        field_name = get_field_name_for_language(lang)
    # Phase 1: Try top-5 variants
    log.info("Phase 1: Querying OpenSearch for top-5 variants:")
    top5_variants = get_transliteration_variants(romanized_word, lang=lang, topk=5, api_url=api_url, timeout=timeout)
    found_variants = query_variants(opensearch_client, index_name, top5_variants, field_name)

    if found_variants:
        log.info(f"Found {len(found_variants)} variants (top-5 was sufficient)")
        return found_variants

    # Phase 2: No matches in top-5, try top-10
    log.info("\nPhase 2: No matches in top-5. Expanding to top-10...")
    top10_variants = get_transliteration_variants(romanized_word, lang=lang, topk=10, api_url=api_url, timeout=timeout)

    # Only query the NEW variants (skip the first 5 we already checked)
    new_variants = top10_variants[5:]
    if new_variants:
        log.info(f"Querying {len(new_variants)} additional variants:")
        found_variants = query_variants(opensearch_client, index_name, new_variants, field_name)

        if found_variants:
            log.info(f"Found {len(found_variants)} variants (needed top-10)")
            return found_variants

    # Phase 3: Still no variants found - fall back to spelling suggester
    log.info("\nPhase 3: No variants found in top-10. Using OpenSearch spelling suggester...")

    suggested_terms = set()
    for variant in top10_variants:
        log.info(f"Getting suggestions for '{variant}'...")
        # Determine language for suggester based on field name
        # Map field names to suggester language names
        if "hindi" in field_name:
            suggester_lang = "hindi"
        elif "sanskrit" in field_name:
            suggester_lang = "sanskrit"
        elif "gujarati" in field_name:
            suggester_lang = "gujarati"
        else:
            suggester_lang = "hindi"  # Default fallback

        suggestions = index_searcher.get_spelling_suggestions(
            index_name=index_name,
            text=variant,
            language=suggester_lang,
            min_score=0.5,
            num_suggestions=3
        )

        if suggestions:
            log.info(f"  Suggestions: {suggestions}")
            # Suggestions are returned as full query strings, split them into words
            for suggestion in suggestions:
                suggested_terms.update(suggestion.split())

    if not suggested_terms:
        log.warning("Spelling suggester returned no results!")
        return []

    # Query OpenSearch again with suggested terms
    log.info(f"\nQuerying OpenSearch with {len(suggested_terms)} suggested terms:")
    for suggested_term in suggested_terms:
        frequency = query_opensearch_for_word(opensearch_client, index_name, suggested_term, field_name)
        log.info(f"  - '{suggested_term}': {frequency} occurrences")

        # Include any suggested term that exists (frequency > 0)
        if frequency > 0:
            found_variants.append((suggested_term, frequency))

    # Sort by frequency descending
    found_variants.sort(key=lambda x: x[1], reverse=True)

    if found_variants:
        log.info(f"Found {len(found_variants)} suggested variants in the index:")
        for variant, freq in found_variants:
            log.info(f"  - '{variant}': {freq} occurrences")
    else:
        log.warning("No suggested variants found in the index!")

    return found_variants


def process_word(
    romanized_word: str,
    opensearch_client: OpenSearch,
    index_name: str,
    index_searcher,
    lang: str = "hi",
    field_name: Optional[str] = None,
    api_url: str = "http://localhost:8500",
    timeout: int = 10
) -> Dict:
    """
    Process a single romanized word and return disambiguation info.

    This is the main function for transliterating and validating a single word.
    It uses a three-phase approach to find the best matches in the corpus.

    Args:
        romanized_word: The romanized word to process
        opensearch_client: OpenSearch client instance
        index_name: Name of the OpenSearch index to query
        index_searcher: IndexSearcher instance for spelling suggestions
        lang: Language code (e.g., "hi" for Hindi, "sa" for Sanskrit, "gu" for Gujarati)
        field_name: The field name to search in (auto-determined from lang if not provided)
        api_url: Base URL of the transliteration API
        timeout: Request timeout in seconds

    Returns:
        Dictionary with the following structure:
        {
            'status': 'clear' | 'multiple' | 'no_match',
            'best_match': str (if status == 'clear'),
            'frequency': int (if status == 'clear'),
            'options': List[Tuple[str, int]] (if status == 'multiple' or 'no_match'),
            'romanized': str
        }

    Example:
        >>> result = process_word("ram", client, "my_index", searcher, lang="hi")
        >>> result
        {'status': 'clear', 'best_match': 'राम', 'frequency': 1234, 'romanized': 'ram'}
    """
    # Auto-determine field name from language if not provided
    if field_name is None:
        field_name = get_field_name_for_language(lang)

    log.info(f"\nProcessing word: '{romanized_word}'")

    # Query OpenSearch with three-phase approach (top-5, top-10, suggester)
    matches = find_best_matches(
        romanized_word,
        opensearch_client,
        index_name,
        index_searcher,
        lang=lang,
        field_name=field_name,
        api_url=api_url,
        timeout=timeout
    )

    if not matches:
        # No matches found - show top transliteration options as fallback
        fallback_variants = get_transliteration_variants(
            romanized_word,
            lang=lang,
            topk=5,
            api_url=api_url,
            timeout=timeout
        )
        return {
            'status': 'no_match',
            'options': [(v, 0) for v in fallback_variants[:3]],  # Show top 3 variants
            'romanized': romanized_word
        }

    if len(matches) == 1:
        # Single clear match
        return {
            'status': 'clear',
            'best_match': matches[0][0],
            'frequency': matches[0][1],
            'romanized': romanized_word
        }
    else:
        # Multiple valid variants
        return {
            'status': 'multiple',
            'options': matches,  # All variants that meet threshold
            'romanized': romanized_word
        }


def get_phrase_combinations(
    word_results: List[Dict],
    max_variants_per_word: int = 3,
    top_k_phrases: int = 3
) -> List[Dict]:
    """
    Generate top phrase combinations from individual word results using Cartesian product.

    This function takes the results from processing individual words and generates
    all possible phrase combinations, scoring them by the sum of word frequencies.

    Args:
        word_results: List of word processing results from process_word()
        max_variants_per_word: Maximum number of variants to consider per word (default: 3)
        top_k_phrases: Number of top phrase recommendations to return (default: 3)

    Returns:
        List of phrase recommendations, each containing:
        {
            'phrase': str,                    # Complete phrase in native script
            'score': int,                     # Sum of word frequencies
            'word_frequencies': List[int],    # Individual word frequencies
            'romanized': str                  # Original romanized phrase
        }

    Example:
        >>> word_results = [
        ...     {'status': 'multiple', 'options': [('यह', 5000), ('ये', 3000)], 'romanized': 'yeh'},
        ...     {'status': 'clear', 'best_match': 'कौन', 'frequency': 8000, 'romanized': 'kaun'},
        ...     {'status': 'multiple', 'options': [('था', 7000), ('ठा', 50)], 'romanized': 'tha'}
        ... ]
        >>> get_phrase_combinations(word_results)
        [
            {'phrase': 'यह कौन था', 'score': 20000, 'word_frequencies': [5000, 8000, 7000], 'romanized': 'yeh kaun tha'},
            {'phrase': 'ये कौन था', 'score': 18000, 'word_frequencies': [3000, 8000, 7000], 'romanized': 'ये kaun tha'},
            ...
        ]
    """
    # Extract top variants for each word
    word_variants_list = []
    romanized_words = []

    for result in word_results:
        romanized_words.append(result['romanized'])

        if result['status'] == 'clear':
            # Single match - only one variant
            word_variants_list.append([
                (result['best_match'], result['frequency'])
            ])
        elif result['status'] == 'multiple':
            # Multiple matches - take top N
            word_variants_list.append(result['options'][:max_variants_per_word])
        else:  # no_match
            # No validated matches - use transliteration suggestions with 0 frequency
            word_variants_list.append(result['options'][:max_variants_per_word])

    # Generate all combinations using Cartesian product
    all_combinations = product(*word_variants_list)

    # Score each combination
    scored_phrases = []
    romanized_phrase = " ".join(romanized_words)

    for combination in all_combinations:
        words = [variant for variant, freq in combination]
        frequencies = [freq for variant, freq in combination]

        phrase = " ".join(words)
        score = sum(frequencies)  # Sum of frequencies

        scored_phrases.append({
            'phrase': phrase,
            'score': score,
            'word_frequencies': frequencies,
            'romanized': romanized_phrase
        })

    # Sort by score descending and return top K
    scored_phrases.sort(key=lambda x: x['score'], reverse=True)
    return scored_phrases[:top_k_phrases]


def process_text(
    romanized_text: str,
    opensearch_client: OpenSearch,
    index_name: str,
    index_searcher,
    lang: str = "hi",
    field_name: Optional[str] = None,
    api_url: str = "http://localhost:8500",
    timeout: int = 10,
    max_variants_per_word: int = 3,
    top_k_phrases: int = 3
) -> Dict:
    """
    Process multiple words in input text and generate top phrase recommendations.

    This function processes each word individually, then generates all possible
    phrase combinations using Cartesian product and returns the top recommendations
    based on frequency scoring.

    Args:
        romanized_text: Space-separated romanized words
        opensearch_client: OpenSearch client instance
        index_name: Name of the OpenSearch index to query
        index_searcher: IndexSearcher instance for spelling suggestions
        lang: Language code (e.g., "hi" for Hindi, "sa" for Sanskrit, "gu" for Gujarati)
        field_name: The field name to search in (auto-determined from lang if not provided)
        api_url: Base URL of the transliteration API
        timeout: Request timeout in seconds
        max_variants_per_word: Maximum variants to consider per word for combinations (default: 3)
        top_k_phrases: Number of top phrase recommendations to return (default: 3)

    Returns:
        Dictionary containing:
        {
            'recommendations': List[Dict],  # Top phrase combinations
            'per_word_results': List[Dict], # Individual word results (for debugging)
            'romanized': str                # Original romanized text
        }

    Example:
        >>> results = process_text("yeh kaun tha", client, "my_index", searcher, lang="hi")
        >>> results['recommendations']
        [
            {'phrase': 'यह कौन था', 'score': 20000, 'word_frequencies': [5000, 8000, 7000], 'romanized': 'yeh kaun tha'},
            {'phrase': 'ये कौन था', 'score': 18000, 'word_frequencies': [3000, 8000, 7000], 'romanized': 'yeh kaun tha'},
            ...
        ]
    """
    # Auto-determine field name from language if not provided
    if field_name is None:
        field_name = get_field_name_for_language(lang)

    words = romanized_text.strip().split()
    per_word_results = []

    # Process each word individually
    for word in words:
        result = process_word(
            word,
            opensearch_client,
            index_name,
            index_searcher,
            lang=lang,
            field_name=field_name,
            api_url=api_url,
            timeout=timeout
        )
        per_word_results.append(result)

    # Generate phrase combinations from word results
    recommendations = get_phrase_combinations(
        word_results=per_word_results,
        max_variants_per_word=max_variants_per_word,
        top_k_phrases=top_k_phrases
    )

    return {
        'recommendations': recommendations,
        'per_word_results': per_word_results,
        'romanized': romanized_text
    }


def health_check(api_url: str = "http://localhost:8500", timeout: int = 5) -> bool:
    """
    Check if the transliteration API is available and healthy.

    Args:
        api_url: Base URL of the transliteration API
        timeout: Request timeout in seconds

    Returns:
        True if the API is responsive, False otherwise

    Example:
        >>> health_check()
        True
    """
    try:
        url = f"{api_url}/"
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except Exception as e:
        log.error(f"Health check failed for transliteration API: {e}")
        return False
