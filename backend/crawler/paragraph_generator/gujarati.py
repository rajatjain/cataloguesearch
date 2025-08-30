import re

from backend.crawler.paragraph_generator.base import BaseParagraphGenerator


class GujaratiParagraphGenerator(BaseParagraphGenerator):
    def __init__(self, config):
        super().__init__(config)

    @property
    def punctuation_suffixes(self):
        return ('।', '.', '?', '!', ':', ')', ']', '}')

    @property
    def stop_prefixes(self):
        return ("શ્રોતા:", "મુમુક્ષુ:", "પ્રશ્ન:")

    @property
    def answer_prefixes(self):
        return ("પૂજ્ય ગુરુદેવશ્રી:", "ઉત્તર:", "સમાધાન:")

    def _normalize_dialogue_patterns(self, text: str) -> str:
        # correct typing mistakes for Gujarati
        text = re.sub(r"મુમુ[^:]*ષુ[^:]*:", "મુમુક્ષુ:", text)

        # Join multiple lines into a single line with spaces
        # BUT do not join lines that start with Gujarati dialogue prefixes
        text = re.sub(
            r'\n(?!શ્રોતા:|પૂજ્ય ગુરુદેવશ્રી:|મુમુક્ષુ:|શંકા:|પ્રશ્ન:|સમાધાન:|ઉત્તર:)', ' ', text)

        return text