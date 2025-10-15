import re
import pytesseract
import pandas as pd
from pdf2image import convert_from_path
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple

# --- Configuration Constants ---

# Heading markers that indicate structural breaks in the document
HEADING_MARKERS = (
    '★',
    'काव्य -',
    'काव्य-',
    'अर्थः',
    'शब्दार्थः',
    'शब्दार्थ',
)

# Header regex patterns - lines matching these will end paragraphs and be excluded
HEADER_REGEX = [
    # Add your regex patterns here, e.g.:
    # r'^\s*Page\s+\d+',  # Page numbers
    # r'^\s*Chapter\s+\d+',  # Chapter headings
]

# Sentence terminators in Devanagari script
SENTENCE_TERMINATORS = ('।', '?', '!', '।।')

# --- Data Structures and State Enum ---

class State(Enum):
    """Represents the current processing state of the generator."""
    STANDARD_PROSE = auto()
    VERSE_BLOCK = auto()
    QA_BLOCK = auto()

@dataclass
class Line:
    """Represents a single line of text with its properties and classifications."""
    text: str
    x_start: int
    x_end: int
    page_num: int
    line_num: int
    tags: Set[str] = field(default_factory=set)
    speaker: Optional[str] = None

@dataclass
class Paragraph:
    """Represents a finalized paragraph."""
    text: str
    page_num: int
    paragraph_type: State
    start_line: int
    end_line: int

    def __repr__(self):
        return (
            f"--- PARAGRAPH (Page: {self.page_num}, Type: {self.paragraph_type.name}, Lines: {self.start_line}-{self.end_line}) ---\n"
            f"{self.text.strip()}\n"
            f"---------------------------------------------------\n"
        )

# --- Classification Logic (Unchanged) ---

class LineClassifier:
    """
    Analyzes raw line data and assigns classification tags.
    This class determines the "what" for each line.
    """
    def __init__(self, avg_left_margin, avg_right_margin, indent_threshold=15, center_threshold=20):
        self.avg_left_margin = avg_left_margin
        self.avg_right_margin = avg_right_margin
        self.indent_threshold = indent_threshold
        self.center_threshold = center_threshold
        self.qa_pattern = re.compile(r'^\s*([^:]+?)\s*:\s*(.*)')

    def classify(self, text: str, x_start: int, x_end: int, page_num: int, line_num: int) -> Line:
        """Assigns a set of tags to a line based on its properties."""
        tags = set()
        speaker = None

        is_indented = (x_start - self.avg_left_margin) > self.indent_threshold
        is_centered = is_indented and (self.avg_right_margin - x_end) > self.center_threshold
        is_not_right_justified = (self.avg_right_margin - x_end) > self.indent_threshold

        if is_centered:
            tags.add('IS_CENTERED')
        elif is_indented:
            tags.add('IS_INDENTED')

        if is_not_right_justified:
            tags.add('IS_NOT_RIGHT_JUSTIFIED')

        stripped_text = text.strip()
        if not stripped_text:
            tags.add('IS_EMPTY')

        # Check for header regex matches
        for pattern in HEADER_REGEX:
            if re.search(pattern, stripped_text):
                tags.add('IS_HEADER_REGEX')
                break

        qa_match = self.qa_pattern.match(stripped_text)
        if qa_match:
            tags.add('IS_QA')
            speaker = qa_match.group(1).strip()
            text = qa_match.group(2).strip()

        if stripped_text.startswith(HEADING_MARKERS):
            tags.add('IS_HEADING')

        if stripped_text.endswith(SENTENCE_TERMINATORS):
            tags.add('HAS_SENTENCE_TERMINATOR')

        if re.search(r'।।\d+।।$', stripped_text):
            tags.add('IS_ABSOLUTE_TERMINATOR')

        return Line(text, int(x_start), int(x_end), page_num, line_num, tags, speaker)

# --- State Machine Logic (Unchanged) ---

