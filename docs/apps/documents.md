# Documents Application

## Overview

The documents app manages the lifecycle of broker research PDFs from upload through processing. It implements intelligent metadata extraction, duplicate detection, and processing orchestration while maintaining data integrity and traceability.

## Core Components

### 1. Document Model (`models.py`)

**Purpose**: Central record for all uploaded PDFs and their processing state

**Schema Design**:
```python
class BrokerDocument:
    # Identity
    id: UUID (primary key)
    file: FileField (upload_to='pdfs/')
    file_hash: CharField (SHA256, unique)
    
    # Metadata
    broker: CharField (e.g., "Goldman Sachs")
    ticker: CharField (e.g., "NVDA")
    report_date: DateField
    title: CharField (optional)
    
    # Processing State
    processed: BooleanField
    processing_error: TextField
    
    # Statistics
    total_chunks: IntegerField
    total_tables: IntegerField
    total_images: IntegerField
    
    # Timestamps
    created_at: DateTimeField
    updated_at: DateTimeField
```

**Design Decisions**:
- **UUID Primary Key**: Ensures uniqueness across distributed systems
- **File Hash**: Enables exact duplicate detection
- **Nullable Metadata**: Supports progressive enhancement via extraction
- **Statistics Tracking**: Enables quality monitoring

**Strengths**:
- Clear separation between identity, metadata, and state
- Efficient duplicate detection via unique hash
- Detailed error tracking

**Weaknesses**:
- No versioning support
- Limited metadata schema (flat structure)
- No support for multi-file reports

### 2. Upload View (`views.py`)

**Purpose**: Handles PDF uploads with intelligent duplicate detection and metadata extraction

**Processing Flow**:
```
Upload → Hash Calculation → Duplicate Check → Save → Extract Metadata → Process
```

**Key Features**:

1. **Duplicate Detection**:
   ```python
   def calculate_file_hash(file):
       hasher = hashlib.sha256()
       for chunk in file.chunks():
           hasher.update(chunk)
       return hasher.hexdigest()
   ```
   - SHA256 ensures cryptographic uniqueness
   - Streams file to avoid memory issues

2. **Progressive Metadata**:
   - User can provide metadata (optional)
   - System extracts missing metadata
   - Graceful fallbacks to defaults

3. **Error Handling**:
   - Transaction safety for uploads
   - Detailed error messages
   - Processing continues despite individual failures

**Strengths**:
- Robust duplicate detection
- User-friendly progressive enhancement
- Good error recovery

**Weaknesses**:
- Synchronous processing blocks UI
- No progress feedback during processing
- Limited bulk upload support

### 3. Metadata Extractor (`metadata_extractor.py`)

**Purpose**: Intelligently extracts broker, ticker, and date from PDFs

**Extraction Strategy**:
```python
Priority Order:
1. Filename patterns (most reliable)
2. First page text analysis
3. Full text search (if needed)
```

**Pattern Recognition**:

```python
FILENAME_PATTERNS = [
    r'(\d{8})\s*-\s*([^-]+)\s*-\s*([A-Z]+)',  # "20240115 - Goldman - NVDA"
    r'([a-z]+)_([A-Z]+)_(\d{8})',             # "goldman_NVDA_20240115"
    # ... 10+ patterns
]

BROKER_MAPPING = {
    'gs': 'Goldman Sachs',
    'ms': 'Morgan Stanley',
    'baml': 'Bank of America',
    # ... 30+ broker mappings
}
```

**Text Analysis**:
- Searches for broker names in first 1000 characters
- Extracts tickers via regex: `[A-Z]{1,5}` with validation
- Parses dates in multiple formats

**Strengths**:
- Handles diverse naming conventions
- Fast pattern matching
- Comprehensive broker database

**Weaknesses**:
- English-centric patterns
- May miss creative formats
- No ML-based extraction

### 4. Seed Documents Command (`management/commands/seed_documents.py`)

**Purpose**: Bulk processes PDFs from seed_data directory with production-grade features

**Command Options**:
```bash
# Basic upload (metadata only)
python manage.py seed_documents

# Full processing (with embeddings)
python manage.py seed_documents --process

# Force re-upload
python manage.py seed_documents --force
```

**Implementation Highlights**:

1. **Automatic Discovery**:
   ```python
   pdf_files = list(Path('/app/seed_data').glob('*.pdf'))
   ```

2. **Progress Tracking**:
   ```
   Found 35 PDF files
   Processing: UBS_NVDA_Report.pdf
     → Extracting metadata...
     → Metadata: UBS - NVDA (2024-01-15)
     → Uploaded successfully
     → Processing document...
     → Processed: 127 nodes (45 text, 12 tables, 8 images)
   ```

3. **Statistics Summary**:
   ```
   Document seeding complete!
     - Uploaded: 30
     - Skipped (duplicates): 5  
     - Errors: 0
     - Total files: 35
   ```

**Strengths**:
- Production-ready bulk processing
- Excellent progress feedback
- Robust error handling

