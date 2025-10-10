# apps/chat/llamaindex_setup.py
"""
LlamaIndex configuration with OpenAI.
This module sets up:
- OpenAI LLM (gpt-4o-mini for reasoning)
- OpenAI embeddings (text-embedding-3-small)
- OpenAI multimodal (gpt-4o for vision)
- pgvector storage
- Global settings
"""

from llama_index.core import Settings, VectorStoreIndex, StorageContext
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.multi_modal_llms.openai import OpenAIMultiModal
from django.conf import settings as django_settings
import logging
import os

logger = logging.getLogger(__name__)

# Singleton instances
_llm = None
_embed_model = None
_vision_model = None
_vector_store = None
_index = None


def get_llm():
    """Get or create OpenAI LLM instance (gpt-4o-mini)"""
    global _llm
    if _llm is None:
        if not django_settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set. Please set it in your .env file.")
            
        logger.info(f"Initializing OpenAI LLM: {django_settings.OPENAI_LLM_MODEL}")
        
        # Set API key in environment for OpenAI SDK
        os.environ['OPENAI_API_KEY'] = str(django_settings.OPENAI_API_KEY)
        
        _llm = OpenAI(
            model=django_settings.OPENAI_LLM_MODEL,
            temperature=0.1,  # Low temperature for factual responses
            max_tokens=2048,
        )
    return _llm


def get_embed_model():
    """Get or create OpenAI embedding model (text-embedding-3-small)"""
    global _embed_model
    if _embed_model is None:
        if not django_settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set. Please set it in your .env file.")
            
        logger.info(f"Initializing OpenAI Embeddings: {django_settings.OPENAI_EMBED_MODEL}")
        
        os.environ['OPENAI_API_KEY'] = django_settings.OPENAI_API_KEY
        
        _embed_model = OpenAIEmbedding(
            model=django_settings.OPENAI_EMBED_MODEL,
            embed_batch_size=100,  # Batch size for efficiency
        )
    return _embed_model


def get_vision_model():
    """Get or create OpenAI vision model (gpt-4o)"""
    global _vision_model
    if _vision_model is None:
        if not django_settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set. Please set it in your .env file.")
            
        logger.info(f"Initializing OpenAI Vision: {django_settings.OPENAI_VISION_MODEL}")
        
        os.environ['OPENAI_API_KEY'] = django_settings.OPENAI_API_KEY
        
        _vision_model = OpenAIMultiModal(
            model=django_settings.OPENAI_VISION_MODEL,
            temperature=0.1,
            max_tokens=1024,
        )
    return _vision_model


def get_vector_store():
    """Get or create pgvector store"""
    global _vector_store
    if _vector_store is None:
        logger.info("Initializing pgvector store")
        
        db_config = django_settings.DATABASES['default']
        
        # Validate database configuration
        required_db_fields = ['NAME', 'HOST', 'PASSWORD', 'PORT', 'USER']
        for field in required_db_fields:
            if not db_config.get(field):
                raise ValueError(f"Database configuration missing required field: {field}")
        
        logger.info(f"Connecting to database: {db_config['NAME']} at {db_config['HOST']}:{db_config['PORT']}")
        
        # text-embedding-3-small has 1536 dimensions
        _vector_store = PGVectorStore.from_params(
            database=db_config['NAME'],
            host=db_config['HOST'],
            password=str(db_config['PASSWORD']),  # Ensure it's a string
            port=db_config['PORT'],
            user=db_config['USER'],
            table_name="llama_index_embeddings",
            embed_dim=django_settings.EMBEDDING_DIMENSION,  # 1536 for text-embedding-3-small
        )
    return _vector_store


def configure_llamaindex():
    """Configure global LlamaIndex settings"""
    Settings.llm = get_llm()
    Settings.embed_model = get_embed_model()
    Settings.chunk_size = django_settings.CHUNK_SIZE
    Settings.chunk_overlap = django_settings.CHUNK_OVERLAP
    
    logger.info("LlamaIndex configured successfully with OpenAI")


def get_index(force_reload=False):
    """
    Get or create the vector index.
    Uses singleton pattern to avoid recreating.
    """
    global _index
    
    if _index is None or force_reload:
        logger.info("Loading/creating vector index")
        
        vector_store = get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        try:
            # Try to load existing index
            _index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                storage_context=storage_context,
            )
            logger.info("Loaded existing vector index")
        except Exception as e:
            logger.warning(f"Could not load existing index: {e}. Creating new one.")
            _index = VectorStoreIndex(
                nodes=[],
                storage_context=storage_context,
            )
            logger.info("Created new vector index")
    
    return _index


def reset_index():
    """Reset the index (for testing/debugging)"""
    global _index
    _index = None
    logger.info("Index reset")