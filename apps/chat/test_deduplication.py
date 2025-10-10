from django.test import TestCase
from unittest.mock import MagicMock
from apps.chat.node_postprocessors import PageDeduplicator
from llama_index.core.schema import NodeWithScore, TextNode


class PageDeduplicatorTest(TestCase):
    def setUp(self):
        self.deduplicator = PageDeduplicator(max_per_page=1, max_per_document=2)
        
    def create_node(self, broker, ticker, date, page, score, content="Test content"):
        """Helper to create test nodes"""
        node = TextNode(
            text=content,
            metadata={
                'broker': broker,
                'ticker': ticker,
                'report_date': date,
                'page_number': int(page)  # page_number, not page_label
            }
        )
        return NodeWithScore(node=node, score=score)
        
    def test_single_chunk_per_page(self):
        """Test that only one chunk per page is returned"""
        # Same document, different pages
        nodes = [
            self.create_node("UBS", "NVDA", "2024-01-15", "5", 0.9, "First chunk page 5"),
            self.create_node("UBS", "NVDA", "2024-01-15", "5", 0.8, "Second chunk page 5"),
            self.create_node("UBS", "NVDA", "2024-01-15", "6", 0.7, "First chunk page 6"),
        ]
        
        result = self.deduplicator._postprocess_nodes(nodes)
        
        # Should get 2 chunks (one per page, but max 2 per document)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].score, 0.9)
        self.assertEqual(result[1].score, 0.7)
        
    def test_max_chunks_per_document(self):
        """Test that max 2 chunks per document are returned"""
        # 4 pages from same document, should only return 2
        nodes = [
            self.create_node("UBS", "NVDA", "2024-01-15", "1", 0.95),
            self.create_node("UBS", "NVDA", "2024-01-15", "2", 0.90),
            self.create_node("UBS", "NVDA", "2024-01-15", "3", 0.85),
            self.create_node("UBS", "NVDA", "2024-01-15", "4", 0.80),
        ]
        
        result = self.deduplicator._postprocess_nodes(nodes)
        
        # Due to max_per_document=2, should only get top 2
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].score, 0.95)
        self.assertEqual(result[1].score, 0.90)
        
    def test_multiple_documents_diversity(self):
        """Test diversity across multiple documents"""
        nodes = [
            # UBS NVDA doc - should get 2 max
            self.create_node("UBS", "NVDA", "2024-01-15", "1", 0.95),
            self.create_node("UBS", "NVDA", "2024-01-15", "2", 0.94),
            self.create_node("UBS", "NVDA", "2024-01-15", "3", 0.89),  # Won't be included
            # Goldman NVDA doc - different document
            self.create_node("Goldman", "NVDA", "2024-01-20", "1", 0.93),
            self.create_node("Goldman", "NVDA", "2024-01-20", "2", 0.92),
            # UBS AAPL doc - different ticker
            self.create_node("UBS", "AAPL", "2024-01-10", "1", 0.91),
        ]
        
        result = self.deduplicator._postprocess_nodes(nodes)
        
        # Should get: 2 from UBS/NVDA, 2 from Goldman/NVDA, 1 from UBS/AAPL = 5 total
        self.assertEqual(len(result), 5)
        
        ubc_nvda_count = sum(1 for n in result 
                            if n.node.metadata['broker'] == 'UBS' 
                            and n.node.metadata['ticker'] == 'NVDA')
        self.assertEqual(ubc_nvda_count, 2)
        
    def test_empty_nodes_list(self):
        """Test handling of empty node list"""
        result = self.deduplicator._postprocess_nodes([])
        self.assertEqual(result, [])
        
    def test_missing_metadata_fields(self):
        """Test nodes with missing metadata fields"""
        node1 = TextNode(text="No metadata")
        node2 = TextNode(text="Partial metadata", metadata={'broker': 'UBS'})
        
        nodes = [
            NodeWithScore(node=node1, score=0.9),
            NodeWithScore(node=node2, score=0.8),
        ]
        
        result = self.deduplicator._postprocess_nodes(nodes)
        self.assertEqual(len(result), 2)
        
    def test_same_page_different_scores(self):
        """Test that highest scoring chunk per page wins"""
        nodes = [
            self.create_node("UBS", "NVDA", "2024-01-15", "10", 0.7, "Lower score"),
            self.create_node("UBS", "NVDA", "2024-01-15", "10", 0.9, "Higher score"),
            self.create_node("UBS", "NVDA", "2024-01-15", "10", 0.8, "Medium score"),
        ]
        
        result = self.deduplicator._postprocess_nodes(nodes)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].score, 0.9)
        self.assertEqual(result[0].node.text, "Higher score")
        
    def test_custom_max_per_page(self):
        """Test custom max_per_page setting"""
        dedup = PageDeduplicator(max_per_page=2, max_per_document=10)
        
        nodes = [
            self.create_node("UBS", "NVDA", "2024-01-15", "5", 0.9),
            self.create_node("UBS", "NVDA", "2024-01-15", "5", 0.8),
            self.create_node("UBS", "NVDA", "2024-01-15", "5", 0.7),
        ]
        
        result = dedup._postprocess_nodes(nodes)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].score, 0.9)
        self.assertEqual(result[1].score, 0.8)