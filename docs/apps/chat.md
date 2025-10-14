# Chat Application - How Natural Language Search Works


## The Fundamental Challenge We're Solving

Financial analysts and investors face an information overload problem. A single company might have dozens of research reports from different investment banks, each 20-50 pages long. Finding specific information requires hours of manual searching, and you might miss crucial insights buried on page 37 of a Morgan Stanley report. 

Our chat system solves this by understanding your questions in natural language and finding the most relevant information across all documents. But here's the crucial part: unlike ChatGPT or other AI systems that might hallucinate plausible-sounding answers, our system ONLY provides information that actually exists in your documents, with precise citations.

## Why We Built on LlamaIndex - A Strategic Technology Choice

When building this system, we selected LlamaIndex, a specialized framework designed specifically for connecting large language models with private documents.

Think of LlamaIndex as a librarian who not only knows where every piece of information is stored but also understands the relationships between different pieces of information. When you ask a question, LlamaIndex orchestrates a complex dance of searching, filtering, and synthesizing to deliver precise answers.


## The Critical Decision: How to Slice Documents for Search

One of our most important architectural decisions involves how we break documents into searchable pieces.

We break each document into pieces of exactly 512 tokens (roughly 380 words or 2-3 paragraphs). This size emerged from brief experimentation:

**What we learned from testing different sizes:**

1. **Very small chunks (128 tokens)** - Like cutting a newspaper article mid-sentence. A chunk might end with "The company's revenue increased by" and the next chunk starts with "45% year-over-year." This makes it impossible to understand the complete thought.

2. **Small chunks (256 tokens)** - Better, but still problematic. You might get a conclusion without its supporting evidence, or data without context explaining what it means.

3. **Large chunks (1024+ tokens)** - Like photocopying entire newspaper pages when you only need one article. When searching for "gross margin," you'd get back entire pages discussing dozens of financial metrics, making it hard to find the specific information you need.

4. **Our sweet spot (512 tokens)** - Typically captures 2-3 complete paragraphs. This ensures that when you search for a concept, you get enough context to understand it fully without drowning in irrelevant information.

**Innovation: 50-token overlap**

We don't just slice documents without any overlap. Instead, each chunk overlaps with its neighbors by 50 tokens (about 2-3 sentences). This overlap ensures that if an important concept spans the boundary between chunks, it will be fully captured in at least one chunk.

## The Three-Stage Deduplication System - Ensuring Diverse, Non-Reduandant Results

Documents often repeat the same information in multiple places. Without intelligent filtering, searching for "NVIDIA price target" might return five chunks all saying "$950" from the same Goldman Sachs report, crowding out different perspectives from Morgan Stanley or Barclays.

Our three-stage deduplication pipeline solves this elegantly:

**Stage 1: Page-Level Deduplication**
We ensure maximum one chunk per page makes it into the final results. Even if a single page contains three paragraphs about NVIDIA's price target, we only show the most relevant one. This prevents dense pages from dominating search results.

**Stage 2: Semantic Deduplication**  
We identify chunks that say essentially the same thing, even with different wording. Using token analysis, we detect when two chunks share more than 80% of their content. For example, if the executive summary says "We initiate coverage with a $950 price target" and page 15 says "Our $950 price target reflects...", we recognize these as duplicates and keep only the most relevant one.

**Stage 3: Content Type Diversification**
Financial insights come from multiple sources - narrative text explains reasoning, tables show the numbers, and charts visualize trends. Our system ensures a mix of these different content types in results. Instead of showing five text chunks, you might see two text explanations, two data tables, and a chart description.

**Real-world impact:**
Without deduplication, a search for "NVIDIA price target" might show:
- Chunk 1: "Our $950 price target..." (page 1)
- Chunk 2: "The $950 target reflects..." (page 2)  
- Chunk 3: "We reiterate our $950..." (page 15)
- Chunk 4: "At $950, NVIDIA would..." (page 18)
- Chunk 5: "Our $950 PT implies..." (page 22)

With deduplication, the same search shows:
- Goldman Sachs: $950 target with reasoning (page 1)
- Morgan Stanley: $875 target with different thesis (page 3)
- Barclays: $920 target with concerns (page 5)
- Historical price target table showing progression
- Chart comparing broker targets

