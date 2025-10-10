# apps/chat/node_postprocessors.py
"""
Custom node postprocessors for deduplication and diversity.
"""

from typing import List, Optional
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.bridge.pydantic import Field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class PageDeduplicator(BaseNodePostprocessor):
    """
    Deduplicate nodes to ensure diversity by limiting nodes per page.
    Keeps only the top-scoring nodes from each page.
    """
    
    max_per_page: int = Field(default=1, description="Maximum number of chunks to return per page")
    max_per_document: int = Field(default=2, description="Maximum number of chunks per document")
    
    def __init__(self, max_per_page: int = 1, max_per_document: int = 2, **kwargs):
        """
        Args:
            max_per_page: Maximum number of chunks to return per page
            max_per_document: Maximum number of chunks per document (broker/ticker/date combo)
        """
        super().__init__(max_per_page=max_per_page, max_per_document=max_per_document, **kwargs)
    
    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        """
        Postprocess nodes to remove duplicates and ensure diversity.
        """
        # Group nodes by page and document
        page_groups = defaultdict(list)
        doc_groups = defaultdict(list)
        
        for node in nodes:
            # Create page key
            page_key = (
                node.metadata.get('broker', ''),
                node.metadata.get('ticker', ''),
                node.metadata.get('report_date', ''),
                node.metadata.get('page_number', 0)
            )
            
            # Create document key (without page number)
            doc_key = (
                node.metadata.get('broker', ''),
                node.metadata.get('ticker', ''),
                node.metadata.get('report_date', '')
            )
            
            page_groups[page_key].append(node)
            doc_groups[doc_key].append(node)
        
        # Select best nodes from each page
        selected_nodes = []
        
        # First pass: get best nodes from each page
        for page_key, page_nodes in page_groups.items():
            # Sort by score (highest first)
            page_nodes.sort(key=lambda x: x.score if x.score else 0, reverse=True)
            # Take only max_per_page nodes
            selected_nodes.extend(page_nodes[:self.max_per_page])
        
        # Sort all selected nodes by score
        selected_nodes.sort(key=lambda x: x.score if x.score else 0, reverse=True)
        
        # Second pass: ensure document diversity
        final_nodes = []
        doc_counts = defaultdict(int)
        
        for node in selected_nodes:
            doc_key = (
                node.metadata.get('broker', ''),
                node.metadata.get('ticker', ''),
                node.metadata.get('report_date', '')
            )
            
            if doc_counts[doc_key] < self.max_per_document:
                final_nodes.append(node)
                doc_counts[doc_key] += 1
        
        logger.info(f"Deduplication: {len(nodes)} nodes -> {len(final_nodes)} nodes")
        
        return final_nodes


class ContentTypeDiversifier(BaseNodePostprocessor):
    """
    Ensure diversity of content types (text, table, image) in results.
    """
    
    min_types: int = Field(default=2, description="Try to include at least this many different content types")
    prefer_diverse: bool = Field(default=True, description="If True, prioritize diversity over pure relevance")
    
    def __init__(self, min_types: int = 2, prefer_diverse: bool = True, **kwargs):
        """
        Args:
            min_types: Try to include at least this many different content types
            prefer_diverse: If True, prioritize diversity over pure relevance
        """
        super().__init__(min_types=min_types, prefer_diverse=prefer_diverse, **kwargs)
    
    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        """
        Postprocess nodes to ensure content type diversity.
        """
        if not self.prefer_diverse:
            return nodes
        
        # Group by content type
        type_groups = defaultdict(list)
        for node in nodes:
            content_type = node.metadata.get('content_type', 'text')
            type_groups[content_type].append(node)
        
        # If we already have diversity, return as is
        if len(type_groups) >= self.min_types:
            return nodes
        
        # Otherwise, try to build a diverse set
        final_nodes = []
        
        # Take one from each type first (round-robin)
        type_iterators = {ctype: iter(nodes) for ctype, nodes in type_groups.items()}
        
        while len(final_nodes) < len(nodes) and type_iterators:
            made_progress = False
            empty_types = []
            
            for content_type, iterator in type_iterators.items():
                try:
                    node = next(iterator)
                    final_nodes.append(node)
                    made_progress = True
                    
                    if len(final_nodes) >= len(nodes):
                        break
                except StopIteration:
                    empty_types.append(content_type)
            
            # Remove exhausted iterators
            for ctype in empty_types:
                del type_iterators[ctype]
            
            if not made_progress:
                break
        
        # Sort by score to maintain relevance
        final_nodes.sort(key=lambda x: x.score if x.score else 0, reverse=True)
        
        return final_nodes


class SemanticDeduplicator(BaseNodePostprocessor):
    """
    Remove semantically similar nodes based on text overlap.
    """
    
    similarity_threshold: float = Field(default=0.8, description="Nodes with > this similarity are considered duplicates")
    
    def __init__(self, similarity_threshold: float = 0.8, **kwargs):
        """
        Args:
            similarity_threshold: Nodes with > this similarity are considered duplicates
        """
        super().__init__(similarity_threshold=similarity_threshold, **kwargs)
    
    def _calculate_overlap(self, text1: str, text2: str) -> float:
        """
        Calculate text overlap ratio using simple token overlap.
        """
        if not text1 or not text2:
            return 0.0
        
        # Simple token-based overlap
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        """
        Remove nodes with high text overlap.
        """
        if len(nodes) <= 1:
            return nodes
        
        final_nodes = [nodes[0]]  # Always keep the highest scoring node
        
        for candidate in nodes[1:]:
            # Check overlap with all selected nodes
            is_duplicate = False
            
            for selected in final_nodes:
                overlap = self._calculate_overlap(candidate.text, selected.text)
                
                if overlap > self.similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                final_nodes.append(candidate)
        
        logger.info(f"Semantic dedup: {len(nodes)} nodes -> {len(final_nodes)} nodes")
        
        return final_nodes