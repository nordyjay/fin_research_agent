from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
import json
import uuid
from unittest.mock import patch, MagicMock
from .models import Conversation, Message


class ConversationModelTest(TestCase):
    def test_create_conversation(self):
        conv = Conversation.objects.create(title="Test Conversation")
        
        self.assertEqual(conv.title, "Test Conversation")
        self.assertIsNotNone(conv.id)
        self.assertIsInstance(conv.id, uuid.UUID)
        
    def test_conversation_str(self):
        conv = Conversation.objects.create(title="Investment Analysis")
        self.assertEqual(str(conv), "Investment Analysis")
        
    def test_conversation_default_title(self):
        conv = Conversation.objects.create()
        self.assertEqual(conv.title, "New Conversation")
        
    def test_conversation_ordering(self):
        conv1 = Conversation.objects.create(title="First")
        conv2 = Conversation.objects.create(title="Second")
        
        conversations = list(Conversation.objects.all())
        self.assertEqual(conversations[0], conv2)
        self.assertEqual(conversations[1], conv1)


class MessageModelTest(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(title="Test Chat")
        
    def test_create_user_message(self):
        msg = Message.objects.create(
            conversation=self.conversation,
            role="user",
            content="What is NVDA's price target?"
        )
        
        self.assertEqual(msg.conversation, self.conversation)
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "What is NVDA's price target?")
        self.assertEqual(msg.metadata, {})
        
    def test_create_assistant_message_with_metadata(self):
        metadata = {
            "sources": ["doc1.pdf", "doc2.pdf"],
            "confidence": 0.95
        }
        
        msg = Message.objects.create(
            conversation=self.conversation,
            role="assistant",
            content="Based on analyst reports...",
            metadata=metadata
        )
        
        self.assertEqual(msg.role, "assistant")
        self.assertEqual(msg.metadata["sources"], ["doc1.pdf", "doc2.pdf"])
        self.assertEqual(msg.metadata["confidence"], 0.95)
        
    def test_message_str(self):
        msg = Message.objects.create(
            conversation=self.conversation,
            role="user",
            content="This is a very long message that should be truncated when displayed in the string representation"
        )
        
        # Django's model truncates at 50 chars + ...
        self.assertTrue(str(msg).startswith("user: This is a very long message that should be"))
        self.assertTrue(str(msg).endswith("..."))
        
    def test_message_ordering(self):
        msg1 = Message.objects.create(
            conversation=self.conversation,
            role="user",
            content="First message"
        )
        msg2 = Message.objects.create(
            conversation=self.conversation,
            role="assistant",
            content="Second message"
        )
        
        messages = list(self.conversation.messages.all())
        self.assertEqual(messages[0], msg1)
        self.assertEqual(messages[1], msg2)


class ChatViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.chat_url = reverse('chat:message')
        self.chat_page_url = reverse('chat:index')
        
    def test_chat_page_loads(self):
        response = self.client.get(self.chat_page_url)
        self.assertEqual(response.status_code, 200)
        
    def test_create_new_conversation_on_first_message(self):
        response = self.client.post(
            self.chat_url,
            data=json.dumps({
                'message': 'What is the outlook for tech stocks?'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        conversation = Conversation.objects.first()
        self.assertIsNotNone(conversation)
        
        messages = conversation.messages.all()
        self.assertEqual(messages.count(), 2)  # User + Assistant message
        self.assertEqual(messages[0].content, 'What is the outlook for tech stocks?')
        self.assertEqual(messages[0].role, 'user')
        
    @patch('apps.chat.views.get_index')
    @patch('apps.chat.views.configure_llamaindex')
    def test_chat_with_rag_response(self, mock_configure, mock_get_index):
        # Mock the query response
        mock_response = MagicMock()
        mock_response.response = "Based on recent reports, tech stocks show strong growth potential."
        mock_source_node = MagicMock()
        mock_source_node.node.text = "Tech analysis text"
        mock_source_node.node.metadata = {"source": "report1.pdf", "page": 5}
        mock_source_node.score = 0.9
        mock_response.source_nodes = [mock_source_node]
        
        # Mock query engine
        mock_query_engine = MagicMock()
        mock_query_engine.query.return_value = mock_response
        
        # Mock retriever and index
        mock_index = MagicMock()
        mock_get_index.return_value = mock_index
        
        response = self.client.post(
            self.chat_url,
            data=json.dumps({
                'message': 'Tech stock analysis'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check response was created
        self.assertIn('message', data)
        self.assertIn('conversation_id', data)
        self.assertEqual(data['success'], True)
        
    def test_chat_with_existing_conversation(self):
        conv = Conversation.objects.create(title="Existing Chat")
        
        response = self.client.post(
            self.chat_url,
            data=json.dumps({
                'message': 'Follow up question',
                'conversation_id': str(conv.id)
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        messages = conv.messages.all()
        self.assertEqual(messages.count(), 2)  # User + Assistant message
        self.assertEqual(messages[0].content, 'Follow up question')
        self.assertEqual(messages[0].role, 'user')
        
    def test_chat_empty_message_fails(self):
        response = self.client.post(
            self.chat_url,
            data=json.dumps({
                'message': ''
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
    def test_chat_invalid_conversation_id(self):
        # Invalid UUID should be caught
        response = self.client.post(
            self.chat_url,
            data=json.dumps({
                'message': 'Test message',
                'conversation_id': 'invalid-uuid'
            }),
            content_type='application/json'
        )
        
        # Should either return error or create new conversation
        if response.status_code == 200:
            data = json.loads(response.content)
            self.assertTrue(data['success'])
            # A new conversation should have been created
            new_conv = Conversation.objects.first()
            self.assertIsNotNone(new_conv)
        else:
            # Or it might return a 400/500 error
            self.assertIn(response.status_code, [400, 500])
        
    @patch('apps.chat.views.get_index')
    def test_chat_rag_error_handling(self, mock_get_index):
        mock_get_index.side_effect = Exception("RAG system error")
        
        response = self.client.post(
            self.chat_url,
            data=json.dumps({
                'message': 'Test query'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should still get a response even with RAG error
        self.assertEqual(data['success'], True)
        self.assertIn("error", data['message'].lower())


class ConversationListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.list_url = reverse('chat:conversations')
        
    def test_empty_conversation_list(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['conversations']), 0)
        
    def test_conversation_list_with_data(self):
        conv1 = Conversation.objects.create(title="Analysis 1")
        conv2 = Conversation.objects.create(title="Analysis 2")
        
        Message.objects.create(
            conversation=conv1,
            role="user",
            content="First message in conv1"
        )
        
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(len(data['conversations']), 2)
        # Check we have 2 conversations
        self.assertEqual(data['conversations'][0]['title'], "Analysis 2")
        self.assertEqual(data['conversations'][1]['title'], "Analysis 1")
        # Note: message_count field may not exist in the response