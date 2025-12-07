import json
import logging
import time
import requests
from typing import List, Dict, Any, Optional

from .base import BookmarkExtractor

log_handle = logging.getLogger(__name__)


class GroqBookmarkExtractor(BookmarkExtractor):
    """
    Groq API implementation for bookmark extraction.
    Uses Llama models via Groq's fast inference API.
    """

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        """
        Initialize Groq bookmark extractor.

        Args:
            api_key: Groq API key
            model: Groq model name to use (default: llama-3.3-70b-versatile)
                   Other options: llama-3.1-70b-versatile, mixtral-8x7b-32768
        """
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        log_handle.info("Initialized GroqBookmarkExtractor with model: %s", model)

    def call_llm(self, indexed_titles: List[Dict[str, Any]]) -> Optional[List[Dict[str, str]]]:
        """
        Call Groq API to extract data from bookmark titles.

        Args:
            indexed_titles: List of dictionaries with 'index' and 'title' keys

        Returns:
            List of dictionaries with extracted data, or None if failed
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        indexed_titles_json = json.dumps(indexed_titles)
        user_message = f"Parse the following list of indexed bookmark titles and return the results:\n\n{indexed_titles_json}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"}
        }

        # Exponential backoff retry logic
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()

                result = response.json()

                # Extract JSON response from Groq
                json_text = result.get('choices', [{}])[0].get('message', {}).get('content')

                if json_text:
                    log_handle.info("Successfully received response from Groq API")
                    parsed_response = json.loads(json_text)
                    log_handle.info("Parsed response type: %s, keys: %s", type(parsed_response),
                                    parsed_response.keys() if isinstance(parsed_response, dict) else "N/A")
                    log_handle.info("Full response: %s", json.dumps(parsed_response)[:500])

                    # Handle different response formats
                    # Groq might return {"results": [...]} or just [...] or a single object
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

                        return parsed_data
                    else:
                        log_handle.warning("Could not extract data from response on attempt %s", attempt + 1)

                else:
                    log_handle.warning("Received empty response from Groq on attempt %s", attempt + 1)

            except requests.exceptions.RequestException as e:
                # Retry on server errors (500+) or rate limit errors (429)
                should_retry = (hasattr(e, 'response') and e.response is not None and
                               (e.response.status_code >= 500 or e.response.status_code == 429))

                if attempt < max_retries - 1 and should_retry:
                    wait_time = 2 ** attempt
                    log_handle.warning("Transient error occurred: %s. Retrying in %s seconds...", e, wait_time)
                    time.sleep(wait_time)
                else:
                    log_handle.error("Fatal error after %s attempts: %s", attempt + 1, e)
                    if hasattr(e, 'response') and e.response is not None:
                        log_handle.error("Response content: %s", e.response.text)
                    break

            except json.JSONDecodeError as e:
                log_handle.error("Error decoding JSON response from Groq on attempt %s: %s", attempt + 1, e)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    break

        return None