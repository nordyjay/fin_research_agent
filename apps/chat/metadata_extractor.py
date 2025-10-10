# apps/chat/metadata_extractor.py
"""
Intelligent metadata extraction from PDF filenames and content.
Uses pattern matching and LLM to extract broker, ticker, and report date.
"""

import re
from datetime import datetime
from pathlib import Path
import pdfplumber
import logging
from .llamaindex_setup import get_llm

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Extract broker, ticker, and date from PDF files
    
    Supports filename patterns like:
    - UBS_NVDA_20231215.pdf
    - Goldman-Sachs-AAPL-Research-Dec-2023.pdf
    - MS_TSLA_Q4_2023.pdf
    - barclays-tesla-15dec2023.pdf
    - JPM_Research_MSFT_2023Q4.pdf
    - Q1FY26-CFO-Commentary.pdf
    
    Falls back to LLM content extraction if filename parsing fails.
    """
    
    # Common broker name patterns and variations
    BROKER_PATTERNS = {
        'ubs': 'UBS',
        'gs': 'Goldman Sachs',
        'goldman': 'Goldman Sachs',
        'goldmansachs': 'Goldman Sachs',
        'goldman-sachs': 'Goldman Sachs',
        'goldman_sachs': 'Goldman Sachs',
        'ms': 'Morgan Stanley',
        'morgan': 'Morgan Stanley',
        'morganstanley': 'Morgan Stanley',
        'morgan-stanley': 'Morgan Stanley',
        'morgan_stanley': 'Morgan Stanley',
        'jpm': 'JPMorgan',
        'jpmorgan': 'JPMorgan',
        'jp-morgan': 'JPMorgan',
        'jp_morgan': 'JPMorgan',
        'jpmc': 'JPMorgan',
        'baml': 'Bank of America',
        'bofa': 'Bank of America',
        'bankofamerica': 'Bank of America',
        'bank-of-america': 'Bank of America',
        'barclays': 'Barclays',
        'citi': 'Citi',
        'citigroup': 'Citi',
        'cs': 'Credit Suisse',
        'credit-suisse': 'Credit Suisse',
        'credit_suisse': 'Credit Suisse',
        'creditsuisse': 'Credit Suisse',
        'db': 'Deutsche Bank',
        'deutsche': 'Deutsche Bank',
        'deutschebank': 'Deutsche Bank',
        'deutsche-bank': 'Deutsche Bank',
        'deutsche_bank': 'Deutsche Bank',
        'wells': 'Wells Fargo',
        'wellsfargo': 'Wells Fargo',
        'wells-fargo': 'Wells Fargo',
        'wells_fargo': 'Wells Fargo',
        'wf': 'Wells Fargo',
        'rbc': 'RBC Capital',
        'rbccm': 'RBC Capital',
        'mizuho': 'Mizuho',
        'jefferies': 'Jefferies',
        'bernstein': 'Bernstein Research',
        'cowen': 'Cowen',
        'needham': 'Needham',
        'piper': 'Piper Sandler',
        'pipersandler': 'Piper Sandler',
        'raymond': 'Raymond James',
        'raymondjames': 'Raymond James',
        'stifel': 'Stifel',
        'truist': 'Truist Securities',
        'wedbush': 'Wedbush',
    }
    
    def __init__(self):
        self.llm = get_llm()
    
    def extract_from_pdf(self, pdf_path, filename=None):
        """
        Extract metadata from PDF file.
        
        Args:
            pdf_path: Path to PDF file
            filename: Original filename (if different from pdf_path)
            
        Returns:
            dict: {'broker': str, 'ticker': str, 'report_date': str}
        """
        logger.info(f"Extracting metadata from: {pdf_path}")
        
        # Start with empty metadata
        metadata = {
            'broker': None,
            'ticker': None,
            'report_date': None
        }
        
        # Try filename extraction first (fastest)
        if filename is None:
            filename = Path(pdf_path).name
        
        filename_metadata = self._extract_from_filename(filename)
        metadata.update(filename_metadata)
        
        # If we're missing any fields, try content extraction
        if not all(metadata.values()):
            content_metadata = self._extract_from_content(pdf_path, metadata)
            # Update only missing fields
            for key, value in content_metadata.items():
                if not metadata.get(key):
                    metadata[key] = value
        
        # Clean up and validate
        metadata = self._validate_metadata(metadata)
        
        logger.info(f"Extracted metadata: {metadata}")
        return metadata
    
    def _extract_from_filename(self, filename):
        """Extract metadata from filename using patterns"""
        metadata = {}
        
        # Clean filename
        clean_name = Path(filename).stem.lower()
        
        # Extract ticker (common patterns: AAPL, NVDA, MSFT)
        # Skip common non-ticker patterns
        # Extract ticker - look for 2-5 uppercase letters surrounded by separators
        ticker_match = re.search(r'(?:^|[-_])(?!FY|Q\d|PDF|CFO|CEO|CTO)([A-Z]{2,5})(?=[-_]|\.|$)', filename)
        if ticker_match:
            metadata['ticker'] = ticker_match.group(1)
        
        # Extract broker
        for pattern, broker_name in self.BROKER_PATTERNS.items():
            if pattern in clean_name:
                metadata['broker'] = broker_name
                break
        
        # Extract date patterns
        date_patterns = [
            # 20231215, 2023-12-15, 2023_12_15
            (r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})', '%Y-%m-%d'),
            # 15Dec2023, 15-Dec-2023
            (r'(\d{1,2})[-_]?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-_]?(\d{4})', '%d-%b-%Y'),
            # Dec2023, December2023
            (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-_]?(\d{4})', '%b-%Y'),
            # Q1-2023, Q1FY23
            (r'Q(\d)[-_]?(?:FY)?(\d{2,4})', 'Q%q-%Y'),
            # 2023Q1
            (r'(\d{4})[-_]?Q(\d)', '%Y-Q%q'),
        ]
        
        for pattern, date_format in date_patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    if 'Q' in date_format:  # Quarter format
                        if len(match.groups()) == 2:
                            quarter = match.group(1) if pattern.startswith('Q') else match.group(2)
                            year = match.group(2) if pattern.startswith('Q') else match.group(1)
                            if len(year) == 2:
                                year = '20' + year
                            # Convert quarter to month (Q1=Jan, Q2=Apr, Q3=Jul, Q4=Oct)
                            quarter_month = (int(quarter) - 1) * 3 + 1
                            metadata['report_date'] = f"{year}-{quarter_month:02d}-01"
                    else:
                        # Parse regular date
                        if len(match.groups()) == 2:  # Month-Year format
                            date_str = f"01-{match.group(1)}-{match.group(2)}"
                            date_obj = datetime.strptime(date_str, f"01-{date_format}")
                        else:
                            date_str = '-'.join(match.groups())
                            date_obj = datetime.strptime(date_str, date_format)
                        metadata['report_date'] = date_obj.strftime('%Y-%m-%d')
                    break
                except:
                    continue
        
        return metadata
    
    def _extract_from_content(self, pdf_path, existing_metadata):
        """Extract metadata from PDF content using LLM"""
        try:
            # Read first 2 pages
            text_content = ""
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages[:2]):  # First 2 pages
                    text = page.extract_text()
                    if text:
                        text_content += text + "\n"
                    if len(text_content) > 3000:  # Limit content
                        break
            
            if not text_content.strip():
                return {}
            
            # Prepare prompt for LLM
            prompt = f"""Analyze this financial research report and extract the following information:

1. BROKER: The investment bank or research firm that published this report (e.g., UBS, Goldman Sachs, Morgan Stanley)
2. TICKER: The stock ticker symbol being analyzed (e.g., AAPL, NVDA, MSFT)
3. REPORT_DATE: The publication date of this report (format: YYYY-MM-DD)

Current extracted values:
- Broker: {existing_metadata.get('broker', 'Not found')}
- Ticker: {existing_metadata.get('ticker', 'Not found')}
- Date: {existing_metadata.get('report_date', 'Not found')}

Please extract any MISSING information from the document content below. If you find the information, provide it. If not found, respond with null.

Document content:
{text_content[:2000]}

Respond in this exact JSON format:
{{
    "broker": "Broker Name or null",
    "ticker": "TICKER or null",
    "report_date": "YYYY-MM-DD or null"
}}"""

            response = self.llm.complete(prompt)
            
            # Parse JSON response
            import json
            result_text = response.text.strip()
            
            # Extract JSON from response (in case LLM adds extra text)
            json_start = result_text.find('{')
            json_end = result_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = result_text[json_start:json_end]
                extracted = json.loads(json_str)
                
                # Clean up the results
                metadata = {}
                if extracted.get('broker') and extracted['broker'] != 'null':
                    metadata['broker'] = extracted['broker']
                if extracted.get('ticker') and extracted['ticker'] != 'null':
                    metadata['ticker'] = extracted['ticker'].upper()
                if extracted.get('report_date') and extracted['report_date'] != 'null':
                    # Validate date format
                    try:
                        date_obj = datetime.strptime(extracted['report_date'], '%Y-%m-%d')
                        metadata['report_date'] = extracted['report_date']
                    except:
                        pass
                
                return metadata
                
        except Exception as e:
            logger.error(f"Error extracting from content: {e}")
        
        return {}
    
    def _validate_metadata(self, metadata):
        """Validate and clean metadata"""
        # Ensure ticker is uppercase
        if metadata.get('ticker'):
            metadata['ticker'] = metadata['ticker'].upper()
        
        # Validate date format
        if metadata.get('report_date'):
            try:
                # Try to parse and reformat date
                date_obj = datetime.strptime(metadata['report_date'], '%Y-%m-%d')
                metadata['report_date'] = date_obj.strftime('%Y-%m-%d')
            except:
                # If invalid, remove it
                metadata['report_date'] = None
        
        # Use defaults for missing values
        metadata['broker'] = metadata.get('broker') or 'Unknown Broker'
        metadata['ticker'] = metadata.get('ticker') or 'UNKNOWN'
        metadata['report_date'] = metadata.get('report_date') or datetime.now().strftime('%Y-%m-%d')
        
        return metadata