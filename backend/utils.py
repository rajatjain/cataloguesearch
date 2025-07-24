import json
import os
import copy
from pathlib import Path
import yaml

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
        return json.dump(processed_obj, fp, ensure_ascii=False, indent=2, **kwargs)
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
        return json.dumps(processed_obj, ensure_ascii=False, indent=2, **kwargs)
    else:
        return json.dumps(obj, ensure_ascii=False, indent=4, **kwargs)
