import logging

from opensearchpy import NotFoundError

from backend.common.opensearch import get_opensearch_client
from backend.config import Config
from backend.utils import json_dumps
from scratch.prod_setup import prod_setup

log_handle = logging.getLogger(__name__)

def get_spelling_suggestions(
        index_name: str, text: str, min_score: float = 0.2, num_suggestions: int = 3):
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
    if not text:
        print("Input text cannot be empty.")
        return []

    client = get_opensearch_client(Config())
    suggester_name = "spell-check"

    query_body = {
        "size": 0,
        "suggest": {
            suggester_name: {
                "text": text,
                "term": {
                    "field": "text_content_hindi",
                    "size": num_suggestions,  # Get up to N suggestions per term.
                    "sort": "score",
                    "min_word_length": 3,
                    "prefix_length": 1,
                }
            }
        }
    }

    try:
        print(f"Querying index '{index_name}' for suggestions on: '{text}'")
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

    except NotFoundError:
        print(f"Error: Index '{index_name}' not found.")
        return []
    except ConnectionError as e:
        print(f"Error: Could not connect to OpenSearch. {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []

if __name__ == '__main__':
    prod_setup()
    config = Config()
    queries = [
        "आश्रव", "आस्रव", "निर्जरा"
    ]
    for query in queries:
        suggestions = get_spelling_suggestions(config.OPENSEARCH_INDEX_NAME, query)
        log_handle.info(f"Suggestions for {query}: {json_dumps(suggestions)}")