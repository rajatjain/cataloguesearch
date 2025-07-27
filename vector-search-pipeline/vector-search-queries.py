import traceback
import numpy as np

from generate_embeddings import get_opensearch_client, \
    initialize_models, MODELS, OPENSEARCH_INDEX_NAME, MODEL_CONFIG
from generate_paragraphs import normalize_hindi_text

OPENSEARCH_INDEX_NAME = "hindi_scriptures"

def perform_search(vector_field: str, query_vector: list, top_k: int = 5):
    """
    Performs a k-NN search on a specific vector field in OpenSearch.
    """
    client = get_opensearch_client()
    print(f"Searching for top {top_k} results in field '{vector_field}'...")

    query = {
        "size": top_k,
        "query": {
            "knn": {
                vector_field: {
                    "vector": query_vector,
                    "k": top_k
                }
            }
        },
        "_source": ["text_content"] # Only retrieve the text content
    }

    try:
        response = client.search(index=OPENSEARCH_INDEX_NAME, body=query)
        return response['hits']['hits']
    except Exception as e:
        traceback.print_exc()
        print(f"Error querying OpenSearch for field {vector_field}: {e}")
        return None


def display_results(results_by_model: dict):
    """
    Displays the search results in a formatted way for easy comparison.
    """
    print("\n" + "="*80)
    print("SEARCH RESULTS")
    print("="*80 + "\n")

    for model_key, hits in results_by_model.items():
        model_name = MODEL_CONFIG[model_key]['name']
        print(f"--- Top 5 Results for: {model_name} ---")
        if hits is None:
            print("  Query failed for this model.")
        elif not hits:
            print("  No results found.")
        else:
            for i, hit in enumerate(hits):
                score = hit['_score']
                text = hit['_source']['text_content']
                # Truncate long text for display
                display_text = (text)
                print(f"  {i+1}. Score: {score:.4f}")
                print(f"     Text: {display_text}\n")
        print("-" * 50 + "\n")


def main():
    """
    Main interactive loop for querying and evaluating models.
    """
    initialize_models()
    opensearch_client = get_opensearch_client()

    if not opensearch_client:
        print("\nCould not connect to OpenSearch. Please check your `get_opensearch_client` function.")
        return

    while True:
        try:
            query = input("Enter your search query (or 'exit' to quit): ")
            if query.lower() == 'exit':
                break
            if not query.strip():
                continue

            # Normalize the user's query
            normalized_query = normalize_hindi_text(query)
            print(f"Normalized query: '{normalized_query}'")

            results_by_model = {}

            # Generate embeddings and query for each model
            for key, model in MODELS.items():
                if not model:
                    results_by_model[key] = None
                    continue

                print(f"Generating embedding with {MODEL_CONFIG[key]['name']}...")
                if key == 'google':
                    query_vector = model.get_embeddings([normalized_query])[0].values
                    embedding_np = np.array(query_vector)
                    norm = np.linalg.norm(embedding_np)
                    query_vector = (embedding_np / norm).tolist()
                else:
                    query_vector = model.encode(normalized_query, normalize_embeddings=True).tolist()

                vector_field = MODEL_CONFIG[key]['field']
                results_by_model[key] = perform_search(vector_field, query_vector)

            display_results(results_by_model)

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            traceback.print_exc()
            print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
