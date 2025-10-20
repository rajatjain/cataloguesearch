# Header Block State Refactoring

## Problem Summary

The paragraph generation state machine incorrectly merges content that is separated by header lines.

### Example Case (page_0015.json)

**Current behavior:**
```
Paragraph 1 (lines 0-8):
  नमः श्री सिद्धेभ्यः
  (book title and metadata...)
  ५ भार »
  सम्यग्दर्शन होते ही जीव चेतन्यमहल का स्वामी बन गया। तीव्र
  पुरुषार्थी को महल का अस्थिरतारूप कचरा निकालने में कम समय लगता
  (verse quote continues...)
```

**Expected behavior:**
```
Paragraph 1: Header metadata (filtered out at write time)
Paragraph 2: Verse quote starting with "सम्यग्दर्शन होते ही..."
```

### Root Cause

1. **Lines 0-3**: Header metadata (invocation, book title, part number) - classified as VERSE_BLOCK (centered text)
2. **Lines 4-5**: Header regex matches (date, reference line) - currently SKIPPED entirely
3. **Lines 6-9**: Actual verse content - classified as VERSE_BLOCK (centered text)

**Current flow:**
- Phase 1: Creates two VERSE_BLOCK paragraphs (lines 0-3 and lines 6-9)
- Lines 4-5 are skipped, so there's no barrier between the two VERSE_BLOCKs
- Phase 2: Combines consecutive VERSE_BLOCKs → merges paragraphs incorrectly

**Why the simple fix didn't work:**

Added `self.state = State.STANDARD_PROSE` when encountering IS_HEADER_REGEX to reset state. This prevented merging during Phase 1, but Phase 2 still sees two consecutive VERSE_BLOCK paragraphs with no barrier between them and combines them.

## Proposed Solution: HEADER_BLOCK State

Instead of skipping header lines, treat them as first-class HEADER_BLOCK paragraphs that act as barriers preventing other paragraph types from combining across them.

### Design Changes

#### 1. Add HEADER_BLOCK State Type

```python
class State(Enum):
    """Represents the current processing state of the generator."""
    STANDARD_PROSE = auto()
    VERSE_BLOCK = auto()
    QA_BLOCK = auto()
    HEADER_BLOCK = auto()  # NEW
```

#### 2. Modify process_line (lines 174-182)

**Before:**
```python
if 'IS_HEADER_REGEX' in line.tags:
    self._finalize_paragraph()
    self._reset_current_paragraph()
    self.state = State.STANDARD_PROSE
    return
```

**After:**
```python
if 'IS_HEADER_REGEX' in line.tags:
    self._finalize_paragraph()
    self._reset_current_paragraph(line)
    self.state = State.HEADER_BLOCK
    return True  # Reprocess to call _handle_header_block_state
```

#### 3. Add _handle_header_block_state Method

```python
def _handle_header_block_state(self, line: Line) -> bool:
    """
    Handle header block state. Headers become single-line or multi-line paragraphs.
    Exit when encountering any non-header line.
    """
    if 'IS_HEADER_REGEX' in line.tags:
        # Continue accumulating consecutive header lines
        self.current_paragraph_lines.append(line)
        return False
    else:
        # Non-header line encountered - end header block
        self._finalize_paragraph()
        self._reset_current_paragraph(line)
        self.state = State.STANDARD_PROSE
        return True  # Reprocess in STANDARD_PROSE state
```

#### 4. Update _finalize_paragraph Separator Logic (line 160)

**Before:**
```python
separator = '\n' if self.state in (State.VERSE_BLOCK, State.QA_BLOCK) else ' '
```

**After:**
```python
separator = '\n' if self.state in (State.VERSE_BLOCK, State.QA_BLOCK, State.HEADER_BLOCK) else ' '
```

#### 5. Update Phase 2: _phase2_combine_by_type

**Add HEADER_BLOCK handling:**

```python
def _phase2_combine_by_type(self, typed_paragraphs):
    # ...
    while i < len(typed_paragraphs):
        page_num, text, para_type = typed_paragraphs[i]

        if para_type == State.HEADER_BLOCK:
            # Don't combine headers - each is separate
            # Headers act as barriers preventing other types from combining
            combined.append((page_num, text, State.HEADER_BLOCK))
            i += 1

        elif para_type == State.VERSE_BLOCK:
            # Combine consecutive VERSE_BLOCK (existing logic)
            verse_texts = [text]
            i += 1
            while i < len(typed_paragraphs) and typed_paragraphs[i][2] == State.VERSE_BLOCK:
                verse_texts.append(typed_paragraphs[i][1])
                i += 1
            combined_text = '\n'.join(verse_texts)
            combined.append((page_num, combined_text, State.VERSE_BLOCK))

        # ... rest of logic
```

