"""
Management command to seed initial documents.
Automatically processes all PDFs in the seed_data directory.
"""

from django.core.management.base import BaseCommand
from django.core.files import File
from apps.documents.models import BrokerDocument
from apps.chat.document_processor import MultimodalDocumentProcessor
from apps.chat.metadata_extractor import MetadataExtractor
from apps.documents.views import calculate_file_hash
from pathlib import Path
import os
import hashlib
from datetime import datetime


class Command(BaseCommand):
    help = 'Seed the database with initial broker research documents'

    def add_arguments(self, parser):
        parser.add_argument(
            '--process',
            action='store_true',
            help='Also process documents after uploading (extract embeddings)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-upload even if file hash exists',
        )

    def calculate_file_hash_from_path(self, file_path):
        """Calculate SHA256 hash of file"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def handle(self, *args, **options):
        self.stdout.write("Starting document seeding...")
        
        # Get all PDFs from seed_data directory
        seed_dir = Path('/app/seed_data')
        if not seed_dir.exists():
            # Fallback for local development
            seed_dir = Path('seed_data')
            
        if not seed_dir.exists():
            self.stdout.write(
                self.style.ERROR(f"Seed data directory not found: {seed_dir}")
            )
            return
            
        pdf_files = list(seed_dir.glob('*.pdf'))
        self.stdout.write(f"Found {len(pdf_files)} PDF files in {seed_dir}")
        
        # Initialize processors
        extractor = MetadataExtractor()
        processor = MultimodalDocumentProcessor() if options['process'] else None
        
        # Track statistics
        uploaded = 0
        skipped = 0
        errors = 0
        
        for pdf_path in sorted(pdf_files):
            filename = pdf_path.name
            self.stdout.write(f"\nProcessing: {filename}")
            
            try:
                # Calculate file hash
                file_hash = self.calculate_file_hash_from_path(str(pdf_path))
                
                # Check if document already exists by hash
                if not options['force']:
                    existing_doc = BrokerDocument.objects.filter(file_hash=file_hash).first()
                    if existing_doc:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  → Skipped (duplicate): {existing_doc.broker} - {existing_doc.ticker} ({existing_doc.report_date})"
                            )
                        )
                        skipped += 1
                        continue
                
                # Extract metadata
                self.stdout.write("  → Extracting metadata...")
                metadata = extractor.extract_from_pdf(
                    pdf_path=str(pdf_path),
                    filename=filename
                )
                
                broker = metadata.get('broker', 'Unknown Broker')
                ticker = metadata.get('ticker', 'UNKNOWN')
                report_date = metadata.get('report_date')
                
                self.stdout.write(
                    f"  → Metadata: {broker} - {ticker} ({report_date or 'No date'})"
                )
                
                # Check for similar documents (same broker, ticker, date)
                if not options['force'] and report_date:
                    similar_exists = BrokerDocument.objects.filter(
                        broker=broker,
                        ticker=ticker,
                        report_date=report_date
                    ).exists()
                    
                    if similar_exists:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  → Similar document already exists, uploading anyway"
                            )
                        )
                
                # Create document record
                with open(pdf_path, 'rb') as f:
                    doc = BrokerDocument.objects.create(
                        file=File(f, name=filename),
                        broker=broker,
                        ticker=ticker,
                        report_date=report_date,
                        file_hash=file_hash,
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(f"  → Uploaded successfully (ID: {doc.id})")
                )
                
                # Process document if requested
                if options['process'] and processor:
                    self.stdout.write("  → Processing document...")
                    try:
                        stats = processor.process_pdf(
                            pdf_path=doc.file.path,
                            broker=doc.broker,
                            ticker=doc.ticker,
                            report_date=doc.report_date,
                            document_id=str(doc.id)  # Add document ID for linking
                        )
                        
                        doc.processed = True
                        doc.total_chunks = stats.get('text_chunks', 0)
                        doc.total_tables = stats.get('tables', 0)
                        doc.total_images = stats.get('images', 0)
                        doc.save()
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  → Processed: {stats['total_nodes']} nodes "
                                f"({stats['text_chunks']} text, {stats['tables']} tables, {stats['images']} images)"
                            )
                        )
                    except Exception as e:
                        doc.processing_error = str(e)
                        doc.save()
                        self.stdout.write(
                            self.style.ERROR(f"  → Processing error: {str(e)}")
                        )
                
                uploaded += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  → Error: {str(e)}")
                )
                errors += 1
        
        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"Document seeding complete!\n"
                f"  - Uploaded: {uploaded}\n"
                f"  - Skipped (duplicates): {skipped}\n"
                f"  - Errors: {errors}\n"
                f"  - Total files: {len(pdf_files)}"
            )
        )