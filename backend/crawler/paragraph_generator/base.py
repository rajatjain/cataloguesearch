import logging
import re
from abc import ABC, abstractmethod
from typing import List, Tuple

from backend.config import Config

log_handle = logging.getLogger(__name__)

class BaseParagraphGenerator(ABC):
    def __init__(self, config: Config):
        self._config = config

    @property
    @abstractmethod
    def punctuation_suffixes(self):
        pass

    @property
    @abstractmethod
    def stop_prefixes(self):
        pass

    @property
    @abstractmethod
    def answer_prefixes(self):
        pass

    @property
    def dialogue_prefixes(self):
        return self.stop_prefixes + self.answer_prefixes

    def generate_paragraphs(self, paragraphs: List[Tuple[int, List[str]]],
                            file_metadata : dict) -> List[Tuple[int, List[str]]]:
        rejected_paras = []
        # Pass 1: Cleanup the null lines etc.
        log_handle.info(f"Generating paragraphs for {len(paragraphs)} pages")
        header_regex = file_metadata.get("header_regex", [])
        header_prefix = file_metadata.get("header_prefix", [])
        typo_list = file_metadata.get("typo_list", [])
        processed_paras = []
        for i, (page_num, para_list) in enumerate(paragraphs):
            for para_num, para in enumerate(para_list):
                para = self._normalize_text(para, typo_list)
                is_header, processed_para = \
                    self._is_header_footer(para_num, para, header_prefix, header_regex)
                if not is_header:
                    processed_paras.append((page_num, processed_para))
                else:
                    log_handle.verbose(f"Skipping para is_header: page:{page_num} -- {para}")
        # Pass 2: Intelligent para reordering
        final_paragraphs = self._combine_paragraphs(processed_paras)
        return final_paragraphs

    def _combine_paragraphs(self, flattened_paras):
        """Language-agnostic paragraph combination logic.
        Conditions:
            - for every paragraph, check if it ends with a punctuation mark
            - if it does, do nothing
            - if it does not, combine it with the next paragraph
            - if next para starts with dialogue prefixes then do not combine
            - if current para starts with question prefix and next with answer prefix then combine
            - final pass: combine Q&A sequences
        """

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
            if para_text.startswith(self.dialogue_prefixes):
                if final_para := _finalize_buffer(paragraph_buffer):
                    combined_phase1.append(final_para)

            # Add the current paragraph to the buffer.
            # If the buffer was just reset, this starts a new one.
            paragraph_buffer.append((page_num, para_text))

            # If the paragraph we just added ends with punctuation,
            # the buffered chunk is now complete. Finalize it.
            # For dialogue prefixes, only finalize if they also end with punctuation
            should_finalize = (para_text.endswith(self.punctuation_suffixes) or
                             (para_text.startswith(self.dialogue_prefixes) and
                              para_text.endswith(self.punctuation_suffixes)))

            if should_finalize:
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

            # Check if we have a question that can be combined with consecutive answers
            if para.startswith(self.stop_prefixes):
                combined_qa = para
                i += 1

                # Keep combining consecutive Q&A pairs
                while (i < num_paras and
                       combined_phase1[i][1].strip().startswith(self.answer_prefixes)):
                    next_para = combined_phase1[i][1].strip()
                    combined_qa += "\n" + next_para
                    i += 1

                    # Check if there's another question following this answer
                    if (i < num_paras and
                        combined_phase1[i][1].strip().startswith(self.stop_prefixes)):
                        next_question = combined_phase1[i][1].strip()
                        combined_qa += "\n" + next_question
                        i += 1

                combined_paragraphs.append((page_num, combined_qa))
            else:
                combined_paragraphs.append((page_num, para))
                i += 1
        return combined_paragraphs

    def _normalize_text(self, text: str, typo_list: List) -> str:
        if not isinstance(text, str):
            return ""

        cleaned_text = text

        # Common punctuation normalization
        cleaned_text = self._normalize_punctuation(cleaned_text)

        # Apply typo corrections
        cleaned_text = self._apply_typo_corrections(cleaned_text, typo_list)

        # Language-specific dialogue pattern normalization
        cleaned_text = self._normalize_dialogue_patterns(cleaned_text)

        # Final cleanup
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        return cleaned_text

    def _normalize_punctuation(self, text: str) -> str:
        # Normalize common OCR misclassifications for the purn viram (।)
        # The purn viram is often misread as |, I, l, or 1.
        purn_viram_errors = ['|', 'I', 'l', '1']
        for error_char in purn_viram_errors:
            text = text.replace(error_char, '।')

        # Normalize "double danda" (end of verses)
        text = text.replace("॥", "।")

        # Remove whitespace after opening punctuation marks.
        # This finds an opening punctuation mark followed by a space and removes the space.
        opening_punctuation = r'[(\[{\'"]'
        text = re.sub(r'(' + opening_punctuation + r')\s+', r'\1', text)

        # Remove whitespace before closing punctuation marks.
        # This finds a space before a closing punctuation mark and removes the space.
        closing_punctuation = r'[।.,?!:;)\]}\'"]'
        text = re.sub(r'\s+(' + closing_punctuation + r')', r'\1', text)

        # Normalize spacing around ellipses (two or more dots).
        # This removes any space before an ellipsis.
        text = re.sub(r'\s+(\.{2,})', r'\1', text)

        return text

    def _apply_typo_corrections(self, text: str, typo_list: List) -> str:
        for typo in typo_list:
            text = text.replace(typo[0], typo[1])
        return text

    @abstractmethod
    def _normalize_dialogue_patterns(self, text: str) -> str:
        pass

    def _is_header_footer(self, para_num, para, header_prefix, header_regex):
        for prefix in header_prefix:
            match = re.search(prefix, para)
            if match:
                stripped_content = match.group(0)
                log_handle.verbose(f"prefix: {prefix} Stripped: '{stripped_content}'")

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
                log_handle.verbose(f"regex: {regex} matched: '{para}'")
                return True, None

        return False, para
