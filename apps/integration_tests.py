from django.test import TestCase, TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock, Mock
import json
import hashlib
from apps.documents.models import BrokerDocument
from apps.chat.models import Conversation, Message
from apps.chat.document_processor import MultimodalDocumentProcessor


class DocumentProcessingIntegrationTest(TransactionTestCase):
    """Integration tests for the full document processing pipeline"""
    
    def setUp(self):
        self.pdf_content = b"%PDF-1.4\nTest PDF content for integration testing"
        self.pdf_file = SimpleUploadedFile(
            "integration_test.pdf", 
            self.pdf_content, 
            content_type="application/pdf"
        )
        
    @patch('apps.chat.document_processor.LlamaParse')
    @patch('apps.chat.document_processor.OpenAIEmbedding')
    @patch('apps.chat.document_processor.VectorStoreIndex')
    def test_full_document_processing_pipeline(self, mock_index, mock_embedding, mock_parser):
        """Test complete document processing from upload to vector storage"""
        
        # Mock LlamaParse
        mock_document = MagicMock()
        mock_document.text = "NVIDIA Corporation (NVDA) Analysis by Goldman Sachs\nDate: January 15, 2024\nPrice target: $850"
        mock_document.metadata = {'page': 1}
        
        mock_parser_instance = MagicMock()
        mock_parser_instance.load_data.return_value = [mock_document]
        mock_parser.return_value = mock_parser_instance
        
        # Mock embedding
        mock_embedding_instance = MagicMock()
        mock_embedding.return_value = mock_embedding_instance
        
        # Mock vector index
        mock_index_instance = MagicMock()
        mock_index.from_documents.return_value = mock_index_instance
        
        # Create document
        doc = BrokerDocument.objects.create(
            file=self.pdf_file,
            broker="Goldman Sachs",
            ticker="NVDA",
            report_date="2024-01-15",
            file_hash=hashlib.sha256(self.pdf_content).hexdigest()
        )
        
        # Process document
        processor = MultimodalDocumentProcessor()
        stats = processor.process_pdf(
            pdf_path=doc.file.path,
            broker=doc.broker,
            ticker=doc.ticker,
            report_date=str(doc.report_date)
        )
        
        # Verify processing
        self.assertIsNotNone(stats)
        self.assertTrue(mock_parser.called)
        self.assertTrue(mock_embedding.called)
        self.assertTrue(mock_index.from_documents.called)
        
    @patch('apps.chat.views.get_index')
    @patch('apps.chat.views.configure_llamaindex')
    def test_rag_query_integration(self, mock_configure, mock_get_index):
        """Test RAG query integration from question to response"""
        
        # Setup mocks
        mock_response = MagicMock()
        mock_response.response = "Based on the analysis, NVDA has a price target of $850"
        mock_source_node = MagicMock()
        mock_source_node.node = MagicMock()
        mock_source_node.node.text = "NVDA price target: $850"
        mock_source_node.node.metadata = {
            'broker': 'Goldman Sachs',
            'ticker': 'NVDA',
            'page_label': '5'
        }
        mock_source_node.score = 0.92
        mock_response.source_nodes = [mock_source_node]
        
        mock_query_engine = MagicMock()
        mock_query_engine.query.return_value = mock_response
        
        mock_index = MagicMock()
        mock_get_index.return_value = mock_index
        
        # Send chat message
        response = self.client.post(
            '/chat/message/',
            data=json.dumps({
                'message': "What is NVDA's price target?"
            }),
            content_type='application/json'
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])


