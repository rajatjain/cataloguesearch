"""
Simple language detection utility for determining if text is in English.
"""

import re


def is_english(text: str, threshold: float = 0.7) -> bool:
    """
    Determine if text is in English by checking if threshold percentage of characters are English.

    This function ignores spaces and other whitespace when calculating the percentage.
    Only alphanumeric characters are considered.

    Args:
        text: Input text to check
        threshold: Minimum percentage of English characters required (default: 0.7 = 70%)

    Returns:
        True if the text has >= threshold English characters, False otherwise

    Example:
        >>> is_english("Hello world")
        True
        >>> is_english("Hello नमस्ते")
        False
        >>> is_english("ram")
        True
        >>> is_english("राम")
        False
        >>> is_english("")
        False
    """
    # Remove all whitespace
    text_no_whitespace = re.sub(r'\s+', '', text)

    # If text is empty after removing whitespace, return False
    if not text_no_whitespace:
        return False

    # Count English characters (a-z, A-Z)
    english_chars = sum(1 for char in text_no_whitespace if char.isalpha() and char.isascii())

    # Count total non-whitespace characters
    total_chars = len(text_no_whitespace)

    # Calculate percentage
    if total_chars == 0:
        return False

    english_percentage = english_chars / total_chars

    return english_percentage >= threshold
