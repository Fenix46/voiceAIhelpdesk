"""REST endpoints for feedback and user satisfaction management."""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Query
from fastapi.responses import JSONResponse

from ...core.logging import get_logger
from ...database import get_feedback_repository, get_conversation_repository, get_ticket_repository
from ..middleware.auth import auth_required
from ..schemas import (
    FeedbackCreateRequest, FeedbackResponse,
    ErrorResponse
)

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback",
    description="Submit user feedback for conversations, tickets, or general system feedback"
)
async def submit_feedback(
    request: FeedbackCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> FeedbackResponse:
    """
    Submit user feedback.
    
    Supports feedback for:
    - Conversations (voice interactions)
    - Tickets (support experience)
    - General system feedback
    - Feature requests
    """
    try:
        # Validate related entities exist if provided
        if request.conversation_id:
            conversation_repo = get_conversation_repository()
            conversation = conversation_repo.get_by_id(request.conversation_id)
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            
            # Check if user can provide feedback for this conversation
            user_role = current_user.get("role", "")
            if conversation.user_id != current_user.get("user_id") and user_role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot provide feedback for this conversation"
                )
        
        if request.ticket_id:
            ticket_repo = get_ticket_repository()
            ticket = ticket_repo.get_by_id(request.ticket_id)
            if not ticket:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Ticket not found"
                )
            
            # Check if user can provide feedback for this ticket
            if not _can_provide_ticket_feedback(ticket, current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot provide feedback for this ticket"
                )
        
        # Prepare feedback data
        feedback_data = {
            "user_id": current_user.get("user_id"),
            "feedback_type": request.feedback_type.value,
            "rating": request.rating,
            "comment": request.comment.strip() if request.comment else None,
            "conversation_id": request.conversation_id,
            "ticket_id": request.ticket_id,
            "category": request.category,
            "tags": request.tags or [],
            "metadata": request.metadata or {},
            "created_at": datetime.now(timezone.utc),
            "is_anonymous": request.is_anonymous,
            "contact_allowed": request.contact_allowed
        }
        
        # Enhanced categorization based on content
        feedback_data = await _enhance_feedback_data(feedback_data)
        
        # Store feedback
        feedback_repo = get_feedback_repository()
        feedback = feedback_repo.create(feedback_data)
        
        # Schedule background tasks
        background_tasks.add_task(
            _process_feedback_tasks,
            feedback.id,
            current_user.get("user_id")
        )
        
        logger.info(
            f"Created feedback {feedback.id}",
            extra={
                "feedback_id": feedback.id,
                "user_id": current_user.get("user_id"),
                "feedback_type": request.feedback_type.value,
                "rating": request.rating,
                "conversation_id": request.conversation_id,
                "ticket_id": request.ticket_id,
                "category": request.category
            }
        )
        
        return _feedback_to_response(feedback)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )


