# apps/chat/views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from .models import Conversation, Message
from .llamaindex_setup import get_index, configure_llamaindex
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import VectorIndexRetriever
from .node_postprocessors import PageDeduplicator, ContentTypeDiversifier, SemanticDeduplicator
import json
import os
import markdown
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def chat_interface(request):
    """Main ChatGPT-style interface"""
    from django.conf import settings
    return render(request, 'chat/chatgpt_style.html', {
        'OPENAI_API_KEY': settings.OPENAI_API_KEY
    })

def test_view(request):
    """Test view to check if views are working"""
    return render(request, 'chat/test.html')

def get_conversations(request):
    """Get list of conversations via AJAX"""
    conversations = Conversation.objects.all().order_by('-updated_at')[:20]
    return JsonResponse({
        'conversations': [
            {
                'id': str(conv.id),
                'title': conv.title,
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat()
            }
            for conv in conversations
        ]
    })

def get_messages(request, conversation_id):
    """Get messages for a specific conversation"""
    try:
        conversation = Conversation.objects.get(id=conversation_id)
        messages = conversation.messages.all()
        
        return JsonResponse({
            'success': True,
            'conversation': {
                'id': str(conversation.id),
                'title': conversation.title
            },
            'messages': [
                {
                    'id': str(msg.id),
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at.isoformat(),
                    'metadata': msg.metadata
                }
                for msg in messages
            ]
        })
    except Conversation.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Conversation not found'}, status=404)

def chat_index(request):
    """Main chat interface"""
    print("DEBUG: chat_index view called")
    try:
        conversations = Conversation.objects.all()[:10]
        print(f"DEBUG: Found {conversations.count()} conversations")
        
        # Let's test if base.html is found
        from django.template.loader import get_template
        try:
            base_template = get_template('base.html')
            print("DEBUG: base.html found successfully")
        except Exception as e:
            print(f"DEBUG: base.html not found: {e}")
        
        # Force debug mode to see template errors
        from django.template import loader
        from django.http import HttpResponse
        
        try:
            template = loader.get_template('chat/index.html')
            html = template.render({'conversations': conversations}, request)
            print(f"DEBUG: Rendered HTML length: {len(html)}")
            print(f"DEBUG: Rendered HTML content: '{html}'")
            print(f"DEBUG: HTML repr: {repr(html)}")
            
            # Let's also try a simple template string to test
            from django.template import Template, Context
            simple = Template("<h1>Test: {{ test }}</h1>")
            simple_html = simple.render(Context({'test': 'Hello World'}))
            print(f"DEBUG: Simple template renders: '{simple_html}'")
            
            if len(html) == 0:
                # Return simple HTML to verify response works
                return HttpResponse("<h1>Template rendered but was empty. Conversations: " + str(conversations.count()) + "</h1>")
            
            return HttpResponse(html)
        except Exception as template_err:
            print(f"TEMPLATE ERROR: {template_err}")
            import traceback
            traceback.print_exc()
            return HttpResponse(f"Template rendering error: {template_err}")
    except Exception as e:
        print(f"ERROR in chat_index: {str(e)}")
        return HttpResponse(f"Error: {str(e)}")

