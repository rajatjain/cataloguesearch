import json
import logging
import time
import requests
from typing import List, Dict, Any, Optional

from .base import BookmarkExtractor

log_handle = logging.getLogger(__name__)


class GeminiBookmarkExtractor(BookmarkExtractor):
    """
    Gemini API implementation for bookmark extraction.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Initialize Gemini bookmark extractor.

        Args:
            api_key: Google AI/Gemini API key
            model: Gemini model name to use
        """
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        log_handle.info("Initialized GeminiBookmarkExtractor with model: %s", model)

        self.output_schema = {
            "type": "ARRAY",
            "description": "A list of extracted pravachan details.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "index": {
                        "type": "INTEGER",
                        "description": "The zero-based index of the title in the input list."
                    },
                    "pravachan_no": {
                        "type": "STRING",
                        "description": "The extracted Pravachan number (e.g., '244-A', '112', '17'). Use null if not found.",
                        "nullable": True
                    },
                    "date": {
                        "type": "STRING",
                        "description": "The extracted date in DD-MM-YYYY format. Use null if not found.",
                        "nullable": True
                    }
                },
                "required": ["index", "pravachan_no", "date"]
            }
        }

    def call_llm(self, indexed_titles: List[Dict[str, Any]]) -> Optional[List[Dict[str, str]]]:
        """
        Call Gemini API to extract data from bookmark titles.

        Args:
            indexed_titles: List of dictionaries with 'index' and 'title' keys

        Returns:
            List of dictionaries with extracted data, or None if failed
        """
        headers = {'Content-Type': 'application/json'}

        indexed_titles_json = json.dumps(indexed_titles)
        query = f"Parse the following list of indexed bookmark titles and return the results according to the JSON schema:\n\n{indexed_titles_json}"

        payload = {
            "contents": [{"parts": [{"text": query}]}],
            "systemInstruction": {"parts": [{"text": self.system_prompt}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": self.output_schema
            },
        }

        # Exponential backoff retry logic
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.api_url}?key={self.api_key}",
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()

                result = response.json()

                # Extract JSON response from Gemini
                json_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')

                if json_text:
                    log_handle.info("Successfully received response from Gemini API")
                    parsed_data = json.loads(json_text)

                    # Post-process: Convert "N/A" strings to None
                    for item in parsed_data:
                        if item.get('pravachan_no') == 'N/A':
                            item['pravachan_no'] = None
                        if item.get('date') == 'N/A':
                            item['date'] = None

                    return parsed_data
                else:
                    log_handle.warning("Received empty response from Gemini on attempt %s", attempt + 1)

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
                    break

            except json.JSONDecodeError as e:
                log_handle.error("Error decoding JSON response from Gemini on attempt %s: %s", attempt + 1, e)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    break

        return None