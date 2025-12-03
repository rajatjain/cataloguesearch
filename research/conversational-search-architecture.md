# Conversational Search Architecture

## Executive Summary

This document outlines the complete architecture for adding conversational search capabilities to CatalogueSearch, designed to stay under $10/month while supporting Hindi and English queries within a ~2GB RAM constraint.

## 1. Cost Analysis for Public LLM APIs

### Recommended: Google Gemini 2.0 Flash (Experimental - FREE)
- **Input:** FREE (currently experimental)
- **Output:** FREE (currently experimental)
- **Why:** Excellent multilingual support (Hindi/English), fast inference, structured output support
- **Monthly estimate:** $0 (while in free tier)
- **Fallback plan:** When charged, estimated $2-3/month for typical usage

### Alternative: OpenAI GPT-4o-mini
- **Input:** $0.150 per 1M tokens
- **Output:** $0.600 per 1M tokens
- **Estimated usage:** ~500 queries/day × 30 days = 15,000 queries/month
  - Input: ~200 tokens/query × 15,000 = 3M tokens = $0.45
  - Output: ~100 tokens/query × 15,000 = 1.5M tokens = $0.90
- **Monthly estimate:** ~$1.35/month
- **Why:** Excellent structured output, good Hindi support, reliable

### Alternative: Anthropic Claude 3 Haiku
- **Input:** $0.25 per 1M tokens
- **Output:** $1.25 per 1M tokens
- **Monthly estimate:** ~$2.63/month
- **Why:** Best instruction following, excellent for query planning

### Alternative: Groq (Free Tier with Llama models)
- **Free tier:** 14,400 requests/day (Llama 3.1 8B)
- **Cost:** FREE for first tier
- **Why:** Good balance, decent Hindi support via multilingual Llama
- **Monthly estimate:** $0

**RECOMMENDATION: Use Gemini 2.0 Flash (free) with OpenAI GPT-4o-mini as fallback**
- Total estimated cost: $0-1.35/month (well under $10 budget)

---

## 2. Architectural Overview

### 2.1 System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  - Conversational UI component                                   │
│  - Session management                                            │
│  - Query history display                                         │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                               │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Conversation Manager (In-Memory)                        │   │
│  │  - Session store (Python dict with LRU)                 │   │
│  │  - Sliding window (last 2-3 turns)                      │   │
│  │  - Pagination state tracking                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Query Planning Module                                   │   │
│  │  - LLM integration (Gemini/OpenAI)                      │   │
│  │  - Prompt engineering for DSL generation                │   │
│  │  - Context-aware query rewriting                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Existing Search Pipeline                                │   │
│  │  - OpenSearch DSL execution                             │   │
│  │  - bge-reranker-base (existing)                         │   │
│  │  - Result formatting                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │   OpenSearch   │
                  │  (Existing)    │
                  └────────────────┘
```

### 2.2 Memory Footprint Analysis

| Component | Memory Usage | Notes |
|-----------|--------------|-------|
| Conversation Manager | ~10-20 MB | In-memory dict with max 100 sessions |
| Query Planning Module | ~5 MB | HTTP client + prompt templates |
| LLM API Calls | 0 MB | External API (no local model) |
| Existing Pipeline | ~700 MB | bge-m3 + reranker (unchanged) |
| **Total New Memory** | **~15-25 MB** | Well under 2GB constraint |

---

## 3. Detailed Component Design

### 3.1 Conversation State Schema

```python
@dataclass
class ConversationTurn:
    """Represents a single turn in conversation"""
    user_query: str                    # Original user input
    understood_intent: str             # LLM-parsed intent
    opensearch_dsl: dict              # Generated OpenSearch query
    results_returned: int             # Number of results returned
    pagination_state: dict            # {from: int, size: int}
    timestamp: datetime

@dataclass
class ConversationSession:
    """Represents an entire conversation session"""
    session_id: str                   # UUID
    language: str                     # Primary language (hindi/english)
    turns: List[ConversationTurn]     # History (max 3 turns)
    current_filters: dict             # Active category filters
    current_search_context: dict      # Last search parameters
    created_at: datetime
    last_active: datetime