**Key insight:** HEADER_BLOCK acts as a barrier. When Phase 2 encounters a HEADER_BLOCK between two VERSE_BLOCKs, it won't combine them because the iteration pointer moves past the header, breaking the "consecutive" condition.

#### 6. Update Phase 3: _phase3_combine_prose

**Treat HEADER_BLOCK like VERSE_BLOCK (don't combine prose across it):**

```python
# VERSE_BLOCK and HEADER_BLOCK: already combined/isolated, just strip type tag
if para_type == State.VERSE_BLOCK or para_type == State.HEADER_BLOCK:
    final_paragraphs.append((page_num, text))
    i += 1
    continue
```

#### 7. Filter HEADER_BLOCK at Write Time

**Issue:** Phase 3 currently returns `List[Tuple[int, str]]` without para_type.

**Options:**

**Option A:** Keep para_type through Phase 3
```python
def _phase3_combine_prose(...) -> List[Tuple[int, str, State]]:
    # Return type includes State
    # Filter in writer:
    content_paragraphs = [
        (page_num, text) for (page_num, text, para_type) in final_paragraphs
        if para_type != State.HEADER_BLOCK
    ]
```

**Option B:** Filter at end of Phase 2 (simpler)
```python
# At end of _phase2_combine_by_type:
return [p for p in combined if p[2] != State.HEADER_BLOCK]
```

**Recommendation:** Option B is simpler - filter out HEADER_BLOCKs at the end of Phase 2.

## Expected Result

**Phase 1 output:**
- Paragraph 1: Lines 0-3 (VERSE_BLOCK) - header metadata
- Paragraph 2: Lines 4-5 (HEADER_BLOCK) - header regex matches
- Paragraph 3: Lines 6-9 (VERSE_BLOCK) - verse quote
- Paragraph 4: Lines 10-15 (STANDARD_PROSE) - commentary

**Phase 2 output:**
- Paragraph 1: Lines 0-3 (VERSE_BLOCK) - header metadata
- Paragraph 2: Lines 4-5 (HEADER_BLOCK) - barriers (will be filtered out)
- Paragraph 3: Lines 6-9 (VERSE_BLOCK) - verse quote (NOT combined with Paragraph 1 because of barrier)
- Paragraph 4: Lines 10-15 (STANDARD_PROSE) - commentary

**After filtering HEADER_BLOCKs:**
- Paragraph 1: Lines 0-3 (VERSE_BLOCK) - header metadata
- Paragraph 2: Lines 6-9 (VERSE_BLOCK) - verse quote
- Paragraph 3: Lines 10-15 (STANDARD_PROSE) - commentary

## Implementation Checklist

**Files to modify:**
- `backend/crawler/paragraph_generator/advanced.py`

**Changes required:**
1. [ ] Add `HEADER_BLOCK = auto()` to State enum (line ~21)
2. [ ] Modify `process_line` to enter HEADER_BLOCK state (lines ~178-182)
3. [ ] Add `_handle_header_block_state` method (~10 lines, after line ~304)
4. [ ] Update `_finalize_paragraph` separator logic (line ~160)
5. [ ] Add HEADER_BLOCK handling in `_phase2_combine_by_type` (~5 lines)
6. [ ] Update `_phase3_combine_prose` to treat HEADER_BLOCK like VERSE_BLOCK (~1 line)
7. [ ] Filter out HEADER_BLOCKs at end of Phase 2 (1 line)

**Estimated complexity:**
- ~30-40 lines of code changes/additions
- Touches 6 methods
- No breaking changes to external API

## Related Issues Fixed

This same architecture fix also addresses:

1. **Page 0021.json issue:** Q&A blocks and verse blocks being merged
   - With state reset fix: Q&A properly exits when encountering centered text
   - HEADER_BLOCK ensures proper separation

2. **General principle:** Any content separated by headers will stay separated

## Alternative Considered

**Simple fix:** Add `self.state = State.STANDARD_PROSE` when encountering IS_HEADER_REGEX

**Why it's insufficient:**
- Only prevents merging during Phase 1
- Phase 2 still combines consecutive VERSE_BLOCKs across the gap left by skipped headers
- Doesn't solve the architectural problem

## Notes

- HEADER_BLOCK is never combined with other HEADER_BLOCKs (each header line/group is independent)
- HEADER_BLOCK acts as an immutable barrier throughout the pipeline
- Headers are filtered out at the last possible moment (end of Phase 2)
- This preserves semantic information longer (good for debugging, alternative outputs)

## Status

**Current:** Not implemented - on back burner

**Decision:** Defer implementation until needed for production

**Workaround:** Configure header_regex patterns more comprehensively to catch header metadata lines (lines 0-3 in the example)