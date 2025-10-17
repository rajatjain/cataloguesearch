# Paragraph Generation: Handling Centered Lines, Headers, and Verses

## Problem Statement

The advanced paragraph generation strategy currently has difficulty distinguishing between different types of centered/short lines:

1. **Headers/Headings** - Should terminate paragraphs
2. **Verses** - Should be kept as separate verse blocks
3. **Attribution lines** - Should terminate paragraphs and not combine with next
4. **Introductory lines** - Should not merge with following verses
5. **Short quotes** - May or may not be centered

## Example Cases

### Case 1: Headers Being Treated as Verses

**File:** `page_0068.json`, Line 15
```
Text: "जड़ल में भी मुनिराज परम सुखी"
x_start: 1015, x_end: 1960
Left indent: ~580, Right indent: ~582
```

**Issue:** This is clearly a CENTERED heading/subtitle, not a verse. It's being classified as `IS_CENTERED` (verse) when it should be a header that terminates the previous paragraph.

**File:** `page_0069.json`, Line 12
```
Text: "गाथा ८ पर प्रवचन"
x_start: 1241, x_end: 1734
```

**Issue:** Another centered header that should break paragraphs.

### Case 2: Attribution Lines

**File:** `page_0068.json`, Line 22
```
Text: "को उपादेय मानते हैं। - पूज्य गुरुदेवश्ी कानजीस्वामी, गुरुदेवश्री के वचनाम्रत, ९७६, पृष्ठ १०९"
x_start: 578, x_end: 2396
```

**Issue:** This attribution line:
- Does NOT end with sentence terminator
- Is NOT right-justified (contrary to initial assumption)
- Currently gets combined with the next paragraph
- Should terminate the paragraph and not combine with next

### Case 3: Introductory Lines Before Verses

**File:** `page_0069.json`, Line 0
```
Text: "अब, बन्धुजनों का संयोग कैसा है ? सो दृष्टान्तपूर्वक कहते हैं --"
x_start: 616, x_end: 2146
Right indent: ~395
```

**Issue:** This line:
- Ends with `--` (colon/dash indicating what follows)
- Introduces the verse that comes next
- Should be kept separate from the verse block
- Currently might get merged with verse

### Case 4: Short Lines That Are NOT Centered

**File:** `page_0069.json`, Line 0 (same as above)

**Issue:** This is a short line but NOT centered enough to be a verse. It's introductory prose before a verse.

## Current Behavior

### Header Handling
- Headers ARE stored in the JSON (not filtered during OCR)
- Headers matched by `header_regex` get tagged with `IS_HEADER_REGEX`
- Current code: Headers are **skipped** (not added to any paragraph)
- **Problem:** Headers don't finalize the current paragraph before being skipped
- **Result:** Text before and after a header can merge into one paragraph

### Centered Line Classification
```python
is_centered = (is_indented AND right_indent_amount > center_threshold)
if is_centered:
    tags.add('IS_CENTERED')
```

**Problem:** This doesn't distinguish between:
- Headers (short, centered, no terminator)
- Verses (centered, may be multi-line)
- Short quotes (may be centered)

## Recommended Solutions

### Solution 1: Fix Header Handling (CRITICAL)

**Current behavior in `_handle_standard_prose_state`:**
```python
if 'IS_HEADER_REGEX' in line.tags:
    self._finalize_paragraph()
    self._reset_current_paragraph()
    return  # Skip the header line
```

**Problem:** The header is skipped but the paragraph is finalized AFTER checking the header. If we're in the middle of a paragraph, we need to finalize BEFORE processing the header.

**Fix:** Ensure paragraph is finalized when header is encountered:
```python
if 'IS_HEADER_REGEX' in line.tags:
    self._finalize_paragraph()
    self._reset_current_paragraph()
    return  # Skip the header
```

The fix is already correct in the current code, but needs verification that it's working as expected.

### Solution 2: Distinguish Headings from Verses

**Add new tag:** `IS_HEADING`

**Detection criteria:**
- Centered (both left and right indent)
- Short (typically < 50 characters)
- Does NOT end with sentence terminator (।, ?, !, etc.)
- May contain heading keywords: "गाथा", "प्रवचन", "अनुप्रेक्षा", "श्लोक", "काव्य"

**Implementation in LineClassifier.classify():**
```python
is_centered = (is_indented and right_indent_amount > center_threshold)
is_short = len(stripped_text) < 50
has_terminator = stripped_text.endswith(sentence_terminators)

# Check for heading keywords
heading_keywords = ['गाथा', 'प्रवचन', 'अनुप्रेक्षा', 'श्लोक', 'काव्य', 'पर प्रवचन']
has_heading_keyword = any(kw in stripped_text for kw in heading_keywords)

if is_centered and is_short and not has_terminator:
    tags.add('IS_HEADING')
elif is_centered:
    tags.add('IS_CENTERED')  # This is a verse
```

