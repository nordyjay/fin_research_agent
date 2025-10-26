# System Architecture - How Everything Works Together


## The Complete Journey: From PDF to Answer

### Step 1: Document Upload - Getting PDFs Into the System

When someone clicks "Upload" and selects a broker research PDF, the system first calculates a unique hash of the entire document. This prevents the same document from being processed twice, saving significant time and computational resources.


### Step 2: Metadata Extraction

The system attempts to understand what document it's processing. This happens through a three-stage approach that balances accuracy with processing speed.

**Stage 1 - Filename Analysis:** The system first examines the filename using pattern matching. It knows that financial firms often follow naming conventions like "20240115 - Goldman Sachs - NVDA - Q4 Analysis.pdf" or "GS_NVDA_2024Q4.pdf". The system maintains a library of over 30 patterns that cover common naming schemes across major brokers. This stage takes mere milliseconds and successfully extracts metadata for about 70% of documents.

**Stage 2 - First Page Scanning:** If the filename doesn't yield clear results, the system reads just the first page of the PDF. Investment research reports typically display the broker name, date, and ticker symbols prominently on the cover page. The system looks for phrases like "Goldman Sachs Research," ticker symbols in headers, and date formats.

**Stage 3 - Deep Document Analysis:** The system performs a complete text extraction and searches the entire document. While this takes 2-3 seconds, it ensures even poorly named or unusually formatted documents get properly categorized.

The system also maintains a comprehensive mapping of broker name variations. It knows that "GS," "Goldman," and "Goldman Sachs & Co." all refer to the same institution. This normalization ensures that searches for "Goldman Sachs NVIDIA research" will find documents regardless of how the broker name appears.

**Why this matters:** Accurate metadata extraction is crucial for search quality. If a Morgan Stanley report about Apple gets mislabeled as a Goldman Sachs report about Microsoft, users won't find it when searching. The three-stage approach balances speed (most documents process quickly) with completeness (even unusual documents get handled correctly).

### Step 3: Document Content Extraction

Our system understands that financial documents contain three distinct types of valuable content, each requiring specialized handling.

**Text Extraction:** Using the PyMuPDF library, the system extracts text page by page. The system preserves formatting cues like headers, paragraphs, and bullet points. It identifies section breaks and maintains reading order even in complex multi-column layouts. Each page's text is tagged with its page number, enabling the precise source attribution that makes this system valuable for financial analysis.

**Table Processing:** Financial documents are filled with data tables, revenue projections, comparative analyses, historical trends. The system uses pdfplumber (specifically chosen for its strong table detection) to identify and extract these tables. Tables are converted to a markdown format that preserves their structure. The system also generates an AI-powered summary of each table. So a complex 20-row financial projection table gets both preserved in full detail AND summarized as "Q1-Q4 2024 revenue projections showing 15% YoY growth with improving margins." This dual approach enables both precise data retrieval and conceptual searching.

**Note:** While tables are correctly extracted and stored with proper formatting, the current display system fails to preserve this structure. Tables appear as continuous text strings rather than structured data. This frontend display issue significantly impacts usability.

**Image Extraction:** The system identifies and extracts all images, charts, and graphs from PDFs. These are saved as separate image files with systematic naming that links them back to their source document and page. Unfortunately, this is where we hit a limitation, while images are successfully extracted, the system does not yet generate searchable descriptions at this point. This means roughly 30% of valuable content (all those charts showing trends, market share diagrams, and visual comparisons) remains invisible to search queries.


### Step 4: Chunking - Breaking Documents Into Searchable Pieces

The system can't search through entire 50-page documents efficiently, so it breaks them into smaller, overlapping pieces called "chunks." Each chunk contains 512 tokens (roughly 380 words or 2-3 paragraphs). This size was chosen after testing revealed that smaller chunks (128-256 tokens) would split important concepts across boundaries. 

