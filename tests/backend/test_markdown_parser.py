"""
Unit tests for MarkdownParser class to test Adhikar functionality.

Tests both scenarios:
1. Simple Granth without Adhikars (all verses have adhikar=None)
2. Adhikar Granth with hierarchical structure (verses have corresponding Adhikar names)
"""

import pytest
import os
from backend.crawler.markdown_parser import MarkdownParser, parse_markdown_file
from backend.crawler.granth import Verse, Granth


class TestMarkdownParser:
    """Test class for MarkdownParser functionality."""
    
    @pytest.fixture
    def parser(self):
        """Create a MarkdownParser instance for testing."""
        return MarkdownParser()
    
    @pytest.fixture
    def simple_granth_path(self):
        """Path to simple granth test file (no Adhikars)."""
        return os.path.join("tests", "data", "md", "hindi", "simple_granth.md")
    
    @pytest.fixture
    def adhikar_granth_path(self):
        """Path to adhikar granth test file (with Adhikars)."""
        return os.path.join("tests", "data", "md", "hindi", "adhikar_granth.md")
    
    @pytest.fixture
    def mixed_granth_path(self):
        """Path to mixed granth test file (with Gatha and Kalash)."""
        return os.path.join("tests", "data", "md", "hindi", "mixed_granth.md")
    
    def test_simple_granth_no_adhikars(self, parser, simple_granth_path):
        """Test parsing of simple granth without Adhikars."""
        # Parse the simple granth file
        granth = parser.parse_file(simple_granth_path)
        
        # Basic structure assertions
        assert isinstance(granth, Granth)
        assert len(granth._verses) == 5
        assert granth._name == simple_granth_path  # fallback name when no config
        
        # Check that all verses have adhikar=None
        for i, verse in enumerate(granth._verses):
            assert isinstance(verse, Verse)
            assert verse._adhikar is None, f"Verse {i+1} should have adhikar=None"
            assert verse._seq_num == i + 1
            assert verse._type == "Shlok"
            assert verse._type_num == str(i + 1)
        
        # Verify specific verse content
        first_verse = granth._verses[0]
        assert "सूर्य उदय होता है" in first_verse._verse
        assert "प्रकाश चारों" in first_verse._translation
        assert first_verse._page_num == 12
        
        last_verse = granth._verses[4]
        assert "मेहनत करने वाले को" in last_verse._verse
        assert "मेहनत करते हैं, वे सफलता" in last_verse._translation
        assert last_verse._page_num == 25
    
    def test_adhikar_granth_with_adhikars(self, parser, adhikar_granth_path):
        """Test parsing of granth with Adhikar structure."""
        # Parse the adhikar granth file
        granth = parser.parse_file(adhikar_granth_path)
        
        # Basic structure assertions
        assert isinstance(granth, Granth)
        assert len(granth._verses) == 7
        
        # Expected Adhikar mapping
        expected_adhikars = [
            (1, "प्रकृति अधिकार"),  # Shlok 1
            (2, "प्रकृति अधिकार"),  # Shlok 2
            (3, "शिक्षा अधिकार"),   # Shlok 3
            (4, "शिक्षा अधिकार"),   # Shlok 4
            (5, "शिक्षा अधिकार"),   # Shlok 5
            (6, "सामाजिक अधिकार"), # Shlok 6
            (7, "सामाजिक अधिकार"), # Shlok 7
        ]
        
        # Check verses and their Adhikars
        for i, (shlok_num, expected_adhikar) in enumerate(expected_adhikars):
            verse = granth._verses[i]
            assert isinstance(verse, Verse)
            assert verse._seq_num == i + 1
            assert verse._type == "Shlok"
            assert verse._type_num == str(shlok_num)
            assert verse._adhikar == expected_adhikar, f"Verse {shlok_num} should belong to '{expected_adhikar}'"
        
        # Verify specific content from different Adhikars
        # प्रकृति अधिकार verses
        nature_verse1 = granth._verses[0]
        assert "आकाश में तारे" in nature_verse1._verse
        assert nature_verse1._adhikar == "प्रकृति अधिकार"
        
        nature_verse2 = granth._verses[1]
        assert "हवा चलती है" in nature_verse2._verse
        assert nature_verse2._adhikar == "प्रकृति अधिकार"
        
        # शिक्षा अधिकार verses
        education_verse1 = granth._verses[2]
        assert "पुस्तक पढ़ना" in education_verse1._verse
        assert education_verse1._adhikar == "शिक्षा अधिकार"
        
        # सामाजिक अधिकार verses
        social_verse1 = granth._verses[5]
        assert "मिलजुलकर काम" in social_verse1._verse
        assert social_verse1._adhikar == "सामाजिक अधिकार"
    
    def test_verse_content_parsing(self, parser, simple_granth_path):
        """Test detailed parsing of verse content (sections, page numbers, etc.)."""
        granth = parser.parse_file(simple_granth_path)
        
        # Test first verse detailed content
        verse1 = granth._verses[0]
        assert verse1._verse.strip().startswith("सूर्य उदय होता है")
        assert verse1._translation.strip().startswith("सूर्य पूर्व दिशा")
        assert verse1._meaning.strip().startswith("यह श्लोक सूर्योदय")
        assert len(verse1._teeka) > 0
        assert len(verse1._bhavarth) > 0
        assert verse1._page_num == 12
        
        # Test verse with multiple teeka/bhavarth paragraphs
        verse2 = granth._verses[1]
        assert len(verse2._teeka) >= 1
        assert verse2._page_num == 15
    
    def test_http_response_format(self, parser, adhikar_granth_path):
        """Test that HTTP response includes adhikar field."""
        granth = parser.parse_file(adhikar_granth_path)
        
        # Get HTTP response
        response = granth.get_http_response()
        
        # Check structure
        assert "verses" in response
        assert len(response["verses"]) == 7
        
        # Check that verses include adhikar field
        for i, verse_data in enumerate(response["verses"]):
            assert "adhikar" in verse_data
            if i < 2:  # First two verses
                assert verse_data["adhikar"] == "प्रकृति अधिकार"
            elif i < 5:  # Next three verses
                assert verse_data["adhikar"] == "शिक्षा अधिकार"
            else:  # Last two verses
                assert verse_data["adhikar"] == "सामाजिक अधिकार"
    
    def test_convenience_function(self, simple_granth_path):
        """Test the parse_markdown_file convenience function."""
        granth = parse_markdown_file(simple_granth_path)
        
        assert isinstance(granth, Granth)
        assert len(granth._verses) == 5
        
        # All verses should have adhikar=None
        for verse in granth._verses:
            assert verse._adhikar is None
    
    def test_text_cleaning(self, parser):
        """Test that text cleaning works properly."""
        # Test text with various Unicode characters
        test_text = "Test\u00A0with\u200Bspecial\u2009characters\uFEFF"
        cleaned = parser.clean_text(test_text)
        
        # NBSP and thin space become regular spaces, zero-width chars are removed
        assert cleaned == "Test withspecial characters"
        
        # Test multiple spaces
        test_text2 = "Multiple    spaces   here"
        cleaned2 = parser.clean_text(test_text2)
        assert cleaned2 == "Multiple spaces here"
    
    def test_verse_numbering_with_adhikars(self, parser, adhikar_granth_path):
        """Test that verse sequence numbers are correct with Adhikars."""
        granth = parser.parse_file(adhikar_granth_path)
        
        # Verify sequence numbering is continuous despite Adhikars
        for i, verse in enumerate(granth._verses):
            assert verse._seq_num == i + 1
        
        # Verify type_num reflects actual Shlok numbers
        type_nums = [verse._type_num for verse in granth._verses]
        assert type_nums == ["1", "2", "3", "4", "5", "6", "7"]
    
    def test_empty_adhikar_handling(self, parser):
        """Test handling of empty or malformed content."""
        # Test with minimal content that has H1 (treated as Adhikar)
        minimal_content = """
# Test

## Shlok 1
Test verse content

### Translation
Test translation
"""
        granth = parser.parse_content(minimal_content, "test.md")
        assert len(granth._verses) == 1
        assert granth._verses[0]._adhikar == "Test"  # H1 content becomes Adhikar
        
        # Test with no H1 tags (no Adhikars)
        no_adhikar_content = """
## Shlok 1
Test verse content

### Translation
Test translation
"""
        granth2 = parser.parse_content(no_adhikar_content, "test2.md")
        assert len(granth2._verses) == 1
        assert granth2._verses[0]._adhikar is None  # No H1 means no Adhikar
    
    def test_mixed_granth_gatha_kalash(self, parser, mixed_granth_path):
        """Test parsing of mixed granth with Gatha and Kalash verses."""
        granth = parser.parse_file(mixed_granth_path)
        
        # Basic structure assertions
        assert isinstance(granth, Granth)
        assert len(granth._verses) == 15  # 9 Gatha + 6 Kalash = 15 verses
        
        # Expected verse types and Adhikars
        expected_verses = [
            (1, "Gatha", 1, "ज्ञान अधिकार"),    # Gatha 1
            (2, "Kalash", 1, "ज्ञान अधिकार"),   # Kalash 1
            (3, "Gatha", 2, "ज्ञान अधिकार"),    # Gatha 2
            (4, "Kalash", 2, "ज्ञान अधिकार"),   # Kalash 2
            (5, "Gatha", 3, "कर्म अधिकार"),     # Gatha 3
            (6, "Gatha", 4, "कर्म अधिकार"),     # Gatha 4
            (7, "Kalash", 3, "कर्म अधिकार"),    # Kalash 3
            (8, "Gatha", 5, "कर्म अधिकार"),     # Gatha 5
            (9, "Kalash", 4, "कर्म अधिकार"),    # Kalash 4
            (10, "Gatha", 6, "मोक्ष अधिकार"),   # Gatha 6
            (11, "Gatha", 7, "मोक्ष अधिकार"),   # Gatha 7
            (12, "Kalash", 5, "मोक्ष अधिकार"),  # Kalash 5
            (13, "Gatha", 8, "मोक्ष अधिकार"),   # Gatha 8
            (14, "Kalash", 6, "मोक्ष अधिकार"),  # Kalash 6
            (15, "Gatha", 9, "मोक्ष अधिकार"),   # Gatha 9
        ]
        
        # Verify each verse
        for i, (seq_num, verse_type, type_num, adhikar) in enumerate(expected_verses):
            verse = granth._verses[i]
            assert isinstance(verse, Verse)
            assert verse._seq_num == seq_num, f"Verse {i+1} seq_num should be {seq_num}"
            assert verse._type == verse_type, f"Verse {i+1} type should be {verse_type}"
            assert verse._type_num == str(type_num), f"Verse {i+1} type_num should be {type_num}"
            assert verse._adhikar == adhikar, f"Verse {i+1} adhikar should be '{adhikar}'"
        
        # Test specific verse content
        # First Gatha
        gatha1 = granth._verses[0]
        assert "सत्य वचन बोलना धर्म है" in gatha1._verse
        assert gatha1._type == "Gatha"
        assert gatha1._type_num == "1"
        assert gatha1._adhikar == "ज्ञान अधिकार"
        assert gatha1._page_num == 5
        
        # First Kalash
        kalash1 = granth._verses[1]
        assert "ज्ञान प्राप्ति से आत्मा का कल्याण" in kalash1._verse
        assert kalash1._type == "Kalash"
        assert kalash1._type_num == "1"
        assert kalash1._adhikar == "ज्ञान अधिकार"
        assert kalash1._page_num == 8
        
        # Test teeka and bhavarth content
        assert len(gatha1._teeka) >= 1
        assert len(gatha1._bhavarth) >= 1
        assert "सत्यवादिता मानव का सर्वोच्च गुण है" in gatha1._teeka[0]
        assert "सत्य बोलने वाला व्यक्ति समाज में आदरणीय होता है" in gatha1._bhavarth[0]
        
        # Count verse types
        gatha_count = sum(1 for v in granth._verses if v._type == "Gatha")
        kalash_count = sum(1 for v in granth._verses if v._type == "Kalash")
        assert gatha_count == 9, "Should have 9 Gatha verses"
        assert kalash_count == 6, "Should have 6 Kalash verses"