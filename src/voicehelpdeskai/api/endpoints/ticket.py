"""REST endpoints for ticket management."""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Query
from fastapi.responses import JSONResponse

from ...core.logging import get_logger
from ...services.ticketing import TicketingService, TicketAnalytics
from ...database import get_ticket_repository, get_user_repository
from ..middleware.auth import auth_required
from ..schemas import (
    TicketCreateRequest, TicketResponse,
    ErrorResponse, PaginationResponse
)

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/create",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ticket",
    description="Create a new IT support ticket with validation and automatic assignment"
)
async def create_ticket(
    request: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> TicketResponse:
    """
    Create a new support ticket.
    
    Features:
    - Input validation and sanitization
    - Automatic priority adjustment based on keywords
    - Smart assignment to available technicians
    - Integration with conversation system
    - Real-time notifications via webhooks
    """
    try:
        # Validate user exists and is active
        user_repo = get_user_repository()
        user = user_repo.get_by_id(request.user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not active"
            )
        
        # Initialize ticketing service
        ticketing_service = TicketingService()
        
        # Prepare ticket data
        ticket_data = {
            "title": request.title.strip(),
            "description": request.description.strip(),
            "priority": request.priority.value,
            "category": request.category,
            "subcategory": request.subcategory,
            "user_id": request.user_id,
            "conversation_id": request.conversation_id,
            "affected_systems": request.affected_systems,
            "business_impact": request.business_impact,
            "urgency_justification": request.urgency_justification,
            "tags": request.tags,
            "custom_fields": request.custom_fields,
            "created_by": current_user.get("user_id"),
            "reporter_email": user.email,
            "reporter_phone": user.phone
        }
        
        # Enhance ticket with smart categorization
        ticket_data = await _enhance_ticket_data(ticket_data)
        
        # Create ticket through service (includes validation, assignment, notifications)
        ticket = await ticketing_service.create_ticket(
            ticket_data=ticket_data,
            auto_assign=True,
            sync_external=True
        )
        
        # Add background tasks
        background_tasks.add_task(
            _post_ticket_creation_tasks,
            ticket.id,
            current_user.get("user_id")
        )
        
        logger.info(
            f"Created ticket {ticket.ticket_number}",
            extra={
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "user_id": request.user_id,
                "priority": request.priority.value,
                "category": request.category,
                "created_by": current_user.get("user_id")
            }
        )
        
        return _ticket_to_response(ticket)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ticket"
        )


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket by ID",
    description="Retrieve detailed information about a specific ticket"
)
async def get_ticket(
    ticket_id: str,
    include_comments: bool = Query(False, description="Include ticket comments"),
    include_history: bool = Query(False, description="Include status history"),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> TicketResponse:
    """
    Get ticket details by ID.
    
    Returns comprehensive ticket information including current status,
    assignment details, and optional comments and history.
    """
    try:
        # Get ticket
        ticket_repo = get_ticket_repository()
        ticket = ticket_repo.get_by_id(ticket_id)
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        # Check access permissions
        if not _can_access_ticket(ticket, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this ticket"
            )
        
        # Get additional data if requested
        additional_data = {}
        if include_comments:
            additional_data["comments"] = await _get_ticket_comments(ticket_id)
        
        if include_history:
            additional_data["status_history"] = await _get_ticket_history(ticket_id)
        
        logger.info(
            f"Retrieved ticket {ticket.ticket_number}",
            extra={
                "ticket_id": ticket_id,
                "accessed_by": current_user.get("user_id"),
                "include_comments": include_comments,
                "include_history": include_history
            }
        )
        
        response = _ticket_to_response(ticket)
        
        # Add additional data if requested
        if additional_data:
            response_dict = response.dict()
            response_dict.update(additional_data)
            return JSONResponse(content=response_dict)
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ticket {ticket_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve ticket"
        )


@router.put(
    "/{ticket_id}/status",
    response_model=TicketResponse,
    summary="Update ticket status",
    description="Update ticket status with workflow validation"
)
async def update_ticket_status(
    ticket_id: str,
    new_status: str,
    comment: Optional[str] = None,
    resolution: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> TicketResponse:
    """
    Update ticket status.
    
    Validates status transition according to workflow rules,
    sends notifications, and logs the change.
    """
    try:
        # Get ticket
        ticket_repo = get_ticket_repository()
        ticket = ticket_repo.get_by_id(ticket_id)
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        # Check if user can modify this ticket
        if not _can_modify_ticket(ticket, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to modify this ticket"
            )
        
        # Initialize ticketing service
        ticketing_service = TicketingService()
        
        # Update status through service (includes workflow validation)
        updated_ticket = await ticketing_service.update_ticket_status(
            ticket_id=ticket_id,
            new_status=new_status,
            user_id=current_user.get("user_id"),
            comment=comment
        )
        
        # Add resolution if provided and status is resolved
        if resolution and new_status in ["resolved", "closed"]:
            ticket_repo.update(ticket_id, {"solution": resolution})
            updated_ticket = ticket_repo.get_by_id(ticket_id)
        
        logger.info(
            f"Updated ticket {ticket.ticket_number} status: {ticket.status} -> {new_status}",
            extra={
                "ticket_id": ticket_id,
                "old_status": ticket.status,
                "new_status": new_status,
                "updated_by": current_user.get("user_id"),
                "has_comment": bool(comment),
                "has_resolution": bool(resolution)
            }
        )
        
        return _ticket_to_response(updated_ticket)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ticket status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ticket status"
        )


@router.put(
    "/{ticket_id}/assign",
    response_model=TicketResponse,
    summary="Assign ticket",
    description="Assign ticket to a user or group"
)
async def assign_ticket(
    ticket_id: str,
    assigned_to: Optional[str] = None,
    assigned_group: Optional[str] = None,
    comment: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> TicketResponse:
    """
    Assign ticket to user or group.
    
    Updates assignment and automatically transitions status if needed.
    """
    try:
        # Get ticket
        ticket_repo = get_ticket_repository()
        ticket = ticket_repo.get_by_id(ticket_id)
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        # Check permissions
        if not _can_modify_ticket(ticket, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to modify this ticket"
            )
        
        if not assigned_to and not assigned_group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either assigned_to or assigned_group must be provided"
            )
        
        # Initialize ticketing service
        ticketing_service = TicketingService()
        
        # Assign ticket
        updated_ticket = await ticketing_service.assign_ticket(
            ticket_id=ticket_id,
            assigned_to=assigned_to,
            assigned_group=assigned_group,
            user_id=current_user.get("user_id")
        )
        
        logger.info(
            f"Assigned ticket {ticket.ticket_number}",
            extra={
                "ticket_id": ticket_id,
                "assigned_to": assigned_to,
                "assigned_group": assigned_group,
                "assigned_by": current_user.get("user_id")
            }
        )
        
        return _ticket_to_response(updated_ticket)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign ticket"
        )