**State machine handling:**
```python
def _handle_standard_prose_state(self, line: Line) -> bool:
    # IS_HEADING should terminate paragraph (like headers)
    if 'IS_HEADING' in line.tags:
        self._finalize_paragraph()
        self._reset_current_paragraph()
        return False  # Don't add heading to paragraph

    # ... rest of the logic
```

### Solution 3: Detect Introductory Lines

**Add new tag:** `IS_INTRODUCTORY`

**Detection criteria:**
- Line ends with `--`, `:`, `:-`
- These typically introduce what follows (verses, examples, etc.)

**Implementation in LineClassifier.classify():**
```python
if stripped_text.endswith(('--', ':', ':-')):
    tags.add('IS_INTRODUCTORY')
```

**State machine handling:**
```python
def _handle_standard_prose_state(self, line: Line) -> bool:
    # ... existing logic ...

    # Introductory lines should end the current paragraph
    if 'IS_INTRODUCTORY' in line.tags:
        if not self.current_paragraph_lines:
            self._reset_current_paragraph(line)
        self.current_paragraph_lines.append(line)
        self._finalize_paragraph()
        self._reset_current_paragraph()
        return False
```

### Solution 4: Handle Attribution Lines

**Detection patterns:**
- Lines containing: `पूज्य`, `श्री`, author titles
- Format: `— Author Name, Book, Page`
- Often start with dash/hyphen

**Options:**
1. Add to `header_regex` in scan_config
2. Add pattern detection in LineClassifier
3. Use `IS_INTRODUCTORY` logic (since they often end sections)

**Recommended:** Add attribution patterns to `header_regex` in scan_config:
```json
"header_regex": [
  "^.{0,5}$",
  "^.*पूज्य.*स्वामी.*पृष्ठ.*$",
  "^.*श्री.*ग्रन्थ.*पृष्ठ.*$"
]
```

### Solution 5: Right-Justified Line Handling (OPTIONAL)

**Initial problem:** Author attributions that are right-justified should terminate paragraphs.

**Analysis:** Based on the data, attribution lines are NOT consistently right-justified. They appear to be left-aligned prose. So this solution may not be needed.

**If needed in future:**
```python
is_right_justified = 'IS_NOT_RIGHT_JUSTIFIED' not in line.tags

if is_right_justified:
    self.current_paragraph_lines.append(line)
    self._finalize_paragraph()
    self._reset_current_paragraph()
    return False
```

## Implementation Priority

1. **High Priority:**
   - Solution 2: Distinguish headings from verses (`IS_HEADING`)
   - Solution 3: Detect introductory lines (`IS_INTRODUCTORY`)

2. **Medium Priority:**
   - Solution 1: Verify header handling is working correctly
   - Solution 4: Add attribution patterns to header_regex

3. **Low Priority:**
   - Solution 5: Right-justified handling (only if pattern emerges)

## Testing Strategy

### Test Cases

1. **Header Breaking:**
   - Verify "गाथा ८ पर प्रवचन" breaks paragraphs
   - Verify "जड़ल में भी मुनिराज परम सुखी" breaks paragraphs

2. **Verse vs Heading:**
   - Centered lines with terminators → VERSE_BLOCK
   - Centered short lines without terminators → HEADING

3. **Introductory Lines:**
   - Lines ending with `--` should end paragraph
   - Next verse should start new paragraph

4. **Attribution Lines:**
   - Lines with "पूज्य गुरुदेवश्ी कानजीस्वामी" should end paragraph
   - Should NOT combine with next paragraph in Phase 3

### Test Files

- `Kartikeyaanuprekshaa_Pravachan_part_1_hin/page_0068.json`
- `Kartikeyaanuprekshaa_Pravachan_part_1_hin/page_0069.json`

## Phase 3 Considerations

After implementing Phase 1 fixes, Phase 3 (prose combination) should also be updated:

**Current issue:** Paragraphs without punctuation endings get combined with next.

**Solution:** Don't combine if:
- Previous paragraph ended with heading/introductory line
- Previous paragraph was attribution

**Implementation:** Add field to `Paragraph` dataclass:
```python
@dataclass
class Paragraph:
    text: str
    page_num: int
    paragraph_type: State
    start_line: int
    end_line: int
    no_combine: bool = False  # Set to True for headings, attributions, introductory
```

Then in Phase 3:
```python
if previous_paragraph.no_combine:
    break  # Don't combine with previous
```

## Future Enhancements

1. Machine learning model to classify line types
2. More sophisticated heading detection using context
3. Better attribution pattern matching
4. Language-specific rules for different text types