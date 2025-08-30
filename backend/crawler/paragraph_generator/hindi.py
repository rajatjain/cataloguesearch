import re

from backend.crawler.paragraph_generator.base import BaseParagraphGenerator


class HindiParagraphGenerator(BaseParagraphGenerator):
    def __init__(self, config):
        super().__init__(config)
    
    @property
    def PUNCTUATION_SUFFIXES(self):
        return ('।', '?', '!', ':', ')', ']', '}')
    
    @property
    def STOP_PREFIXES(self):
        return ("श्रोता:", "मुमुक्षु:", "प्रश्न:")
    
    @property
    def ANSWER_PREFIXES(self):
        return ("पूज्य गुरुदेवश्री:", "उत्तर:", "समाधान:")

    def _normalize_dialogue_patterns(self, text: str) -> str:
        # correct typing mistakes
        text = re.sub(r"मुमु[^:]*श[^:]*:", "मुमुक्षु:", text)

        # Join multiple lines into a single line with spaces
        # BUT do not join lines that start with "श्रोता:" or "पूज्य गुरुदेवश्री:" or "मुमुक्षु:"
        text = re.sub(r'\n(?!श्रोता:|पूज्य गुरुदेवश्री:|मुमुक्षु:|शंका:|प्रश्न:|समाधान:|उत्तर:)', ' ', text)

        return text
