# apps/chat/views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from .models import Conversation, Message
from .llamaindex_setup import get_index, configure_llamaindex
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import VectorIndexRetriever
import json

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
            
            # Create query engine with retrieval
            retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=10,
            )
            
            query_engine = RetrieverQueryEngine.from_args(
                retriever=retriever,
                response_mode="compact",
            )
            
            # Get response
            response = query_engine.query(user_message)
        except Exception as rag_error:
            # If RAG fails, provide a fallback response
            print(f"RAG Error: {str(rag_error)}")
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
        
        # Extract sources
        sources = []
        for node in response.source_nodes:
            sources.append({
                'broker': node.metadata.get('broker', 'Unknown'),
                'ticker': node.metadata.get('ticker', ''),
                'report_date': node.metadata.get('report_date', ''),
                'page_number': node.metadata.get('page_number', ''),
                'content_type': node.metadata.get('content_type', 'text'),
                'score': node.score if hasattr(node, 'score') else None,
                'text_preview': node.text[:200] + "..." if len(node.text) > 200 else node.text
            })
        
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