@router.get(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    summary="Get feedback by ID",
    description="Retrieve specific feedback entry by ID"
)
async def get_feedback(
    feedback_id: str,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> FeedbackResponse:
    """Get feedback details by ID."""
    try:
        feedback_repo = get_feedback_repository()
        feedback = feedback_repo.get_by_id(feedback_id)
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
        
        # Check access permissions
        user_role = current_user.get("role", "")
        if feedback.user_id != current_user.get("user_id") and user_role not in ["admin", "support"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this feedback"
            )
        
        return _feedback_to_response(feedback)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get feedback {feedback_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feedback"
        )


@router.get(
    "/",
    summary="List feedback entries",
    description="List feedback entries with filtering and pagination"
)
async def list_feedback(
    feedback_type: Optional[str] = Query(None, description="Filter by feedback type"),
    rating_min: Optional[int] = Query(None, ge=1, le=5, description="Minimum rating"),
    rating_max: Optional[int] = Query(None, ge=1, le=5, description="Maximum rating"),
    category: Optional[str] = Query(None, description="Filter by category"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    conversation_id: Optional[str] = Query(None, description="Filter by conversation"),
    ticket_id: Optional[str] = Query(None, description="Filter by ticket"),
    created_after: Optional[datetime] = Query(None, description="Created after date"),
    created_before: Optional[datetime] = Query(None, description="Created before date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> Dict[str, Any]:
    """
    List feedback entries with advanced filtering.
    
    Non-admin users can only see their own feedback.
    """
    try:
        feedback_repo = get_feedback_repository()
        
        # Build filters
        filters = {}
        if feedback_type:
            filters["feedback_type"] = feedback_type
        if rating_min is not None:
            filters["rating_min"] = rating_min
        if rating_max is not None:
            filters["rating_max"] = rating_max
        if category:
            filters["category"] = category
        if conversation_id:
            filters["conversation_id"] = conversation_id
        if ticket_id:
            filters["ticket_id"] = ticket_id
        if created_after:
            filters["created_after"] = created_after
        if created_before:
            filters["created_before"] = created_before
        
        # Apply user-level filtering for non-admin users
        user_role = current_user.get("role", "")
        if user_role not in ["admin", "support"]:
            filters["user_id"] = current_user.get("user_id")
        elif user_id:
            filters["user_id"] = user_id
        
        # Execute search
        search_result = feedback_repo.search(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size
        )
        
        # Convert feedback to response format
        feedback_entries = [_feedback_to_response(fb) for fb in search_result.items]
        
        logger.info(
            f"Listed feedback entries",
            extra={
                "filters": filters,
                "page": page,
                "page_size": page_size,
                "total_results": search_result.pagination.total_items,
                "requested_by": current_user.get("user_id")
            }
        )
        
        return {
            "feedback": feedback_entries,
            "pagination": {
                "page": search_result.pagination.page,
                "page_size": search_result.pagination.page_size,
                "total_items": search_result.pagination.total_items,
                "total_pages": search_result.pagination.total_pages,
                "has_next": search_result.pagination.has_next,
                "has_previous": search_result.pagination.has_previous
            },
            "summary": {
                "total_feedback": search_result.pagination.total_items,
                "average_rating": _calculate_average_rating(search_result.items),
                "rating_distribution": _calculate_rating_distribution(search_result.items)
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to list feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list feedback"
        )


@router.put(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    summary="Update feedback",
    description="Update existing feedback entry (only by owner or admin)"
)
async def update_feedback(
    feedback_id: str,
    rating: Optional[int] = Query(None, ge=1, le=5, description="New rating"),
    comment: Optional[str] = Query(None, description="Updated comment"),
    category: Optional[str] = Query(None, description="Updated category"),
    tags: Optional[List[str]] = Query(None, description="Updated tags"),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> FeedbackResponse:
    """Update feedback entry (limited time window or admin)."""
    try:
        feedback_repo = get_feedback_repository()
        feedback = feedback_repo.get_by_id(feedback_id)
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
        
        # Check permissions
        user_role = current_user.get("role", "")
        if feedback.user_id != current_user.get("user_id") and user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to modify this feedback"
            )
        
        # Check time window for non-admin users (24 hours)
        if user_role != "admin":
            hours_since_creation = (datetime.now(timezone.utc) - feedback.created_at).total_seconds() / 3600
            if hours_since_creation > 24:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Feedback can only be updated within 24 hours of creation"
                )
        
        # Prepare updates
        updates = {}
        if rating is not None:
            updates["rating"] = rating
        if comment is not None:
            updates["comment"] = comment.strip()
        if category is not None:
            updates["category"] = category
        if tags is not None:
            updates["tags"] = tags
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No updates provided"
            )
        
        updates["updated_at"] = datetime.now(timezone.utc)
        
        # Update feedback
        updated_feedback = feedback_repo.update(feedback_id, updates)
        
        logger.info(
            f"Updated feedback {feedback_id}",
            extra={
                "feedback_id": feedback_id,
                "updated_by": current_user.get("user_id"),
                "updates": list(updates.keys())
            }
        )
        
        return _feedback_to_response(updated_feedback)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update feedback {feedback_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feedback"
        )


@router.get(
    "/analytics/summary",
    summary="Get feedback analytics summary",
    description="Get summarized feedback analytics and trends"
)
async def get_feedback_analytics(
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    feedback_type: Optional[str] = Query(None, description="Filter by type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> Dict[str, Any]:
    """Get feedback analytics summary (admin/support only)."""
    try:
        user_role = current_user.get("role", "")
        if user_role not in ["admin", "support"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Analytics access requires admin or support role"
            )
        
        feedback_repo = get_feedback_repository()
        
        # Build filters for analytics
        filters = {}
        if start_date:
            filters["created_after"] = start_date
        if end_date:
            filters["created_before"] = end_date
        if feedback_type:
            filters["feedback_type"] = feedback_type
        if category:
            filters["category"] = category
        
        # Get feedback data
        search_result = feedback_repo.search(
            filters=filters,
            page_size=1000  # Large page for analytics
        )
        
        feedback_entries = search_result.items
        
        # Calculate analytics
        analytics = {
            "total_feedback": len(feedback_entries),
            "average_rating": _calculate_average_rating(feedback_entries),
            "rating_distribution": _calculate_rating_distribution(feedback_entries),
            "feedback_by_type": _calculate_type_distribution(feedback_entries),
            "feedback_by_category": _calculate_category_distribution(feedback_entries),
            "satisfaction_trend": _calculate_satisfaction_trend(feedback_entries),
            "top_positive_themes": _extract_positive_themes(feedback_entries),
            "top_negative_themes": _extract_negative_themes(feedback_entries),
            "response_rate": _calculate_response_rate(feedback_entries)
        }
        
        return analytics
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get feedback analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get feedback analytics"
        )


# Helper functions

async def _enhance_feedback_data(feedback_data: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance feedback data with smart categorization."""
    try:
        comment = feedback_data.get("comment", "").lower()
        
        # Auto-categorize based on keywords if no category provided
        if not feedback_data.get("category") and comment:
            if any(word in comment for word in ["veloce", "rapido", "tempo", "lento"]):
                feedback_data["category"] = "response_time"
            elif any(word in comment for word in ["difficile", "complicato", "confuso", "facile"]):
                feedback_data["category"] = "usability"
            elif any(word in comment for word in ["bug", "errore", "problema", "non funziona"]):
                feedback_data["category"] = "technical_issue"
            elif any(word in comment for word in ["gentile", "cortese", "professionale", "maleducato"]):
                feedback_data["category"] = "service_quality"
            elif any(word in comment for word in ["audio", "voce", "sentire", "volume"]):
                feedback_data["category"] = "audio_quality"
        
        # Add sentiment analysis tags
        if comment:
            if feedback_data.get("rating", 0) >= 4:
                if "tags" not in feedback_data:
                    feedback_data["tags"] = []
                feedback_data["tags"].append("positive")
            elif feedback_data.get("rating", 0) <= 2:
                if "tags" not in feedback_data:
                    feedback_data["tags"] = []
                feedback_data["tags"].append("negative")
        
        return feedback_data
    
    except Exception as e:
        logger.error(f"Failed to enhance feedback data: {e}")
        return feedback_data


async def _process_feedback_tasks(feedback_id: str, user_id: str):
    """Background tasks after feedback submission."""
    try:
        # Update user satisfaction metrics
        # Send notifications for low ratings
        # Trigger escalation if needed
        
        feedback_repo = get_feedback_repository()
        feedback = feedback_repo.get_by_id(feedback_id)
        
        if feedback and feedback.rating <= 2:
            # Low rating - might need attention
            logger.warning(
                f"Low rating feedback received: {feedback_id}",
                extra={
                    "feedback_id": feedback_id,
                    "rating": feedback.rating,
                    "user_id": user_id
                }
            )
        
        logger.debug(f"Feedback processing completed for {feedback_id}")
    
    except Exception as e:
        logger.error(f"Failed to process feedback tasks for {feedback_id}: {e}")


def _can_provide_ticket_feedback(ticket, current_user: Dict[str, Any]) -> bool:
    """Check if user can provide feedback for a ticket."""
    user_role = current_user.get("role", "")
    user_id = current_user.get("user_id")
    
    # Admin can access all
    if user_role == "admin":
        return True
    
    # Ticket owner can provide feedback
    if ticket.user_id == user_id:
        return True
    
    # Assigned technician can provide feedback
    if ticket.assigned_to == user_id:
        return True
    
    return False


def _feedback_to_response(feedback) -> FeedbackResponse:
    """Convert feedback model to response format."""
    return FeedbackResponse(
        id=feedback.id,
        user_id=feedback.user_id if not feedback.is_anonymous else None,
        feedback_type=feedback.feedback_type,
        rating=feedback.rating,
        comment=feedback.comment,
        conversation_id=feedback.conversation_id,
        ticket_id=feedback.ticket_id,
        category=feedback.category,
        tags=feedback.tags or [],
        created_at=feedback.created_at,
        updated_at=feedback.updated_at,
        is_anonymous=feedback.is_anonymous,
        contact_allowed=feedback.contact_allowed
    )


def _calculate_average_rating(feedback_entries: List) -> float:
    """Calculate average rating from feedback entries."""
    if not feedback_entries:
        return 0.0
    
    ratings = [fb.rating for fb in feedback_entries if fb.rating]
    return sum(ratings) / len(ratings) if ratings else 0.0


def _calculate_rating_distribution(feedback_entries: List) -> Dict[str, int]:
    """Calculate rating distribution."""
    distribution = {str(i): 0 for i in range(1, 6)}
    
    for feedback in feedback_entries:
        if feedback.rating:
            distribution[str(feedback.rating)] += 1
    
    return distribution


def _calculate_type_distribution(feedback_entries: List) -> Dict[str, int]:
    """Calculate feedback type distribution."""
    distribution = {}
    for feedback in feedback_entries:
        type_name = feedback.feedback_type
        distribution[type_name] = distribution.get(type_name, 0) + 1
    return distribution


def _calculate_category_distribution(feedback_entries: List) -> Dict[str, int]:
    """Calculate category distribution."""
    distribution = {}
    for feedback in feedback_entries:
        if feedback.category:
            distribution[feedback.category] = distribution.get(feedback.category, 0) + 1
    return distribution


def _calculate_satisfaction_trend(feedback_entries: List) -> Dict[str, float]:
    """Calculate satisfaction trend over time."""
    # Mock implementation - in production, group by time periods
    return {
        "current_week": _calculate_average_rating(feedback_entries[-7:] if len(feedback_entries) >= 7 else feedback_entries),
        "previous_week": _calculate_average_rating(feedback_entries[-14:-7] if len(feedback_entries) >= 14 else []),
        "trend": "stable"  # "improving", "declining", "stable"
    }


def _extract_positive_themes(feedback_entries: List) -> List[str]:
    """Extract common positive themes from comments."""
    # Mock implementation - in production, use NLP
    return ["fast response", "helpful support", "easy to use", "good audio quality"]


def _extract_negative_themes(feedback_entries: List) -> List[str]:
    """Extract common negative themes from comments."""
    # Mock implementation - in production, use NLP
    return ["slow response", "audio issues", "difficult to understand", "technical problems"]


def _calculate_response_rate(feedback_entries: List) -> float:
    """Calculate response rate (feedback with comments vs total)."""
    if not feedback_entries:
        return 0.0
    
    with_comments = len([fb for fb in feedback_entries if fb.comment and fb.comment.strip()])
    return (with_comments / len(feedback_entries)) * 100