```

### 3.2 Conversation Manager (In-Memory)

```python
class ConversationManager:
    """
    Manages conversation sessions with LRU eviction policy.
    Zero external dependencies, minimal memory footprint.
    """

    def __init__(self, max_sessions: int = 100, ttl_minutes: int = 30):
        self._sessions: OrderedDict[str, ConversationSession] = OrderedDict()
        self._max_sessions = max_sessions
        self._ttl = timedelta(minutes=ttl_minutes)

    def create_session(self, language: str = "hindi") -> str:
        """Create new session, return session_id"""

    def add_turn(self, session_id: str, turn: ConversationTurn) -> None:
        """Add turn to session, maintain sliding window of 3 turns"""

    def get_context(self, session_id: str) -> Optional[ConversationSession]:
        """Retrieve session context for query planning"""

    def cleanup_expired(self) -> int:
        """Remove sessions older than TTL"""
```

### 3.3 Query Planning Module

#### 3.3.1 LLM Prompt Template

```python
QUERY_PLANNING_PROMPT = """You are a query planning assistant for a religious text search system.
Your job is to convert natural language queries into OpenSearch Query DSL (JSON).

CONTEXT:
- User is searching a corpus of Hindi and Gujarati religious texts (Pravachan, Granth)
- Previous conversation: {conversation_history}
- Current filters: {current_filters}
- Last pagination state: {pagination_state}

USER QUERY: "{user_query}"

TASK:
1. Understand user intent (new_search, refine_search, pagination, filter_modification, expansion)
2. Generate OpenSearch Query DSL JSON
3. Update filters if mentioned
4. Set pagination parameters (from, size)

RULES:
- For "show more results": increment 'from' by 'size'
- For "only from 2023": add filter to metadata.Year field
- For "what about [topic]": create new search, keep context
- For refinements: modify existing query filters
- Detect language from query (hindi/gujarati/english)
- Use text_content_hindi or text_content_gujarati fields appropriately
- NO HALLUCINATION: Only generate queries, don't synthesize answers

OUTPUT FORMAT (JSON):
{
  "intent": "new_search|refine_search|pagination|filter_modification|expansion",
  "language": "hindi|gujarati|english",
  "opensearch_dsl": {
    "query": { ... },
    "from": 0,
    "size": 20,
    "highlight": { ... }
  },
  "filters": {
    "categories": { ... }
  },
  "explanation": "Brief explanation of what you understood"
}
"""
```

#### 3.3.2 Query Planner Implementation

```python
class QueryPlanner:
    """
    Converts natural language queries to OpenSearch DSL using LLM.
    Supports Gemini and OpenAI with automatic fallback.
    """

    def __init__(self, primary_provider: str = "gemini"):
        self.primary_provider = primary_provider
        self.gemini_client = None  # Initialize based on config
        self.openai_client = None

    async def plan_query(
        self,
        user_query: str,
        conversation_context: Optional[ConversationSession] = None
    ) -> QueryPlan:
        """
        Main entry point: Parse NL query into OpenSearch DSL.

        Args:
            user_query: Natural language query from user
            conversation_context: Previous conversation turns

        Returns:
            QueryPlan with intent, DSL, filters, and explanation
        """

    def _build_prompt(self, user_query: str, context: ConversationSession) -> str:
        """Build LLM prompt with conversation history"""

    async def _call_gemini(self, prompt: str) -> dict:
        """Call Gemini 2.0 Flash API"""

    async def _call_openai(self, prompt: str) -> dict:
        """Fallback: Call OpenAI GPT-4o-mini"""

    def _validate_dsl(self, dsl: dict) -> bool:
        """Validate generated DSL is safe and well-formed"""
```

### 3.4 Intent Classification

| Intent | Description | Example Query | Action |
|--------|-------------|---------------|--------|
| `new_search` | Fresh query, clear previous context | "Tell me about karma" | Create new search, reset pagination |
| `refine_search` | Modify previous search | "Only from Gurudev" | Add/modify filters, keep base query |
| `pagination` | Continue to next page | "Show more results" | Increment `from` parameter |
| `filter_modification` | Change active filters | "Remove year filter" | Update filter state |
| `expansion` | Related but new query | "What about moksha?" | New search with semantic context |

### 3.5 Pagination State Management

```python
class PaginationTracker:
    """Track pagination across conversation turns"""

    def __init__(self):
        self.current_from = 0
        self.page_size = 20
        self.total_results = 0
        self.results_exhausted = False

    def next_page(self) -> Tuple[int, int]:
        """Get next page parameters"""
        self.current_from += self.page_size
        return (self.current_from, self.page_size)

    def reset(self):
        """Reset pagination for new search"""
        self.current_from = 0
        self.results_exhausted = False
