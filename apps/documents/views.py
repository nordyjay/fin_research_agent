# apps/documents/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import BrokerDocument
from apps.chat.document_processor import MultimodalDocumentProcessor
from apps.chat.metadata_extractor import MetadataExtractor
import os
import hashlib
import logging

logger = logging.getLogger(__name__)

def calculate_file_hash(file):
    """Calculate SHA256 hash of uploaded file"""
    hasher = hashlib.sha256()
    for chunk in file.chunks():
        hasher.update(chunk)
    return hasher.hexdigest()


def upload_document(request):
    """Upload and process PDF"""
    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf_file')
        broker = request.POST.get('broker', '').strip()
        ticker = request.POST.get('ticker', '').strip()
        report_date = request.POST.get('report_date')
        
        if not pdf_file:
            messages.error(request, "PDF file is required")
            return redirect('documents:upload')
        
        # Calculate file hash to check for duplicates
        file_hash = calculate_file_hash(pdf_file)
        pdf_file.seek(0)  # Reset file pointer after reading
        
        # Check for existing document with same hash
        existing_doc = BrokerDocument.objects.filter(file_hash=file_hash).first()
        if existing_doc:
            messages.warning(request, 
                f"This document has already been uploaded: {existing_doc.broker} - {existing_doc.ticker} ({existing_doc.report_date}). "
                f"Original filename: {os.path.basename(existing_doc.file.name)}")
            return redirect('documents:upload')
        
        # Save the file temporarily to extract metadata
        doc = BrokerDocument.objects.create(
            file=pdf_file,
            broker=None,  # Will be filled by metadata extraction
            ticker=None,
            report_date=None,
            file_hash=file_hash,  # Save the hash
        )
        
        # Extract metadata if not provided
        if not all([broker, ticker, report_date]):
            logger.info(f"Extracting metadata for {pdf_file.name}")
            try:
                extractor = MetadataExtractor()
                extracted_metadata = extractor.extract_from_pdf(
                    pdf_path=doc.file.path,
                    filename=pdf_file.name
                )
                
                # Use extracted metadata for missing fields
                broker = broker or extracted_metadata.get('broker')
                ticker = ticker or extracted_metadata.get('ticker')
                report_date = report_date or extracted_metadata.get('report_date')
                
                # Update document with metadata
                doc.broker = broker
                doc.ticker = ticker
                doc.report_date = report_date
                doc.save()
                
                messages.info(request, f"Extracted metadata - Broker: {broker}, Ticker: {ticker}, Date: {report_date}")
            except Exception as e:
                logger.error(f"Error extracting metadata: {e}")
                messages.warning(request, "Could not extract metadata from PDF. Using defaults.")
                # Use defaults if extraction fails
                doc.broker = broker or 'Unknown Broker'
                doc.ticker = ticker or 'UNKNOWN'
                doc.report_date = report_date
                doc.save()
        
        # Check for similar documents (same broker, ticker, date)
        similar_docs = BrokerDocument.objects.filter(
            broker=doc.broker,
            ticker=doc.ticker,
            report_date=doc.report_date
        ).exclude(id=doc.id)
        
        if similar_docs.exists():
            similar_doc = similar_docs.first()
            messages.warning(request, 
                f"A similar document already exists: {similar_doc.broker} - {similar_doc.ticker} ({similar_doc.report_date}). "
                f"Uploaded on: {similar_doc.created_at.strftime('%Y-%m-%d %H:%M')}. "
                "Processing anyway in case it contains different content.")
        
        try:
            # Process document
            processor = MultimodalDocumentProcessor()
            stats = processor.process_pdf(
                pdf_path=doc.file.path,
                broker=doc.broker,
                ticker=doc.ticker,
                report_date=doc.report_date,
                document_id=str(doc.id)  # Pass document ID for linking
            )
            
            doc.processed = True
            doc.save()
            
            messages.success(request, f"Document processed successfully! Created {stats.get('total_nodes', 0)} nodes.")
            
            # Update document statistics
            doc.total_chunks = stats.get('text_chunks', 0)
            doc.total_tables = stats.get('tables', 0)
            doc.total_images = stats.get('images', 0)
            doc.save()
            
        except Exception as e:
            doc.processing_error = str(e)
            doc.save()
            messages.error(request, f"Processing error: {str(e)}")
        
        return redirect('documents:upload')
    
    documents = BrokerDocument.objects.all()
    return render(request, 'documents/upload.html', {
        'documents': documents
    })


def view_document(request, document_id):
    """View PDF document in browser"""
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    
    doc = get_object_or_404(BrokerDocument, id=document_id)
    
    try:
        with open(doc.file.path, 'rb') as pdf:
            response = HttpResponse(pdf.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{doc.get_display_name()}.pdf"'
            return response
    except FileNotFoundError:
        messages.error(request, "PDF file not found")
        return redirect('documents:upload')


def download_document(request, document_id):
    """Download PDF document"""
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    
    doc = get_object_or_404(BrokerDocument, id=document_id)
    
    try:
        with open(doc.file.path, 'rb') as pdf:
            response = HttpResponse(pdf.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{doc.get_display_name()}.pdf"'
            return response
    except FileNotFoundError:
        messages.error(request, "PDF file not found")
        return redirect('documents:upload')
