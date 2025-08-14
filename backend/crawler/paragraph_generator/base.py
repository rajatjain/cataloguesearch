import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

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
        """Three-phase approach:
        Phase 1: Combine paragraphs until each ends with proper punctuation
        Phase 2: Split by all DIALOGUE_PREFIXES  
        Phase 3: Combine paragraphs when multiple start with dialogue prefixes
        """
        # Define constants for clarity
        PUNCTUATION_SUFFIXES = ('।', '?', '!', ':', ')', ']', '}')
        STOP_PREFIXES = ("श्रोता:", "मुमुक्षु:", "प्रश्न:")
        ANSWER_PREFIXES = ("पूज्य गुरुदेवश्री:", "उत्तर:", "समाधान:")
        DIALOGUE_PREFIXES = STOP_PREFIXES + ANSWER_PREFIXES

        # Phase 1: Ensure each paragraph is fully punctuated
        phase1_result = self._phase1_ensure_punctuation(flattened_paras, PUNCTUATION_SUFFIXES, DIALOGUE_PREFIXES)
        
        # Phase 2: Split by all DIALOGUE_PREFIXES
        phase2_result = self._phase2_split_by_dialogue(phase1_result, DIALOGUE_PREFIXES)
        
        # Phase 3: Combine paragraphs when multiple start with dialogue prefixes
        phase3_result = self._phase3_combine_dialogue_pairs(phase2_result, STOP_PREFIXES, ANSWER_PREFIXES)
        
        return phase3_result

    def _phase1_ensure_punctuation(self, flattened_paras, punctuation_suffixes, dialogue_prefixes):
        """Phase 1: Append paragraphs until each paragraph ends with proper punctuation"""
        result = []
        paragraph_buffer = []

        def _finalize_buffer():
            if not paragraph_buffer:
                return
            page_num = paragraph_buffer[0][0]
            text_content = " ".join(p[1] for p in paragraph_buffer)
            result.append((page_num, text_content))
            paragraph_buffer.clear()

        for page_num, para_text in flattened_paras:
            para_text = para_text.strip()
            if not para_text:
                continue

            paragraph_buffer.append((page_num, para_text))

            # If the paragraph we just added ends with punctuation,
            # the buffered chunk is now complete. Finalize it.
            # For dialogue prefixes, only finalize if they also end with punctuation
            should_finalize = (para_text.endswith(PUNCTUATION_SUFFIXES) or 
                             (para_text.startswith(DIALOGUE_PREFIXES) and 
                              para_text.endswith(PUNCTUATION_SUFFIXES)))
            
            if should_finalize:
                if final_para := _finalize_buffer(paragraph_buffer):
                    combined_phase1.append(final_para)

        # Finalize any remaining buffer
        _finalize_buffer()
        return result

    def _phase2_split_by_dialogue(self, paragraphs, dialogue_prefixes):
        num_paras = len(combined_phase1)
        while i < num_paras:
            page_num, para = combined_phase1[i]
            para = para.strip()

            # Check if we have a question that can be combined with consecutive answers
            if para.startswith(STOP_PREFIXES):
                combined_qa = para
                i += 1
                
                # Keep combining consecutive Q&A pairs
                while (i < num_paras and 
                       combined_phase1[i][1].strip().startswith(ANSWER_PREFIXES)):
                    next_para = combined_phase1[i][1].strip()
                    combined_qa += "\n" + next_para
                    i += 1
                    
                    # Check if there's another question following this answer
                    if (i < num_paras and 
                        combined_phase1[i][1].strip().startswith(STOP_PREFIXES)):
                        next_question = combined_phase1[i][1].strip()
                        combined_qa += "\n" + next_question
                        i += 1
                
                combined_paragraphs.append((page_num, combined_qa))
            else:
                # Non-dialogue paragraph, add as-is
                result.append((page_num, para_text))
                i += 1
                
        return result

    def _normalize_text(self, text: str, typo_list: List):
        raise NotImplementedError("Implement inside subclass")

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