Instead of repetition, users ideally get comprehensive, diverse perspectives.


**Critical configuration decisions:**

1. **Temperature = 0.1** - This makes responses nearly deterministic. Ask the same question twice, get the same answer. This consistency is crucial for financial analysis where reproducibility matters.

2. **Single-shot synthesis** - We give the model ALL relevant chunks at once rather than iteratively refining. This prevents the model from drifting away from source material.

3. **Strict citation requirements** - Our prompt engineering forces the model to cite sources for every claim, this is likely the most ripe area for optimization as queries can be considerably optimized.

## The "Retrieve More, Show Less" Strategy - Why Over-Retrieval Improves Quality

A counterintuitive finding: retrieving exactly what you need often gives worse results than retrieving too much and filtering. Here's why.

**Our approach in simple terms:**
1. Retrieve 15 potentially relevant chunks from the database
2. Apply our three-stage deduplication filter
3. Present the best 5-7 chunks to the AI for answer generation

**Why not just retrieve 5 chunks?**

Imagine searching a library for books about NVIDIA. If you only pull the 5 books closest to the "NVIDIA" section, they might all be from the same publisher. But if you pull 15 books and then select the 5 most diverse and informative ones, you get multiple perspectives.

The same principle applies here. Vector similarity (the mathematical measure of relevance) often ranks multiple chunks from the same document highest. By retrieving 15 and filtering to 5-7, we ensure diversity of sources and perspectives.

The computational cost is higher (processing 15 chunks instead of 5) but the answer quality improves. Users ideally get comprehensive, multi-perspective answers instead of single-source echoes.

## Why We Include Full Source Text - Building Trust Through Transparency

Most AI systems give you an answer and expect you to trust it, we every answer comes with the complete source text that was used to generate it.


## Understanding Our Critical Failures - What's Broken and Why

### Image Processing Not Yet Implemented

The most severe limitation of our system is that roughly 30% of valuable content - all charts, graphs, and visual elements is completely invisible to search. While we successfully extract images from PDFs, we cannot generate searchable descriptions at this time.  This is planned functionality


**Current limitations:**
1. **No time awareness** - Searching for "latest NVIDIA report" doesn't prioritize recent documents
2. **No synonym understanding** - "GS" doesn't match "Goldman Sachs"
3. **No intent detection** - Can't distinguish "compare broker views" from "find specific data"

**Impact on users:**
Users must craft perfect queries. Instead of asking naturally "What's the latest on NVIDIA?", they must specify "NVIDIA analysis from January 2024" to get recent results.

### The Missing Caching Layer

Every identical query generates fresh API calls to OpenAI, even if the same question was asked seconds ago. This architectural oversight has significant implications:

**Performance impact:**
- Repeated queries take 1-2 seconds instead of instant
- Users waiting for answers they've asked before

### Poor Formatting of Results

While our system successfully retrieves tables and structured data, they display as plain text blocks, losing their visual structure. Financial tables showing quarterly results or peer comparisons become walls of numbers that are difficult to parse.

**Note: This is partly due to weak table and text formatting capabilities in the artifact display system.**

**Solutions:**
- Implement table rendering components (react-table, ag-grid)
- Use markdown-to-HTML converters with proper styling
- Add proper character escaping and encoding
- Provide raw markdown view as interim solution

## What We Got Right - Strengths Worth Preserving

### 1. Source Attribution
Every single piece of information can be traced to its exact source document and page.

### 2. Strategic Deduplication
Our three-stage pipeline transforms repetitive search results into diverse, comprehensive answers. This system represents innovation in RAG architectures.

### 3. Reliable Vector Search
Using PostgreSQL with pgvector provides consistent, reliable search without the complexity of managing separate vector databases. Simple sometimes beats sophisticated.

### 4. Hallucination Prevention
Our prompt engineering ensures the AI only uses information from provided documents. Users never get plausible-sounding but false information, a critical requirement for financial applications.

### 5. Flexible Metadata Filtering
Users can limit searches to specific brokers, time periods, or companies.