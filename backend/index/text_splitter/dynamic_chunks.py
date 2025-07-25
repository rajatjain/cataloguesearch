import logging
import os
import re

from sentence_transformers import SentenceTransformer, util as st_util

from backend.common.embedding_models import get_embedding_model
from backend.index.text_splitter.base import BaseChunkSplitter
from backend.utils import json_dumps

log_handle = logging.getLogger(__name__)

class DynamicChunksSplitter(BaseChunkSplitter):
    def __init__(self, config):
        super().__init__(config)
        self._similarity_threshold = \
            config.settings()["index"]["chunking_algos"]["dynamic"]["similarity_threshold"]
        self._stop_phrases = self._get_default_stop_phrases()
        # --- NEW: Pre-compile the regex pattern for efficiency ---
        sorted_phrases = sorted(list(self._stop_phrases), key=len, reverse=True)
        self._stop_phrases_pattern = re.compile(
            r'\s*(' + '|'.join(re.escape(p) for p in sorted_phrases) + r')\s*[।?!]*'
        )


    def get_chunks(self, document_id, pages_text_path: list[str]) -> list[dict]:
        """
        Splits the text from the given pages into dynamic chunks based on the configured chunk size and overlap.

        Args:
            pages_text_path (list[str]): List of file paths containing text content.

        Returns:
            list[str]: A list of text chunks.
        """
        max_pages = len(pages_text_path)
        all_chunks = []
        model = get_embedding_model(self._config.EMBEDDING_MODEL_NAME)
        log_handle.info(
            f"Generating embeddings for {max_pages} pages..."
        )
        for i, fname in enumerate(pages_text_path):
            page_num = self._get_page_num(fname)
            log_handle.info(f"Processing page {page_num} for file {fname}...")
            if not os.path.exists(fname):
                log_handle.error(f"File not found: {fname}")
                continue
            raw_text = ""
            with open(fname, "r", encoding="utf-8") as f:
                raw_text = f.read()
            cleaned_text = self._clean_page_content(raw_text)
            if not cleaned_text.strip():
                continue
            paragraphs = re.split(r"\n\s*\n", cleaned_text)

            for para_index, paragraph_text in enumerate(paragraphs):
                if not paragraph_text.strip():
                    continue
                paragraph_id = f"para_p{page_num:04d}_i{para_index:02d}"

                raw_sentences = re.split(r'(?<=[।?!])\s*', paragraph_text)
                stripped_sentences = [s.strip() for s in raw_sentences if s.strip()]
                sentences = []
                min_words_in_sentence = 2
                if stripped_sentences:
                    sentence_buffer = stripped_sentences[0]
                    for i in range(1, len(stripped_sentences)):
                        next_sentence = stripped_sentences[i]
                        if len(next_sentence.split()) < min_words_in_sentence:
                            sentence_buffer += " " + next_sentence
                        else:
                            sentences.append(sentence_buffer)
                            sentence_buffer = next_sentence
                    sentences.append(sentence_buffer)

                if not sentences:
                    log_handle.info(f"No sentences found in paragraph {para_index}...")
                    continue

                base_doc = {
                    "document_id": document_id,
                    "page_number": page_num,
                    "paragraph_id": paragraph_id,
                    "text_content": paragraph_text
                }
                if len(sentences) == 1:
                    chunk_id = self._get_document_hash(
                        document_id, page_num, para_index, sentences[0]
                    )
                    embedded_text = self._create_embedding_text(sentences)
                    curr_doc = base_doc.copy()
                    curr_doc["chunk_id"] = chunk_id
                    curr_doc["embedding_text"] = embedded_text
                    all_chunks.append(curr_doc)
                    continue

                embeddings = model.encode(
                    sentences, convert_to_tensor=True, normalize_embeddings=True)
                similarities = st_util.cos_sim(embeddings, embeddings)
                adjacent_similarities = [
                    similarities[i, i+1].item() for i in range(len(sentences) - 1)
                ]

                current_chunk_start_index = 0
                chunk_counter_in_para = 0
                for i, score in enumerate(adjacent_similarities):
                    # More robust logic to prevent breaks around filler sentences ---
                    # Clean the sentences of punctuation before checking against the stop phrase set.
                    cleaned_s1 = re.sub(r'[।?!]+$', '', sentences[i]).strip()
                    cleaned_s2 = re.sub(r'[।?!]+$', '', sentences[i+1]).strip()

                    is_stop_boundary = cleaned_s1 in self._stop_phrases or \
                                       cleaned_s2 in self._stop_phrases
                    if score < self._similarity_threshold and not is_stop_boundary:
                        chunk_end_index = i + 1
                        embedding_text = self._create_embedding_text(
                            sentences[current_chunk_start_index:chunk_end_index]
                        )
                        chunk_id = self._get_document_hash(
                            document_id, page_num, para_index, embedding_text
                        )
                        curr_doc = base_doc.copy()
                        curr_doc["chunk_id"] = chunk_id
                        curr_doc["embedding_text"] = embedding_text
                        all_chunks.append(curr_doc)
                        current_chunk_start_index = chunk_end_index
                        chunk_counter_in_para += 1

                final_part_text = " ".join(sentences[current_chunk_start_index:])
                if final_part_text.strip():
                    embedding_text = self._create_embedding_text(sentences[current_chunk_start_index:])
                    chunk_id = self._get_document_hash(document_id, page_num, para_index, embedding_text)
                    curr_doc = base_doc.copy()
                    curr_doc["chunk_id"] = chunk_id
                    curr_doc["embedding_text"] = embedding_text
                    all_chunks.append(curr_doc)

                log_handle.verbose(
                    f"all_chunks: {json_dumps(all_chunks)}"
                )
        log_handle.info(f"Generating embeddings for {len(all_chunks)} chunks in parallel...")
        all_chunks_embeddings = self._add_embeddings_parallel(all_chunks)
        return all_chunks

    def _clean_page_content(self, text: str) -> str:
        """
        Removes header and footer text from a page based on finding the first and
        last lines that contain sentence-terminating punctuation.
        """
        lines = text.split('\n')

        # Find the start index of the content block
        content_start_index = -1
        for i, line in enumerate(lines):
            if self._is_likely_content_line(line):
                content_start_index = i
                break

        # Find the end index of the content block (searching from the end)
        content_end_index = -1
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]
            if self._is_likely_content_line(line):
                content_end_index = i
                break

        # If no valid content lines were found, return an empty string
        if content_start_index == -1 \
                or content_end_index == -1 or content_start_index > content_end_index:
            return ""

        # Extract the content block from the first valid line to the last valid line
        content_lines = lines[content_start_index : content_end_index + 1]

        return "\n".join(content_lines)

    def _is_likely_content_line(self, line: str) -> bool:
        """
        A simple heuristic to determine if a line is content.
        A line is considered content ONLY if it contains a sentence-terminating punctuation mark.
        """
        stripped_line = line.strip()
        if not stripped_line:
            return False

        # A line is content if it has punctuation. All other heuristics are removed.
        has_punctuation = any(p in stripped_line for p in ['।', '?', '!'])
        return has_punctuation

    def _get_default_stop_phrases(self) -> set[str]:
        """
        Returns a list of stop phrases that are used to identify non-content lines.
        """
        return {
            "आहा", "आहाहा", "समझ में आया", "देखो", "है न", "आहाहाहा"
        }

    def _create_embedding_text(self, sentences: list) -> str:
        """
        Creates a clean string for embedding by removing stop phrases from the joined text.
        """
        # --- FIX: New logic to remove stop phrases from within the text ---
        # 1. Join all sentences of the chunk to form the initial text.
        full_chunk_text = " ".join(sentences)

        # 2. Use the pre-compiled regex to replace all occurrences of stop phrases with a space.
        cleaned_text = self._stop_phrases_pattern.sub(' ', full_chunk_text)

        # 3. Clean up any resulting multiple spaces to ensure a clean final string.
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        return cleaned_text
