import logging
import re

from backend.crawler.text_splitter.base import BaseChunkSplitter
from backend.utils import json_dumps

log_handle = logging.getLogger(__name__)

class ParagraphChunksSplitter(BaseChunkSplitter):
    def __init__(self, config):
        super().__init__(config)

    def get_chunks(self, document_id :str, pages_text_path: list[str]) -> list[dict]:
        """
        Processes a list of file paths into paragraph chunks.

        Args:
            document_id (str): The unique identifier of the document.
            pages_text_path (list[str]): A list of file paths.

        Returns:
            list[dict]: A list of dictionaries, each representing a paragraph.
        """
        log_handle.info(f"Processing {len(pages_text_path)} pages...")
        sorted_file_paths = sorted(pages_text_path)

        buffer_page_num = -1
        page_num_params_dict = dict()
        for file_path in sorted_file_paths:
            page_num = self._get_page_num(file_path)
            log_handle.info(f"Processing page {page_num} for file {file_path}...")

            raw_text = ""
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            clean_text = self._clean_page_content(raw_text)
            if not clean_text.strip():
                continue
            page_paras = re.split(r'\n\s*\n', clean_text)
            log_handle.verbose(f"page {page_num} has {len(page_paras)} paragraphs")

            if buffer_page_num != -1:
                log_handle.verbose(f"last para of page {buffer_page_num} is incomplete")
                # last para of previous page is incomplete
                last_para = page_num_params_dict[buffer_page_num][-1]
                last_para += "\n" + page_paras[0]
                page_num_params_dict[buffer_page_num][-1] = last_para
                del page_paras[0]
                buffer_page_num = -1

            # Skip if no paragraphs left after merging
            if not page_paras:
                continue

            last_para = page_paras[-1]
            last_line = last_para.strip().split('\n')[-1]
            last_line = last_line.strip()
            # last character of last line should be a stop phrase
            if not any(p in last_line[-1] for p in ['।', '?', '!', '|']):
                log_handle.info(f"last para of page {page_num} is incomplete")
                buffer_page_num = page_num

            log_handle.verbose(f"page {page_num} has {json_dumps(page_paras)} paragraphs")
            page_num_params_dict[page_num] = page_paras

        # now fill the dicts

        all_chunks = []
        for page_num in page_num_params_dict.keys():
            paras = page_num_params_dict[page_num]
            for i, para in enumerate(paras):
                para_id = f"{page_num}_i{i}"
                chunk_id = self._get_document_hash(
                    document_id, page_num, i, para.strip()
                )
                chunk = {
                    "document_id": document_id,
                    "paragraph_id": para_id,
                    "page_number": page_num,
                    "chunk_id": chunk_id,
                    "text_content": para.strip()
                }
                all_chunks.append(chunk)

        all_chunks.sort(key=lambda x: (x["page_number"], x["paragraph_id"]))
        return all_chunks