@router.post(
    "/{ticket_id}/escalate",
    response_model=TicketResponse,
    summary="Escalate ticket",
    description="Escalate ticket to higher support level"
)
async def escalate_ticket(
    ticket_id: str,
    escalation_reason: str,
    escalation_level: int = 1,
    escalated_to: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> TicketResponse:
    """
    Escalate ticket to higher support level.
    
    Increases priority, assigns to escalation team, and sends notifications.
    """
    try:
        # Get ticket
        ticket_repo = get_ticket_repository()
        ticket = ticket_repo.get_by_id(ticket_id)
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        # Check permissions
        if not _can_modify_ticket(ticket, current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to modify this ticket"
            )
        
        # Initialize ticketing service
        ticketing_service = TicketingService()
        
        # Escalate ticket
        updated_ticket = await ticketing_service.escalate_ticket(
            ticket_id=ticket_id,
            escalation_level=escalation_level,
            escalation_reason=escalation_reason,
            escalated_to=escalated_to
        )
        
        logger.info(
            f"Escalated ticket {ticket.ticket_number} to level {escalation_level}",
            extra={
                "ticket_id": ticket_id,
                "escalation_level": escalation_level,
                "escalation_reason": escalation_reason,
                "escalated_by": current_user.get("user_id"),
                "escalated_to": escalated_to
            }
        )
        
        return _ticket_to_response(updated_ticket)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to escalate ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to escalate ticket"
        )


