"""VectorStore implementation with ChromaDB for RAG capabilities."""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

from ..core.config import settings
from .manager import DatabaseManager
from .models import KnowledgeBase, SystemLog, SystemLogSeverity

logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    """Base exception for VectorStore operations."""
    pass


class VectorStore:
    """
    VectorStore implementation with ChromaDB integration for RAG capabilities.
    
    Features:
    - Document embedding and storage
    - Semantic similarity search
    - Incremental updates with change detection
    - Performance caching and optimization
    - Integration with knowledge base
    """
    
    def __init__(
        self,
        collection_name: str = "knowledge_base_vectors",
        persist_directory: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        cache_size: int = 1000,
        similarity_threshold: float = 0.7
    ):
        """
        Initialize VectorStore with ChromaDB.
        
        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory for persistent storage
            embedding_model: SentenceTransformers model name
            cache_size: Maximum number of cached embeddings
            similarity_threshold: Minimum similarity score for results
        """
        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        self.cache_size = cache_size
        
        # Initialize embedding model
        try:
            self.embedding_model = SentenceTransformer(embedding_model)
            logger.info(f"Loaded embedding model: {embedding_model}")
        except Exception as e:
            logger.error(f"Failed to load embedding model {embedding_model}: {e}")
            raise VectorStoreError(f"Failed to initialize embedding model: {e}")
        
        # Initialize ChromaDB client
        self.persist_directory = persist_directory or "./data/vectorstore"
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info(f"Initialized ChromaDB client with persist directory: {self.persist_directory}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise VectorStoreError(f"Failed to initialize ChromaDB: {e}")
        
        # Get or create collection
        try:
            self.collection = self._get_or_create_collection()
            logger.info(f"Using ChromaDB collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to initialize collection: {e}")
            raise VectorStoreError(f"Failed to initialize collection: {e}")
        
        # Initialize performance cache
        self._embedding_cache: Dict[str, List[float]] = {}
        self._search_cache: Dict[str, List[Dict]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        
        # Performance metrics
        self.metrics = {
            "embeddings_generated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "search_queries": 0,
            "documents_indexed": 0,
            "last_sync": None
        }
        
        # Database manager for logging and KB integration
        self.db_manager = DatabaseManager()
    
    def _get_or_create_collection(self):
        """Get existing collection or create new one."""
        try:
            # Try to get existing collection
            collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"Found existing collection: {self.collection_name}")
            return collection
        except Exception:
            # Create new collection if it doesn't exist
            embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {self.collection_name}")
            return collection
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate content hash for change detection."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _get_cached_embedding(self, content: str) -> Optional[List[float]]:
        """Get embedding from cache if available and not expired."""
        cache_key = self._generate_content_hash(content)
        
        if cache_key in self._embedding_cache:
            # Check if cache entry is still valid (24 hours)
            if cache_key in self._cache_timestamps:
                age = time.time() - self._cache_timestamps[cache_key]
                if age < 24 * 3600:  # 24 hours
                    self.metrics["cache_hits"] += 1
                    return self._embedding_cache[cache_key]
                else:
                    # Remove expired entry
                    del self._embedding_cache[cache_key]
                    del self._cache_timestamps[cache_key]
        
        self.metrics["cache_misses"] += 1
        return None
    
    def _cache_embedding(self, content: str, embedding: List[float]):
        """Cache embedding with LRU eviction."""
        cache_key = self._generate_content_hash(content)
        
        # Evict oldest entries if cache is full
        if len(self._embedding_cache) >= self.cache_size:
            # Remove oldest entry
            oldest_key = min(self._cache_timestamps.keys(), 
                           key=lambda k: self._cache_timestamps[k])
            del self._embedding_cache[oldest_key]
            del self._cache_timestamps[oldest_key]
        
        self._embedding_cache[cache_key] = embedding
        self._cache_timestamps[cache_key] = time.time()
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text with caching."""
        # Check cache first
        cached_embedding = self._get_cached_embedding(text)
        if cached_embedding is not None:
            return cached_embedding
        
        # Generate new embedding
        try:
            embedding = self.embedding_model.encode(text, normalize_embeddings=True)
            embedding_list = embedding.tolist()
            
            # Cache the embedding
            self._cache_embedding(text, embedding_list)
            self.metrics["embeddings_generated"] += 1
            
            return embedding_list
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise VectorStoreError(f"Embedding generation failed: {e}")
    
    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        force_update: bool = False
    ) -> bool:
        """
        Add or update document in vector store.
        
        Args:
            doc_id: Unique document identifier
            content: Document text content
            metadata: Optional document metadata
            force_update: Force update even if content unchanged
            
        Returns:
            bool: True if document was added/updated, False if skipped
        """
        if not content or not content.strip():
            logger.warning(f"Skipping empty content for document {doc_id}")
            return False
        
        try:
            # Check if document needs updating
            content_hash = self._generate_content_hash(content)
            
            if not force_update:
                # Check if document already exists with same content
                try:
                    existing = self.collection.get(ids=[doc_id])
                    if existing['ids'] and existing['metadatas'][0]:
                        existing_hash = existing['metadatas'][0].get('content_hash')
                        if existing_hash == content_hash:
                            logger.debug(f"Document {doc_id} unchanged, skipping update")
                            return False
                except Exception:
                    # Document doesn't exist, proceed with adding
                    pass
            
            # Prepare metadata
            doc_metadata = metadata or {}
            doc_metadata.update({
                'content_hash': content_hash,
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'content_length': len(content)
            })
            
            # Generate embedding
            embedding = self._generate_embedding(content)
            
            # Add/update document in collection
            self.collection.upsert(
                ids=[doc_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[doc_metadata]
            )
            
            self.metrics["documents_indexed"] += 1
            logger.info(f"Successfully indexed document {doc_id}")
            
            # Log operation
            self._log_operation("document_indexed", {
                "doc_id": doc_id,
                "content_length": len(content),
                "metadata_keys": list(doc_metadata.keys())
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document {doc_id}: {e}")
            self._log_operation("document_index_failed", {
                "doc_id": doc_id,
                "error": str(e)
            }, severity=SystemLogSeverity.ERROR)
            raise VectorStoreError(f"Failed to add document {doc_id}: {e}")
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
        min_similarity: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query: Search query text
            n_results: Maximum number of results to return
            filter_metadata: Optional metadata filters
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of matching documents with scores and metadata
        """
        if not query or not query.strip():
            logger.warning("Empty search query provided")
            return []
        
        # Check search cache
        cache_key = f"{query}_{n_results}_{str(filter_metadata)}_{min_similarity}"
        cached_results = self._search_cache.get(cache_key)
        if cached_results and cache_key in self._cache_timestamps:
            # Check cache age (5 minutes for search results)
            age = time.time() - self._cache_timestamps[cache_key]
            if age < 300:  # 5 minutes
                logger.debug(f"Returning cached search results for: {query[:50]}...")
                return cached_results
        
        try:
            start_time = time.time()
            
            # Generate query embedding
            query_embedding = self._generate_embedding(query)
            
            # Prepare search parameters
            search_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"]
            }
            
            # Add metadata filtering if provided
            if filter_metadata:
                search_kwargs["where"] = filter_metadata
            
            # Execute search
            results = self.collection.query(**search_kwargs)
            
            # Process results
            processed_results = []
            if results['ids'][0]:  # Check if we have results
                for i, doc_id in enumerate(results['ids'][0]):
                    distance = results['distances'][0][i]
                    similarity = 1 - distance  # Convert distance to similarity
                    
                    # Apply similarity threshold
                    threshold = min_similarity or self.similarity_threshold
                    if similarity < threshold:
                        continue
                    
                    processed_results.append({
                        'id': doc_id,
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] or {},
                        'similarity': similarity,
                        'distance': distance
                    })
            
            # Sort by similarity (highest first)
            processed_results.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Cache results
            self._search_cache[cache_key] = processed_results
            self._cache_timestamps[cache_key] = time.time()
            
            # Update metrics
            self.metrics["search_queries"] += 1
            search_time = time.time() - start_time
            
            # Log search operation
            self._log_operation("vector_search", {
                "query_length": len(query),
                "results_count": len(processed_results),
                "search_time_ms": round(search_time * 1000, 2),
                "min_similarity": threshold
            })
            
            logger.info(f"Search completed: {len(processed_results)} results in {search_time:.2f}s")
            return processed_results
            
        except Exception as e:
            logger.error(f"Search failed for query '{query[:50]}...': {e}")
            self._log_operation("vector_search_failed", {
                "query_length": len(query),
                "error": str(e)
            }, severity=SystemLogSeverity.ERROR)
            raise VectorStoreError(f"Search failed: {e}")
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete document from vector store.
        
        Args:
            doc_id: Document identifier to delete
            
        Returns:
            bool: True if document was deleted, False if not found
        """
        try:
            # Check if document exists
            existing = self.collection.get(ids=[doc_id])
            if not existing['ids']:
                logger.warning(f"Document {doc_id} not found for deletion")
                return False
            
            # Delete document
            self.collection.delete(ids=[doc_id])
            
            # Clear related caches
            self._clear_search_cache()
            
            logger.info(f"Successfully deleted document {doc_id}")
            self._log_operation("document_deleted", {"doc_id": doc_id})
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            self._log_operation("document_delete_failed", {
                "doc_id": doc_id,
                "error": str(e)
            }, severity=SystemLogSeverity.ERROR)
            return False
    
    def sync_with_knowledge_base(self, force_full_sync: bool = False) -> Dict[str, int]:
        """
        Sync vector store with knowledge base.
        
        Args:
            force_full_sync: Force full sync instead of incremental
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            "processed": 0,
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "errors": 0
        }
        
        try:
            logger.info("Starting knowledge base synchronization...")
            start_time = time.time()
            
            with self.db_manager.get_session() as session:
                # Get active knowledge base articles
                query = session.query(KnowledgeBase).filter(
                    KnowledgeBase.is_deleted == False,
                    KnowledgeBase.status == "published"
                )
                
                # For incremental sync, only get recently updated articles
                if not force_full_sync and self.metrics.get("last_sync"):
                    last_sync = datetime.fromisoformat(self.metrics["last_sync"])
                    query = query.filter(KnowledgeBase.updated_at > last_sync)
                
                articles = query.all()
                
                for article in articles:
                    try:
                        stats["processed"] += 1
                        
                        # Prepare document content
                        content_parts = [
                            f"Title: {article.title}",
                            f"Problem: {article.problem_description}",
                            f"Solution: {article.solution}"
                        ]
                        
                        if article.keywords:
                            content_parts.append(f"Keywords: {', '.join(article.keywords)}")
                        
                        document_content = "\n\n".join(content_parts)
                        
                        # Prepare metadata
                        metadata = {
                            "kb_id": article.id,
                            "title": article.title,
                            "category": article.category,
                            "subcategory": article.subcategory,
                            "success_rate": article.success_rate,
                            "usage_count": article.usage_count,
                            "difficulty_level": article.difficulty_level,
                            "tags": article.tags or [],
                            "created_at": article.created_at.isoformat(),
                            "updated_at": article.updated_at.isoformat()
                        }
                        
                        # Add/update document
                        if self.add_document(
                            doc_id=f"kb_{article.id}",
                            content=document_content,
                            metadata=metadata
                        ):
                            if self._document_exists(f"kb_{article.id}"):
                                stats["updated"] += 1
                            else:
                                stats["added"] += 1
                        
                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(f"Failed to sync article {article.id}: {e}")
            
            # Clean up deleted articles
            if force_full_sync:
                stats["deleted"] = self._cleanup_deleted_articles()
            
            # Update sync timestamp
            self.metrics["last_sync"] = datetime.now(timezone.utc).isoformat()
            
            sync_time = time.time() - start_time
            logger.info(f"Sync completed in {sync_time:.2f}s: {stats}")
            
            # Log sync operation
            self._log_operation("kb_sync_completed", {
                **stats,
                "sync_time_seconds": round(sync_time, 2),
                "force_full_sync": force_full_sync
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Knowledge base sync failed: {e}")
            self._log_operation("kb_sync_failed", {
                "error": str(e),
                "stats": stats
            }, severity=SystemLogSeverity.ERROR)
            raise VectorStoreError(f"Sync failed: {e}")
    
    def _document_exists(self, doc_id: str) -> bool:
        """Check if document exists in collection."""
        try:
            results = self.collection.get(ids=[doc_id])
            return bool(results['ids'])
        except Exception:
            return False
    
    def _cleanup_deleted_articles(self) -> int:
        """Remove documents for deleted knowledge base articles."""
        deleted_count = 0
        
        try:
            # Get all documents in collection
            all_docs = self.collection.get()
            
            if not all_docs['ids']:
                return 0
            
            # Get active KB article IDs
            with self.db_manager.get_session() as session:
                active_articles = session.query(KnowledgeBase.id).filter(
                    KnowledgeBase.is_deleted == False,
                    KnowledgeBase.status == "published"
                ).all()
                active_ids = {f"kb_{article.id}" for article in active_articles}
            
            # Find documents to delete
            docs_to_delete = []
            for doc_id in all_docs['ids']:
                if doc_id.startswith('kb_') and doc_id not in active_ids:
                    docs_to_delete.append(doc_id)
            
            # Delete obsolete documents
            if docs_to_delete:
                self.collection.delete(ids=docs_to_delete)
                deleted_count = len(docs_to_delete)
                logger.info(f"Cleaned up {deleted_count} obsolete documents")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0
    
    def _clear_search_cache(self):
        """Clear search result cache."""
        self._search_cache.clear()
        # Keep timestamp cache for embedding cache
        search_keys = [k for k in self._cache_timestamps.keys() 
                      if k in self._search_cache]
        for key in search_keys:
            del self._cache_timestamps[key]
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get vector store collection statistics."""
        try:
            count_result = self.collection.count()
            
            return {
                "collection_name": self.collection_name,
                "document_count": count_result,
                "embedding_cache_size": len(self._embedding_cache),
                "search_cache_size": len(self._search_cache),
                "metrics": self.metrics,
                "similarity_threshold": self.similarity_threshold
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"error": str(e)}
    
    def _log_operation(
        self,
        event_type: str,
        details: Dict[str, Any],
        severity: SystemLogSeverity = SystemLogSeverity.INFO
    ):
        """Log vector store operation."""
        try:
            with self.db_manager.get_session() as session:
                log_entry = SystemLog(
                    event_type=f"vectorstore_{event_type}",
                    severity=severity.value,
                    source="VectorStore",
                    message=f"VectorStore operation: {event_type}",
                    details=details
                )
                session.add(log_entry)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to log operation: {e}")


class RAGService:
    """
    Retrieval-Augmented Generation service combining vector search with knowledge base.
    """
    
    def __init__(self, vector_store: VectorStore):
        """Initialize RAG service with vector store."""
        self.vector_store = vector_store
        self.db_manager = DatabaseManager()
    
    def find_relevant_solutions(
        self,
        problem_description: str,
        max_results: int = 5,
        category_filter: Optional[str] = None,
        min_similarity: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Find relevant solutions for a problem using vector similarity search.
        
        Args:
            problem_description: Description of the problem
            max_results: Maximum number of solutions to return
            category_filter: Optional category to filter results
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of relevant solutions with metadata and similarity scores
        """
        try:
            # Prepare search filters
            filters = {}
            if category_filter:
                filters["category"] = category_filter
            
            # Search for similar documents
            search_results = self.vector_store.search(
                query=problem_description,
                n_results=max_results,
                filter_metadata=filters if filters else None,
                min_similarity=min_similarity
            )
            
            # Enrich results with additional KB data
            enriched_results = []
            for result in search_results:
                kb_id = result['metadata'].get('kb_id')
                if kb_id:
                    # Get full knowledge base article
                    with self.db_manager.get_session() as session:
                        article = session.query(KnowledgeBase).filter(
                            KnowledgeBase.id == kb_id
                        ).first()
                        
                        if article:
                            enriched_result = {
                                **result,
                                'kb_article': {
                                    'id': article.id,
                                    'title': article.title,
                                    'problem_description': article.problem_description,
                                    'solution': article.solution,
                                    'category': article.category,
                                    'success_rate': article.success_rate,
                                    'usage_count': article.usage_count,
                                    'difficulty_level': article.difficulty_level,
                                    'estimated_time_minutes': article.estimated_time_minutes,
                                    'tags': article.tags
                                }
                            }
                            enriched_results.append(enriched_result)
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"Failed to find relevant solutions: {e}")
            return []
    
    def get_context_for_llm(
        self,
        user_query: str,
        max_context_length: int = 2000,
        max_solutions: int = 3
    ) -> str:
        """
        Get formatted context for LLM based on user query.
        
        Args:
            user_query: User's question or problem description
            max_context_length: Maximum length of context string
            max_solutions: Maximum number of solutions to include
            
        Returns:
            Formatted context string for LLM
        """
        try:
            solutions = self.find_relevant_solutions(
                problem_description=user_query,
                max_results=max_solutions,
                min_similarity=0.5
            )
            
            if not solutions:
                return "No relevant solutions found in the knowledge base."
            
            context_parts = ["Relevant solutions from knowledge base:"]
            current_length = len(context_parts[0])
            
            for i, solution in enumerate(solutions, 1):
                kb_article = solution.get('kb_article', {})
                similarity = solution.get('similarity', 0)
                
                solution_text = f"""
{i}. {kb_article.get('title', 'Unknown Title')} (Similarity: {similarity:.2f})
   Problem: {kb_article.get('problem_description', 'N/A')[:200]}...
   Solution: {kb_article.get('solution', 'N/A')[:300]}...
   Success Rate: {kb_article.get('success_rate', 0):.1%}
"""
                
                if current_length + len(solution_text) > max_context_length:
                    break
                
                context_parts.append(solution_text)
                current_length += len(solution_text)
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to get context for LLM: {e}")
            return f"Error retrieving context: {e}"


# Global vector store instance
_vector_store_instance: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get global vector store instance (singleton pattern)."""
    global _vector_store_instance
    
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    
    return _vector_store_instance


def get_rag_service() -> RAGService:
    """Get RAG service instance."""
    return RAGService(get_vector_store())