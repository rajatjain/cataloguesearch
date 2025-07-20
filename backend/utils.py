# utils.py
import json
import os
import re
import copy
from typing import List, Dict, Any, Tuple, Optional

from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer

# Global variables for Firebase (as per instructions)
# These are typically provided by the Canvas runtime environment.
# They are included here for completeness but might not be directly used in this specific Python backend example
# unless you integrate Firebase for authentication/storage.
app_id = os.environ.get('__app_id', 'default-app-id')
firebase_config_str = os.environ.get('__firebase_config', '{}')
firebase_config = json.loads(firebase_config_str)
initial_auth_token = os.environ.get('__initial_auth_token')


_embedding_model_cache = {}

def load_embedding_model(model_name: str) -> SentenceTransformer:
    """
    Loads and caches the specified SentenceTransformer embedding model.
    """
    if model_name not in _embedding_model_cache:
        print(f"Loading embedding model: {model_name}")
        model = SentenceTransformer(model_name)
        _embedding_model_cache[model_name] = model
    return _embedding_model_cache[model_name]

async def call_llm(prompt: str, llm_model_name: str, llm_api_key: str, response_schema: Optional[Dict[str, Any]] = None) -> str:
    """
    Calls the LLM (Gemini 2.0 Flash) to get a structured response.
    """
    chat_history = []
    chat_history.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": chat_history,
    }
    if response_schema:
        payload["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }

    # The API key will be automatically provided by the Canvas runtime for gemini-2.0-flash
    api_key_param = f"key={llm_api_key}" if llm_api_key else ""
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{llm_model_name}:generateContent?{api_key_param}"

    # --- IMPORTANT ---
    # In a real FastAPI application deployed, you would use an asynchronous HTTP client
    # like 'httpx' to make the actual API call to the Gemini API.
    # For this example, and for local testing without actual API calls,
    # we are simulating a successful LLM response.
    # You MUST replace this dummy response with actual API call logic when deploying.
    # --- IMPORTANT ---

    print(f"Simulating LLM call with prompt: {prompt}")
    print(f"Simulating LLM call to URL: {api_url}")
    print(f"Simulating LLM payload: {json.dumps(payload, indent=2)}")

    # Dummy responses based on expected schema
    if response_schema and response_schema.get("type") == "ARRAY":
        # This is likely for snippet extraction
        dummy_response_text = """
        [
            {
                "file_name": "example_file.txt",
                "page_number": 1,
                "snippet": "यह एक उदाहरण अंश है जिसमें महत्वपूर्ण कीवर्ड **हाइलाइट** किए गए हैं।"
            },
            {
                "file_name": "another_file.txt",
                "page_number": 2,
                "snippet": "બીજો એક ઉદાહરણ અંશ જેમાં મહત્વપૂર્ણ કીવર્ડ્સ **હાઇલાઇટ** કરવામાં આવ્યા છે."
            }
        ]
        """
    elif response_schema and response_schema.get("type") == "OBJECT" and "expanded_query" in response_schema.get("properties", {}):
        # This is for query expansion
        dummy_response_text = """
        {
            "expanded_query": "भारत की प्राचीन परंपरा, योग, भारतीय संस्कृति, इतिहास"
        }
        """
    else:
        # Default dummy response if no specific schema or for general text generation
        dummy_response_text = "Default simulated LLM response."

    try:
        parsed_json = json.loads(dummy_response_text)
        return json.dumps(parsed_json) # Return as JSON string as per fetch result
    except json.JSONDecodeError:
        print("Error decoding dummy LLM response.")
        return "[]" # Return empty array or appropriate default

def chunk_text(text: str, file_name: str, page_number: int, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
    """
    Splits text into chunks.
    Given the requirement that each input file is a single page,
    the entire text content is treated as one chunk, and the provided page_number is used.
    The chunk_size and chunk_overlap parameters are now effectively ignored.
    """
    # Treat the entire file content as a single chunk
    chunks = [{
        "content": text,
        "file_name": file_name,
        "page_number": page_number, # Use the page_number passed as input
    }]
    return chunks

def detect_language(text: str) -> str:
    """
    Detects the language of the given text (Hindi or Gujarati).
    Returns 'hi' for Hindi, 'gu' for Gujarati, or 'unknown'.
    """
    try:
        lang = detect(text)
        if lang == 'gu':
            return 'gu'
        elif lang == 'hi':
            return 'hi'
        # langdetect might return 'en' for some mixed or short texts,
        # but given the requirement, we prioritize hi/gu.
        # If it's not hi or gu, we'll treat it as unknown for this context.
        return 'unknown'
    except LangDetectException:
        return 'unknown'

def extract_highlighted_words(highlighted_text: str, pre_tag: str = "**", post_tag: str = "**") -> List[str]:
    """
    Extracts words/phrases wrapped by pre_tag and post_tag from a highlighted string.
    """
    # Regex to find content between pre_tag and post_tag
    pattern = re.compile(re.escape(pre_tag) + "(.*?)" + re.escape(post_tag))
    matches = pattern.findall(highlighted_text)
    # Split each match by space and flatten the list, then remove duplicates
    words = []
    for match in matches:
        words.extend(match.split())
    return list(set(words)) # Return unique words

def remove_highlight_tags(text: str, pre_tag: str = "**", post_tag: str = "**") -> str:
    """
    Removes highlight tags from a string.
    """
    return text.replace(pre_tag, "").replace(post_tag, "")

def _recursive_truncate(obj, fields_to_truncate):
    """
    A helper function to recursively traverse a data structure and truncate
    the values of specified fields.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in fields_to_truncate:
                if isinstance(value, list):
                    obj[key] = f"<list of {len(value)} items truncated>"
                else:
                    # You can customize this for other types if needed
                    obj[key] = f"<value truncated>"
            else:
                _recursive_truncate(value, fields_to_truncate)
    elif isinstance(obj, list):
        for item in obj:
            _recursive_truncate(item, fields_to_truncate)
    return obj

def json_dump(obj, fp, **kwargs):
    """
    Dumps an object to a file-like object in JSON format, with an option to truncate fields.

    To truncate fields, pass a list of keys:
    json_dump(data, f, truncate_fields=['vector_embedding'])
    """
    truncate_fields = kwargs.pop('truncate_fields', None)

    if truncate_fields:
        # Process a copy to avoid side effects
        obj_copy = copy.deepcopy(obj)
        processed_obj = _recursive_truncate(obj_copy, truncate_fields)
        return json.dump(processed_obj, fp, ensure_ascii=False, indent=4, **kwargs)
    else:
        return json.dump(obj, fp, ensure_ascii=False, indent=4, **kwargs)

def json_dumps(obj, **kwargs):
    """
    Serializes an object to a JSON formatted string, with an option to truncate fields.

    To truncate fields, pass a list of keys:
    json_dumps(data, truncate_fields=['vector_embedding'])
    """
    truncate_fields = kwargs.pop('truncate_fields', None)

    if truncate_fields:
        # Process a copy to avoid side effects
        obj_copy = copy.deepcopy(obj)
        processed_obj = _recursive_truncate(obj_copy, truncate_fields)
        return json.dumps(processed_obj, ensure_ascii=False, indent=4, **kwargs)
    else:
        return json.dumps(obj, ensure_ascii=False, indent=4, **kwargs)
