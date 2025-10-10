# Chat Application

## Overview

The chat app implements a sophisticated RAG (Retrieval-Augmented Generation) system that enables conversational analysis of financial documents. It combines semantic search, intelligent deduplication, and multimodal understanding to deliver accurate, sourced responses.

## Core Components

### 1. LlamaIndex Configuration (`llamaindex_setup.py`)

**Purpose**: Centralizes AI model configuration and initialization

**Key Features**:
- Singleton pattern for resource efficiency
- Automatic environment configuration
- Model selection optimized for use case:
  - `gpt-4o-mini`: General reasoning (fast, cost-effective)
  - `gpt-4o`: Vision tasks (charts, images)
  - `text-embedding-3-small`: Semantic search (1536 dimensions)

**Strengths**:
- Clean separation of concerns
- Easy model swapping
- Consistent configuration

**Weaknesses**:
- No fallback models if OpenAI is down
- Limited error recovery

### 2. Document Processor (`document_processor.py`)

**Purpose**: Transforms PDFs into searchable, multimodal knowledge chunks

**Processing Pipeline**:
```python
PDF → Text Extraction → Chunking (512 tokens, 50 overlap)
    → Table Detection → Markdown Conversion → Summarization  
    → Image Extraction → Vision Analysis → Description
```

**Key Algorithms**:
- **Text Chunking**: Semantic splitting with overlap for context preservation
- **Table Processing**: 
  1. Extract via pdfplumber
  2. Convert to markdown
  3. Generate summary with GPT-4o-mini
  4. Store both summary and raw data
- **Image Processing**:
  1. Extract via PyMuPDF
  2. Filter small/irrelevant images
  3. Save to disk
  4. Generate descriptions (currently failing)

**Strengths**:
- Handles complex PDF structures
- Preserves table relationships
- Metadata-rich chunks

**Weaknesses**:
- Image description fails due to API mismatch
- No OCR fallback for scanned PDFs
- Sequential processing (slow for large docs)

### 3. Query Engine (`views.py` + `rag_engine.py`)

**Purpose**: Converts natural language queries into accurate, sourced responses

**Query Flow**:
```
User Query → Vector Search (top 15) → Deduplication → Reranking → Synthesis
```

**Deduplication Strategy** (`node_postprocessors.py`):
1. **PageDeduplicator**: Max 1 chunk per page, 2 per document
2. **SemanticDeduplicator**: 80% similarity threshold
3. **ContentTypeDiversifier**: Ensures mix of text/table/image results

**Response Synthesis**:
- Custom prompt template for financial context
- Source attribution with page numbers
- Streaming response support

**Strengths**:
- Excellent deduplication prevents redundant information
- Fast retrieval (< 500ms typical)
- Clear source attribution

**Weaknesses**:
- No query understanding/reformulation
- Limited context window utilization
- No conversation memory between sessions

### 4. Chat Interface (`chatgpt_style.html`)

**Purpose**: Provides intuitive conversational UI with real-time features

**Key Features**:
- **Real-time Updates**: WebSocket-like experience with polling
- **Source Viewing**: Click-through to original artifacts
- **Conversation Management**: Multiple chat sessions
- **Progress Indicators**: Loading states and animations

**Technical Implementation**:
- Pure JavaScript (no framework dependencies)
- Tailwind CSS for responsive design
- CSRF protection
- XSS prevention via escaping

**Strengths**:
- Clean, professional interface
- Mobile responsive
- Fast initial load

**Weaknesses**:
- No real WebSocket support
- Limited offline capabilities
- Basic error handling

## Data Models

### Message Model
```python
class Message:
    conversation: ForeignKey(Conversation)
    role: 'user' | 'assistant'
    content: TextField
    metadata: JSONField  # stores sources
    created_at: DateTimeField
```

### Source Metadata Structure
```json
{
  "sources": [
    {
      "node_id": "uuid",
      "broker": "Goldman Sachs",
      "ticker": "NVDA",
      "report_date": "2024-01-15",
      "page_number": 7,
      "content_type": "table",
      "score": 0.89,
      "text_preview": "Revenue projections...",
      "image_path": "/media/extracted/gs_nvda_p7.png"
    }
  ]
}
```

## Performance Characteristics

### Response Times
- **First query**: 2-5 seconds (cold start)
- **Subsequent queries**: 0.5-2 seconds
- **Document processing**: 10-30 seconds per PDF

### Resource Usage
- **Memory**: 200-500MB per worker
- **CPU**: Moderate (spikes during embedding)
- **Storage**: ~1MB per PDF page (including images)

## Security Considerations

### Implemented
- CSRF protection on all endpoints
- XSS prevention via template escaping
- SQL injection prevention via ORM
- File upload validation

### Missing
- Rate limiting
- User authentication (beyond admin)
- Audit logging
- Input sanitization for prompts

## Integration Points

### External APIs
1. **OpenAI Embeddings API**: 
   - Endpoint: `https://api.openai.com/v1/embeddings`
   - Rate limit: 3000 RPM
   - Batch size: 100

2. **OpenAI Chat API**:
   - Endpoint: `https://api.openai.com/v1/chat/completions`
   - Rate limit: 10000 RPM
   - Streaming enabled

3. **OpenAI Vision API**:
   - Currently broken due to implementation issue
   - Should accept base64 or URLs

### Internal APIs
- `/chat/message/`: Send message, get response
- `/chat/conversations/`: List conversations
- `/chat/artifact/<id>/`: Retrieve source artifacts

## Known Issues & Limitations

### Critical
1. **Image Processing Broken**: API expects different format
2. **No Conversation Context**: Each query is independent
3. **Limited Error Recovery**: Fails hard on API errors

### Important
1. **No Query Caching**: Identical queries hit OpenAI each time
2. **Sequential Processing**: Can't parallelize document processing
3. **Memory Pressure**: Large conversations can OOM

### Nice-to-Have
1. **No Export Functionality**: Can't save conversations
2. **Basic Search UI**: No advanced filters
3. **Limited Analytics**: No usage tracking

## Optimization Opportunities

### Quick Wins
1. Implement Redis caching for embeddings
2. Batch API calls where possible
3. Add client-side response caching

### Medium Term
1. Async document processing with Celery
2. Implement conversation memory
3. Add query understanding layer

### Long Term
1. Fine-tune models for finance domain
2. Implement hybrid search (keyword + semantic)
3. Build custom reranking models

## Testing Approach

### Current Coverage
- Basic model tests
- View integration tests (limited)

### Recommended Tests
```python
# Query accuracy
def test_nvda_price_target_query():
    response = query_engine.query("What is Goldman's NVDA price target?")
    assert "price target" in response.lower()
    assert any(s.broker == "Goldman Sachs" for s in response.sources)

# Deduplication
def test_deduplication():
    results = retriever.retrieve("NVDA revenue", top_k=20)
    pages_seen = set()
    for r in results:
        page_key = (r.metadata.broker, r.metadata.page_number)
        assert page_key not in pages_seen
        pages_seen.add(page_key)
```

## Maintenance Notes

### Daily Operations
- Monitor OpenAI API usage
- Check for failed document processing
- Clear old conversation data

### Common Issues
1. **"Rate limit exceeded"**: Implement exponential backoff
2. **"Embedding dimension mismatch"**: Check model consistency
3. **"No results found"**: Verify documents are processed

### Upgrade Path
- LlamaIndex: Follow migration guides carefully
- OpenAI: API versions are backward compatible
- Django: Standard upgrade process