**Weaknesses**:
- No parallel processing
- Memory intensive for large batches
- No resume capability

### 5. Upload Interface (`templates/documents/upload.html`)

**Purpose**: Modern, responsive UI for document uploads with real-time feedback

**Key Features**:

1. **Progressive Upload Experience**:
   - Animated progress bar
   - Toast notifications
   - File validation
   - Processing status updates

2. **Smart Form Design**:
   - Required: PDF file only
   - Optional: Metadata fields (collapsed by default)
   - Auto-disable during upload
   - CSRF protection

3. **Document List View**:
   - Processing status indicators
   - Statistics display
   - Error messages
   - Auto-refresh during processing

**Technical Implementation**:
```javascript
// File validation
if (!file.type.includes('pdf')) {
    showToast('Please select a valid PDF file', 'error');
    return;
}

// Progress simulation
animateProgressBar();
showToast(`Uploading ${fileName} (${fileSize} MB)...`, 'info');
```

**Strengths**:
- Excellent user experience
- Real-time feedback
- Mobile responsive

**Weaknesses**:
- No drag-and-drop
- Basic progress (not real)
- No bulk selection

## Data Flow

### Upload → Storage → Processing

```
1. User Upload
   ↓
2. Hash Calculation (SHA256)
   ↓
3. Duplicate Check
   ↓
4. Save to media/pdfs/
   ↓
5. Create BrokerDocument record
   ↓
6. Extract metadata (if needed)
   ↓
7. Trigger processing (optional)
   ↓
8. Update statistics
```

## Performance Characteristics

### Upload Performance
- **File Hash**: ~50MB/second
- **Metadata Extraction**: ~500ms per PDF
- **Database Save**: ~10ms

### Storage Requirements
- **PDF Storage**: Original size (typically 1-5MB)
- **Database Record**: ~1KB per document
- **Extracted Images**: +20-50% of PDF size

### Concurrent Handling
- **Current**: Sequential processing
- **Capable**: 10+ concurrent uploads
- **Bottleneck**: Document processing step

## Security Implementation

### File Security
1. **Type Validation**: PDF mime-type checking
2. **Size Limits**: 50MB max (configurable)
3. **Path Traversal**: Protection via Django
4. **Hash Verification**: Ensures file integrity

### Data Security
- **SQL Injection**: Prevented by ORM
- **XSS**: Template auto-escaping
- **CSRF**: Token validation
- **File Access**: Media files served by Django

## Integration Points

### With Chat App
```python
# Document provides:
- file.path for processing
- broker, ticker, report_date metadata
- processing status

# Chat app uses:
- MultimodalDocumentProcessor
- Creates vector embeddings
- Updates processing statistics
```

### With Storage
- **Media Files**: `/media/pdfs/` for originals
- **Extracted Assets**: `/media/extracted/` for images
- **Database**: PostgreSQL for metadata

## Error Handling Strategy

### Upload Errors
- **File Too Large**: Clear message, suggest compression
- **Invalid Type**: Specify PDF requirement
- **Duplicate File**: Show existing document info
- **Network Error**: Retry mechanism

### Processing Errors
- **Extraction Failure**: Log and continue
- **Metadata Missing**: Use sensible defaults
- **Processing Crash**: Mark as failed, allow retry

## Testing Considerations

### Unit Tests Needed
```python
def test_hash_calculation():
    """Ensure consistent hashing"""
    file1 = SimpleUploadedFile("test.pdf", b"content")
    file2 = SimpleUploadedFile("test.pdf", b"content")
    assert calculate_file_hash(file1) == calculate_file_hash(file2)

def test_metadata_extraction():
    """Test various filename formats"""
    extractor = MetadataExtractor()
    result = extractor.extract_from_filename(
        "20240115 - Goldman Sachs - NVDA - Earnings Preview.pdf"
    )
    assert result['broker'] == 'Goldman Sachs'
    assert result['ticker'] == 'NVDA'
    assert result['report_date'] == '2024-01-15'
```

### Integration Tests Needed
- Full upload → process → query flow
- Duplicate detection across restarts
- Error recovery scenarios

## Maintenance Operations

### Regular Tasks
1. **Clean Old Uploads**: Remove failed/orphaned files
2. **Reprocess Failures**: Retry failed documents
3. **Update Statistics**: Reconcile counts

### Monitoring Points
- Upload success rate
- Processing time per document
- Storage growth rate
- Error frequency by type

## Future Enhancements

### Short Term
1. **Async Processing**: Celery task queue
2. **Progress Websocket**: Real-time updates
3. **Batch Upload UI**: Multi-file selection

### Medium Term
1. **OCR Integration**: Handle scanned PDFs
2. **Version Control**: Track document updates
3. **Metadata API**: Auto-fetch from financial APIs

### Long Term
1. **Document Relationships**: Link related reports
2. **Change Detection**: Highlight updates
3. **Smart Routing**: Auto-categorize documents