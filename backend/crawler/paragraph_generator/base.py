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

            # Only finalize if paragraph ends with punctuation
            # Don't finalize just because it starts with dialogue prefix
            if para_text.endswith(punctuation_suffixes):
                _finalize_buffer()

        # Finalize any remaining buffer
        _finalize_buffer()
        return result

    def _phase2_split_by_dialogue(self, paragraphs, dialogue_prefixes):
        """Phase 2: Split paragraphs by all DIALOGUE_PREFIXES"""
        result = []
        
        for page_num, para_text in paragraphs:
            # Find all dialogue prefix positions
            split_positions = []
            for prefix in dialogue_prefixes:
                pos = para_text.find(prefix)
                while pos != -1:
                    if pos == 0 or para_text[pos-1].isspace():  # Ensure it's at word boundary
                        split_positions.append(pos)
                    pos = para_text.find(prefix, pos + 1)
            
            if not split_positions:
                result.append((page_num, para_text))
                continue
                
            # Sort positions and split
            split_positions = sorted(set(split_positions))
            last_pos = 0
            
            for pos in split_positions:
                if pos > last_pos:
                    # Add text before this dialogue prefix
                    before_text = para_text[last_pos:pos].strip()
                    if before_text:
                        result.append((page_num, before_text))
                last_pos = pos
            
            # Add remaining text from last position
            if last_pos < len(para_text):
                remaining_text = para_text[last_pos:].strip()
                if remaining_text:
                    result.append((page_num, remaining_text))
                    
        return result

    def _phase3_combine_dialogue_pairs(self, paragraphs, stop_prefixes, answer_prefixes):
        """Phase 3: Combine consecutive dialogue paragraphs into single paragraphs"""
        result = []
        i = 0
        dialogue_prefixes = stop_prefixes + answer_prefixes
        
        while i < len(paragraphs):
            page_num, para_text = paragraphs[i]
            para_text = para_text.strip()
            
            # Check if current paragraph starts with dialogue prefix
            if para_text.startswith(dialogue_prefixes):
                # Start collecting consecutive dialogue paragraphs
                dialogue_buffer = [para_text]
                dialogue_page_num = page_num
                j = i + 1
                
                # Continue collecting while next paragraphs start with dialogue prefixes
                while (j < len(paragraphs) and 
                       paragraphs[j][1].strip().startswith(dialogue_prefixes)):
                    dialogue_buffer.append(paragraphs[j][1].strip())
                    j += 1
                
                # Combine all collected dialogue paragraphs
                combined_dialogue = "\n".join(dialogue_buffer)
                result.append((dialogue_page_num, combined_dialogue))
                i = j  # Skip all processed paragraphs
            else:
                # Non-dialogue paragraph, add as-is
                result.append((page_num, para_text))
                i += 1
                
        return result

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