class ParagraphGenerator:
    """
    A state-based engine that processes classified lines to generate paragraphs.
    """
    def __init__(self):
        self.state = State.STANDARD_PROSE
        self.paragraphs: List[Paragraph] = []
        self._reset_current_paragraph()

    def _reset_current_paragraph(self, line: Optional[Line] = None):
        self.current_paragraph_lines: List[Line] = []
        self.current_paragraph_speaker: Optional[str] = None
        if line:
            self.paragraph_start_line = line.line_num
            self.paragraph_page_num = line.page_num
        else:
            self.paragraph_start_line = -1
            self.paragraph_page_num = -1

    def _finalize_paragraph(self):
        if not self.current_paragraph_lines:
            return
        full_text = ' '.join(line.text.strip() for line in self.current_paragraph_lines).strip()
        if full_text:
            end_line = self.current_paragraph_lines[-1].line_num
            para = Paragraph(
                text=full_text,
                page_num=self.paragraph_page_num,
                paragraph_type=self.state,
                start_line=self.paragraph_start_line,
                end_line=end_line
            )
            self.paragraphs.append(para)

    def process_line(self, line: Line):
        if 'IS_EMPTY' in line.tags:
            return
        # Handle header regex matches: end paragraph and skip the line
        if 'IS_HEADER_REGEX' in line.tags:
            self._finalize_paragraph()
            self._reset_current_paragraph()
            return
        initial_state = self.state
        handler = getattr(self, f'_handle_{initial_state.name.lower()}_state')
        reprocess = handler(line)
        if reprocess:
            self.process_line(line)

    def flush(self):
        self._finalize_paragraph()
        return self.paragraphs

    def _handle_standard_prose_state(self, line: Line) -> bool:
        if 'IS_HEADING' in line.tags or 'IS_ABSOLUTE_TERMINATOR' in line.tags:
            self._finalize_paragraph()
            self._reset_current_paragraph(line)
            self.current_paragraph_lines.append(line)
            self._finalize_paragraph()
            self._reset_current_paragraph()
            return False
        if 'IS_CENTERED' in line.tags:
            self._finalize_paragraph()
            self._reset_current_paragraph(line)
            self.state = State.VERSE_BLOCK
            return True
        if 'IS_QA' in line.tags:
            self._finalize_paragraph()
            self._reset_current_paragraph(line)
            self.state = State.QA_BLOCK
            return True
        if not self.current_paragraph_lines:
            self._reset_current_paragraph(line)
        self.current_paragraph_lines.append(line)
        is_last_line = 'HAS_SENTENCE_TERMINATOR' in line.tags and 'IS_NOT_RIGHT_JUSTIFIED' in line.tags
        if is_last_line:
            self._finalize_paragraph()
            self._reset_current_paragraph()
        return False

    def _handle_verse_block_state(self, line: Line) -> bool:
        if 'IS_CENTERED' in line.tags:
            self.current_paragraph_lines.append(line)
            return False
        else:
            self._finalize_paragraph()
            self._reset_current_paragraph(line)
            self.state = State.STANDARD_PROSE
            return True

    def _handle_qa_block_state(self, line: Line) -> bool:
        is_structural_break = 'IS_HEADING' in line.tags or 'IS_ABSOLUTE_TERMINATOR' in line.tags
        is_new_prose = 'IS_INDENTED' in line.tags and 'IS_QA' not in line.tags
        if is_structural_break or is_new_prose:
            self._finalize_paragraph()
            self._reset_current_paragraph(line)
            self.state = State.STANDARD_PROSE
            return True
        if 'IS_QA' in line.tags:
            if self.current_paragraph_speaker is None:
                self.current_paragraph_speaker = line.speaker
            elif self.current_paragraph_speaker != line.speaker:
                self._finalize_paragraph()
                self._reset_current_paragraph(line)
                self.current_paragraph_speaker = line.speaker
        if not self.current_paragraph_lines:
            self._reset_current_paragraph(line)
        self.current_paragraph_lines.append(line)
        return False

# --- Main PDF Processing Function (MODIFIED FOR PYTESSERACT) ---

