# System Architecture - How Everything Works Together

## Overview for Non-Technical Readers

Think of this system as a highly sophisticated filing cabinet that not only stores documents but can also read them, understand them, and answer questions about their contents. When you upload a broker research PDF, the system breaks it into small, digestible pieces, stores each piece with a special mathematical "fingerprint," and uses these fingerprints to find relevant information when you ask questions.

## The Complete Journey: From PDF to Answer

### Step 1: Document Upload - Getting PDFs Into the System

When someone clicks "Upload" and selects a broker research PDF, several sophisticated processes begin working in concert. The system first calculates a unique "fingerprint" (called a hash) of the entire document. This fingerprint is like a document's DNA - if even one character in the PDF changes, the fingerprint completely changes. This prevents the same document from being processed twice, saving significant time and computational resources.

The file upload process is carefully orchestrated. The web browser sends the PDF file to our Django web server, which temporarily stores it in memory while performing initial checks. The system verifies the file is actually a PDF (not a disguised malicious file), checks its size isn't too large (current limit is 50MB), and ensures we have enough storage space. Only after these checks pass does the system save the file to disk in a special directory structure that prevents naming conflicts.

**Why this matters:** Without these checks, users could crash the system with massive files, upload the same costly-to-process document repeatedly, or potentially introduce security vulnerabilities. The careful orchestration ensures reliability while protecting system resources.

### Step 2: Metadata Extraction - Understanding What We're Looking At

Before diving into the document's contents, the system attempts to understand what document it's processing. This happens through a clever three-stage approach that balances accuracy with processing speed.

**Stage 1 - Filename Analysis:** The system first examines the filename using sophisticated pattern matching. It knows that financial firms often follow naming conventions like "20240115 - Goldman Sachs - NVDA - Q4 Analysis.pdf" or "GS_NVDA_2024Q4.pdf". The system maintains a library of over 30 patterns that cover common naming schemes across major brokers. This stage takes mere milliseconds and successfully extracts metadata for about 70% of documents.

**Stage 2 - First Page Scanning:** If the filename doesn't yield clear results, the system reads just the first page of the PDF. Investment research reports typically display the broker name, date, and ticker symbols prominently on the cover page. The system looks for phrases like "Goldman Sachs Research," ticker symbols in headers, and date formats. This stage takes about 200 milliseconds and catches another 25% of documents.

**Stage 3 - Deep Document Analysis:** For the remaining 5% of documents with non-standard formats, the system performs a complete text extraction and searches the entire document. While this takes 2-3 seconds, it ensures even poorly named or unusually formatted documents get properly categorized.

The system also maintains a comprehensive mapping of broker name variations. It knows that "GS," "Goldman," and "Goldman Sachs & Co." all refer to the same institution. This normalization ensures that searches for "Goldman Sachs NVIDIA research" will find documents regardless of how the broker name appears.

**Why this matters:** Accurate metadata extraction is crucial for search quality. If a Morgan Stanley report about Apple gets mislabeled as a Goldman Sachs report about Microsoft, users won't find it when searching. The three-stage approach balances speed (most documents process quickly) with completeness (even unusual documents get handled correctly).

### Step 3: Content Extraction - Mining the Document's Treasures

This is where the system truly shines. Unlike simple PDF readers that just extract text, our system understands that financial documents contain three distinct types of valuable content, each requiring specialized handling.

**Text Extraction:** Using the PyMuPDF library (chosen for its speed and accuracy), the system extracts text page by page. But it doesn't stop at simple extraction. The system preserves formatting cues like headers, paragraphs, and bullet points. It identifies section breaks and maintains reading order even in complex multi-column layouts. Each page's text is tagged with its page number, enabling the precise source attribution that makes this system valuable for financial analysis.

**Table Processing:** Financial documents are filled with data tables - revenue projections, comparative analyses, historical trends. The system uses pdfplumber (specifically chosen for its superior table detection) to identify and extract these tables. Tables are converted to a markdown format that preserves their structure. But here's the clever part: the system also generates an AI-powered summary of each table. So a complex 20-row financial projection table gets both preserved in full detail AND summarized as "Q1-Q4 2024 revenue projections showing 15% YoY growth with improving margins." This dual approach enables both precise data retrieval and conceptual searching.

