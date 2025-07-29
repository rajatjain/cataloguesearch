import re
from typing import List

from backend.crawler.paragraph_generator.base import BaseParagraphGenerator, log_handle


class HindiParagraphGenerator(BaseParagraphGenerator):
    def __init__(self, config):
        super().__init__(config)

    def _normalize_text(self, para_num, text: str) -> str:
        if not isinstance(text, str):
            return ""

        log_handle.info(f"Calling normalize text")
        cleaned_text = text

        if para_num == 0 and len(text) < 35 \
            and len(re.findall(f"[0-9०-९]", text)) > 2:
            log_handle.info(f"Para 0, less text. High probability that this is a header. {text}")

        # Normalize common OCR misclassifications for the purn viram (।)
        # The purn viram is often misread as |, I, l, or 1.
        purn_viram_errors = ['|', 'I', 'l', '1']
        for error_char in purn_viram_errors:
            cleaned_text = cleaned_text.replace(error_char, '।')

        # Normalize "double danda" (end of verses)
        cleaned_text = cleaned_text.replace("॥", "।")

        # Remove whitespace after opening punctuation marks.
        # This finds an opening punctuation mark followed by a space and removes the space.
        opening_punctuation = r'[(\[{\'"]'
        cleaned_text = re.sub(r'(' + opening_punctuation + r')\s+', r'\1', cleaned_text)

        # Remove whitespace before closing punctuation marks.
        # This finds a space before a closing punctuation mark and removes the space.
        closing_punctuation = r'[।,?!:;)\]}\'"]'
        cleaned_text = re.sub(r'\s+(' + closing_punctuation + r')', r'\1', cleaned_text)

        # Normalize spacing around ellipses (two or more dots).
        # This removes any space before an ellipsis.
        cleaned_text = re.sub(r'\s+(\.{2,})', r'\1', cleaned_text)

        cleaned_text = cleaned_text.replace("गुरुदेव श्री", "गुरुदेवश्री")

        # Join multiple lines into a single line with spaces
        # BUT do not join lines that start with "श्रोता:" or "पूज्य गुरुदेवश्री:" or "मुमुक्षु:"
        cleaned_text = re.sub(r'\n(?!श्रोता:|पूज्य गुरुदेवश्री:|मुमुक्षु:)', ' ', cleaned_text)

        # Clean up any potential multiple spaces that might have been created
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        log_handle.info(f"Normalized text: {cleaned_text}")
        return cleaned_text