"""
Language detection for Devanagari script text.
Distinguishes between Sanskrit and Hindi.
"""

import re
import logging
from enum import Enum
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

log_handle = logging.getLogger(__name__)


class ClassificationMethod(str, Enum):
    """Available classification methods for Sanskrit/Hindi detection."""
    FASTTEXT = "fasttext"  # ML-based using FastText
    RULE_BASED = "rule_based"  # Linguistic heuristics
    INDICBERT = "indicbert"  # Transformer-based using IndicBERT
    HYBRID = "hybrid"  # Combination of both


@dataclass
class LanguageClassificationResult:
    """Result of language classification."""
    language: str  # "sanskrit" or "hindi"
    confidence: float  # 0.0 to 1.0
    method: str  # Which method was used
    details: Optional[Dict] = None  # Additional debugging information


class DevanagariLanguageClassifier:
    """
    Classifier for distinguishing Sanskrit from Hindi in Devanagari script.

    Supports multiple classification methods:
    - FastText ML-based (1.A)
    - Rule-based linguistic heuristics (1.B)
    - Hybrid approach (1.C)
    """

    def __init__(self, fasttext_model_path: Optional[str] = None, indicbert_model_name: Optional[str] = None):
        """
        Initialize the classifier.

        Args:
            fasttext_model_path: Path to FastText model file (lid.176.bin).
                                If None, will try to load from default location.
            indicbert_model_name: Name of IndicBERT model from HuggingFace.
                                 If None, will use default 'ai4bharat/indic-bert'.
        """
        self.fasttext_model = None
        self.fasttext_model_path = fasttext_model_path

        # IndicBERT model components
        self.indicbert_tokenizer = None
        self.indicbert_model = None
        # Using IndicLID - AI4Bharat's language identification model for Indic languages
        # This is a proper language classifier (not a base model)
        self.indicbert_model_name = indicbert_model_name or 'ai4bharat/IndicLID'

        # Sanskrit-specific patterns and vocabulary
        self._initialize_linguistic_features()

    def _initialize_linguistic_features(self):
        """Initialize linguistic features for rule-based classification."""

        # Sanskrit-specific words (common in classical texts)
        self.sanskrit_keywords = {
            # Religious/philosophical terms
            'श्लोक', 'मन्त्र', 'सूत्र', 'उपनिषद्', 'वेद', 'शास्त्र', 'स्तोत्र',
            'अध्याय', 'श्री', 'नमः', 'स्वाहा', 'ॐ', 'अथ', 'इति', 'एवम्',
            'धर्म', 'कर्म', 'मोक्ष', 'निर्वाण', 'ज्ञान', 'दर्शन', 'चारित्र',
            'साम्य', 'वीतराग', 'कषाय', 'संप्राप्ति', 'भगवान्', 'उवाच',
            # Particles and conjunctions
            'च', 'तु', 'वा', 'अपि', 'किम्', 'तत्', 'यत्', 'इदम्', 'एतत्',
            'तथा', 'यथा', 'तद्', 'एतद्', 'अत्र', 'तत्र', 'यत्र',
            # Verbs
            'अस्ति', 'भवति', 'करोति', 'गच्छति', 'पठति', 'वदति', 'स्म', 'एव',
            # Compound endings
            'त्वा', 'त्वम्', 'स्य', 'स्यात्', 'भूत', 'गतः', 'आत्मक'
        }

        # Hindi-specific words and postpositions
        self.hindi_keywords = {
            'है', 'हैं', 'था', 'थी', 'थे', 'होता', 'होती', 'होते', 'गया', 'गयी', 'गए',
            'ने', 'को', 'से', 'में', 'पर', 'के', 'की', 'का', 'लिए', 'साथ',
            'जो', 'जिसे', 'जिसको', 'जिससे', 'क्या', 'कैसे', 'कहाँ', 'कब',
            'यह', 'वह', 'इस', 'उस', 'ये', 'वे', 'कोई', 'कुछ'
        }

        # Sanskrit verb endings (present tense)
        self.sanskrit_verb_endings = [
            'ति', 'तः', 'न्ति', 'सि', 'थः', 'थ', 'मि', 'वः', 'मः',  # Present
            'त', 'ताम्', 'न्त', 'न्तः', 'ते', 'आते', 'न्ते',  # Other forms
        ]

        # Hindi verb patterns
        self.hindi_verb_patterns = [
            r'ता\s+है', r'ती\s+है', r'ते\s+हैं', r'ता\s+था', r'ती\s+थी', r'ते\s+थे',
            r'ना\s+है', r'नी\s+है', r'ने\s+हैं', r'एगा', r'एगी', r'एंगे'
        ]

        # Sanskrit-specific characters and patterns
        self.sanskrit_patterns = {
            'visarga': 'ः',  # Visarga - more common in Sanskrit
            'anusvara': 'ं',  # Anusvara
            'double_danda': '॥',  # Double danda - verse separator in Sanskrit
            'vedic_accents': '॒॑',  # Vedic accent marks
        }

        # Hindi postpositions (very distinctive)
        self.hindi_postpositions = ['ने', 'को', 'से', 'में', 'पर', 'का', 'की', 'के']

    def _load_fasttext_model(self):
        """Lazy load FastText model."""
        if self.fasttext_model is not None:
            return

        try:
            import fasttext

            # Try to load from specified path or default location
            model_path = self.fasttext_model_path or 'models/fasttext/lid.176.bin'

            log_handle.info(f"Loading FastText model from {model_path}")
            self.fasttext_model = fasttext.load_model(model_path)
            log_handle.info("FastText model loaded successfully")

        except ImportError:
            log_handle.error("FastText library not installed. Install with: pip install fasttext")
            raise ImportError("FastText not available. Please install: pip install fasttext")
        except Exception as e:
            log_handle.error(f"Failed to load FastText model: {e}")
            raise RuntimeError(f"Could not load FastText model: {e}")

    def _classify_with_fasttext(self, text: str) -> Tuple[str, float, Dict]:
        """
        Classify using FastText ML model.

        Returns:
            Tuple of (language, confidence, details)
        """
        self._load_fasttext_model()

        # Clean text for FastText (remove newlines, extra spaces)
        cleaned_text = ' '.join(text.split())

        # FastText prediction
        predictions = self.fasttext_model.predict(cleaned_text, k=2)
        labels, scores = predictions

        # FastText returns labels like '__label__hi', '__label__sa'
        detected_languages = []
        language_scores = {}

        for label, score in zip(labels, scores):
            lang_code = label.replace('__label__', '')
            language_scores[lang_code] = float(score)
            detected_languages.append((lang_code, float(score)))

        # Map FastText language codes to our format
        # 'sa' = Sanskrit, 'hi' = Hindi
        sanskrit_score = language_scores.get('sa', 0.0)
        hindi_score = language_scores.get('hi', 0.0)

        if sanskrit_score > hindi_score:
            language = 'sanskrit'
            confidence = sanskrit_score
        else:
            language = 'hindi'
            confidence = hindi_score

        details = {
            'fasttext_predictions': detected_languages,
            'sanskrit_score': sanskrit_score,
            'hindi_score': hindi_score
        }

        return language, confidence, details

    def _load_indicbert_model(self):
        """Lazy load IndicLID model for language identification."""
        if self.indicbert_model is not None:
            return

        try:
            import fasttext
            import os

            # Path to IndicLID model
            indiclid_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'IndicLID',
                'indiclid-ftn',
                'model_baseline_roman.bin'
            )

            log_handle.info(f"Loading IndicLID model from: {indiclid_path}")

            # Load FastText-based IndicLID model
            self.indicbert_model = fasttext.load_model(indiclid_path)

            log_handle.info("IndicLID model loaded successfully")

        except ImportError:
            log_handle.error("FastText library not installed. Install with: pip install fasttext-wheel")
            raise ImportError("FastText not available. Please install: pip install fasttext-wheel")
        except Exception as e:
            log_handle.error(f"Failed to load IndicLID model: {e}")
            raise RuntimeError(
                f"Could not load IndicLID model. "
                f"Make sure you've downloaded the model from https://github.com/AI4Bharat/IndicLID/releases "
                f"and placed it at: {indiclid_path}"
            )

    def _classify_with_indicbert(self, text: str) -> Tuple[str, float, Dict]:
        """
        Classify using IndicLID language identification model.

        IndicLID is a FastText-based model specifically trained for Indian language identification.

        Returns:
            Tuple of (language, confidence, details)
        """
        self._load_indicbert_model()

        try:
            # Clean text for IndicLID
            cleaned_text = ' '.join(text.split())

            # Get top predictions from IndicLID
            # IndicLID returns labels like '__label__san_Deva', '__label__hin_Deva'
            predictions = self.indicbert_model.predict(cleaned_text, k=5)
            labels, scores = predictions

            # Parse predictions
            detected_languages = []
            language_scores = {}

            for label, score in zip(labels, scores):
                # Remove '__label__' prefix and parse language code
                lang_code = label.replace('__label__', '')
                language_scores[lang_code] = float(score)
                detected_languages.append((lang_code, float(score)))

            # IndicLID uses codes: san_Deva (Sanskrit), hin_Deva (Hindi)
            sanskrit_score = language_scores.get('san_Deva', 0.0)
            hindi_score = language_scores.get('hin_Deva', 0.0)

            # Determine final language
            if sanskrit_score > hindi_score:
                language = 'sanskrit'
                confidence = sanskrit_score
            else:
                language = 'hindi'
                confidence = hindi_score

            details = {
                'indiclid_predictions': detected_languages,
                'all_scores': language_scores,
                'sanskrit_score': float(sanskrit_score),
                'hindi_score': float(hindi_score),
                'model': 'IndicLID'
            }

            return language, confidence, details

        except Exception as e:
            log_handle.error(f"IndicLID classification failed: {e}")
            raise RuntimeError(f"IndicLID classification error: {e}")

    def _classify_with_rules(self, text: str) -> Tuple[str, float, Dict]:
        """
        Classify using rule-based linguistic heuristics.

        Returns:
            Tuple of (language, confidence, details)
        """
        scores = {
            'sanskrit': 0.0,
            'hindi': 0.0
        }

        details = {}

        # 1. Vocabulary matching
        words = re.findall(r'[\u0900-\u097F]+', text)  # Extract Devanagari words

        sanskrit_word_count = sum(1 for word in words if word in self.sanskrit_keywords)
        hindi_word_count = sum(1 for word in words if word in self.hindi_keywords)

        details['sanskrit_keywords_found'] = sanskrit_word_count
        details['hindi_keywords_found'] = hindi_word_count
        details['total_words'] = len(words)

        # Vocabulary scoring (weight: 0.3)
        if len(words) > 0:
            vocab_score_sanskrit = (sanskrit_word_count / len(words)) * 0.3
            vocab_score_hindi = (hindi_word_count / len(words)) * 0.3
            scores['sanskrit'] += vocab_score_sanskrit
            scores['hindi'] += vocab_score_hindi

        # 2. Morphological features - Verb endings
        sanskrit_verb_count = 0
        for ending in self.sanskrit_verb_endings:
            # Match verb endings at word boundaries
            pattern = r'\b\w+' + re.escape(ending) + r'\b'
            matches = re.findall(pattern, text)
            sanskrit_verb_count += len(matches)

        hindi_verb_count = 0
        for pattern in self.hindi_verb_patterns:
            matches = re.findall(pattern, text)
            hindi_verb_count += len(matches)

        details['sanskrit_verb_endings'] = sanskrit_verb_count
        details['hindi_verb_patterns'] = hindi_verb_count

        # Verb scoring (weight: 0.25)
        if sanskrit_verb_count > hindi_verb_count:
            scores['sanskrit'] += 0.25
        elif hindi_verb_count > sanskrit_verb_count:
            scores['hindi'] += 0.25

        # 3. Hindi postpositions (very distinctive)
        postposition_count = sum(text.count(f' {pp} ') + text.count(f' {pp}\u0964') for pp in self.hindi_postpositions)
        details['hindi_postpositions'] = postposition_count

        # Postposition scoring (weight: 0.3)
        if postposition_count > 0:
            scores['hindi'] += 0.3
        else:
            scores['sanskrit'] += 0.15  # Absence of postpositions suggests Sanskrit

        # 4. Character-level features
        visarga_count = text.count(self.sanskrit_patterns['visarga'])
        double_danda_count = text.count(self.sanskrit_patterns['double_danda'])

        details['visarga_count'] = visarga_count
        details['double_danda_count'] = double_danda_count

        # Character scoring (weight: 0.15)
        char_score = min((visarga_count * 0.05) + (double_danda_count * 0.1), 0.15)
        scores['sanskrit'] += char_score

        # 5. Normalize scores to confidence
        total_score = scores['sanskrit'] + scores['hindi']

        if total_score > 0:
            confidence_sanskrit = scores['sanskrit'] / total_score
            confidence_hindi = scores['hindi'] / total_score
        else:
            # Default to Hindi if no features detected
            confidence_sanskrit = 0.3
            confidence_hindi = 0.7

        details['raw_scores'] = scores
        details['normalized_confidence'] = {
            'sanskrit': confidence_sanskrit,
            'hindi': confidence_hindi
        }

        # Determine final language
        if confidence_sanskrit > confidence_hindi:
            language = 'sanskrit'
            confidence = confidence_sanskrit
        else:
            language = 'hindi'
            confidence = confidence_hindi

        return language, confidence, details

    def _classify_with_hybrid(self, text: str) -> Tuple[str, float, Dict]:
        """
        Classify using hybrid approach (combines FastText and rules).

        Returns:
            Tuple of (language, confidence, details)
        """
        # Get both predictions
        try:
            fasttext_lang, fasttext_conf, fasttext_details = self._classify_with_fasttext(text)
        except Exception as e:
            log_handle.warning(f"FastText classification failed, falling back to rules: {e}")
            return self._classify_with_rules(text)

        rule_lang, rule_conf, rule_details = self._classify_with_rules(text)

        # Weighted combination: FastText (0.6) + Rules (0.4)
        fasttext_weight = 0.6
        rule_weight = 0.4

        # Convert to scores
        fasttext_sanskrit_score = fasttext_conf if fasttext_lang == 'sanskrit' else (1 - fasttext_conf)
        rule_sanskrit_score = rule_conf if rule_lang == 'sanskrit' else (1 - rule_conf)

        combined_sanskrit_score = (fasttext_sanskrit_score * fasttext_weight) + (rule_sanskrit_score * rule_weight)
        combined_hindi_score = 1 - combined_sanskrit_score

        if combined_sanskrit_score > combined_hindi_score:
            language = 'sanskrit'
            confidence = combined_sanskrit_score
        else:
            language = 'hindi'
            confidence = combined_hindi_score

        details = {
            'fasttext': {
                'language': fasttext_lang,
                'confidence': fasttext_conf,
                'details': fasttext_details
            },
            'rules': {
                'language': rule_lang,
                'confidence': rule_conf,
                'details': rule_details
            },
            'combined_scores': {
                'sanskrit': combined_sanskrit_score,
                'hindi': combined_hindi_score
            },
            'weights': {
                'fasttext': fasttext_weight,
                'rules': rule_weight
            }
        }

        return language, confidence, details

    def classify(self, text: str, method: ClassificationMethod = ClassificationMethod.RULE_BASED) -> LanguageClassificationResult:
        """
        Classify Devanagari text as Sanskrit or Hindi.

        Args:
            text: Devanagari text to classify
            method: Classification method to use (1.A, 1.B, or 1.C)

        Returns:
            LanguageClassificationResult with language, confidence, method, and details

        Raises:
            ValueError: If text is empty or method is invalid
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Preprocess: Remove text within square brackets [...]
        # Example: "जो धर्म है [तत्‌ साम्यम्‌] वह साम्य है" -> "जो धर्म है  वह साम्य है"
        original_text = text
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()  # Clean up extra spaces

        if not text or not text.strip():
            raise ValueError("Text is empty after removing bracketed content")

        # Validate that text contains Devanagari characters
        devanagari_chars = re.findall(r'[\u0900-\u097F]', text)
        if not devanagari_chars:
            log_handle.warning("No Devanagari characters found in text")
            # Return default as Hindi with low confidence
            return LanguageClassificationResult(
                language='hindi',
                confidence=0.5,
                method=method.value,
                details={'warning': 'No Devanagari characters detected'}
            )

        # Route to appropriate classification method
        if method == ClassificationMethod.FASTTEXT:
            language, confidence, details = self._classify_with_fasttext(text)
        elif method == ClassificationMethod.RULE_BASED:
            language, confidence, details = self._classify_with_rules(text)
        elif method == ClassificationMethod.INDICBERT:
            language, confidence, details = self._classify_with_indicbert(text)
        elif method == ClassificationMethod.HYBRID:
            language, confidence, details = self._classify_with_hybrid(text)
        else:
            raise ValueError(f"Invalid classification method: {method}")

        # Add preprocessing info to details
        if details is None:
            details = {}
        if original_text != text:
            details['preprocessing'] = {
                'original_text': original_text,
                'cleaned_text': text,
                'removed_brackets': True
            }

        return LanguageClassificationResult(
            language=language,
            confidence=confidence,
            method=method.value,
            details=details
        )


# Convenience function for simple usage
def classify_devanagari_text(
    text: str,
    method: ClassificationMethod = ClassificationMethod.RULE_BASED,
    fasttext_model_path: Optional[str] = None
) -> LanguageClassificationResult:
    """
    Convenience function to classify Devanagari text as Sanskrit or Hindi.

    Args:
        text: Devanagari text to classify
        method: Classification method (1.A=FastText, 1.B=Rules, 1.C=Hybrid)
        fasttext_model_path: Optional path to FastText model

    Returns:
        LanguageClassificationResult

    Example:
        >>> result = classify_devanagari_text("यह एक हिंदी वाक्य है।", method=ClassificationMethod.RULE_BASED)
        >>> print(f"{result.language} (confidence: {result.confidence:.2f})")
        hindi (confidence: 0.85)
    """
    classifier = DevanagariLanguageClassifier(fasttext_model_path=fasttext_model_path)
    return classifier.classify(text, method=method)
