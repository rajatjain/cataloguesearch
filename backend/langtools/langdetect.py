"""
Simple language detection utility for determining if text is in English, Hindi, or Sanskrit.
"""

import re

# Hindi stopwords for language detection
HINDI_STOPWORDS = {
    # Original list
    "है", "हैं", "के", "को", "में", "से", "की", "का", "पर", "कि", "और", "ही", "भी", "तो", "नहीं", "यह", "वह", "इस", "उस", "जो",

    # Verbs (to be)
    "ने", "थे", "था", "थी", "थीं", "हो", "होता", "होती", "होते", "हूँ", "हूं",

    # Past tense markers
    "गया", "गई", "गए", "गयी", "गये",

    # Continuous tense
    "रहा", "रही", "रहे", "रहें",

    # Motion verbs
    "जा", "जाता", "जाती", "जाते",

    # Postpositions
    "लिए", "साथ", "बाद", "पहले", "तक", "द्वारा", "बिना", "अंदर", "बाहर",

    # Temporal/aspectual
    "अभी", "अब", "फिर", "कभी", "जब", "तब",

    # Adjectival suffix
    "वाला", "वाली", "वाले", "वालों",

    # Pronouns
    "मैं", "तुम", "आप", "हम", "तुम्हारा", "तुम्हारी", "तुम्हारे",
    "उन", "उनका", "उनकी", "उनके", "इन", "इनका", "इनकी", "इनके",
    "मेरा", "मेरी", "मेरे", "हमारा", "हमारी", "हमारे",
    "कोई", "कुछ", "सब", "सभी", "कौन", "किसी", "किसे",

    # Conjunctions
    "या", "लेकिन", "परन्तु", "परंतु", "मगर", "जैसे", "वैसे", "ऐसे",

    # Question words
    "क्या", "कैसे", "कब", "कहाँ", "कहां", "क्यों", "कितना", "कितनी", "कितने",

    # Others
    "एक", "दो", "बहुत", "ज्यादा", "कम", "थोड़ा", "सकता", "सकती", "सकते", "चाहिए"
}


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


def detect_hindi_or_sanskrit(text: str, min_stopword_matches: int = 1) -> str:
    """
    Detect if Devanagari text is Hindi or Sanskrit based on Hindi stopwords.

    This function tokenizes the text and checks for presence of common Hindi stopwords.
    If enough Hindi stopwords are found, the text is classified as Hindi, otherwise Sanskrit.

    Args:
        text: Input text in Devanagari script
        min_stopword_matches: Minimum number of Hindi stopword matches to classify as Hindi (default: 1)

    Returns:
        "hindi" if Hindi stopwords are found, "sanskrit" otherwise

    Example:
        >>> detect_hindi_or_sanskrit("यह एक किताब है")
        'hindi'
        >>> detect_hindi_or_sanskrit("रामायणम् महाकाव्यम्")
        'sanskrit'
    """
    # Tokenize by splitting on whitespace and common punctuation
    tokens = re.findall(r'\S+', text.lower())

    # Count matches with Hindi stopwords
    hindi_matches = sum(1 for token in tokens if token in HINDI_STOPWORDS)

    # If we have enough Hindi stopword matches, classify as Hindi
    return "hindi" if hindi_matches >= min_stopword_matches else "sanskrit"