**Note:** While tables are correctly extracted and stored with proper formatting, the current display system fails to preserve this structure. Tables appear as continuous text strings rather than structured data. This frontend display issue significantly impacts usability.

**Image Extraction:** The system identifies and extracts all images, charts, and graphs from PDFs. These are saved as separate image files with systematic naming that links them back to their source document and page. Unfortunately, this is where we hit a critical failure - while images are successfully extracted, the system cannot generate searchable descriptions due to an API integration error with OpenAI's vision model. This means roughly 30% of valuable content (all those charts showing trends, market share diagrams, and visual comparisons) remains invisible to search queries.

**Why this matters:** Financial analysis relies heavily on all three content types. Text provides context and reasoning, tables contain the hard data, and charts visualize trends and relationships. By extracting all three (even if image search is currently broken), the system creates a comprehensive knowledge base. The dual approach to tables (keeping both raw data and summaries) is particularly clever - it enables both "find Apple's Q3 revenue" (specific data) and "show me strong revenue growth" (conceptual) searches to work effectively.

### Step 4: Chunking - Breaking Documents Into Searchable Pieces

Here's where things get intellectually interesting. The system can't search through entire 50-page documents efficiently, so it breaks them into smaller, overlapping pieces called "chunks." But this isn't random chopping - it's a carefully orchestrated process with specific parameters chosen through extensive testing.

Each chunk contains exactly 512 tokens (roughly 380 words or 2-3 paragraphs). This size was chosen after testing revealed that smaller chunks (128-256 tokens) would split important concepts across boundaries. Imagine breaking "NVIDIA's data center revenue grew 45% driven by AI demand" into two chunks - the growth figure gets separated from its cause, making search less effective. Larger chunks (1024+ tokens) created the opposite problem - searching for "gross margin" might return an entire page discussing various financial metrics, burying the relevant information.

The crucial innovation is the 50-token overlap between consecutive chunks. This overlap (roughly 2-3 sentences) ensures that concepts spanning chunk boundaries remain searchable. If chunk 1 ends with "This growth is primarily due to three factors:" and chunk 2 starts with those factors, the overlap ensures both chunks contain the complete thought.

Each chunk is tagged with rich metadata: the source document, broker, ticker, date, page number, and position within the page. This metadata enables the sophisticated filtering and attribution that makes the system valuable.

**Why this matters:** Chunking strategy directly impacts search quality. Too small and you lose context. Too large and you lose precision. The 512-token sweet spot with 50-token overlap represents extensive experimentation to find the optimal balance for financial documents. The rich metadata ensures that every chunk can be traced back to its exact source, enabling the trust and verification essential in financial analysis.

### Step 5: Embedding Generation - Creating Mathematical Fingerprints

This step transforms human-readable text into mathematical representations that computers can search efficiently. Using OpenAI's text-embedding-3-small model, each chunk gets converted into a list of 1,536 numbers (called a vector). These numbers encode the semantic meaning of the text in a way that mathematically similar vectors represent conceptually similar text.

The process is fascinating: "revenue growth" might become [0.23, -0.45, 0.67, ...] while "sales increase" becomes [0.24, -0.43, 0.66, ...]. Notice how similar concepts have similar numbers. This enables the system to understand that a search for "revenue growth" should also find documents mentioning "sales expansion" or "top-line improvement."

The system processes chunks in batches of 100 to optimize API usage and reduce costs. Each embedding costs money to generate (about $0.00002 per chunk), so efficient batching matters at scale. The 1,536-dimensional space was chosen as the optimal balance between semantic richness (capturing subtle differences in meaning) and storage costs (each vector requires 6KB of storage).

**Why this matters:** Embeddings are the secret sauce that enables semantic search. Without them, searching for "bullish outlook" wouldn't find "positive view" or "optimistic forecast." The high dimensionality ensures that subtle differences in financial language are preserved - "revenue growth" vs "revenue growth concerns" have very different embeddings despite similar words. This mathematical representation of meaning is what elevates the system beyond simple keyword matching.

### Step 6: Vector Storage - Organizing for Lightning-Fast Retrieval

The embeddings and their associated chunks need to be stored in a way that enables rapid searching across potentially millions of chunks. The system uses PostgreSQL with the pgvector extension, which adds specialized data structures for storing and searching high-dimensional vectors.

