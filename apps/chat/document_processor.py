# apps/chat/document_processor.py
"""
Multimodal document processor using OpenAI.
Handles PDF ingestion with text, tables, and images.
"""

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import ImageDocument
from pathlib import Path
import pdfplumber
import fitz
from PIL import Image
import io
import logging
import base64
from .llamaindex_setup import get_index, get_vision_model, configure_llamaindex, get_llm

logger = logging.getLogger(__name__)


class MultimodalDocumentProcessor:
    """
    Processes PDFs with multimodal content using OpenAI:
    1. Text extraction and chunking
    2. Table extraction and summarization (GPT-4o-mini)
    3. Image/chart extraction and description (GPT-4o vision)
    """
    
    def __init__(self):
        try:
            configure_llamaindex()
            self.index = get_index()
            self.vision_model = get_vision_model()
            self.llm = get_llm()
            self.node_parser = SentenceSplitter(
                chunk_size=512,
                chunk_overlap=50,
            )
        except Exception as e:
            logger.error(f"Error initializing document processor: {e}")
            raise
        
    def process_pdf(self, pdf_path, broker, ticker, report_date, document_id=None):
        """
        Main processing pipeline.
        
        Args:
            pdf_path: Path to PDF file
            broker: Broker name (e.g., "UBS")
            ticker: Stock ticker (e.g., "NVDA")
            report_date: Report date string
            
        Returns:
            dict: Processing statistics
        """
        logger.info(f"Processing PDF: {pdf_path}")
        logger.info(f"Metadata - Broker: {broker}, Ticker: {ticker}, Date: {report_date}")
        
        all_documents = []
        stats = {
            'text_chunks': 0,
            'tables': 0,
            'images': 0,
            'total_nodes': 0,
        }
        
        # Base metadata for all content
        base_metadata = {
            'broker': broker if broker else 'Unknown',
            'ticker': ticker if ticker else 'Unknown',
            'report_date': str(report_date) if report_date else '',
            'source_file': str(pdf_path),
            'document_id': document_id if document_id else None,
        }
        
        # 1. Extract text
        logger.info("Extracting text...")
        text_docs = self._extract_text(pdf_path, base_metadata)
        all_documents.extend(text_docs)
        stats['text_chunks'] = len(text_docs)
        
        # 2. Extract tables
        logger.info("Extracting tables...")
        table_docs = self._extract_tables(pdf_path, base_metadata)
        all_documents.extend(table_docs)
        stats['tables'] = len(table_docs)
        
        # 3. Extract images
        logger.info("Extracting images...")
        image_docs = self._extract_images(pdf_path, base_metadata)
        all_documents.extend(image_docs)
        stats['images'] = len(image_docs)
        
        # 4. Parse into nodes
        logger.info("Creating nodes...")
        nodes = self.node_parser.get_nodes_from_documents(all_documents)
        stats['total_nodes'] = len(nodes)
        
        # 5. Add to index
        logger.info(f"Indexing {len(nodes)} nodes...")
        try:
            self.index.insert_nodes(nodes)
        except Exception as e:
            logger.error(f"Error indexing nodes: {e}")
            raise Exception(f"Failed to index document: {str(e)}")
        
        logger.info(f"Processing complete: {stats}")
        return stats
    
    def _extract_text(self, pdf_path, base_metadata):
        """Extract and chunk text from PDF"""
        documents = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                
                if text and text.strip():
                    doc = Document(
                        text=text,
                        metadata={
                            **base_metadata,
                            'page_number': page_num,
                            'content_type': 'text',
                        }
                    )
                    documents.append(doc)
        
        return documents
    
    def _extract_tables(self, pdf_path, base_metadata):
        """Extract tables and generate summaries using GPT-4o-mini"""
        table_documents = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                
                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue
                    
                    try:
                        # Convert to markdown
                        table_md = self._table_to_markdown(table)
                        
                        # Generate summary using OpenAI
                        summary = self._summarize_table(table_md)
                        
                        # Create document with both summary and raw data
                        content = f"TABLE SUMMARY:\n{summary}\n\nRAW TABLE DATA:\n{table_md}"
                        
                        doc = Document(
                            text=content,
                            metadata={
                                **base_metadata,
                                'page_number': page_num,
                                'content_type': 'table',
                                'table_index': table_idx,
                            }
                        )
                        table_documents.append(doc)
                        
                    except Exception as e:
                        logger.error(f"Error processing table on page {page_num}: {e}")
                        continue
        
        return table_documents
    
    def _extract_images(self, pdf_path, base_metadata):
        """Extract images and generate descriptions using GPT-4o vision"""
        image_documents = []
        
        try:
            pdf_doc = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_doc)):
                page = pdf_doc[page_num]
                images = page.get_images()
                
                for img_idx, img in enumerate(images):
                    try:
                        xref = img[0]
                        base_image = pdf_doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        
                        # Save image
                        image = Image.open(io.BytesIO(image_bytes))
                        
                        # Only process reasonable-sized images
                        if image.width < 50 or image.height < 50:
                            continue
                        
                        # Create safe filename
                        broker_safe = base_metadata['broker'].replace(' ', '_').replace('/', '_')
                        ticker_safe = base_metadata['ticker'].replace(' ', '_').replace('/', '_')
                        image_filename = f"{broker_safe}_{ticker_safe}_p{page_num+1}_img{img_idx}.png"
                        
                        # Use relative path from settings
                        from django.conf import settings
                        import os
                        extracted_dir = os.path.join(settings.MEDIA_ROOT, 'extracted')
                        os.makedirs(extracted_dir, exist_ok=True)
                        
                        image_path = os.path.join(extracted_dir, image_filename)
                        image.save(image_path)
                        
                        # Describe image using GPT-4o vision
                        description = self._describe_image(image_path)
                        
                        # Create document
                        doc = Document(
                            text=f"IMAGE DESCRIPTION:\n{description}",
                            metadata={
                                **base_metadata,
                                'page_number': page_num + 1,
                                'content_type': 'image',
                                'image_path': str(image_path),
                                'image_index': img_idx,
                            }
                        )
                        image_documents.append(doc)
                        
                    except Exception as e:
                        logger.error(f"Error processing image on page {page_num}: {e}")
                        continue
            
            pdf_doc.close()
            
        except Exception as e:
            logger.error(f"Error extracting images: {e}")
        
        return image_documents
    
    def _table_to_markdown(self, table):
        """Convert table array to markdown format"""
        if not table or len(table) == 0:
            return ""
        
        lines = []
        
        # Header
        headers = [str(cell) if cell else "" for cell in table[0]]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # Rows
        for row in table[1:]:
            cells = [str(cell) if cell else "" for cell in row]
            lines.append("| " + " | ".join(cells) + " |")
        
        return "\n".join(lines)
    
    def _summarize_table(self, table_md):
        """Generate concise summary of table using GPT-4o-mini"""
        prompt = f"""Analyze this financial table and provide a concise summary.

Focus on:
1. What type of data is shown (price targets, revenue, ratings, etc.)
2. Key numbers and trends
3. Any notable changes or patterns

Table:
{table_md}

Provide a 2-3 sentence summary:"""
        
        try:
            response = self.llm.complete(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error summarizing table: {e}")
            return "Table containing financial data."
    
    def _describe_image(self, image_path):
        """Describe image using GPT-4o vision"""
        prompt = """Analyze this image from a financial research report.

If it's a chart or graph:
- Type of visualization (line chart, bar chart, etc.)
- What metrics are displayed
- Key trends or patterns
- Notable data points

If it's a logo or decorative:
- Simply note that it's not analytical content

Provide a clear, concise description:"""
        
        try:
            # Ensure image_path is a string
            image_path_str = str(image_path) if not isinstance(image_path, str) else image_path
            
            # Create ImageDocument for LlamaIndex
            image_doc = ImageDocument(image_path=image_path_str)
            
            # Use OpenAI multimodal to describe
            response = self.vision_model.complete(
                prompt=prompt,
                image_documents=[image_doc]
            )
            
            return response.text.strip() if response and hasattr(response, 'text') else "Image from financial report."
            
        except Exception as e:
            logger.error(f"Error describing image at {image_path}: {e}")
            return "Chart or image from financial report."