def process_pdf_with_tesseract(pdf_path: str, lang: str = 'hin+guj',
                               top_crop: int = 0, bottom_crop: int = 0) -> List[Tuple[int, str]]:
    """
    Converts PDF pages to images, runs Tesseract OCR, and generates paragraphs.

    Args:
        pdf_path: Path to the PDF file
        lang: Tesseract language code (default: 'hin+guj')
        top_crop: Percentage to crop from top (0-50)
        bottom_crop: Percentage to crop from bottom (0-50)
    """
    try:
        images = convert_from_path(pdf_path)
    except Exception as e:
        print(f"Error converting PDF to images. Is Poppler installed and in your PATH?")
        print(f"Original error: {e}")
        return []

    generator = ParagraphGenerator()
    global_line_counter = 0

    # Validate crop percentages
    if not (0 <= top_crop <= 50):
        print(f"Warning: top_crop must be between 0 and 50. Using 0.")
        top_crop = 0
    if not (0 <= bottom_crop <= 50):
        print(f"Warning: bottom_crop must be between 0 and 50. Using 0.")
        bottom_crop = 0

    if top_crop > 0 or bottom_crop > 0:
        print(f"Cropping enabled: {top_crop}% from top, {bottom_crop}% from bottom")

    for page_num, image in enumerate(images, 1):
        # Apply cropping if specified
        if top_crop > 0 or bottom_crop > 0:
            width, height = image.size
            top_pixels = int(height * top_crop / 100)
            bottom_pixels = int(height * bottom_crop / 100)
            # Crop: (left, top, right, bottom)
            image = image.crop((0, top_pixels, width, height - bottom_pixels))
        # Use Tesseract to get detailed information about words and their positions
        # Using a DataFrame makes it easier to process this data
        try:
            ocr_data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DATAFRAME)
        except pytesseract.TesseractNotFoundError:
            print("Tesseract Error: The Tesseract executable was not found.")
            print("Please make sure Tesseract is installed and its location is in your system's PATH.")
            return []

        ocr_data = ocr_data.dropna(subset=['text'])
        ocr_data = ocr_data[ocr_data.conf > 30] # Filter out low-confidence words

        if ocr_data.empty:
            continue

        # Reconstruct lines from word data
        lines_on_page = []
        for (block_num, par_num, line_num), line_df in ocr_data.groupby(['block_num', 'par_num', 'line_num']):
            text = ' '.join(line_df['text'].astype(str))
            x_start = line_df['left'].min()
            x_end = (line_df['left'] + line_df['width']).max()
            lines_on_page.append({'text': text, 'x_start': x_start, 'x_end': x_end})

        if not lines_on_page:
            continue

        # Calculate page margins from reconstructed lines
        left_margins = [line['x_start'] for line in lines_on_page]
        right_margins = [line['x_end'] for line in lines_on_page]
        avg_left = sorted(left_margins)[len(left_margins) // 2]
        avg_right = sorted(right_margins)[len(right_margins) // 2]

        classifier = LineClassifier(avg_left, avg_right)

        for line_info in lines_on_page:
            classified_line = classifier.classify(
                text=line_info['text'],
                x_start=line_info['x_start'],
                x_end=line_info['x_end'],
                page_num=page_num,
                line_num=global_line_counter
            )
            generator.process_line(classified_line)
            global_line_counter += 1

    final_paragraphs = generator.flush()

    output = [(p.page_num, p.text) for p in final_paragraphs]
    return output

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Extract paragraphs from PDF using OCR')
    parser.add_argument('pdf_file', help='Path to the PDF file')
    parser.add_argument('--top-crop', type=int, default=0,
                        help='Percentage to crop from top (0-50, default: 0)')
    parser.add_argument('--bottom-crop', type=int, default=0,
                        help='Percentage to crop from bottom (0-50, default: 0)')
    parser.add_argument('--lang', type=str, default='hin+guj',
                        help='Tesseract language code (default: hin+guj)')

    args = parser.parse_args()

    try:
        # Call the new tesseract-based function with crop parameters
        paragraphs_output = process_pdf_with_tesseract(
            args.pdf_file,
            lang=args.lang,
            top_crop=args.top_crop,
            bottom_crop=args.bottom_crop
        )

        if paragraphs_output:
            print(f"Successfully processed {len(paragraphs_output)} paragraphs using Tesseract.\n")
            for i, (page, content) in enumerate(paragraphs_output):
                print(f"--- Paragraph {i+1} (from Page {page}) ---")
                print(content)
                print("-" * (20 + len(str(i+1)) + len(str(page))))

    except FileNotFoundError:
        print(f"Error: The file '{args.pdf_file}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")