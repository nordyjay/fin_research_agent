"""
Management command to seed initial documents.
Automatically processes the 3 provided broker research PDFs.
"""

from django.core.management.base import BaseCommand
from django.core.files import File
from apps.documents.models import BrokerDocument
from pathlib import Path
import os


class Command(BaseCommand):
    help = 'Seed the database with initial broker research documents'

    def handle(self, *args, **options):
        self.stdout.write("Starting document seeding...")
        
        # Define documents to seed
        seed_documents = [
            {
                'filename': 'ubs_nvda_20231211.pdf',
                'broker': 'UBS',
                'ticker': 'NVDA',
                'report_date': '2023-12-11',
                'path': '/app/seed_data/ubs_nvda_20231211.pdf'
            },
            {
                'filename': 'barclays_nvda_20240111.pdf',
                'broker': 'Barclays',
                'ticker': 'NVDA',
                'report_date': '2024-01-11',
                'path': '/app/seed_data/barclays_nvda_20240111.pdf'
            },
            {
                'filename': 'barclays_crm_20240222.pdf',
                'broker': 'Barclays',
                'ticker': 'CRM',
                'report_date': '2024-02-22',
                'path': '/app/seed_data/barclays_crm_20240222.pdf'
            }
        ]
        
        for doc_info in seed_documents:
            # Check if document already exists
            if BrokerDocument.objects.filter(
                broker=doc_info['broker'],
                ticker=doc_info['ticker'],
                report_date=doc_info['report_date']
            ).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Document already exists: {doc_info['broker']} - {doc_info['ticker']} ({doc_info['report_date']})"
                    )
                )
                continue
            
            # Check if file exists
            if not os.path.exists(doc_info['path']):
                self.stdout.write(
                    self.style.ERROR(f"File not found: {doc_info['path']}")
                )
                continue
            
            try:
                # Create document record
                with open(doc_info['path'], 'rb') as f:
                    doc = BrokerDocument.objects.create(
                        file=File(f, name=doc_info['filename']),
                        broker=doc_info['broker'],
                        ticker=doc_info['ticker'],
                        report_date=doc_info['report_date'],
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created document: {doc_info['filename']}"
                    )
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error creating {doc_info['filename']}: {str(e)}")
                )
        
        self.stdout.write(self.style.SUCCESS("Document seeding complete!"))