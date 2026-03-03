"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, validator


# Base schemas
class BaseResponse(BaseModel):
    """Base response schema."""
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response schema."""
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    timestamp: float
    version: str


class PaginationResponse(BaseModel):
    """Pagination information schema."""
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


# Enum schemas
class ConversationStatus(str, Enum):
    """Conversation status enum."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingStatus(str, Enum):
    """Processing status enum."""
    QUEUED = "queued"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"


class AudioFormat(str, Enum):
    """Supported audio formats."""
    WAV = "wav"
    MP3 = "mp3"
    OGG = "ogg"
    WEBM = "webm"
    M4A = "m4a"


class TicketPriority(int, Enum):
    """Ticket priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


class TicketStatus(str, Enum):
    """Ticket status enum."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_USER = "pending_user"
    PENDING_VENDOR = "pending_vendor"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


# Conversation schemas
class ConversationStartRequest(BaseModel):
    """Request schema for starting a conversation."""
    user_id: str = Field(..., description="User ID initiating the conversation")
    audio_format: AudioFormat = Field(default=AudioFormat.WAV, description="Preferred audio format")
    language: str = Field(default="it", description="Language code (ISO 639-1)")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context data")
    session_metadata: Dict[str, Any] = Field(default_factory=dict, description="Session metadata")


class ConversationStartResponse(BaseResponse):
    """Response schema for conversation start."""
    conversation_id: str
    session_id: str
    websocket_url: str
    sse_url: str
    expires_at: datetime
    configuration: Dict[str, Any]


class ConversationEndRequest(BaseModel):
    """Request schema for ending a conversation."""
    conversation_id: str
    reason: Optional[str] = Field(None, description="Reason for ending conversation")
    feedback_score: Optional[int] = Field(None, ge=1, le=5, description="User satisfaction score")
    feedback_comment: Optional[str] = Field(None, description="User feedback comment")


class ConversationEndResponse(BaseResponse):
    """Response schema for conversation end."""
    conversation_id: str
    status: ConversationStatus
    duration_seconds: float
    transcript_url: Optional[str]
    summary: Optional[str]
    actions_taken: List[str]
    created_tickets: List[str] = Field(default_factory=list)


class TranscriptEntry(BaseModel):
    """Schema for a single transcript entry."""
    timestamp: datetime
    speaker: str  # "user" or "assistant"
    text: str
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    language: Optional[str] = None
    processing_time_ms: Optional[float] = None


class ConversationTranscriptResponse(BaseResponse):
    """Response schema for conversation transcript."""
    conversation_id: str
    transcript: List[TranscriptEntry]
    language: str
    total_duration: float
    word_count: int
    summary: Optional[str]
    sentiment_analysis: Optional[Dict[str, Any]]