```

---

## 4. API Endpoint Design

### 4.1 New Endpoints

#### POST /api/conversation/start
Create a new conversation session.

**Request:**
```json
{
  "language": "hindi"  // optional, defaults to "hindi"
}
```

**Response:**
```json
{
  "session_id": "uuid-v4",
  "language": "hindi",
  "created_at": "2025-12-02T10:30:00Z"
}
```

#### POST /api/conversation/query
Submit a conversational query.

**Request:**
```json
{
  "session_id": "uuid-v4",
  "query": "Show me more results about karma from 2023 only"
}
```

**Response:**
```json
{
  "session_id": "uuid-v4",
  "intent": "refine_search",
  "explanation": "Showing next page of karma results, filtered to 2023",
  "results": {
    "pravachan_results": { ... },  // Existing format
    "granth_results": { ... }
  },
  "conversation_context": {
    "current_query": "karma",
    "active_filters": {
      "Year": ["2023"]
    },
    "pagination": {
      "current_page": 2,
      "has_more": true
    }
  }
}
```

#### GET /api/conversation/history/{session_id}
Retrieve conversation history.

**Response:**
```json
{
  "session_id": "uuid-v4",
  "turns": [
    {
      "user_query": "karma",
      "results_count": 20,
      "timestamp": "2025-12-02T10:30:00Z"
    }
  ]
}
```

#### DELETE /api/conversation/{session_id}
End conversation session (optional, sessions auto-expire).

---

## 5. Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Set up Gemini/OpenAI API clients
- [ ] Implement ConversationManager (in-memory)
- [ ] Create basic QueryPlanner with prompt template
- [ ] Add /api/conversation/start endpoint
- [ ] Unit tests for conversation storage

### Phase 2: Query Planning (Week 2)
- [ ] Implement intent classification logic
- [ ] Build prompt engineering for each intent type
- [ ] Add DSL validation and safety checks
- [ ] Handle pagination state tracking
- [ ] Integration tests with mock LLM

### Phase 3: Search Integration (Week 3)
- [ ] Connect QueryPlanner to existing IndexSearcher
- [ ] Implement /api/conversation/query endpoint
- [ ] Test with real OpenSearch queries
- [ ] Add error handling and fallbacks
- [ ] End-to-end testing

### Phase 4: Frontend & Polish (Week 4)
- [ ] Create conversational UI component
- [ ] Add chat-like interface
- [ ] Display conversation context
- [ ] Show query explanations
- [ ] User testing and refinement

---

## 6. Key Design Decisions

### 6.1 Why Public LLM APIs?
- **Cost effective:** $0-1.35/month vs $0 for self-hosted but better quality
- **Zero memory overhead:** No local model (saves ~1-2GB RAM)
- **Better multilingual support:** GPT-4o-mini and Gemini excel at Hindi/English
- **Lower latency:** API calls are fast (~500ms)
- **No maintenance:** No model updates or ONNX conversion needed

### 6.2 Why In-Memory Storage?
- **Simplicity:** No Redis dependency, zero config
- **Performance:** Nanosecond lookup times
- **Low overhead:** ~10-20MB for 100 sessions
- **Session-scoped:** Conversations don't need persistence beyond session

### 6.3 Why Sliding Window (3 turns)?
- **Memory efficient:** Each turn ~1-2KB, total ~6KB per session
- **Sufficient context:** Most conversational queries reference last 1-2 turns
- **Prevents context bloat:** Older turns irrelevant for current intent

### 6.4 Why NOT Generate Answers?
- **Requirement:** System must return only original source snippets
- **No hallucination:** LLM only plans queries, doesn't synthesize content
- **Trust:** Users see authentic text from religious sources
- **LLM role:** Query understanding and DSL generation only

---

## 7. Example Conversational Flows

### Example 1: Query Refinement
```
User: "karma ke baare mein batao"
System: [Searches for "karma", returns 20 results]

User: "sirf 2023 ke results dikhao"
LLM Intent: refine_search
LLM Action: Add filter {"Year": ["2023"]} to existing query
System: [Returns 8 results filtered to 2023]
```

### Example 2: Pagination
```
User: "moksha"
System: [Returns results 1-20]

User: "aur results dikhao"
LLM Intent: pagination
LLM Action: Set from=20, size=20
System: [Returns results 21-40]
```

### Example 3: Query Expansion
```
User: "dharma kya hai"
System: [Returns results about dharma]

User: "karma ke baare mein bhi batao"
LLM Intent: expansion
LLM Action: New search for "karma", keep language context
System: [Returns fresh results about karma]
```

### Example 4: Filter Modification
```
User: "Gurudev ke pravachan"
System: [Filters by Author: "Gurudev"]

