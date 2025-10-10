# apps/documents/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import BrokerDocument
from apps.chat.document_processor import MultimodalDocumentProcessor
from apps.chat.metadata_extractor import MetadataExtractor
import os
import logging

logger = logging.getLogger(__name__)

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
        
        # Save the file temporarily to extract metadata
        doc = BrokerDocument.objects.create(
            file=pdf_file,
            broker=None,  # Will be filled by metadata extraction
            ticker=None,
            report_date=None,
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
        
        try:
            # Process document
            processor = MultimodalDocumentProcessor()
            stats = processor.process_pdf(
                pdf_path=doc.file.path,
                broker=doc.broker,
                ticker=doc.ticker,
                report_date=doc.report_date
            )
            
            doc.processed = True
            doc.save()
            
            messages.success(request, f"Document processed successfully! Created {stats.get('total_nodes', 0)} nodes.")
            
        except Exception as e:
            doc.processing_error = str(e)
            doc.save()
            messages.error(request, f"Processing error: {str(e)}")
        
        return redirect('documents:upload')
    
    documents = BrokerDocument.objects.all()
    return render(request, 'documents/upload.html', {
        'documents': documents
    })