# Ticket schemas
class TicketCreateRequest(BaseModel):
    """Request schema for creating a ticket."""
    title: str = Field(..., min_length=5, max_length=500, description="Ticket title")
    description: str = Field(..., min_length=10, description="Detailed description")
    priority: TicketPriority = Field(default=TicketPriority.NORMAL, description="Ticket priority")
    category: str = Field(..., description="Ticket category")
    subcategory: Optional[str] = Field(None, description="Ticket subcategory")
    user_id: str = Field(..., description="User ID creating the ticket")
    conversation_id: Optional[str] = Field(None, description="Associated conversation ID")
    affected_systems: List[str] = Field(default_factory=list, description="Affected systems/services")
    business_impact: Optional[str] = Field(None, description="Business impact description")
    urgency_justification: Optional[str] = Field(None, description="Urgency justification")
    tags: List[str] = Field(default_factory=list, description="Ticket tags")
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Custom fields")

    @validator('title')
    def validate_title(cls, v):
        """Validate title format."""
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()

    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags format."""
        return [tag.strip().lower() for tag in v if tag.strip()]


class TicketResponse(BaseResponse):
    """Response schema for ticket data."""
    id: str
    ticket_number: str
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    category: str
    subcategory: Optional[str]
    user_id: str
    assigned_to: Optional[str]
    assigned_group: Optional[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    tags: List[str]
    solution: Optional[str]
    customer_satisfaction: Optional[int]
    business_impact: Optional[str]
    estimated_resolution_time: Optional[int]  # minutes
    actual_resolution_time: Optional[int]  # minutes


# Analytics schemas
class AnalyticsPeriod(str, Enum):
    """Analytics time period."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class MetricValue(BaseModel):
    """Schema for a metric value."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DashboardMetrics(BaseModel):
    """Schema for dashboard metrics."""
    conversation_stats: Dict[str, Union[int, float]]
    ticket_stats: Dict[str, Union[int, float]]
    performance_metrics: Dict[str, float]
    user_satisfaction: Dict[str, Union[int, float]]
    trending_issues: List[Dict[str, Any]]
    system_health: Dict[str, str]


class AnalyticsDashboardResponse(BaseResponse):
    """Response schema for analytics dashboard."""
    period: AnalyticsPeriod
    start_date: datetime
    end_date: datetime
    metrics: DashboardMetrics
    charts_data: Dict[str, List[MetricValue]]


# Feedback schemas
class FeedbackType(str, Enum):
    """Feedback type enum."""
    CONVERSATION = "conversation"
    TICKET = "ticket"
    GENERAL = "general"
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"


class FeedbackCreateRequest(BaseModel):
    """Request schema for creating feedback."""
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(None, description="Feedback comment")
    conversation_id: Optional[str] = Field(None, description="Related conversation ID")
    ticket_id: Optional[str] = Field(None, description="Related ticket ID")
    category: Optional[str] = Field(None, description="Feedback category")
    tags: Optional[List[str]] = Field(None, description="Feedback tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    is_anonymous: bool = Field(default=False, description="Submit anonymously")
    contact_allowed: bool = Field(default=True, description="Allow contact for follow-up")

    @validator('comment')
    def validate_comment(cls, v):
        """Validate comment if provided."""
        if v and len(v.strip()) < 5:
            raise ValueError('Comment must be at least 5 characters long')
        return v.strip() if v else None


class FeedbackResponse(BaseResponse):
    """Response schema for feedback data."""
    id: str
    user_id: Optional[str]  # None if anonymous
    feedback_type: FeedbackType
    rating: int
    comment: Optional[str]
    conversation_id: Optional[str]
    ticket_id: Optional[str]
    category: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: Optional[datetime]
    is_anonymous: bool
    contact_allowed: bool


# Legacy feedback schema for backward compatibility
class FeedbackRequest(BaseModel):
    """Request schema for submitting feedback."""
    feedback_type: FeedbackType
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: str = Field(..., min_length=10, description="Feedback comment")
    user_id: str
    related_id: Optional[str] = Field(None, description="Related conversation/ticket ID")
    category: Optional[str] = Field(None, description="Feedback category")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    anonymous: bool = Field(default=False, description="Submit anonymously")


# WebSocket schemas
class WebSocketMessage(BaseModel):
    """Base WebSocket message schema."""
    type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: str


class AudioChunkMessage(WebSocketMessage):
    """Audio chunk message schema."""
    type: str = "audio_chunk"
    data: bytes = Field(..., description="Audio data")
    sequence: int = Field(..., description="Chunk sequence number")
    format: AudioFormat
    sample_rate: int = Field(default=16000)
    channels: int = Field(default=1)


class TranscriptionMessage(WebSocketMessage):
    """Transcription message schema."""
    type: str = "transcription"
    text: str
    is_partial: bool = Field(default=False)
    confidence: float = Field(..., ge=0.0, le=1.0)
    language: str


class StatusUpdateMessage(WebSocketMessage):
    """Status update message schema."""
    type: str = "status_update"
    status: ProcessingStatus
    message: str
    progress: Optional[float] = Field(None, ge=0.0, le=1.0)


class ErrorMessage(WebSocketMessage):
    """Error message schema."""
    type: str = "error"
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class HeartbeatMessage(WebSocketMessage):
    """Heartbeat message schema."""
    type: str = "heartbeat"


# SSE schemas
class SSEEvent(BaseModel):
    """Server-Sent Event schema."""
    event: str
    data: Dict[str, Any]
    id: Optional[str] = None
    retry: Optional[int] = None


class TranscriptionUpdate(BaseModel):
    """Transcription update event data."""
    conversation_id: str
    text: str
    is_partial: bool
    confidence: float
    timestamp: datetime


class ProcessingUpdate(BaseModel):
    """Processing status update event data."""
    conversation_id: str
    status: ProcessingStatus
    stage: str
    progress: float
    estimated_completion: Optional[datetime]


class QueueUpdate(BaseModel):
    """Queue position update event data."""
    conversation_id: str
    position: int
    estimated_wait_time: int  # seconds


class SystemAlert(BaseModel):
    """System alert event data."""
    alert_type: str
    severity: str
    message: str
    affected_services: List[str]
    timestamp: datetime


# Authentication schemas
class TokenRequest(BaseModel):
    """Token request schema."""
    username: str
    password: str
    scope: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


class UserInfo(BaseModel):
    """User information schema."""
    user_id: str
    username: str
    email: str
    full_name: str
    role: str
    permissions: List[str] = Field(default_factory=list)
    is_active: bool = True


# Validation schemas
class ValidationError(BaseModel):
    """Validation error schema."""
    field: str
    message: str
    rejected_value: Any


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with field details."""
    validation_errors: List[ValidationError] = Field(default_factory=list)