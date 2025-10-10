# Financial Research Agent

A multimodal RAG (Retrieval-Augmented Generation) system for analyzing broker research PDFs using Django, pgvector, and OpenAI APIs.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- OpenAI API key
- 8GB+ RAM recommended

### Setup

1. **Clone and configure**
   ```bash
   git clone <repository>
   cd fin_research_agent
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

2. **Build and run**
   ```bash
   docker-compose up --build
   ```

3. **Access the application**
   - Chat Interface: http://localhost:8000/chat/
   - Admin Panel: http://localhost:8000/admin/ (admin/admin123)

### Automatic Document Seeding

The system can automatically process PDFs from the `seed_data/` directory on startup:

```bash
# Basic upload only (fast)
docker-compose up

# Upload + process with embeddings (slower but complete)
docker-compose exec web python manage.py seed_documents --process
```

## High-Level Architecture

### System Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│                 │     │                  │     │                 │
│   Web Client    │────▶│  Django Server   │────▶│   PostgreSQL    │
│   (React-like)  │     │   (REST API)     │     │   + pgvector    │
│                 │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │
                                │
                        ┌───────▼────────┐
                        │                │
                        │  OpenAI APIs   │
                        │  - GPT-4o-mini │
                        │  - GPT-4o      │
                        │  - Embeddings  │
                        │                │
                        └────────────────┘
```

### Core Components

1. **Document Processing Pipeline**
   - Extracts text, tables, and images from PDFs
   - Generates embeddings for semantic search
   - Stores in pgvector for efficient retrieval

2. **RAG Query Engine**
   - Retrieves relevant document chunks
   - Implements deduplication and diversity
   - Synthesizes responses with citations

3. **Chat Interface**
   - ChatGPT-style conversational UI
   - Real-time streaming responses
   - Source attribution and artifact viewing

### Technology Stack

- **Backend**: Django 5.2, Python 3.11
- **Vector Database**: PostgreSQL with pgvector
- **AI/ML**: LlamaIndex, OpenAI APIs
- **Document Processing**: PyMuPDF, pdfplumber
- **Frontend**: Vanilla JS with Tailwind CSS
- **Infrastructure**: Docker, Docker Compose

## Key Features

- **Multimodal Analysis**: Processes text, tables, and images from PDFs
- **Intelligent Search**: Semantic search with vector embeddings
- **Source Attribution**: Every response includes traceable sources
- **Duplicate Detection**: Prevents redundant document uploads
- **Bulk Processing**: Automatic seeding from directory
- **Production Ready**: Dockerized with proper error handling

## Directory Structure

```
fin_research_agent/
├── apps/
│   ├── chat/          # RAG query engine and chat interface
│   └── documents/     # PDF upload and processing
├── config/           # Django settings
├── seed_data/        # PDFs for automatic seeding
├── media/           # Uploaded files and extracted assets
└── docs/            # Detailed documentation
```

## Development

```bash
# Run tests
docker-compose exec web python manage.py test

# Access Django shell
docker-compose exec web python manage.py shell

# View logs
docker-compose logs -f web
```

## Documentation

For detailed documentation, see the [`docs/`](docs/) directory:
- [System Architecture](docs/architecture.md)
- [Chat App Details](docs/apps/chat.md)
- [Documents App Details](docs/apps/documents.md)
- [Deployment Guide](docs/deployment.md)

## License

[Your License]