def chat_detail(request, conversation_id):
    """Individual conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    messages = conversation.messages.all()
    
    return render(request, 'chat/chat.html', {
        'conversation': conversation,
        'messages': messages
    })

@require_POST
def chat_message(request):
    """Handle chat messages"""
    try:
        data = json.loads(request.body)
        conversation_id = data.get('conversation_id')
        user_message = data.get('message')
        
        # Get or create conversation
        if conversation_id:
            conversation = Conversation.objects.get(id=conversation_id)
        else:
            conversation = Conversation.objects.create(
                title=user_message[:50] + "..." if len(user_message) > 50 else user_message
            )
        
        if not user_message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty'
            }, status=400)
            
        # Save user message
        user_msg = Message.objects.create(
            conversation=conversation,
            role='user',
            content=user_message
        )
        
        # Check if OpenAI API key is configured
        from django.conf import settings
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == 'your-openai-api-key-here':
            # Return a helpful message if API key is not set
            assistant_msg = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content="I notice the OpenAI API key is not configured. Please set your OPENAI_API_KEY in the .env file to enable AI responses. For now, I can't process your query about: " + user_message
            )
            
            return JsonResponse({
                'success': True,
                'conversation_id': str(conversation.id),
                'message': assistant_msg.content,
                'sources': []
            })
        
        try:
            # Query LlamaIndex
            configure_llamaindex()
            index = get_index()
            
            # Create retriever - fetch more results initially for diversity
            retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=15,  # Fetch more initially, postprocessors will filter
            )
            
            logger.info(f"Created retriever with top_k=15")
            
            # Create postprocessors for deduplication and diversity
            postprocessors = [
                PageDeduplicator(max_per_page=1, max_per_document=2),
                SemanticDeduplicator(similarity_threshold=0.8),
                ContentTypeDiversifier(min_types=2, prefer_diverse=True),
            ]
            
            logger.info(f"Created {len(postprocessors)} postprocessors for deduplication")
            
            # Create query engine with postprocessors
            query_engine = RetrieverQueryEngine.from_args(
                retriever=retriever,
                response_mode="compact",
                node_postprocessors=postprocessors,
            )
            
            # Get response
            logger.info(f"Querying with message: {user_message[:50]}...")
            response = query_engine.query(user_message)
            logger.info(f"Got {len(response.source_nodes)} source nodes after processing")
        except Exception as rag_error:
            # If RAG fails, provide a fallback response
            logger.error(f"RAG Error: {str(rag_error)}", exc_info=True)
            assistant_msg = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=f"I encountered an error while processing your request. This might be because no documents have been uploaded yet or there's an issue with the vector database. Error: {str(rag_error)}"
            )
            
            return JsonResponse({
                'success': True,
                'conversation_id': str(conversation.id),
                'message': assistant_msg.content,
                'sources': []
            })
        
        # Extract sources with node IDs for artifact retrieval
        sources = []
        for idx, node in enumerate(response.source_nodes):
            # Debug: check what attributes the node has
            print(f"Node {idx}: type={type(node)}, has node_id={hasattr(node, 'node_id')}")
            if hasattr(node, 'node_id'):
                print(f"  node_id: {node.node_id}")
            
            # Try different ways to get node ID
            node_id = None
            if hasattr(node, 'node_id'):
                node_id = node.node_id
            elif hasattr(node, 'id_'):
                node_id = node.id_
            elif hasattr(node, 'doc_id'):
                node_id = node.doc_id
            else:
                # Generate a temporary ID based on content hash
                import hashlib
                node_id = hashlib.md5(node.text.encode()).hexdigest()[:12]
                print(f"  Generated node_id: {node_id}")
            
            source_data = {
                'node_id': node_id,
                'broker': node.metadata.get('broker', 'Unknown'),
                'ticker': node.metadata.get('ticker', ''),
                'report_date': node.metadata.get('report_date', ''),
                'page_number': node.metadata.get('page_number', ''),
                'content_type': node.metadata.get('content_type', 'text'),
                'score': node.score if hasattr(node, 'score') else None,
                'text_preview': node.text[:200] + "..." if len(node.text) > 200 else node.text,
                'text': node.text,  # Include full text for modal display
                'metadata': node.metadata,  # This should contain document_id if present
                'document_id': node.metadata.get('document_id', None)  # Also expose at top level
            }
            
            # Debug logging to see if document_id is present
            if node.metadata.get('document_id'):
                logger.info(f"Source has document_id: {node.metadata.get('document_id')}")
            else:
                logger.info(f"Source missing document_id. Metadata keys: {list(node.metadata.keys())}")
            
            # Add image path if available
            if 'image_path' in node.metadata:
                source_data['image_path'] = node.metadata['image_path']
            
            sources.append(source_data)
        
        # Save assistant message
        assistant_msg = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=str(response),
            metadata={'sources': sources}
        )
        
        return JsonResponse({
            'success': True,
            'conversation_id': str(conversation.id),
            'message': str(response),
            'sources': sources
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@require_GET
def get_artifact(request, node_id):
    """Retrieve artifact content (image, table, or text) by node ID"""
    try:
        # Log the request
        print(f"Getting artifact for node_id: {node_id}")
        
        # Get the index and retrieve the node
        configure_llamaindex()
        index = get_index()
        
        # For now, let's create a simple test response to see if the issue is with node retrieval
        # or with the JSON serialization
        if node_id == "test":
            return JsonResponse({
                'type': 'text',
                'content': 'This is a test response with\nnewlines\tand tabs.',
                'metadata': {
                    'broker': 'Test Broker',
                    'ticker': 'TEST',
                    'page': 1,
                    'date': '2024-01-01'
                }
            })
        
        # Get node from storage
        node = None
        try:
            # First try the standard docstore
            docstore = getattr(index, 'docstore', None)
            if docstore:
                node = docstore.get_node(node_id)
                print(f"Got node from docstore: {node is not None}")
        except Exception as e:
            print(f"Error getting node from docstore: {e}")
            
        if not node:
            try:
                # Try to get from the vector store's storage context
                storage_context = getattr(index, 'storage_context', None)
                if storage_context and hasattr(storage_context, 'docstore'):
                    node = storage_context.docstore.get_node(node_id)
                    print(f"Got node from storage_context: {node is not None}")
            except Exception as e:
                print(f"Error getting node from storage_context: {e}")
        
        if not node:
            # As a last resort, try to search for the node
            print(f"Could not find node {node_id} in any store")
            return JsonResponse({'error': f'Artifact not found: {node_id}'}, status=404)
        
        if not node:
            return JsonResponse({'error': 'Artifact not found'}, status=404)
        
        content_type = node.metadata.get('content_type', 'text')
        
        if content_type == 'image':
            # Return image file
            image_path = node.metadata.get('image_path')
            if image_path and os.path.exists(image_path):
                return FileResponse(open(image_path, 'rb'), content_type='image/png')
            else:
                return JsonResponse({'error': 'Image file not found'}, status=404)
                
        elif content_type == 'table':
            # Extract table from text and convert to HTML
            text = node.text
            
            # Find the table markdown in the text
            lines = text.split('\n')
            table_start = None
            table_lines = []
            
            for i, line in enumerate(lines):
                if line.strip().startswith('|'):
                    if table_start is None:
                        table_start = i
                    table_lines.append(line)
                elif table_start is not None and not line.strip().startswith('|'):
                    break
            
            if table_lines:
                # Convert markdown table to HTML
                md = markdown.Markdown(extensions=['tables'])
                table_html = md.convert('\n'.join(table_lines))
                
                # Clean the HTML to ensure it's JSON-safe
                table_html = table_html.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                
                return JsonResponse({
                    'type': 'table',
                    'content': table_html,
                    'metadata': {
                        'broker': node.metadata.get('broker'),
                        'ticker': node.metadata.get('ticker'),
                        'page': node.metadata.get('page_number'),
                        'date': node.metadata.get('report_date')
                    }
                }, json_dumps_params={'ensure_ascii': False})
            else:
                # Escape the text for HTML
                import html
                escaped_text = html.escape(text)
                
                return JsonResponse({
                    'type': 'table',
                    'content': f'<pre>{escaped_text}</pre>',
                    'metadata': {
                        'broker': node.metadata.get('broker'),
                        'ticker': node.metadata.get('ticker'),
                        'page': node.metadata.get('page_number'),
                        'date': node.metadata.get('report_date')
                    }
                }, json_dumps_params={'ensure_ascii': False})
                
        else:  # text
            # Let Django's JsonResponse handle the serialization properly
            return JsonResponse({
                'type': 'text',
                'content': node.text,  # Django will properly escape this
                'metadata': {
                    'broker': node.metadata.get('broker'),
                    'ticker': node.metadata.get('ticker'),
                    'page': node.metadata.get('page_number'),
                    'date': node.metadata.get('report_date')
                }
            }, json_dumps_params={'ensure_ascii': False})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)