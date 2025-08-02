import json
import os
import copy
from pathlib import Path
import yaml
import concurrent.futures
import time
from tqdm import tqdm
from typing import Callable, List, Any
import numpy as np
from starlette.responses import JSONResponse as StarletteJSONResponse

class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle special types like NumPy's float32,
    which are not serializable by default.
    """

    def default(self, o):
        # Handle numpy float types
        if isinstance(o, (np.float_, np.float16, np.float32, np.float64)):
            return float(o)
        # Handle numpy integer types
        if isinstance(o, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64,
                          np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(o)
        # Handle numpy arrays
        if isinstance(o, np.ndarray):
            return o.tolist()
        # Let the base class default method raise the TypeError for other types
        return super().default(o)

class JSONResponse(StarletteJSONResponse):
    """
    A custom JSONResponse class that uses an encoder capable of handling
    NumPy data types (like float32) which are common in ML/data science outputs.
    """

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=CustomJSONEncoder,  # Use our custom encoder
        ).encode("utf-8")


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
        return json.dump(processed_obj, fp, ensure_ascii=False, indent=2,
                         cls=CustomJSONEncoder, **kwargs)
    else:
        return json.dump(obj, fp, ensure_ascii=False, indent=2,
                         cls=CustomJSONEncoder, **kwargs)

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
        return json.dumps(processed_obj, ensure_ascii=False, indent=2,
                          cls=CustomJSONEncoder, **kwargs)
    else:
        return json.dumps(obj, ensure_ascii=False, indent=2,
                          cls=CustomJSONEncoder, **kwargs)


def map_concurrently(func: Callable, items: List[Any], max_workers: int = 10) -> List[Any]:
    results = [None] * len(items)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {executor.submit(func, item): i for i, item in enumerate(items)}
        for future in tqdm(concurrent.futures.as_completed(future_to_index), total=len(items), desc="Processing via Class Method"):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as e:
                print(f"Item at index {index} generated an exception: {e}")
    return results