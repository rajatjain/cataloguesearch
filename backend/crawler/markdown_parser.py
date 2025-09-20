import logging

import markdown
from bs4 import BeautifulSoup
import re
from typing import List, Optional
from .granth import Verse, Granth, GranthMetadata
from backend.common.utils import get_merged_config

log_handle = logging.getLogger(__name__)

class MarkdownParser:
    """Parser for converting markdown files to Granth objects."""
    
    def __init__(self, base_folder: Optional[str] = None):
        self.md = markdown.Markdown()
        self.base_folder = base_folder
    
    def clean_text(self, text: str) -> str:
        """Clean text by removing/replacing special characters like NBSP."""
        if not text:
            return text
        
        # Replace common problematic characters
        text = text.replace('\u00A0', ' ')  # Non-breaking space (NBSP)
        text = text.replace('\u200B', '')   # Zero-width space
        text = text.replace('\u2009', ' ')  # Thin space
        text = text.replace('\u202F', ' ')  # Narrow no-break space
        text = text.replace('\uFEFF', '')   # Zero-width no-break space (BOM)
        
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def parse_file(self, file_path: str) -> Granth:
        """Parse a markdown file and return a Granth object."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse_content(content, file_path)
    
    def parse_content(self, content: str, original_filename: str) -> Granth:
        """Parse markdown content and return a Granth object."""
        # Convert markdown to HTML
        html = self.md.convert(content)
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract verses
        verses = self._extract_verses(soup)
        
        # Load metadata from config files if base_folder is provided
        if self.base_folder:
            config = get_merged_config(original_filename, self.base_folder)
            metadata = GranthMetadata(
                anuyog=config.get("Anuyog", ""),
                language=config.get("language", "hindi"), 
                author=config.get("Author", "Unknown"),
                teekakar=config.get("Teekakar", "Unknown"),
                file_url=config.get("file_url", "")
            )
            granth_name = config.get("name", "Unknown")
        else:
            # Fallback to default metadata
            metadata = GranthMetadata(
                anuyog="",
                language="hindi",
                author="Unknown",
                teekakar="Unknown",
                file_url=original_filename
            )
            granth_name = original_filename
        log_handle.info(f"config: {metadata}")
        
        return Granth(
            name=granth_name,
            original_filename=original_filename,
            metadata=metadata,
            verses=verses
        )
    
    def _extract_verses(self, soup: BeautifulSoup) -> List[Verse]:
        """Extract all verses from the parsed HTML, tracking Adhikars."""
        verses = []
        current_adhikar = None
        seq_num = 1
        
        # Find all H1 and H2 tags in document order
        all_headers = soup.find_all(['h1', 'h2'])
        
        for header in all_headers:
            if header.name == 'h1':
                # Update current Adhikar
                current_adhikar = self.clean_text(header.get_text())
                log_handle.info(f"Found Adhikar: {current_adhikar}")
            elif header.name == 'h2':
                # Extract verse with current Adhikar
                verse = self._extract_single_verse(header, seq_num, soup, current_adhikar)
                if verse:
                    verses.append(verse)
                    seq_num += 1
        
        return verses
    
    def _extract_single_verse(self, h2_tag, seq_num: int, soup: BeautifulSoup, adhikar: Optional[str] = None) -> Optional[Verse]:
        """Extract a single verse from an H2 tag and its following content."""
        # Extract type and type_num from H1 text
        h2_text = self.clean_text(h2_tag.get_text())
        verse_type, type_num = self._parse_verse_header(h2_text)
        
        if not verse_type:
            return None
        
        # Get all content until the next H1 or H2
        content_elements = []
        current = h2_tag.next_sibling
        
        while current and (not hasattr(current, 'name') or current.name not in ['h1', 'h2']):
            if hasattr(current, 'name') and current.name:
                content_elements.append(current)
            current = current.next_sibling
        
        # Extract verse text (first non-header content)
        verse_text = self._extract_verse_text(content_elements)
        
        # Extract sections
        sections = self._extract_sections(content_elements)
        
        # Map sections to verse fields
        translation = self._get_section_content(sections, ["Translation"])
        meaning = self._get_section_content(sections, ["Meaning"])
        teeka = self._get_section_content_list(sections, ["Teeka"])
        bhavarth = self._get_section_content_list(sections, ["Bhavarth"])
        
        # Extract page number from "Page <num>" section
        page_num = self._extract_page_number(sections)

        return Verse(
            seq_num=seq_num,
            verse=self.clean_text(verse_text),
            type=verse_type,
            type_num=type_num,
            translation=self.clean_text(translation),
            language="Hindi",
            meaning=self.clean_text(meaning),
            teeka=[self.clean_text(t) for t in teeka],
            bhavarth=[self.clean_text(b) for b in bhavarth],
            page_num=page_num,
            adhikar=adhikar
        )
    
    def _parse_verse_header(self, header_text: str) -> tuple[Optional[str], Optional[int]]:
        """Parse verse header to extract type and number."""
        # Match patterns like "Shlok 1", "Gatha 15", "Kalash 3"
        match = re.match(r'^(Shlok|Gatha|Kalash)\s+(\d+)', header_text, re.IGNORECASE)
        if match:
            verse_type = match.group(1).capitalize()
            type_num = int(match.group(2))
            return verse_type, type_num
        
        return None, None
    
    def _extract_verse_text(self, content_elements: List) -> str:
        """Extract the main verse text (Sanskrit/Prakrit) from content elements."""
        verse_lines = []
        
        for element in content_elements:
            if element.name == 'h3':
                break  # Stop at first section header
            
            if element.name == 'p':
                text = self.clean_text(element.get_text())
                if text:
                    verse_lines.append(text)

        return '\n'.join(verse_lines)
    
    def _extract_sections(self, content_elements: List) -> dict:
        """Extract all H2 sections and their content."""
        sections = {}
        current_section = None
        current_content = []
        
        for element in content_elements:
            if element.name == 'h3':
                # Save previous section
                if current_section:
                    sections[current_section] = current_content
                
                # Start new section
                current_section = self.clean_text(element.get_text())
                current_content = []
            
            elif current_section and element.name in ['p', 'ul', 'ol', 'blockquote']:
                text = self.clean_text(element.get_text())
                if text:
                    current_content.append(text)
        
        # Save last section
        if current_section:
            sections[current_section] = current_content
        
        return sections
    
    def _get_section_content(self, sections: dict, section_names: List[str]) -> str:
        """Get content from the first matching section name."""
        for name in section_names:
            if name in sections:
                return '\n'.join(sections[name])
        return ""
    
    def _get_section_content_list(self, sections: dict, section_names: List[str]) -> List[str]:
        """Get content as list from matching section names."""
        content_list = []
        for name in section_names:
            if name in sections:
                content_list.extend(sections[name])
        return content_list
    
    def _extract_page_number(self, sections: dict) -> Optional[int]:
        """Extract page number from 'Page <num>' section headers."""
        for section_name in sections.keys():
            # Match "Page Number - <number>" or "Page Number <number>" patterns
            match = re.match(r'^Page\s+Number\s*-?\s*(\d+)$', section_name, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None


def parse_markdown_file(file_path: str, base_folder: Optional[str] = None) -> Granth:
    """Convenience function to parse a markdown file."""
    parser = MarkdownParser(base_folder)
    return parser.parse_file(file_path)
