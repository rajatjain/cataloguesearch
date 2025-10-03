from backend.utils import json_dumps


class Verse:
    """Verse defines all the content of a single Verse within a Granth (scripture). The structure
    of the Verse is as follows:

        - seq_num:       The sequence number in which this verse occurs. This may be different
                         from the actual verse number in the Granth. For example, Samaysar,
                         Niyamsar etc. have both Gathas and Kalash. So, Kalash 24 may have a
                         sequence number of 35 if there are 13 Gathas before Kalash 24. etc.
        - verse:         The original Sanskrit/Prakrit/Hindi verse
        - type:          Gatha/Kalash/Shlok etc.
        - type_num:      The actual number/range of the gatha/kalash/shlok (e.g., "1", "1-6", "356-365").
        - translation:   The hindi/gujarati translation
        - language:      The language in which the verse is translated and the meaning/teeka etc.
                         is written
        - meaning:       The gaatharth/anyavarth/shlokarth
        - teeka:         Full Teeka. This is a list comprising multiple paragraphs
        - bhavarth:      Full Bhavarth. This is a list comprising multiple paragraphs
        - page_num:      Page Number in the original PDF file.
        - adhikar:       The Adhikar (chapter/section) this verse belongs to, if any.

    """
    def __init__(
        self, seq_num, verse, type, type_num, translation, language, meaning, teeka, bhavarth, page_num=None, adhikar=None
    ):
        self._seq_num = seq_num
        self._verse = verse
        self._type = type
        self._type_num = type_num
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
            Type Num: {self._type_num}
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
            "type_num": self._type_num,
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
        - name:        Name of the Granth
        - metadata:    Metadata associated with the Granth
    """
    def __init__(
        self, name, original_filename,
        metadata, verses):
        self._name = name
        self._original_filename = original_filename
        self._metadata = metadata
        self._verses = verses
    
    def __str__(self):
        return f"Granth(name='{self._name}', verses={len(self._verses)}, metadata={self._metadata})"
    
    def get_http_response(self):
        """Convert Granth to dictionary for HTTP response"""
        return {
            "name": self._name,
            "original_filename": self._original_filename,
            "metadata": self._metadata.get_http_response(),
            "verses": [verse.get_http_response() for verse in self._verses]
        }