@router.get(
    "/search",
    summary="Search tickets",
    description="Search tickets with advanced filtering and pagination"
)
async def search_tickets(
    query: Optional[str] = Query(None, description="Search query"),
    status: Optional[List[str]] = Query(None, description="Filter by status"),
    priority: Optional[List[int]] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    created_after: Optional[datetime] = Query(None, description="Created after date"),
    created_before: Optional[datetime] = Query(None, description="Created before date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> Dict[str, Any]:
    """
    Search tickets with advanced filtering.
    
    Supports full-text search, multiple filters, pagination, and sorting.
    """
    try:
        # Get ticket repository
        ticket_repo = get_ticket_repository()
        
        # Build filters
        filters = {}
        if status:
            filters["status"] = status
        if priority:
            filters["priority"] = priority
        if category:
            filters["category"] = [category]
        if assigned_to:
            filters["assigned_to"] = assigned_to
        if user_id:
            filters["user_id"] = user_id
        if created_after:
            filters["created_after"] = created_after
        if created_before:
            filters["created_before"] = created_before
        
        # Apply user-level filtering (non-admin users see only their tickets)
        user_role = current_user.get("role", "")
        if user_role != "admin" and not user_id:
            filters["user_id"] = current_user.get("user_id")
        
        # Execute search
        search_result = ticket_repo.search(
            query=query,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size
        )
        
        # Convert tickets to response format
        tickets = [_ticket_to_response(ticket) for ticket in search_result.items]
        
        logger.info(
            f"Ticket search executed",
            extra={
                "query": query,
                "filters": filters,
                "page": page,
                "page_size": page_size,
                "total_results": search_result.pagination.total_items,
                "searched_by": current_user.get("user_id")
            }
        )
        
        return {
            "tickets": tickets,
            "pagination": {
                "page": search_result.pagination.page,
                "page_size": search_result.pagination.page_size,
                "total_items": search_result.pagination.total_items,
                "total_pages": search_result.pagination.total_pages,
                "has_next": search_result.pagination.has_next,
                "has_previous": search_result.pagination.has_previous
            },
            "facets": search_result.facets or {},
            "query_info": {
                "query": query,
                "filters_applied": len(filters),
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        }
    
    except Exception as e:
        logger.error(f"Ticket search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search tickets"
        )


# Helper functions

async def _enhance_ticket_data(ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """Enhance ticket data with smart categorization and priority adjustment."""
    try:
        title = ticket_data.get("title", "").lower()
        description = ticket_data.get("description", "").lower()
        
        # Smart priority adjustment based on keywords
        urgent_keywords = ["emergenza", "critico", "bloccato", "non funziona", "down", "offline"]
        high_keywords = ["importante", "urgente", "problema grave", "non riesco"]
        
        if any(keyword in title or keyword in description for keyword in urgent_keywords):
            if ticket_data.get("priority", 2) < 4:
                ticket_data["priority"] = 4
                if "tags" not in ticket_data:
                    ticket_data["tags"] = []
                ticket_data["tags"].append("auto-escalated")
        elif any(keyword in title or keyword in description for keyword in high_keywords):
            if ticket_data.get("priority", 2) < 3:
                ticket_data["priority"] = 3
        
        # Smart categorization enhancement
        if not ticket_data.get("subcategory"):
            if "email" in title or "posta" in title:
                ticket_data["subcategory"] = "email"
            elif "stampante" in title or "print" in title:
                ticket_data["subcategory"] = "printer"
            elif "rete" in title or "internet" in title or "wifi" in title:
                ticket_data["subcategory"] = "network"
            elif "password" in title or "accesso" in title or "login" in title:
                ticket_data["subcategory"] = "access"
        
        return ticket_data
        
    except Exception as e:
        logger.error(f"Failed to enhance ticket data: {e}")
        return ticket_data


async def _post_ticket_creation_tasks(ticket_id: str, created_by: str):
    """Background tasks to run after ticket creation."""
    try:
        # Update user statistics
        user_repo = get_user_repository()
        user_repo.increment_ticket_count(created_by)
        
        # Check for escalation rules
        ticketing_service = TicketingService()
        await ticketing_service.check_escalation_rules()
        
        logger.debug(f"Post-creation tasks completed for ticket {ticket_id}")
        
    except Exception as e:
        logger.error(f"Post-creation tasks failed for ticket {ticket_id}: {e}")


def _can_access_ticket(ticket, current_user: Dict[str, Any]) -> bool:
    """Check if user can access ticket."""
    user_role = current_user.get("role", "")
    user_id = current_user.get("user_id")
    
    # Admin can access all tickets
    if user_role == "admin":
        return True
    
    # User can access their own tickets
    if ticket.user_id == user_id:
        return True
    
    # Assigned technician can access
    if ticket.assigned_to == user_id:
        return True
    
    # Support team members can access tickets in their department
    if user_role in ["support", "technician"]:
        return True
    
    return False


def _can_modify_ticket(ticket, current_user: Dict[str, Any]) -> bool:
    """Check if user can modify ticket."""
    user_role = current_user.get("role", "")
    user_id = current_user.get("user_id")
    
    # Admin can modify all tickets
    if user_role == "admin":
        return True
    
    # Assigned technician can modify
    if ticket.assigned_to == user_id:
        return True
    
    # Support team can modify
    if user_role in ["support", "technician", "manager"]:
        return True
    
    # Ticket owner can modify open tickets
    if ticket.user_id == user_id and ticket.status in ["open", "pending_user"]:
        return True
    
    return False


def _ticket_to_response(ticket) -> TicketResponse:
    """Convert ticket model to response format."""
    return TicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        category=ticket.category,
        subcategory=ticket.subcategory,
        user_id=ticket.user_id,
        assigned_to=ticket.assigned_to,
        assigned_group=ticket.assigned_group,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        tags=ticket.tags or [],
        solution=ticket.solution,
        customer_satisfaction=ticket.customer_satisfaction,
        business_impact=ticket.business_impact,
        estimated_resolution_time=ticket.estimated_resolution_time,
        actual_resolution_time=ticket.actual_resolution_time
    )


async def _get_ticket_comments(ticket_id: str) -> List[Dict[str, Any]]:
    """Get ticket comments."""
    # TODO: Implement ticket comments retrieval
    return []


async def _get_ticket_history(ticket_id: str) -> List[Dict[str, Any]]:
    """Get ticket status history."""
    # TODO: Implement ticket history retrieval
    return []