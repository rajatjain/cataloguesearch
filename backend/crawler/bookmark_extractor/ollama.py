import json
import logging
import requests
from typing import List, Dict, Any, Optional

from .base import BookmarkExtractor

log_handle = logging.getLogger(__name__)


class OllamaBookmarkExtractor(BookmarkExtractor):
    """
    Ollama implementation for bookmark extraction.
    Uses local Ollama models for completely offline, private inference.
    """

    def __init__(self, model: str = "nuextract", base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama bookmark extractor.

        Args:
            model: Ollama model name to use (default: nuextract)
                   Other options: qwen2.5:7b, llama3.1:8b, phi4
            base_url: Ollama API base URL (default: http://localhost:11434)
        """
        super().__init__()
        self.model = model
        self.base_url = base_url
        self.api_url = f"{base_url}/api/chat"
        log_handle.info("Initialized OllamaBookmarkExtractor with model: %s", model)

    def call_llm(self, indexed_titles: List[Dict[str, Any]]) -> Optional[List[Dict[str, str]]]:
        """
        Call Ollama API to extract data from bookmark titles.

        Args:
            indexed_titles: List of dictionaries with 'index' and 'title' keys

        Returns:
            List of dictionaries with extracted data, or None if failed
        """
        indexed_titles_json = json.dumps(indexed_titles)

        # NuExtract expects a specific format - combine system prompt with user message
        full_prompt = f"""{self.system_prompt}

Parse the following list of indexed bookmark titles and return the results:

{indexed_titles_json}

Return a JSON array where each element has: index, pravachan_no, date"""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "num_predict": 50000  # Allow very long responses for large batches
            }
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=300
            )
            response.raise_for_status()

            result = response.json()

            # Extract JSON response from Ollama
            message_content = result.get('message', {}).get('content', '')

            if message_content:
                log_handle.info("Successfully received response from Ollama API")
                # Log first 500 chars of response for debugging
                log_handle.info("Response preview: %s", message_content[:500] if len(message_content) > 500 else message_content)
                parsed_response = json.loads(message_content)
                log_handle.info("Parsed response type: %s, keys: %s", type(parsed_response), list(parsed_response.keys()) if isinstance(parsed_response, dict) else 'N/A')

                # Handle different response formats
                # Ollama might return {"results": [...]} or just [...]
                if isinstance(parsed_response, list):
                    parsed_data = parsed_response
                elif isinstance(parsed_response, dict):
                    # Check if it's a wrapper object with results
                    if 'results' in parsed_response or 'data' in parsed_response or 'bookmarks' in parsed_response:
                        parsed_data = (parsed_response.get('results') or
                                     parsed_response.get('data') or
                                     parsed_response.get('bookmarks'))
                    # Check if it's a single result object (has 'index' key)
                    elif 'index' in parsed_response:
                        # Wrap single object in a list
                        parsed_data = [parsed_response]
                    else:
                        # Try first value as fallback
                        first_val = list(parsed_response.values())[0] if parsed_response else None
                        parsed_data = first_val if isinstance(first_val, list) else None
                else:
                    log_handle.error("Unexpected response format: %s", type(parsed_response))
                    parsed_data = None

                if parsed_data:
                    # Post-process: Convert "N/A" strings to None
                    for item in parsed_data:
                        if item.get('pravachan_no') == 'N/A':
                            item['pravachan_no'] = None
                        if item.get('date') == 'N/A':
                            item['date'] = None

                    log_handle.info("Successfully extracted %d items", len(parsed_data))
                    return parsed_data
                else:
                    log_handle.warning("Could not extract data from response")

            else:
                log_handle.warning("Received empty response from Ollama")

        except requests.exceptions.ConnectionError as e:
            log_handle.error("Failed to connect to Ollama. Is Ollama running? Error: %s", e)
            log_handle.error("Make sure Ollama is running: 'ollama serve' or check if Ollama app is running")

        except requests.exceptions.RequestException as e:
            log_handle.error("Error calling Ollama API: %s", e)
            if hasattr(e, 'response') and e.response is not None:
                log_handle.error("Response content: %s", e.response.text)

        except json.JSONDecodeError as e:
            log_handle.error("Error decoding JSON response from Ollama: %s", e)
            log_handle.error("Raw response: %s", message_content if 'message_content' in locals() else 'N/A')

        return None