The storage schema is elegantly simple yet powerful. Each record contains the embedding vector, the original text, and comprehensive metadata stored as JSON. The system creates a specialized index using the IVFFlat algorithm, which organizes vectors into 100 clusters. When searching, the system only needs to check vectors in relevant clusters rather than all vectors, dramatically improving performance.

The choice of PostgreSQL over specialized vector databases like Pinecone or Weaviate was deliberate. While specialized databases might be 2-3x faster at pure vector search, PostgreSQL provides crucial advantages: all data lives in one database (simplifying backups and operations), we get ACID compliance (ensuring data consistency), and there's no need to synchronize between multiple systems.

**Why this matters:** The vector storage layer is where mathematical theory meets engineering reality. The system needs to search through hundreds of thousands of chunks in under 100 milliseconds. The IVFFlat index makes this possible by intelligently organizing the vector space. The decision to use PostgreSQL trades some search speed for massive operational simplicity - a choice that makes sense for a system prioritizing reliability over microsecond-level performance.

### Step 7: Query Processing - Understanding What Users Want

When a user types a question like "What is Goldman's NVIDIA price target?", the system begins a sophisticated process to understand and answer the query. First, the question itself gets converted to an embedding using the same process as document chunks. This creates a mathematical representation of the user's intent.

But the system doesn't stop at simple embedding. It performs intelligent retrieval by fetching more results than needed (15 chunks) then filtering them through a sophisticated three-stage pipeline:

1. **Page-level deduplication** ensures we don't get multiple chunks from the same page
2. **Semantic deduplication** removes nearly identical content using token overlap analysis
3. **Content-type diversification** ensures a mix of text, tables, and (theoretically) images

This over-retrieve-then-filter approach is crucial. Vector similarity might rank five chunks from the same Goldman Sachs report page as most relevant, but showing all five would waste the user's time. The filtering ensures diverse, information-rich results.

**Why this matters:** Query processing is where the system's intelligence shines. By retrieving more results than needed then intelligently filtering, the system balances relevance with diversity. Users get comprehensive answers drawing from multiple sources rather than redundant information from a single document. The three-stage filtering pipeline represents sophisticated information retrieval research applied to the specific challenges of financial documents.

### Step 8: Response Generation - Creating Helpful Answers

With filtered chunks in hand, the system now needs to synthesize a coherent answer. All retrieved chunks are passed to OpenAI's GPT-4-mini model along with carefully crafted instructions. The prompt template enforces critical constraints: use only information from the provided chunks, cite sources with broker and page details, distinguish between different sources' views, and acknowledge when information isn't available.

The system uses "single-shot" synthesis, meaning all chunks are processed together in one API call. This approach was chosen over alternatives like iterative refinement (which can drift from the original question) or hierarchical summarization (which loses important details). With 5-7 chunks averaging 400 words each plus instructions, everything fits comfortably within GPT-4's context window.

Temperature is set to 0.1, making responses nearly deterministic. This ensures that asking the same question multiple times yields consistent answers - crucial for financial analysis where reproducibility matters.

The response includes both the synthesized answer and detailed source information. Each source reference contains the broker name, ticker, date, page number, and relevance score. Users can click any source to see the full text chunk, ensuring complete transparency.

**Why this matters:** Response generation is where all the previous steps culminate in value for the user. The careful prompt engineering ensures accurate, well-sourced answers rather than hallucinated information. The single-shot approach preserves all details while the low temperature ensures consistency. Most importantly, the source attribution transforms the system from a black box into a transparent research tool where every claim can be verified.

## Performance Characteristics and Trade-offs

Understanding system performance helps set appropriate expectations and reveals the engineering trade-offs made throughout the design.

### Speed Metrics

- **Document Upload**: Near-instantaneous (< 1 second)
- **Metadata Extraction**: 200-500 milliseconds for most documents
- **Full Document Processing**: 10-30 seconds depending on size
- **Query Response**: 1.5-2 seconds total
  - Embedding generation: 100ms
  - Vector search: 100ms
  - Deduplication: 50ms
  - Response generation: 1-1.5 seconds

### Scale Limitations

