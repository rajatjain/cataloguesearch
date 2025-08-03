import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from backend.common.embedding_models import get_embedding
from backend.config import Config
from backend.utils import json_dumps

log_handle = logging.getLogger(__name__)

class BaseParagraphGenerator:
    def __init__(self, config: Config):
        self._config = config

    def generate_paragraphs(self, paragraphs: List[Tuple[int, List[str]]],
                            file_metadata : dict) -> List[Tuple[int, List[str]]]:
        rejected_paras = []
        # Pass 1: Cleanup the null lines etc.
        log_handle.info(f"scan_config: {json_dumps(file_metadata)}")
        header_regex = file_metadata.get("header_regex", [])
        header_prefix = file_metadata.get("header_prefix", [])
        processed_paras = []
        for i, (page_num, para_list) in enumerate(paragraphs):
            for para_num, para in enumerate(para_list):
                para = self._normalize_text(para)
                is_header, processed_para = \
                    self._is_header_footer(para_num, para, header_prefix, header_regex)
                if not is_header:
                    processed_paras.append((page_num, processed_para))

        # Pass 2: Intelligent para reordering
        final_paragraphs = self._combine_paragraphs(processed_paras)
        return final_paragraphs

    def _combine_paragraphs(self, flattened_paras):
        """Conditions:
            - for every paragraph, check if it ends with a punctuation mark
            - if it does, do nothing
            - if it does not, combine it with the next paragraph
            - if next para starts with "श्रोता:" then do not combine
            - if current para starts with "श्रोता:" and next with "पूज्य गुरुदेवश्री:" then combine
            - final pass: if any para contains "(श्रोता: " then split the rest of it into two paragraphs
        """
        i = 0
        # --- Start of Refactored Section ---

        # Define constants for clarity
        PUNCTUATION_SUFFIXES = ('।', '?', '!', ':', ')', ']', '}')
        STOP_PREFIXES = ("श्रोता:", "मुमुक्षु:", "प्रश्न:")
        ANSWER_PREFIXES = ("पूज्य गुरुदेवश्री:", "उत्तर:", "समाधान:")
        DIALOGUE_PREFIXES = STOP_PREFIXES + ANSWER_PREFIXES

        combined_phase1 = []
        # A buffer to hold paragraphs that are being combined into a single thought.
        paragraph_buffer = []

        def _finalize_buffer(buf: list) -> tuple | None:
            """
            Combines paragraphs in the buffer, clears the buffer,
            and returns the final (page_num, text) tuple.
            """
            if not buf:
                return None
            # The page number of the combined paragraph is the page number of its first part.
            page_num = buf[0][0]
            # Join the text parts.
            text_content = " ".join(p[1] for p in buf)
            buf.clear()  # Clear the buffer after processing
            return page_num, text_content

        for page_num, para_text in flattened_paras:
            para_text = para_text.strip()
            if not para_text:
                continue

            # If the current paragraph starts with a stop prefix, it marks the
            # end of the previous buffered paragraph. Finalize the buffer before proceeding.
            if para_text.startswith(DIALOGUE_PREFIXES):
                if final_para := _finalize_buffer(paragraph_buffer):
                    combined_phase1.append(final_para)

            # Add the current paragraph to the buffer.
            # If the buffer was just reset, this starts a new one.
            paragraph_buffer.append((page_num, para_text))

            # If the paragraph we just added ends with punctuation,
            # the buffered chunk is now complete. Finalize it.
            if para_text.endswith(PUNCTUATION_SUFFIXES) \
                    or para_text.startswith(DIALOGUE_PREFIXES):
                if final_para := _finalize_buffer(paragraph_buffer):
                    combined_phase1.append(final_para)

        # After the loop, there might be a remaining incomplete paragraph in the buffer.
        if final_para := _finalize_buffer(paragraph_buffer):
            combined_phase1.append(final_para)

        combined_paragraphs = []
        i = 0
        num_paras = len(combined_phase1)
        while i < num_paras:
            page_num, para = combined_phase1[i]
            para = para.strip()

            # Check if the next paragraph exists and meets the combination criteria
            if (para.startswith(STOP_PREFIXES) and
                    i + 1 < num_paras and
                    combined_phase1[i + 1][1].strip().startswith(ANSWER_PREFIXES)):

                # Combine with the next paragraph ---
                next_para = combined_phase1[i + 1][1].strip()
                combined_para = para + "\n" + next_para
                combined_paragraphs.append((page_num, combined_para))

                i += 2
            else:
                combined_paragraphs.append((page_num, para))
                i += 1
        return combined_paragraphs

    def _normalize_text(self, text: str):
        raise NotImplementedError("Implement inside subclass")

    def _is_header_footer(self, para_num, para, header_prefix, header_regex):
        for prefix in header_prefix:
            para = re.sub(prefix, '', para, count=1)
            para = para.strip()

        if para_num == 0 and len(para) < 35 \
                and len(re.findall(f"[0-9०-९]", para)) > 2:
            return True, None

        # Para has many numbers in it.
        if 0 < len(para) < 20:
            all_digits = r'[0-9०-९]'
            num_digits = len(re.findall(all_digits, para))
            if num_digits / len(para) >= 0.3:
                return True, None

        # Check if para is a header_regex
        for regex in header_regex:
            if re.search(regex, para):
                return True, None

        return False, para

