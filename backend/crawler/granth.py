from typing import List, Optional
from backend.utils import json_dumps


class ProseSection:
    """
    Represents hierarchical prose content (headings, text, subsections).
    Used for non-verse content like commentary, explanations, Q&A sections.

    Attributes:
        seq_num:        Global sequence number (continues across verses and prose)
        heading:        Section heading (e.g., "Saar", "नरकगति के दुःख")
        content:        List of paragraphs under this heading (each para indexed separately)
        subsections:    Nested subsections (hierarchical structure)
        page_num:       Page number in the original PDF
        adhikar:        The Adhikar (chapter/section) this prose belongs to
    """
    def __init__(
        self,
        seq_num: int,
        heading: str,
        content: List[str],
        subsections: Optional[List['ProseSection']] = None,
        page_num: Optional[int] = None,
        adhikar: Optional[str] = None
    ):
        self._seq_num = seq_num
        self._heading = heading
        self._content = content  # List of paragraphs
        self._subsections = subsections or []
        self._page_num = page_num
        self._adhikar = adhikar

    def __str__(self):
        section_preview = f"""
            ProseSection Seq: {self._seq_num}
            Heading: {self._heading}
            Content Paragraphs: {len(self._content)}
            Subsections: {len(self._subsections)}
            Page Num: {self._page_num}
            Adhikar: {self._adhikar}
        """
        return section_preview

    def get_http_response(self):
        """Convert ProseSection to dictionary for HTTP response"""
        return {
            "seq_num": self._seq_num,
            "heading": self._heading,
            "content": self._content,
            "subsections": [subsec.get_http_response() for subsec in self._subsections],
            "page_num": self._page_num,
            "adhikar": self._adhikar
        }


class Verse:
    """Verse defines all the content of a single Verse within a Granth (scripture). The structure
    of the Verse is as follows:

        - seq_num:             The sequence number in which this verse occurs. This may be different
                               from the actual verse number in the Granth. For example, Samaysar,
                               Niyamsar etc. have both Gathas and Kalash. So, Kalash 24 may have a
                               sequence number of 35 if there are 13 Gathas before Kalash 24. etc.
        - verse:               The original Sanskrit/Prakrit/Hindi verse
        - type:                Gatha/Kalash/Shlok etc.
        - type_start_num:      The starting number (e.g., 1 for "1-6", 247 for "247")
        - type_end_num:        The ending number (e.g., 6 for "1-6", 247 for "247")
        - translation:         The hindi/gujarati translation
        - language:            The language in which the verse is translated and the meaning/teeka etc.
                               is written
        - meaning:             The gaatharth/anyavarth/shlokarth
        - teeka:               Full Teeka. This is a list comprising multiple paragraphs
        - bhavarth:            Full Bhavarth. This is a list comprising multiple paragraphs
        - page_num:            Page Number in the original PDF file.
        - adhikar:             The Adhikar (chapter/section) this verse belongs to, if any.

    """
    def __init__(
        self, seq_num, verse, type, type_start_num, type_end_num, translation, language, meaning, teeka, bhavarth, page_num=None, adhikar=None
    ):
        self._seq_num = seq_num
        self._verse = verse
        self._type = type
        self._type_start_num = type_start_num
        self._type_end_num = type_end_num
        self._translation = translation
        self._language = language
        self._meaning = meaning
        self._teeka = teeka
        self._bhavarth = bhavarth
        self._page_num = page_num
        self._adhikar = adhikar
    
    def __str__(self):
        verse_preview = f"""
            Verse Seq: {self._seq_num}
            Verse: {self._verse}
            Type: {self._type}
            Type Start Num: {self._type_start_num}
            Type End Num: {self._type_end_num}
            Translation: {self._translation}
            Language: {self._language}
            Meaning: {self._meaning}
            Teeka: {json_dumps(self._teeka)}
            Bhavarth: {json_dumps(self._bhavarth)}
            Page Num: {self._page_num}
            Adhikar: {self._adhikar}
        """
        return verse_preview
    
    def get_http_response(self):
        """Convert Verse to dictionary for HTTP response"""
        return {
            "seq_num": self._seq_num,
            "verse": self._verse,
            "type": self._type,
            "type_start_num": self._type_start_num,
            "type_end_num": self._type_end_num,
            "translation": self._translation,
            "language": self._language,
            "meaning": self._meaning,
            "teeka": self._teeka,
            "bhavarth": self._bhavarth,
            "page_num": self._page_num,
            "adhikar": self._adhikar
        }

class GranthMetadata:
    def __init__(
        self, anuyog, language, author, teekakar, file_url
    ):
        self._anuyog = anuyog
        self._language = language
        self._author = author
        self._teekakar = teekakar
        self._file_url = file_url
    
    def __str__(self):
        return f"GranthMetadata(anuyog='{self._anuyog}', lang='{self._language}', author='{self._author}', teekakar='{self._teekakar}')"
    
    def get_http_response(self):
        """Convert GranthMetadata to dictionary for HTTP response"""
        return {
            "anuyog": self._anuyog,
            "language": self._language,
            "author": self._author,
            "teekakar": self._teekakar,
            "file_url": self._file_url
        }


class Granth:
    """Granth defines all the relevant content of a single Granth
        - name:             Name of the Granth
        - metadata:         Metadata associated with the Granth
        - verses:           List of Verse objects (verse-based content)
        - prose_sections:   List of ProseSection objects (prose/commentary content)
    """
    def __init__(
        self,
        name,
        original_filename,
        metadata,
        verses,
        prose_sections
    ):
        self._name = name
        self._original_filename = original_filename
        self._metadata = metadata
        self._verses = verses
        self._prose_sections = prose_sections or []

    def __str__(self):
        return (f"Granth(name='{self._name}', verses={len(self._verses)}, "
                f"prose_sections={len(self._prose_sections)}, metadata={self._metadata})")

    def get_http_response(self):
        """Convert Granth to dictionary for HTTP response"""
        return {
            "name": self._name,
            "original_filename": self._original_filename,
            "metadata": self._metadata.get_http_response(),
            "verses": [verse.get_http_response() for verse in self._verses],
            "prose_sections": [section.get_http_response() for section in self._prose_sections]
        }