The main innovation identified is the 50-token overlap between consecutive chunks. This overlap (roughly 2-3 sentences) ensures that concepts spanning chunk boundaries remain searchable. If chunk 1 ends with "This growth is primarily due to three factors:" and chunk 2 starts with those factors, the overlap ensures both chunks contain the complete thought.

Each chunk is tagged with rich metadata: the source document, broker, ticker, date, page number, and position within the page. This metadata enables the filtering and attribution that makes the system valuable.

**Why this matters:** Chunking strategy directly impacts search quality. Too small and you lose context. Too large and you lose precision. The 512-token size with 50-token overlap represents limited experimentation to find the balance for financial documents. The rich metadata ensures that every chunk can be traced back to its exact source, enabling the trust in financial analysis.  This is a area ripe for research and optimization.

### Step 5: Embedding Generation

This step transforms human-readable text into mathematical representations that computers can search efficiently. Using OpenAI's text-embedding-3-small model, each chunk gets converted into a list of 1,536 numbers. These numbers encode the semantic meaning of the text in a way that mathematically similar vectors represent conceptually similar text.

Example: "revenue growth" might become [0.23, -0.45, 0.67, ...] while "sales increase" becomes [0.24, -0.43, 0.66, ...]. Notice how similar concepts have similar numbers. This enables the system to understand that a search for "revenue growth" should also find documents mentioning "sales expansion" or "top-line improvement."


**Why this matters:** Embeddings are the core that enables semantic search. Without them, searching for "bullish outlook" wouldn't find "positive view" or "optimistic forecast." The high dimensionality aims to ensure that subtle differences in financial language are preserved - "revenue growth" vs "revenue growth concerns" have very different embeddings despite similar words.

### Step 6: Vector Storage

The embeddings and their associated chunks need to be stored in a way that enables fast searching across potentially millions of chunks. The system uses PostgreSQL with the pgvector extension, which adds specialized data structures for storing and searching high-dimensional vectors.

The storage schema is as follows. Each record contains the embedding vector, the original text, and metadata stored as JSON. The system creates a specialized index using the IVFFlat algorithm, which organizes vectors into 100 clusters. When searching, the system only needs to check vectors in relevant clusters rather than all vectors, improving performance.

The choice of PostgreSQL over specialized vector databases like Pinecone or Weaviate was deliberate. While specialized databases might be 2-3x faster at pure vector search, PostgreSQL provides advantages: all data lives in one database (simplifying backups and operations), and there's no need to synchronize between multiple systems.


### Step 7: Query Processing

When a user types a question like "What is Goldman's NVIDIA price target?", the system begins a process to understand and answer the query. First, the question itself gets converted to an embedding using the same process as document chunks. 

It performs retrieval by fetching more results than needed (15 chunks) then filtering them through a three-stage deduplication pipeline:

1. **Page-level deduplication** ensures we don't get multiple chunks from the same page
2. **Semantic deduplication** removes nearly identical content using token overlap analysis
3. **Content-type diversification** ensures a mix of text, tables, and (theoretically) images

Vector similarity might rank five chunks from the same Goldman Sachs report page as most relevant, but showing all five would waste the user's time. The filtering ensures diverse, information-rich results.

### Step 8: Response Generation

With filtered chunks in hand, the system now needs to synthesize a coherent answer. All retrieved chunks are passed to OpenAI's GPT-4-mini model along with prompting. The prompt template enforces critical constraints: use only information from the provided chunks, cite sources with broker and page details, distinguish between different sources' views, and acknowledge when information isn't available.

Temperature is set to 0.1, making responses nearly deterministic. This ensures that asking the same question multiple times yields consistent answers, pertinant for financial analysis where reproducibility matters.

The response includes both the synthesized answer and detailed source information. Each source reference contains the broker name, ticker, date, page number, and relevance score. Users can click any source to see the full text chunk, ensuring complete transparency.


## Performance Characteristics and Trade-offs

Understanding system performance helps set appropriate expectations and reveals the engineering trade-offs made throughout the design.

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
