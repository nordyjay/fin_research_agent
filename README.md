# Financial Research Agent

A system that transforms broker research PDFs into an intelligent Q&A interface, allowing users to search across hundreds of financial documents using natural language questions.

## What This System Does

Imagine having hundreds of broker research reports (Goldman Sachs, Morgan Stanley, Barclays, etc.) about companies like NVIDIA, Apple, or Microsoft. These PDFs contain valuable insights but finding specific information requires manually searching through each document. This system solves that problem.

**Core Functionality:**
1. **Uploads broker research PDFs** - The system ingests financial research documents from major investment banks
2. **Extracts all content** - Text, tables, and images are pulled from PDFs and made searchable
3. **Enables natural language search** - Ask "What is Goldman's price target for NVIDIA?" and get precise answers
4. **Provides source attribution** - Every answer links back to the exact page in the original PDF

## How to Use This System

### Quick Start (For Developers)

```bash
# Prerequisites: Docker installed on your machine

# 1. Copy environment template and add your OpenAI API key
cp .env.example .env
# Edit .env file and add: OPENAI_API_KEY=your-key-here

# 2. Start the system
docker-compose up --build

# 3. Access the web interface
# Open browser to: http://localhost:8000/chat/
```

The system automatically loads 4 sample PDFs on first start. Processing takes about 2-3 minutes.

### What Happens Behind the Scenes

When you start the system:
1. **Database Creation** - Sets up PostgreSQL with special vector search capabilities
2. **PDF Processing** - Reads the 4 sample PDFs and extracts their content
3. **Embedding Generation** - Converts text into mathematical representations for search
4. **Web Interface** - Starts a ChatGPT-style interface for asking questions

## Documentation Guide - What Each Document Covers

### System Architecture (`docs/architecture.md`)
**What it explains:** The complete technical flow from uploading a PDF to getting an answer
**Why read this:** Understand how all the pieces work together - database, web server, AI models
**Key insights:** 
- Detailed walkthrough of what happens when you upload a document
- How user questions get transformed into search queries
- Why we chose PostgreSQL over specialized vector databases
- Performance characteristics and limits

### Chat Application (`docs/apps/chat.md`)
**What it explains:** The question-answering system and how it finds relevant information
**Why read this:** Learn how the system understands questions and generates accurate answers
**Key insights:**
- Why answers are accurate and always cite sources
- How the system avoids showing duplicate information
- The three-stage filtering process that ensures diverse results
- Why image search is completely broken (and how to fix it)

### Documents Application (`docs/apps/documents.md`)
**What it explains:** How PDFs are uploaded, processed, and stored
**Why read this:** Understand the document ingestion pipeline and metadata extraction
**Key insights:**
- How the system prevents uploading the same document twice
- Why processing takes 10-30 seconds per document
- How broker names and dates are automatically extracted
- The trade-offs in our synchronous processing approach

### RAG Implementation (`docs/rag_implementation.md`)
**What it explains:** The search technology that powers question answering
**Why read this:** Deep dive into how semantic search works without getting too technical
**Key insights:**
- Why the system understands "revenue growth" vs "revenue growth concerns"
- How 512-token chunks balance accuracy and performance
- The sophisticated deduplication that prevents repetitive answers
- Why we retrieve 15 results but only show 5-7

### Strengths & Weaknesses (`docs/strengths_weaknesses.md`)
**What it explains:** Honest assessment of what works well and what's broken
**Why read this:** Understand limitations before using in production
**Key insights:**
- Image processing is completely broken (30% of content unsearchable)
- No caching means unnecessary costs for repeated questions
- Synchronous architecture limits to ~10 concurrent users
- Table and text formatting in results needs improvement

## Key Features Explained

### 1. Multimodal Document Processing
The system doesn't just extract text - it understands documents have three types of content:
- **Text**: The narrative sections explaining analysis
- **Tables**: Financial data, projections, and comparisons
- **Images**: Charts and graphs (currently broken - these are extracted but not searchable)

### 2. Intelligent Deduplication
When searching, the same information often appears multiple times (executive summary, detailed analysis, conclusion). The system intelligently filters to show diverse perspectives rather than repetitive content.

### 3. Source Attribution
Every piece of information in an answer can be clicked to see the original source. This is critical for financial analysis where verification matters. Users see not just "Goldman says $950" but can click through to see the exact context.

### 4. Automatic Metadata Extraction
Drop in a PDF named "20240115 - Goldman Sachs - NVDA - Initiating Coverage.pdf" and the system automatically understands:
- Broker: Goldman Sachs
- Company: NVIDIA (NVDA)
- Date: January 15, 2024

## Current Limitations

### Critical Issues
1. **Image Processing Broken** - Charts and graphs are extracted but not searchable due to an API error
2. **No User Authentication** - Anyone can access all documents (not suitable for confidential data)
3. **Synchronous Processing** - Uploading documents blocks other operations
4. **No Caching** - Asking the same question twice costs money each time

### Quality Issues
1. **Table Formatting** - Tables in search results show as basic text, losing visual structure
2. **Text Formatting** - Multi-paragraph responses lose formatting, appearing as walls of text
3. **No Progress Tracking** - The progress bar during upload is fake
4. **Limited Scale** - System slows significantly beyond 100,000 text chunks

## Technology Stack

The system uses modern, production-ready technologies:

- **Django**: Web framework handling uploads, API endpoints, and user interface
- **PostgreSQL + pgvector**: Database storing documents and enabling vector search
- **OpenAI APIs**: Powers text understanding, embeddings, and response generation
- **LlamaIndex**: Orchestrates document processing and retrieval
- **Docker**: Ensures consistent deployment across environments

## Why These Design Choices Matter

### Why PostgreSQL Instead of Specialized Vector Databases?
Specialized vector databases like Pinecone are faster but require managing another service. PostgreSQL with pgvector is slower but keeps everything in one database - simpler operations, easier backups, lower complexity.

### Why 512 Token Chunks?
Financial documents discuss complex topics. Too small (128 tokens) and you split concepts mid-thought. Too large (2048 tokens) and search becomes imprecise. 512 tokens typically captures 2-3 complete paragraphs - the sweet spot for financial analysis.

### Why Three-Stage Deduplication?
Without deduplication, searching "NVIDIA price target" might return 5 chunks all saying "$950" from the same report. Our pipeline ensures diverse sources: different pages, different semantic content, different content types (text vs tables).

## For Product Managers and Business Users

This system transforms static PDF libraries into dynamic knowledge bases. Instead of manually searching through documents, users can ask natural questions and get sourced answers in seconds.

**Business Value:**
- Reduces research time from hours to seconds
- Ensures no insights are missed across large document sets
- Provides audit trail with source attribution
- Scales to thousands of documents

**Ready for Production?** Not quite. The system needs 2-4 weeks of engineering to fix critical issues (broken images, add authentication, implement caching) before enterprise deployment.

## Next Steps

1. **For Developers**: Run the system locally and explore the codebase
2. **For Technical Managers**: Review architecture and strengths/weaknesses documents
3. **For Product Teams**: Try the interface and document additional requirements
4. **For Everyone**: Understand this is a prototype demonstrating feasibility, not a production system

The foundation is solid. With focused development on the identified weaknesses, this can become a powerful tool for financial research teams.