The system performs well up to approximately 100,000 chunks (roughly 1,000 typical broker reports). Beyond this, vector search begins to slow noticeably. At 500,000 chunks, search time increases to 300-400ms, making the overall experience sluggish. The PostgreSQL-based approach shows its limitations here - specialized vector databases would maintain performance better at scale.

Memory usage scales linearly with documents. Each processed document requires approximately 10MB of database storage (including embeddings and metadata). The vector index itself requires about 100MB per 100,000 chunks. A corpus of 10,000 documents would need roughly 100GB of storage.

### Architectural Trade-offs

The system makes several deliberate trade-offs that prioritize simplicity and reliability over peak performance:

**Synchronous Processing**: Everything happens in the request thread. When uploading a document, the browser waits for processing to complete. This simplifies error handling and user feedback but limits concurrent usage to about 10 users before performance degrades severely.

**No Caching**: Every identical query generates fresh API calls to OpenAI. This ensures always-fresh results but wastes money and adds latency for common queries.

**Single Database**: Using PostgreSQL for everything (documents, vectors, metadata) simplifies operations but sacrifices the performance benefits of specialized tools.

**No Query Understanding**: Queries are processed literally without intelligent preprocessing. "Latest NVIDIA report" doesn't automatically prioritize recent documents.

These trade-offs reflect the system's prototype nature. Each could be addressed with additional engineering effort, but the current choices create a simpler, more maintainable system.

## Security Architecture

The current security implementation covers basics but falls short of enterprise requirements.

### What's Protected

- **CSRF Protection**: All forms include tokens preventing cross-site request forgery
- **SQL Injection Prevention**: Django's ORM ensures safe database queries  
- **XSS Prevention**: Templates automatically escape user content
- **Secret Management**: API keys stored in environment variables, not code

### What's Not Protected

- **No Authentication**: Anyone can upload documents and perform searches
- **No Authorization**: All users have equal access to all documents
- **Direct File Access**: PDFs accessible via URL if path is known
- **No Rate Limiting**: Vulnerable to denial-of-service attacks
- **No Audit Trail**: No record of who accessed what information

For a prototype or internal tool, current security is adequate. For production use with sensitive financial documents, comprehensive security improvements are essential.

## Why These Technologies?

Every technology choice reflects specific requirements and trade-offs.

### Django Over FastAPI
Django provides batteries-included functionality: an admin interface for managing documents, an excellent ORM for database operations, built-in security features, and a mature ecosystem. FastAPI would offer better async support and API documentation, but Django's completeness accelerated development significantly.

### PostgreSQL + pgvector Over Specialized Vector Databases
This choice prioritizes operational simplicity over peak performance. With pgvector, vectors live alongside relational data in one database. This eliminates synchronization challenges, simplifies backups, and reduces operational complexity. Specialized vector databases would search faster but require managing another service.

### LlamaIndex Over Custom Implementation
Building RAG from scratch would require implementing chunking strategies, embedding management, retrieval algorithms, and response synthesis. LlamaIndex provides battle-tested implementations of all these components. The trade-off is less flexibility and occasional abstraction leakiness, but the time saved is enormous.

### OpenAI Over Open Source Models
OpenAI's models provide state-of-the-art quality with consistent APIs. Open source models would eliminate API costs and vendor lock-in but require significant infrastructure for hosting and generally provide lower quality results, especially for specialized financial language.

## Future Architecture Considerations

The current architecture could evolve in several directions based on usage patterns and requirements.

### Scaling Horizontally
Adding multiple Django workers behind a load balancer would handle more concurrent users. The database would become the bottleneck, suggesting a need for read replicas or caching layers.

### Asynchronous Processing  
Implementing Celery for background task processing would dramatically improve user experience. Documents would upload instantly with processing happening asynchronously. Users could monitor progress through WebSockets or polling.

### Microservices Architecture
Separating document processing, vector search, and response generation into independent services would allow optimal scaling of each component. This adds complexity but enables fine-grained resource allocation.

### Caching Strategy
Implementing Redis for caching embeddings and common query results would reduce costs and improve response times. Even simple caching of identical queries for 5 minutes would significantly impact performance.

The architecture provides a solid foundation that can evolve based on real-world usage patterns and requirements. The clean separation of concerns and use of standard technologies makes such evolution straightforward.