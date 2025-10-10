"""
Test script for metadata extraction.
Run this to test filename pattern matching.
"""

from metadata_extractor import MetadataExtractor

# Test filename patterns
test_filenames = [
    "UBS_NVDA_20231215.pdf",
    "Goldman-Sachs-AAPL-Research-Dec-2023.pdf",
    "MS_TSLA_Q4_2023.pdf",
    "barclays-tesla-15dec2023.pdf",
    "JPM_Research_MSFT_2023Q4.pdf",
    "Q1FY26-CFO-Commentary.pdf",
    "morgan-stanley-nvidia-research-2024-01-15.pdf",
    "2024Q1_GOOGL_Citi_Research.pdf",
    "WellsFargo_AMZN_Jan2024.pdf",
    "deutsche-bank-meta-q3-2023-results.pdf",
]

def test_filename_extraction():
    """Test metadata extraction from filenames"""
    extractor = MetadataExtractor()
    
    print("Testing filename metadata extraction:\n")
    print("-" * 80)
    
    for filename in test_filenames:
        metadata = extractor._extract_from_filename(filename)
        print(f"Filename: {filename}")
        print(f"  Broker: {metadata.get('broker', 'Not found')}")
        print(f"  Ticker: {metadata.get('ticker', 'Not found')}")
        print(f"  Date: {metadata.get('report_date', 'Not found')}")
        print("-" * 80)

if __name__ == "__main__":
    test_filename_extraction()