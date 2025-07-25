from backend.index.text_splitter.base import BaseChunkSplitter


class DynamicChunksSplitter(BaseChunkSplitter):
    def __init__(self, config, document_id):
        self._similarity_threshold = \
            config.settings()["chunking_algos"]["dynamic"]["similarity_threshold"]

    def get_chunks(self, pages_text_path: list[str]) -> list[str]:
        """
        Splits the text from the given pages into dynamic chunks based on the configured chunk size and overlap.

        Args:
            pages_text_path (list[str]): List of file paths containing text content.

        Returns:
            list[str]: A list of text chunks.
        """
        raise NotImplementedError("DynamicChunksSplitter must implement get_chunks method")

    def _clean_page_content(self, text: str) -> str:
        """
        Removes header and footer text from a page based on finding the first and
        last lines that contain sentence-terminating punctuation.
        """
        lines = text.split('\n')

        # Find the start index of the content block
        content_start_index = -1
        for i, line in enumerate(lines):
            if any(p in line for p in ['।', '?', '!']):
                content_start_index = i
                break

        # Find the end index of the content block (searching from the end)
        content_end_index = -1
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i]
            if any(p in line for p in ['।', '?', '!']):
                content_end_index = i
                break

        # If no valid content lines were found, return an empty string
        if content_start_index == -1 \
                or content_end_index == -1 or content_start_index > content_end_index:
            return ""

        # Extract the content block from the first valid line to the last valid line
        content_lines = lines[content_start_index : content_end_index + 1]

        return "\n".join(content_lines)