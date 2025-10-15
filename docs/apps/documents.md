# Document Management

## The Business Problem We're Solving

Investment professionals receive dozens of research PDFs every day, reports from Goldman Sachs, Morgan Stanley, Barclays, and other major banks analyzing companies and markets.

Our documents application ingests PDFs, extracts crucial metadata (who wrote it, when, about which company), and prepares the content for search. 

## PDF Processing

### Step 1: The Upload Experience

**Duplicate prevention** - We calculate a unique fingerprint (SHA256 hash) to detect if this exact document already exists

The duplicate detection deserves special attention. Imagine five analysts all uploading the same Goldman Sachs report. Without our fingerprinting system, we'd waste time and money processing the same document five times. With it, we instantly recognize duplicates and skip redundant processing.

**The user experience challenge:**
Upload and processing takes 10-30 seconds - an eternity in web time. We show progress indicators and status messages ("Extracting metadata...", "Processing content...") to reassure users the system is working. While these progress bars are currently "fake" (they animate on a timer rather than showing real progress), they significantly reduce user anxiety and support requests.

### Step 2: Automatic Metadata Extraction

One of our system's most sophisticated features is automatic metadata extraction. When someone uploads "GS_NVDA_20240115.pdf", we automatically understand this is a Goldman Sachs report about NVIDIA from January 15, 2024. But the real magic happens with poorly named files.

**Our three-stage extraction approach:**

**Stage 1: Filename Parsing**
We maintain a library of 30+ regex patterns covering common naming conventions across Wall Street. Examples:
- "20240115 - Goldman Sachs - NVDA - Q4 Analysis.pdf"
- "MS_AAPL_Bull_Case_March_2024.pdf"
- "Barclays-TSLA-Downgrade-20240301.pdf"

This stage succeeds for about 70% of documents and takes milliseconds.

**Stage 2: First Page Analysis**
When filenames fail us, we read the first page. Investment research follows predictable patterns - broker names appear in headers, dates in footers, and ticker symbols prominently displayed. We scan for phrases like:
- "Goldman Sachs Research"
- Company names and ticker symbols
- Date patterns in multiple formats

This catches another ~25% of documents.

**Stage 3: Deep Document Scan**
For the remaining 5% with non-standard formats, we extract and analyze the entire document's text. While expensive in processing time, this ensures even the most unusually formatted documents get properly categorized.

**The Broker Name Challenge:**
Wall Street firms use many name variations. We maintain such mappings as:
- "GS" → "Goldman Sachs"
- "CS" → "Credit Suisse"

This normalization ensures that searching for "Goldman Sachs NVIDIA research" finds documents regardless of whether they use "GS", "Goldman", or "Goldman Sachs & Co."

### Step 3: Content Processing

Once we understand what document we're dealing with, we extract its content for search. This involves three distinct extraction processes:

**Text Extraction:**
Using specialized PDF libraries, we extract text while preserving structure. We maintain:
- Paragraph boundaries (crucial for context)
- Page numbers (for source attribution)
- Headers and sections (for organization)
- Reading order in multi-column layouts

**Table Extraction:**
Financial documents are filled with data tables - revenue projections, peer comparisons, historical metrics. We use specialized table detection to:
- Identify table boundaries
- Extract data while preserving structure
- Convert to searchable markdown format
- Generate AI summaries of table contents

**Image Extraction:**
Charts, graphs, and diagrams. We extract these as separate files, maintaining links to their source pages. Unfortunately, our image description system is currently broken, making this visual content unsearchable.

### Step 4: Quality Verification and Storage

After extraction, we perform quality checks and store results:

**Statistics Tracking:**
We count and store:
- Total text chunks extracted
- Number of tables found
- Count of images extracted

These statistics help users verify processing succeeded and understand document composition. A report showing "0 tables" when it should have financial data indicates a processing problem.

**Storage Architecture:**
- Original PDFs: Stored in the file system with unique names
- Metadata: Stored in PostgreSQL for fast querying
- Processing flags: Track which documents are fully processed
- Extraction results: Linked to enable reprocessing if needed

## Architecture Decisions and Their Implications


### Why Synchronous Processing

Currently, when you upload a document, your browser waits for the entire processing to complete. This creates several severe problems:

**User Experience Issues:**
- Browser may timeout on large documents
- No ability to upload multiple documents efficiently
- Feels slow and unresponsive

**Scalability Limitations:**
- Web server threads blocked during processing
- 10 concurrent uploads would liekly overwhelm the system
- No ability to distribute processing load
- Single point of failure

**The Correct Architecture:**
Documents should be queued for background processing using tools like Celery. Users would see immediate confirmation of upload, then receive notifications when processing completes. This would enable:
- Batch uploads of dozens of documents
- Progress tracking for each document
- Resilience to failures (automatic retry)
- Horizontal scaling across multiple workers

We chose synchronous processing for prototype simplicity, but it's the #1 architectural debt limiting production use.

### Why We Store Metadata as Separate Fields

We debated between:
1. **JSON blob** - Store all metadata in one field `{"broker": "GS", "ticker": "NVDA"}`
2. **Separate columns** - Individual database fields for each metadata type

We chose separate columns because:
- Enables efficient database indexing
- Allows partial metadata (some fields can be null)
- Supports complex queries ("all Goldman reports from Q1")
- Database can enforce data types and constraints

The tradeoff is more complex schema management, but the query performance benefits are substantial.

## User Interface Decisions

### Progressive Disclosure for Metadata Override

The upload interface hides metadata fields by default, showing them only when users click "Override extracted metadata". Why?

**The 90/10 Rule:**
- 90% of the time, our extraction works perfectly
- Showing all fields would overwhelm users with unnecessary choices
- Users who need overrides can access them with one click

This design principle - hide complexity, reveal on demand - makes the system approachable for casual users while maintaining power user features.


### Toast Notifications for Processing Stages

We show toast notifications for each processing stage:
1. "Uploading PDF..."
2. "Extracting metadata..."
3. "Processing document content..."
4. "Creating searchable index..."


## Strengths of Our Approach

### 1. Duplicate Detection
The SHA256 hashing completely eliminates duplicate processing. In testing with users repeatedly uploading the same documents, we saved thousands of dollars in processing costs.

### 2. Flexible Metadata Extraction
Our three-stage approach handles the chaos of real-world document naming. From pristine "20240115_GS_NVDA_Initiation.pdf" to horrible "Report(1)(2)_FINAL_v2.pdf", we extract metadata successfully 95% of the time.

### 3. Graceful Degradation
When metadata extraction fails, documents still upload successfully with empty metadata. Users can manually add metadata later. This prevents extraction failures from blocking the critical path.

### 4. Comprehensive Processing Statistics
Storing chunk counts, table counts, and image counts provides valuable quality assurance. Users can spot processing problems ("Why does this 40-page report only have 5 chunks?") and verify completeness.

## Critical Limitations

### 1. Synchronous Processing Blocks Everything
This is our most severe architectural flaw. The synchronous design limits us to roughly 10 concurrent users before the system becomes unusable. Production systems need asynchronous job queues.

### 2. No Batch Upload Capability
Users must upload documents one at a time. Investment teams often receive 20-30 documents after earnings season. Our system turns a 2-minute drag-and-drop into a 30-minute clicking marathon.

### 3. Local File Storage Won't Scale
Storing PDFs on the web server's local disk means:
- Can't scale horizontally (files trapped on single server)
- Backup complexity
- Disaster recovery challenges

Production systems need cloud object storage (S3, Azure Blob, etc.).

### 4. No Version Control
When Morgan Stanley updates their NVIDIA report, we treat it as a completely new document. There's no connection between versions, no tracking of changes, and no way to see how analysis evolved.

### 5. Missing User Permissions
Currently, all users see all documents. For a prototype, this is fine. For production use with sensitive financial documents, we need:
- User authentication
- Document-level permissions
- Access audit trails
- Compliance controls

## Performance Characteristics and Limits

**Current Performance Metrics:**
- SHA256 calculation: ~50MB/second (fast enough)
- Metadata extraction: 200-500ms typical, 3s worst case
- Full processing: 10-30 seconds depending on document size
- Database overhead: ~10ms per operation (negligible)

**Scalability Limits:**
- Works well up to 10,000 documents
- Query performance degrades slightly at 50,000 documents
- Synchronous processing limits to ~10 concurrent users
- Local storage practical up to ~100GB of PDFs



