"""Comprehensive SQLAlchemy models for VoiceHelpDeskAI database layer."""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text, JSON, 
    ForeignKey, Index, UniqueConstraint, CheckConstraint, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects import sqlite
from sqlalchemy.sql import func

from .base import Base


class TicketStatus(PyEnum):
    """Ticket status enumeration."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_USER = "pending_user"
    PENDING_VENDOR = "pending_vendor"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketPriority(PyEnum):
    """Ticket priority enumeration."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


class TicketCategory(PyEnum):
    """Ticket category enumeration."""
    SOFTWARE = "software"
    HARDWARE = "hardware"
    NETWORK = "network"
    SECURITY = "security"
    ACCESS = "access"
    GENERAL = "general"


class ConversationSentiment(PyEnum):
    """Conversation sentiment enumeration."""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class SystemLogSeverity(PyEnum):
    """System log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditMixin:
    """Mixin class for audit logging capabilities."""
    
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    
    # Soft delete support
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(255), nullable=True)


class User(Base, AuditMixin):
    """User model for storing user information and preferences."""
    
    __tablename__ = "users"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Basic user information
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    
    # Organizational information
    department = Column(String(100), nullable=True, index=True)
    role = Column(String(100), nullable=True)
    manager_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    employee_id = Column(String(50), unique=True, nullable=True)
    location = Column(String(255), nullable=True)
    
    # Authentication and security
    hashed_password = Column(String(255), nullable=True)  # For local auth
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # User preferences and settings
    language = Column(String(10), default="it", nullable=False)
    timezone = Column(String(50), default="Europe/Rome", nullable=False)
    preferences = Column(JSON, default=lambda: {}, nullable=False)
    
    # Voice and AI preferences
    preferred_voice_id = Column(String(100), nullable=True)
    voice_speed = Column(Float, default=1.0, nullable=False)
    enable_voice_responses = Column(Boolean, default=True, nullable=False)
    preferred_response_style = Column(String(50), default="professional", nullable=False)
    
    # Usage statistics
    total_conversations = Column(Integer, default=0, nullable=False)
    total_tickets = Column(Integer, default=0, nullable=False)
    last_activity = Column(DateTime(timezone=True), nullable=True, index=True)
    satisfaction_score = Column(Float, nullable=True)
    
    # Relationships
    manager = relationship("User", remote_side=[id], back_populates="direct_reports")
    direct_reports = relationship("User", back_populates="manager")
    tickets = relationship("Ticket", back_populates="user", lazy="dynamic")
    conversations = relationship("Conversation", back_populates="user", lazy="dynamic")
    
    # Indexes
    __table_args__ = (
        Index("idx_user_active_department", "is_active", "department"),
        Index("idx_user_last_activity", "last_activity"),
        Index("idx_user_email_active", "email", "is_active"),
        CheckConstraint("satisfaction_score IS NULL OR (satisfaction_score >= 1.0 AND satisfaction_score <= 5.0)", name="chk_satisfaction_range"),
        CheckConstraint("voice_speed >= 0.5 AND voice_speed <= 2.0", name="chk_voice_speed_range"),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class Ticket(Base, AuditMixin):
    """Ticket model for storing support tickets."""
    
    __tablename__ = "tickets"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_number = Column(String(20), unique=True, nullable=False, index=True)
    
    # Basic ticket information
    title = Column(String(500), nullable=False, index=True)
    description = Column(Text, nullable=False)
    status = Column(String(20), default=TicketStatus.OPEN.value, nullable=False, index=True)
    priority = Column(Integer, default=TicketPriority.NORMAL.value, nullable=False, index=True)
    category = Column(String(50), default=TicketCategory.GENERAL.value, nullable=False, index=True)
    subcategory = Column(String(100), nullable=True, index=True)
    
    # User and assignment information
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assigned_to = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    assigned_group = Column(String(100), nullable=True, index=True)
    reporter_email = Column(String(255), nullable=True)
    reporter_phone = Column(String(20), nullable=True)
    
    # Technical details
    affected_systems = Column(JSON, default=list, nullable=False)
    asset_ids = Column(JSON, default=list, nullable=False)
    error_codes = Column(JSON, default=list, nullable=False)
    ip_addresses = Column(JSON, default=list, nullable=False)
    software_versions = Column(JSON, default=list, nullable=False)
    
    # Problem description
    reproduction_steps = Column(JSON, default=list, nullable=False)
    error_messages = Column(JSON, default=list, nullable=False)
    business_impact = Column(Text, nullable=True)
    urgency_justification = Column(Text, nullable=True)
    
    # Resolution information
    solution = Column(Text, nullable=True)
    resolution_steps = Column(JSON, default=list, nullable=False)
    resolution_category = Column(String(100), nullable=True)
    workaround = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    
    # Time tracking
    estimated_resolution_time = Column(Integer, nullable=True)  # minutes
    actual_resolution_time = Column(Integer, nullable=True)  # minutes
    first_response_time = Column(Integer, nullable=True)  # minutes
    resolution_deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True, index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Escalation and approval
    escalation_level = Column(Integer, default=0, nullable=False)
    escalation_reason = Column(Text, nullable=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    escalated_to = Column(String(36), ForeignKey("users.id"), nullable=True)
    requires_approval = Column(Boolean, default=False, nullable=False)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Quality and feedback
    customer_satisfaction = Column(Integer, nullable=True)  # 1-5 scale
    resolution_quality_score = Column(Float, nullable=True)  # 0.0-1.0
    feedback_comments = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    
    # External integration
    external_ticket_id = Column(String(100), nullable=True)
    vendor_name = Column(String(100), nullable=True)
    vendor_ticket_id = Column(String(100), nullable=True)
    
    # AI and automation
    auto_generated = Column(Boolean, default=False, nullable=False)
    ai_confidence_score = Column(Float, nullable=True)
    auto_categorization = Column(Boolean, default=False, nullable=False)
    suggested_solutions = Column(JSON, default=list, nullable=False)
    
    # Additional metadata
    tags = Column(JSON, default=list, nullable=False)
    attachments = Column(JSON, default=list, nullable=False)
    related_ticket_ids = Column(JSON, default=list, nullable=False)
    knowledge_base_articles = Column(JSON, default=list, nullable=False)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="tickets")
    assignee = relationship("User", foreign_keys=[assigned_to])
    escalated_user = relationship("User", foreign_keys=[escalated_to])
    approver = relationship("User", foreign_keys=[approved_by])
    conversations = relationship("Conversation", back_populates="ticket", lazy="dynamic")
    
    # Indexes
    __table_args__ = (
        Index("idx_ticket_status_priority", "status", "priority"),
        Index("idx_ticket_category_subcategory", "category", "subcategory"),
        Index("idx_ticket_user_status", "user_id", "status"),
        Index("idx_ticket_assigned_status", "assigned_to", "status"),
        Index("idx_ticket_created_status", "created_at", "status"),
        Index("idx_ticket_resolution_deadline", "resolution_deadline"),
        Index("idx_ticket_number_user", "ticket_number", "user_id"),
        CheckConstraint("priority >= 1 AND priority <= 5", name="chk_priority_range"),
        CheckConstraint("customer_satisfaction IS NULL OR (customer_satisfaction >= 1 AND customer_satisfaction <= 5)", name="chk_satisfaction_range"),
        CheckConstraint("resolution_quality_score IS NULL OR (resolution_quality_score >= 0.0 AND resolution_quality_score <= 1.0)", name="chk_quality_range"),
        CheckConstraint("escalation_level >= 0", name="chk_escalation_positive"),
    )
    
    def __repr__(self):
        return f"<Ticket(id={self.id}, number={self.ticket_number}, status={self.status})>"


class Conversation(Base, AuditMixin):
    """Conversation model for storing conversation transcripts and metadata."""
    
    __tablename__ = "conversations"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(100), nullable=False, index=True)
    
    # Relationships
    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Conversation content
    transcript = Column(Text, nullable=True)
    original_audio_path = Column(String(500), nullable=True)
    processed_audio_path = Column(String(500), nullable=True)
    language = Column(String(10), default="it", nullable=False)
    
    # AI Processing results
    nlu_results = Column(JSON, default=lambda: {}, nullable=False)
    intent_classification = Column(JSON, default=lambda: {}, nullable=False)
    entity_extraction = Column(JSON, default=lambda: {}, nullable=False)
    sentiment_analysis = Column(JSON, default=lambda: {}, nullable=False)
    
    # Conversation metrics
    sentiment = Column(String(20), default=ConversationSentiment.NEUTRAL.value, nullable=False, index=True)
    confidence_score = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    word_count = Column(Integer, nullable=True)
    turn_count = Column(Integer, default=0, nullable=False)
    
    # Quality metrics
    transcription_quality = Column(Float, nullable=True)
    response_quality = Column(Float, nullable=True)
    user_satisfaction = Column(Integer, nullable=True)  # 1-5 scale
    escalated_to_human = Column(Boolean, default=False, nullable=False)
    escalation_reason = Column(String(200), nullable=True)
    
    # Processing metadata
    stt_provider = Column(String(50), nullable=True)
    stt_model = Column(String(100), nullable=True)
    llm_provider = Column(String(50), nullable=True)
    llm_model = Column(String(100), nullable=True)
    tts_provider = Column(String(50), nullable=True)
    tts_voice_id = Column(String(100), nullable=True)
    
    # Performance metrics
    total_processing_time = Column(Float, nullable=True)
    stt_processing_time = Column(Float, nullable=True)
    nlu_processing_time = Column(Float, nullable=True)
    llm_processing_time = Column(Float, nullable=True)
    tts_processing_time = Column(Float, nullable=True)
    
    # Conversation flow
    conversation_state = Column(String(50), nullable=True)
    last_user_message = Column(Text, nullable=True)
    last_assistant_message = Column(Text, nullable=True)
    context_data = Column(JSON, default=lambda: {}, nullable=False)
    
    # Feedback and analytics
    feedback_score = Column(Float, nullable=True)
    feedback_comments = Column(Text, nullable=True)
    analytics_data = Column(JSON, default=lambda: {}, nullable=False)
    
    # Technical metadata
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    api_version = Column(String(20), nullable=True)
    
    # Relationships
    ticket = relationship("Ticket", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    
    # Indexes
    __table_args__ = (
        Index("idx_conversation_user_created", "user_id", "created_at"),
        Index("idx_conversation_ticket_created", "ticket_id", "created_at"),
        Index("idx_conversation_session_user", "session_id", "user_id"),
        Index("idx_conversation_sentiment_created", "sentiment", "created_at"),
        Index("idx_conversation_duration", "duration_seconds"),
        CheckConstraint("user_satisfaction IS NULL OR (user_satisfaction >= 1 AND user_satisfaction <= 5)", name="chk_user_satisfaction_range"),
        CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)", name="chk_confidence_range"),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="chk_duration_positive"),
    )
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, sentiment={self.sentiment})>"


class KnowledgeBase(Base, AuditMixin):
    """Knowledge base model for storing IT solutions and documentation."""
    
    __tablename__ = "knowledge_base"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Content identification
    title = Column(String(500), nullable=False, index=True)
    problem_description = Column(Text, nullable=False)
    solution = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, index=True)
    subcategory = Column(String(100), nullable=True, index=True)
    
    # Classification and tagging
    keywords = Column(JSON, default=list, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    affected_systems = Column(JSON, default=list, nullable=False)
    software_versions = Column(JSON, default=list, nullable=False)
    hardware_models = Column(JSON, default=list, nullable=False)
    
    # Content metadata
    difficulty_level = Column(String(20), default="intermediate", nullable=False)
    estimated_time_minutes = Column(Integer, nullable=True)
    prerequisites = Column(JSON, default=list, nullable=False)
    related_articles = Column(JSON, default=list, nullable=False)
    
    # Authoring and maintenance
    author_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    last_reviewed = Column(DateTime(timezone=True), nullable=True, index=True)
    review_due_date = Column(DateTime(timezone=True), nullable=True, index=True)
    version = Column(String(20), default="1.0", nullable=False)
    
    # Usage and effectiveness metrics
    view_count = Column(Integer, default=0, nullable=False)
    usage_count = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, default=0.0, nullable=False, index=True)
    success_votes = Column(Integer, default=0, nullable=False)
    total_votes = Column(Integer, default=0, nullable=False)
    average_rating = Column(Float, nullable=True)
    
    # AI and search optimization
    embedding_vector = Column(Text, nullable=True)  # Serialized vector for similarity search
    search_rank = Column(Float, default=0.0, nullable=False, index=True)
    auto_generated = Column(Boolean, default=False, nullable=False)
    ai_confidence = Column(Float, nullable=True)
    
    # Content status and lifecycle
    status = Column(String(20), default="draft", nullable=False, index=True)  # draft, published, archived, deprecated
    is_featured = Column(Boolean, default=False, nullable=False, index=True)
    is_internal_only = Column(Boolean, default=False, nullable=False)
    expiration_date = Column(DateTime(timezone=True), nullable=True)
    
    # External sources and references
    source_url = Column(String(1000), nullable=True)
    external_id = Column(String(100), nullable=True)
    vendor_documentation = Column(String(1000), nullable=True)
    
    # Relationships
    author = relationship("User", foreign_keys=[author_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    approver = relationship("User", foreign_keys=[approved_by])
    
    # Indexes
    __table_args__ = (
        Index("idx_kb_category_success", "category", "success_rate"),
        Index("idx_kb_status_featured", "status", "is_featured"),
        Index("idx_kb_usage_success", "usage_count", "success_rate"),
        Index("idx_kb_title_category", "title", "category"),
        Index("idx_kb_search_rank", "search_rank", "status"),
        Index("idx_kb_review_due", "review_due_date"),
        CheckConstraint("success_rate >= 0.0 AND success_rate <= 1.0", name="chk_success_rate_range"),
        CheckConstraint("average_rating IS NULL OR (average_rating >= 1.0 AND average_rating <= 5.0)", name="chk_rating_range"),
        CheckConstraint("success_votes <= total_votes", name="chk_votes_consistency"),
        CheckConstraint("estimated_time_minutes IS NULL OR estimated_time_minutes > 0", name="chk_time_positive"),
    )
    
    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, title={self.title[:50]}...)>"


class SystemLog(Base):
    """System log model for storing application events and audit trail."""
    
    __tablename__ = "system_logs"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Event identification
    timestamp = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), default=SystemLogSeverity.INFO.value, nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)  # component/service name
    
    # Event details
    message = Column(Text, nullable=False)
    details = Column(JSON, default=lambda: {}, nullable=False)
    error_code = Column(String(50), nullable=True, index=True)
    stack_trace = Column(Text, nullable=True)
    
    # Context information
    user_id = Column(String(36), nullable=True, index=True)
    session_id = Column(String(100), nullable=True, index=True)
    conversation_id = Column(String(36), nullable=True, index=True)
    ticket_id = Column(String(36), nullable=True, index=True)
    request_id = Column(String(100), nullable=True, index=True)
    
    # Technical context
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    endpoint = Column(String(200), nullable=True)
    http_method = Column(String(10), nullable=True)
    http_status = Column(Integer, nullable=True, index=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Performance metrics
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    network_latency = Column(Float, nullable=True)
    
    # Additional metadata
    environment = Column(String(20), nullable=True, index=True)  # dev, staging, prod
    version = Column(String(50), nullable=True)
    correlation_id = Column(String(100), nullable=True, index=True)
    parent_event_id = Column(String(36), nullable=True, index=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_log_timestamp_severity", "timestamp", "severity"),
        Index("idx_log_source_event_type", "source", "event_type"),
        Index("idx_log_user_timestamp", "user_id", "timestamp"),
        Index("idx_log_error_timestamp", "error_code", "timestamp"),
        Index("idx_log_correlation", "correlation_id"),
        Index("idx_log_performance", "response_time_ms", "timestamp"),
    )
    
    def __repr__(self):
        return f"<SystemLog(id={self.id}, event_type={self.event_type}, severity={self.severity})>"


class UserPreference(Base, AuditMixin):
    """User preference model for storing detailed user settings."""
    
    __tablename__ = "user_preferences"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign key
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Preference identification
    preference_category = Column(String(50), nullable=False, index=True)  # ui, voice, notifications, etc.
    preference_key = Column(String(100), nullable=False, index=True)
    preference_value = Column(JSON, nullable=False)
    
    # Metadata
    description = Column(String(500), nullable=True)
    is_system_managed = Column(Boolean, default=False, nullable=False)
    last_used = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Relationship
    user = relationship("User")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "preference_category", "preference_key", name="uq_user_preference"),
        Index("idx_preference_category_key", "preference_category", "preference_key"),
    )
    
    def __repr__(self):
        return f"<UserPreference(user_id={self.user_id}, category={self.preference_category}, key={self.preference_key})>"


class TicketComment(Base, AuditMixin):
    """Ticket comment model for storing ticket updates and communication."""
    
    __tablename__ = "ticket_comments"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign keys
    ticket_id = Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Comment content
    content = Column(Text, nullable=False)
    comment_type = Column(String(50), default="comment", nullable=False, index=True)  # comment, status_change, assignment, etc.
    is_internal = Column(Boolean, default=False, nullable=False, index=True)
    is_solution = Column(Boolean, default=False, nullable=False)
    
    # Status changes
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=True)
    status_change_reason = Column(Text, nullable=True)
    
    # Time tracking
    time_spent_minutes = Column(Integer, nullable=True)
    billable_time = Column(Boolean, default=True, nullable=False)
    
    # Attachments and references
    attachments = Column(JSON, default=list, nullable=False)
    related_kb_articles = Column(JSON, default=list, nullable=False)
    
    # Relationships
    ticket = relationship("Ticket")
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_comment_ticket_created", "ticket_id", "created_at"),
        Index("idx_comment_user_created", "user_id", "created_at"),
        Index("idx_comment_type_internal", "comment_type", "is_internal"),
    )
    
    def __repr__(self):
        return f"<TicketComment(id={self.id}, ticket_id={self.ticket_id}, type={self.comment_type})>"


class ConversationMessage(Base, AuditMixin):
    """Individual messages within a conversation."""
    
    __tablename__ = "conversation_messages"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign key
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Message content
    message_type = Column(String(20), nullable=False, index=True)  # user, assistant, system
    content = Column(Text, nullable=False)
    original_content = Column(Text, nullable=True)  # Before processing
    
    # Audio information
    audio_path = Column(String(500), nullable=True)
    audio_duration = Column(Float, nullable=True)
    audio_format = Column(String(20), nullable=True)
    
    # Processing metadata
    processing_time = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    intent_classification = Column(JSON, nullable=True)
    entity_extraction = Column(JSON, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    
    # Quality metrics
    transcription_confidence = Column(Float, nullable=True)
    response_quality_score = Column(Float, nullable=True)
    user_feedback = Column(Integer, nullable=True)  # thumbs up/down
    
    # Relationships
    conversation = relationship("Conversation")
    
    # Indexes
    __table_args__ = (
        Index("idx_message_conversation_created", "conversation_id", "created_at"),
        Index("idx_message_type_created", "message_type", "created_at"),
        Index("idx_message_sentiment", "sentiment_score"),
    )
    
    def __repr__(self):
        return f"<ConversationMessage(id={self.id}, conversation_id={self.conversation_id}, type={self.message_type})>"


# Event listeners for automatic ticket number generation
@event.listens_for(Ticket, "before_insert")
def generate_ticket_number(mapper, connection, target):
    """Generate ticket number before insert."""
    if not target.ticket_number:
        # Simple ticket number generation - in production, use more sophisticated logic
        year = datetime.now().year
        # Query for the highest ticket number of the current year
        result = connection.execute(
            f"SELECT MAX(ticket_number) FROM tickets WHERE ticket_number LIKE 'TK{year}%'"
        ).scalar()
        
        if result:
            # Extract the number and increment
            last_num = int(result.split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1
        
        target.ticket_number = f"TK{year}-{next_num:06d}"


# Event listeners for audit logging
@event.listens_for(User, "before_update")
@event.listens_for(Ticket, "before_update")
@event.listens_for(Conversation, "before_update")
@event.listens_for(KnowledgeBase, "before_update")
def update_timestamp(mapper, connection, target):
    """Update timestamp on record update."""
    target.updated_at = datetime.now(timezone.utc)