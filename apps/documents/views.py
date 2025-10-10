# apps/documents/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import BrokerDocument
from apps.chat.document_processor import MultimodalDocumentProcessor
import os

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
        
        # Save document with optional metadata
        doc = BrokerDocument.objects.create(
            file=pdf_file,
            broker=broker if broker else None,
            ticker=ticker if ticker else None,
            report_date=report_date if report_date else None,
        )
        
        try:
            # Process document
            processor = MultimodalDocumentProcessor()
            stats = processor.process_pdf(
                pdf_path=doc.file.path,
                broker=broker if broker else 'Unknown',
                ticker=ticker if ticker else 'Unknown',
                report_date=report_date if report_date else ''
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