User: "author filter hatao aur granth type add karo"
LLM Intent: filter_modification
LLM Action: Remove Author filter, add content_type: "Granth"
System: [Returns Granth results without author filter]
```

---

## 8. Testing Strategy

### 8.1 Unit Tests
- ConversationManager session lifecycle
- Pagination state transitions
- Intent classification accuracy
- DSL validation

### 8.2 Integration Tests
- Full query planning flow
- LLM API response parsing
- OpenSearch query execution
- Error handling and fallbacks

### 8.3 End-to-End Tests
- Multi-turn conversations
- Language mixing (Hindi/English)
- Filter combinations
- Pagination edge cases

### 8.4 Performance Tests
- Memory usage under load (100 concurrent sessions)
- LLM API latency (p95 < 1s)
- Session cleanup efficiency

---

## 9. Monitoring and Observability

### 9.1 Metrics to Track
- LLM API call count and cost (daily)
- Average tokens per query (input/output)
- Intent classification distribution
- Conversation session duration
- Query success rate
- Memory usage per session

### 9.2 Logging
- All LLM prompts and responses (debug mode)
- Generated OpenSearch DSL queries
- Conversation turn metadata
- API errors and fallbacks

---

## 10. Security Considerations

### 10.1 DSL Injection Prevention
- Validate all generated DSL against schema
- Whitelist allowed query types
- Sanitize user input before LLM
- Limit query complexity (max depth, clauses)

### 10.2 Rate Limiting
- Per-session query rate limit (10 queries/minute)
- Global LLM API call limit (100 queries/minute)
- Session creation limit (5 per IP per hour)

### 10.3 API Key Management
- Store Gemini/OpenAI keys in environment variables
- Rotate keys quarterly
- Monitor for unauthorized usage

---

## 11. Cost Monitoring

### 11.1 Budget Alerts
- Set alert at $5/month (50% of budget)
- Track daily spending trends
- Automatically switch to free tier (Groq) if exceeded

### 11.2 Cost Optimization
- Cache common query patterns (e.g., "show more")
- Use cheaper model (Gemini free tier) first
- Implement simple rule-based intents before LLM call
  - "show more" → pagination intent (no LLM needed)
  - "aur results" → pagination intent (no LLM needed)

---

## 12. Future Enhancements (Post-MVP)

### 12.1 Advanced Features
- Multi-language mixing detection (Hindi + Gujarati in one query)
- Query suggestions based on conversation history
- Bookmark conversation threads
- Export conversation history

### 12.2 Performance Optimizations
- Intent caching for common patterns
- Prompt compression techniques
- Batch LLM calls for multiple sessions
- Persistent session storage (PostgreSQL)

### 12.3 Model Improvements
- Fine-tune smaller model on query planning task
- Migrate to self-hosted Qwen2.5-1.5B if cost increases
- Experiment with prompt optimization for fewer tokens

---

## 13. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM API cost spike | High | Low | Budget alerts, automatic fallback to Groq free tier |
| LLM generates invalid DSL | Medium | Medium | DSL validation, fallback to simple keyword search |
| Poor Hindi query understanding | High | Medium | Use Gemini (better multilingual), add few-shot examples |
| Session memory leak | Medium | Low | TTL cleanup, max session limit, monitoring |
| API rate limits | Medium | Low | Exponential backoff, queue management |

---

## 14. Success Metrics

### 14.1 Technical Metrics
- Query planning accuracy: >85% correct intent classification
- DSL generation success rate: >95% valid queries
- Average response time: <2s end-to-end
- Memory usage: <50MB for conversational components
- Cost: <$2/month average

### 14.2 User Experience Metrics
- Conversation completion rate: >70%
- Average turns per session: 3-5
- User satisfaction (survey): >4/5
- Query refinement usage: >30% of sessions

---

## 15. Conclusion

This architecture delivers conversational search capability while respecting all constraints:

✅ **Cost:** $0-1.35/month (well under $10 budget)
✅ **Memory:** ~15-25MB new overhead (well under 2GB limit)
✅ **No AI Generation:** LLM only plans queries, returns original snippets
✅ **Multi-turn Context:** Sliding window with 3-turn history
✅ **All Features:** Query refinement, pagination, expansion, filter modification
✅ **Multilingual:** Hindi + English support via Gemini/GPT-4o-mini

The system leverages public LLM APIs for quality query understanding while maintaining simplicity with in-memory storage, making it both cost-effective and performant.