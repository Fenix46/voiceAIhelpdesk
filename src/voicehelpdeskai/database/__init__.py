"""Database layer initialization and utilities."""

from .base import Base, engine, SessionLocal, get_db, create_tables
from .manager import DatabaseManager
from .models import (
    # Core models
    User, Ticket, Conversation, KnowledgeBase, SystemLog,
    # Supporting models
    UserPreference, TicketComment, ConversationMessage,
    # Enums
    TicketStatus, TicketPriority, TicketCategory,
    ConversationSentiment, SystemLogSeverity,
    # Mixins
    AuditMixin
)
from .repositories import (
    # Repository classes
    UserRepository, TicketRepository, ConversationRepository,
    KnowledgeRepository, SystemLogRepository,
    # Factory functions
    get_repository_factory, get_user_repository, get_ticket_repository,
    get_conversation_repository, get_knowledge_repository, get_systemlog_repository
)
from .vectorstore import VectorStore, RAGService, get_vector_store, get_rag_service

# Version information
__version__ = "1.0.0"

# Export all public components
__all__ = [
    # Database core
    "Base", "engine", "SessionLocal", "get_db", "create_tables",
    
    # Database manager
    "DatabaseManager",
    
    # Models
    "User", "Ticket", "Conversation", "KnowledgeBase", "SystemLog",
    "UserPreference", "TicketComment", "ConversationMessage",
    
    # Enums
    "TicketStatus", "TicketPriority", "TicketCategory",
    "ConversationSentiment", "SystemLogSeverity",
    
    # Mixins
    "AuditMixin",
    
    # Repositories
    "UserRepository", "TicketRepository", "ConversationRepository",
    "KnowledgeRepository", "SystemLogRepository",
    "get_repository_factory", "get_user_repository", "get_ticket_repository",
    "get_conversation_repository", "get_knowledge_repository", "get_systemlog_repository",
    
    # Vector store and RAG
    "VectorStore", "RAGService", "get_vector_store", "get_rag_service",
]


def initialize_database(create_tables_if_not_exist: bool = True, sync_vectorstore: bool = True):
    """
    Initialize the database layer with all required components.
    
    Args:
        create_tables_if_not_exist: Create database tables if they don't exist
        sync_vectorstore: Synchronize vector store with knowledge base
    """
    try:
        # Create tables if needed
        if create_tables_if_not_exist:
            create_tables()
            print("✓ Database tables initialized")
        
        # Initialize vector store
        if sync_vectorstore:
            vector_store = get_vector_store()
            stats = vector_store.sync_with_knowledge_base(force_full_sync=True)
            print(f"✓ Vector store synchronized: {stats}")
        
        # Verify database manager
        db_manager = DatabaseManager()
        health = db_manager.health_check()
        if health.get("status") == "healthy":
            print("✓ Database manager initialized and healthy")
        else:
            print(f"⚠ Database manager health check: {health}")
        
        print("✓ Database layer initialization complete")
        return True
        
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        return False


def get_database_info():
    """Get comprehensive database layer information."""
    try:
        db_manager = DatabaseManager()
        vector_store = get_vector_store()
        
        info = {
            "database_manager": {
                "health": db_manager.health_check(),
                "metrics": db_manager.get_metrics(),
                "connection_pool": db_manager.get_connection_info()
            },
            "vector_store": {
                "stats": vector_store.get_collection_stats(),
                "metrics": vector_store.metrics
            },
            "models": {
                "count": len([User, Ticket, Conversation, KnowledgeBase, SystemLog,
                            UserPreference, TicketComment, ConversationMessage]),
                "tables": [model.__tablename__ for model in [
                    User, Ticket, Conversation, KnowledgeBase, SystemLog,
                    UserPreference, TicketComment, ConversationMessage
                ]]
            }
        }
        
        return info
        
    except Exception as e:
        return {"error": str(e)}