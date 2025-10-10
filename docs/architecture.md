# System Architecture

## Overview

The Financial Research Agent is a production-ready RAG system designed to analyze broker research PDFs at scale. It combines modern AI techniques with robust engineering practices to deliver accurate, traceable insights from financial documents.

## Design Principles

1. **Multimodal First**: Extract maximum value from all content types (text, tables, images)
2. **Traceable**: Every insight links back to source documents with page-level precision
3. **Scalable**: Horizontal scaling through pgvector and stateless Django workers
4. **Maintainable**: Clear separation of concerns with Django apps architecture

## Core Architecture

### Data Flow

```
PDF Upload → Document Processor → Vector Embeddings → pgvector Storage
                    ↓                                        ↓
                Text Chunks                          Semantic Search
                Table Summaries                             ↓
                Image Descriptions                   Query Engine
                                                           ↓
                                                    Response Synthesis
```

### Component Breakdown

#### 1. Document Ingestion Layer
- **Purpose**: Transform unstructured PDFs into searchable knowledge
- **Components**:
  - `MetadataExtractor`: Intelligent parsing of broker, ticker, dates
  - `MultimodalDocumentProcessor`: Orchestrates extraction pipeline
  - `BrokerDocument` model: Tracks processing state and statistics

#### 2. Vector Storage Layer
- **Purpose**: Enable semantic search across millions of documents
- **Technology**: PostgreSQL + pgvector extension
- **Schema**:
  ```sql
  -- Simplified view
  CREATE TABLE llama_index_embeddings (
    id UUID PRIMARY KEY,
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    metadata JSONB,
    text TEXT
  );
  ```
- **Indexing**: IVFFlat for approximate nearest neighbor search

#### 3. Query Processing Layer
- **Purpose**: Convert natural language queries into accurate responses
- **Components**:
  - `VectorIndexRetriever`: Fetches semantically similar chunks
  - `NodePostprocessors`: Deduplication, diversity, relevance filtering
  - `ResponseSynthesizer`: Combines chunks into coherent answers

#### 4. Application Layer
- **Chat Interface**: Real-time conversational UI with streaming
- **Document Management**: Upload, process, and track PDFs
- **Admin Interface**: Monitor system health and document status

## Technology Decisions

### Why pgvector?
- **Pros**: 
  - Native PostgreSQL integration
  - ACID compliance for embeddings
  - Single database for all data
  - Excellent Django ORM support
- **Cons**:
  - Less mature than specialized vector DBs
  - Requires PostgreSQL 15+

### Why LlamaIndex?
- **Pros**:
  - Best-in-class document processing
  - Flexible query pipeline
  - Strong multimodal support
  - Active development
- **Cons**:
  - Steeper learning curve
  - Occasional API changes

### Why OpenAI APIs?
- **Pros**:
  - State-of-the-art models
  - Consistent quality
  - Multimodal capabilities (GPT-4V)
- **Cons**:
  - Cost at scale
  - Vendor lock-in
  - Network dependency

## Scalability Considerations

### Current Capabilities
- Handles 100+ PDFs with 10,000+ pages
- Sub-second query response times
- Concurrent document processing

### Bottlenecks
1. **Embedding Generation**: Limited by OpenAI rate limits
2. **Image Processing**: Sequential GPT-4V calls are slow
3. **Memory Usage**: Large PDFs can consume significant RAM

### Scaling Strategies
1. **Horizontal**: Add Django workers behind load balancer
2. **Caching**: Redis for embedding cache
3. **Async Processing**: Celery for background jobs
4. **Partitioning**: Shard by ticker or date range

## Security Architecture

### Data Protection
- Environment-based configuration
- Encrypted API keys
- File hash verification
- SQL injection prevention via ORM

### Access Control
- Django authentication system
- Admin/user role separation
- CSRF protection
- Secure file uploads

## Monitoring & Observability

### Current Implementation
- Django logging framework
- Processing statistics per document
- Error tracking in database

### Recommended Additions
- Prometheus metrics
- Grafana dashboards
- Sentry error tracking
- OpenTelemetry tracing

## Deployment Architecture

### Development
```
Docker Compose
├── web (Django)
├── db (PostgreSQL + pgvector)
└── volumes (persistent storage)
```

### Production (Recommended)
```
Kubernetes Cluster
├── Django Deployment (3+ replicas)
├── PostgreSQL StatefulSet
├── Redis Cache
├── Nginx Ingress
└── Persistent Volumes
```

## Future Architecture Considerations

### Short Term
1. Implement caching layer
2. Add async task processing
3. Improve image processing pipeline

### Long Term
1. Multi-tenant architecture
2. Real-time document updates
3. Custom fine-tuned models
4. GraphQL API layer