class EndToEndChatTest(TransactionTestCase):
    """End-to-end tests for the chat functionality"""
    
    @patch('apps.chat.views.get_index')
    @patch('apps.chat.views.configure_llamaindex')
    def test_complete_chat_flow(self, mock_configure, mock_get_index):
        """Test complete chat flow from user input to response"""
        
        # Mock the query response
        mock_response = MagicMock()
        mock_response.response = "NVIDIA's latest price target from analysts is $850, representing significant upside."
        mock_source_node = MagicMock()
        mock_source_node.node = MagicMock()
        mock_source_node.node.text = 'We maintain our $850 price target...'
        mock_source_node.node.metadata = {
            'broker': 'Goldman Sachs',
            'ticker': 'NVDA',
            'page': '12'
        }
        mock_source_node.score = 0.95
        mock_response.source_nodes = [mock_source_node]
        
        # Mock query engine
        mock_query_engine = MagicMock()
        mock_query_engine.query.return_value = mock_response
        
        # Mock index - need to handle the VectorIndexRetriever and RetrieverQueryEngine creation
        mock_index = MagicMock()
        mock_get_index.return_value = mock_index
        
        # Need to mock the RetrieverQueryEngine
        with patch('apps.chat.views.RetrieverQueryEngine') as mock_engine_class:
            mock_engine_class.from_args.return_value = mock_query_engine
        
        # Send initial message
        response = self.client.post(
            '/chat/',
            data=json.dumps({
                'message': "What's the latest on NVDA?"
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
            # Verify response structure
            self.assertIn('message', data)
            self.assertIn('conversation_id', data)
            self.assertTrue(data['success'])
            self.assertIn('$850', data['message'])
        
        # Verify database state
        conv = Conversation.objects.get(id=data['conversation_id'])
        self.assertEqual(conv.messages.count(), 2)
        
        user_msg = conv.messages.filter(role='user').first()
        self.assertEqual(user_msg.content, "What's the latest on NVDA?")
        
        assistant_msg = conv.messages.filter(role='assistant').first()
        self.assertIn('$850', assistant_msg.content)
        # Check metadata if it exists
        if 'sources' in assistant_msg.metadata:
            self.assertGreater(len(assistant_msg.metadata['sources']), 0)
        
    @patch('apps.chat.views.get_index')
    @patch('apps.chat.views.configure_llamaindex')
    def test_multi_turn_conversation(self, mock_configure, mock_get_index):
        """Test multi-turn conversation with context preservation"""
        
        # Setup mock for query engine
        mock_query_engine = MagicMock()
        
        # First response
        mock_response1 = MagicMock()
        mock_response1.response = "NVDA is trading at $750"
        mock_response1.source_nodes = []
        
        # Second response  
        mock_response2 = MagicMock()
        mock_response2.response = "The price target is $850, implying 13% upside from $750"
        mock_response2.source_nodes = []
        
        # Configure mock to return different responses
        mock_query_engine.query.side_effect = [mock_response1, mock_response2]
        
        # Mock index and engine creation
        mock_index = MagicMock()
        mock_get_index.return_value = mock_index
        
        with patch('apps.chat.views.RetrieverQueryEngine') as mock_engine_class:
            mock_engine_class.from_args.return_value = mock_query_engine
            
            # First turn
            response1 = self.client.post(
                '/chat/message/',
                data=json.dumps({'message': "What's NVDA's current price?"}),
                content_type='application/json'
            )
            
            data1 = json.loads(response1.content)
            conv_id = data1['conversation_id']
            
            # Second turn
            response2 = self.client.post(
                '/chat/message/',
                data=json.dumps({
                    'message': "What's the upside potential?",
                    'conversation_id': conv_id
                }),
                content_type='application/json'
            )
            
            self.assertEqual(response2.status_code, 200)
            data2 = json.loads(response2.content)
            self.assertIn('13% upside', data2['message'])
            
            # Verify conversation has 4 messages (2 user, 2 assistant)
            conv = Conversation.objects.get(id=conv_id)
            self.assertEqual(conv.messages.count(), 4)


class DocumentDeduplicationIntegrationTest(TestCase):
    """Integration tests for document deduplication"""
    
    def test_duplicate_detection_prevents_reprocessing(self):
        """Test that duplicate files are detected and not reprocessed"""
        
        pdf_content = b"%PDF-1.4\nDuplicate test content"
        file_hash = hashlib.sha256(pdf_content).hexdigest()
        
        # Create first document
        doc1 = BrokerDocument.objects.create(
            file=SimpleUploadedFile("first.pdf", pdf_content),
            broker="UBS",
            ticker="AAPL",
            report_date="2024-01-15",
            file_hash=file_hash,
            processed=True
        )
        
        # Attempt to create duplicate
        duplicate_file = SimpleUploadedFile("duplicate.pdf", pdf_content)
        
        response = self.client.post(
            '/documents/upload/',
            {
                'pdf_file': duplicate_file,
                'broker': 'Different Broker',
                'ticker': 'AAPL'
            }
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Verify only one document exists
        self.assertEqual(BrokerDocument.objects.count(), 1)
        
        # Verify warning message
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("already been uploaded" in str(m) for m in messages))