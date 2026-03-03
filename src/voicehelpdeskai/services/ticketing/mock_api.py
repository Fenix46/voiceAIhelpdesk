"""Mock Ticket API implementation with REST endpoints and webhook simulation."""

import asyncio
import csv
import io
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from ...database import get_db, DatabaseManager, get_ticket_repository
from ...database.models import Ticket, TicketStatus, TicketPriority, TicketCategory

logger = logging.getLogger(__name__)


# Pydantic models for API requests/responses
class TicketCreateRequest(BaseModel):
    """Request model for creating a ticket."""
    title: str = Field(..., min_length=5, max_length=500)
    description: str = Field(..., min_length=10)
    priority: int = Field(default=2, ge=1, le=5)
    category: str = Field(default="general")
    subcategory: Optional[str] = None
    user_id: str
    reporter_email: Optional[str] = None
    reporter_phone: Optional[str] = None
    affected_systems: List[str] = Field(default_factory=list)
    asset_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    business_impact: Optional[str] = None
    urgency_justification: Optional[str] = None

    @validator('category')
    def validate_category(cls, v):
        valid_categories = [e.value for e in TicketCategory]
        if v not in valid_categories:
            raise ValueError(f'Category must be one of: {valid_categories}')
        return v


class TicketUpdateRequest(BaseModel):
    """Request model for updating a ticket."""
    title: Optional[str] = Field(None, min_length=5, max_length=500)
    description: Optional[str] = Field(None, min_length=10)
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    category: Optional[str] = None
    subcategory: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_group: Optional[str] = None
    solution: Optional[str] = None
    resolution_steps: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    internal_notes: Optional[str] = None

    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = [e.value for e in TicketStatus]
            if v not in valid_statuses:
                raise ValueError(f'Status must be one of: {valid_statuses}')
        return v


class TicketResponse(BaseModel):
    """Response model for ticket data."""
    id: str
    ticket_number: str
    title: str
    description: str
    status: str
    priority: int
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


class BatchOperationRequest(BaseModel):
    """Request model for batch operations."""
    ticket_ids: List[str]
    operation: str  # "update_status", "assign", "add_tag", "bulk_delete"
    parameters: Dict[str, Any]


class BatchOperationResponse(BaseModel):
    """Response model for batch operations."""
    total_requested: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]]
    results: List[Dict[str, Any]]


class WebhookConfig(BaseModel):
    """Configuration for webhook notifications."""
    url: str
    events: List[str]  # "created", "updated", "status_changed", "assigned"
    secret: Optional[str] = None
    active: bool = True


class TicketSearchRequest(BaseModel):
    """Request model for ticket search."""
    query: Optional[str] = None
    status: Optional[List[str]] = None
    priority: Optional[List[int]] = None
    category: Optional[List[str]] = None
    assigned_to: Optional[str] = None
    user_id: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    tags: Optional[List[str]] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=1000)
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc")


class TicketStatsResponse(BaseModel):
    """Response model for ticket statistics."""
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    avg_resolution_time_hours: Optional[float]
    avg_response_time_minutes: Optional[float]
    satisfaction_score: Optional[float]
    by_category: Dict[str, int]
    by_priority: Dict[str, int]
    by_status: Dict[str, int]
    trending_tags: List[Dict[str, Any]]


class MockTicketAPI:
    """
    Mock Ticket API with comprehensive REST endpoints and webhook simulation.
    
    Features:
    - Full CRUD operations for tickets
    - Advanced search and filtering
    - Batch operations
    - Export capabilities
    - Statistics and analytics
    - Webhook simulation for real-time updates
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Initialize Mock Ticket API."""
        self.db_manager = db_manager or DatabaseManager()
        self.webhooks: List[WebhookConfig] = []
        self.app = FastAPI(
            title="VoiceHelpDeskAI Mock Ticket API",
            description="Mock ticketing system API for development and testing",
            version="1.0.0"
        )
        
        # Setup routes
        self._setup_routes()
        
        logger.info("MockTicketAPI initialized")
    
    def _setup_routes(self):
        """Setup API routes."""
        
        @self.app.post("/tickets", response_model=TicketResponse, status_code=201)
        async def create_ticket(
            ticket_data: TicketCreateRequest,
            background_tasks: BackgroundTasks,
            db: Session = Depends(get_db)
        ):
            """Create a new ticket."""
            try:
                ticket_repo = get_ticket_repository()
                
                # Create ticket using repository
                ticket = ticket_repo.create({
                    "title": ticket_data.title,
                    "description": ticket_data.description,
                    "priority": ticket_data.priority,
                    "category": ticket_data.category,
                    "subcategory": ticket_data.subcategory,
                    "user_id": ticket_data.user_id,
                    "reporter_email": ticket_data.reporter_email,
                    "reporter_phone": ticket_data.reporter_phone,
                    "affected_systems": ticket_data.affected_systems,
                    "asset_ids": ticket_data.asset_ids,
                    "tags": ticket_data.tags,
                    "business_impact": ticket_data.business_impact,
                    "urgency_justification": ticket_data.urgency_justification
                })
                
                # Trigger webhook
                background_tasks.add_task(
                    self._trigger_webhook, 
                    "created", 
                    self._ticket_to_dict(ticket)
                )
                
                return self._ticket_to_response(ticket)
                
            except Exception as e:
                logger.error(f"Failed to create ticket: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/tickets/{ticket_id}", response_model=TicketResponse)
        async def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
            """Get ticket by ID."""
            try:
                ticket_repo = get_ticket_repository()
                ticket = ticket_repo.get_by_id(ticket_id)
                
                if not ticket:
                    raise HTTPException(status_code=404, detail="Ticket not found")
                
                return self._ticket_to_response(ticket)
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get ticket {ticket_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/tickets/{ticket_id}", response_model=TicketResponse)
        async def update_ticket(
            ticket_id: str,
            ticket_data: TicketUpdateRequest,
            background_tasks: BackgroundTasks,
            db: Session = Depends(get_db)
        ):
            """Update ticket."""
            try:
                ticket_repo = get_ticket_repository()
                
                # Get current ticket
                ticket = ticket_repo.get_by_id(ticket_id)
                if not ticket:
                    raise HTTPException(status_code=404, detail="Ticket not found")
                
                # Prepare update data
                update_data = {k: v for k, v in ticket_data.dict(exclude_unset=True).items() if v is not None}
                
                # Track status changes
                old_status = ticket.status
                
                # Update ticket
                updated_ticket = ticket_repo.update(ticket_id, update_data)
                
                # Trigger appropriate webhooks
                if old_status != updated_ticket.status:
                    background_tasks.add_task(
                        self._trigger_webhook, 
                        "status_changed", 
                        {
                            **self._ticket_to_dict(updated_ticket),
                            "old_status": old_status,
                            "new_status": updated_ticket.status
                        }
                    )
                
                background_tasks.add_task(
                    self._trigger_webhook, 
                    "updated", 
                    self._ticket_to_dict(updated_ticket)
                )
                
                return self._ticket_to_response(updated_ticket)
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to update ticket {ticket_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/tickets/{ticket_id}")
        async def delete_ticket(
            ticket_id: str, 
            background_tasks: BackgroundTasks,
            db: Session = Depends(get_db)
        ):
            """Delete ticket (soft delete)."""
            try:
                ticket_repo = get_ticket_repository()
                
                # Get ticket before deletion
                ticket = ticket_repo.get_by_id(ticket_id)
                if not ticket:
                    raise HTTPException(status_code=404, detail="Ticket not found")
                
                # Soft delete
                ticket_repo.delete(ticket_id)
                
                # Trigger webhook
                background_tasks.add_task(
                    self._trigger_webhook, 
                    "deleted", 
                    self._ticket_to_dict(ticket)
                )
                
                return {"message": "Ticket deleted successfully"}
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to delete ticket {ticket_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/tickets/search")
        async def search_tickets(
            search_request: TicketSearchRequest,
            db: Session = Depends(get_db)
        ):
            """Search tickets with advanced filtering."""
            try:
                ticket_repo = get_ticket_repository()
                
                # Build search filters
                filters = {}
                if search_request.status:
                    filters["status"] = search_request.status
                if search_request.priority:
                    filters["priority"] = search_request.priority
                if search_request.category:
                    filters["category"] = search_request.category
                if search_request.assigned_to:
                    filters["assigned_to"] = search_request.assigned_to
                if search_request.user_id:
                    filters["user_id"] = search_request.user_id
                if search_request.created_after:
                    filters["created_after"] = search_request.created_after
                if search_request.created_before:
                    filters["created_before"] = search_request.created_before
                if search_request.tags:
                    filters["tags"] = search_request.tags
                
                # Execute search
                result = ticket_repo.search(
                    query=search_request.query,
                    filters=filters,
                    sort_by=search_request.sort_by,
                    sort_order=search_request.sort_order,
                    page=search_request.page,
                    page_size=search_request.page_size
                )
                
                return {
                    "tickets": [self._ticket_to_response(ticket) for ticket in result.items],
                    "pagination": {
                        "page": result.pagination.page,
                        "page_size": result.pagination.page_size,
                        "total_items": result.pagination.total_items,
                        "total_pages": result.pagination.total_pages,
                        "has_next": result.pagination.has_next,
                        "has_previous": result.pagination.has_previous
                    },
                    "facets": result.facets
                }
                
            except Exception as e:
                logger.error(f"Failed to search tickets: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/tickets/batch", response_model=BatchOperationResponse)
        async def batch_operation(
            operation_request: BatchOperationRequest,
            background_tasks: BackgroundTasks,
            db: Session = Depends(get_db)
        ):
            """Perform batch operations on tickets."""
            try:
                ticket_repo = get_ticket_repository()
                results = []
                errors = []
                successful = 0
                
                for ticket_id in operation_request.ticket_ids:
                    try:
                        ticket = ticket_repo.get_by_id(ticket_id)
                        if not ticket:
                            errors.append({
                                "ticket_id": ticket_id,
                                "error": "Ticket not found"
                            })
                            continue
                        
                        if operation_request.operation == "update_status":
                            new_status = operation_request.parameters.get("status")
                            old_status = ticket.status
                            updated_ticket = ticket_repo.update(ticket_id, {"status": new_status})
                            
                            # Trigger webhook for status change
                            background_tasks.add_task(
                                self._trigger_webhook,
                                "status_changed",
                                {
                                    **self._ticket_to_dict(updated_ticket),
                                    "old_status": old_status,
                                    "new_status": new_status
                                }
                            )
                            
                            results.append({
                                "ticket_id": ticket_id,
                                "old_status": old_status,
                                "new_status": new_status,
                                "success": True
                            })
                            successful += 1
                            
                        elif operation_request.operation == "assign":
                            assigned_to = operation_request.parameters.get("assigned_to")
                            assigned_group = operation_request.parameters.get("assigned_group")
                            
                            update_data = {}
                            if assigned_to:
                                update_data["assigned_to"] = assigned_to
                            if assigned_group:
                                update_data["assigned_group"] = assigned_group
                            
                            updated_ticket = ticket_repo.update(ticket_id, update_data)
                            
                            # Trigger webhook for assignment
                            background_tasks.add_task(
                                self._trigger_webhook,
                                "assigned",
                                self._ticket_to_dict(updated_ticket)
                            )
                            
                            results.append({
                                "ticket_id": ticket_id,
                                "assigned_to": assigned_to,
                                "assigned_group": assigned_group,
                                "success": True
                            })
                            successful += 1
                            
                        elif operation_request.operation == "add_tag":
                            new_tag = operation_request.parameters.get("tag")
                            current_tags = ticket.tags or []
                            if new_tag not in current_tags:
                                current_tags.append(new_tag)
                                updated_ticket = ticket_repo.update(ticket_id, {"tags": current_tags})
                                
                                results.append({
                                    "ticket_id": ticket_id,
                                    "tag_added": new_tag,
                                    "success": True
                                })
                                successful += 1
                            else:
                                results.append({
                                    "ticket_id": ticket_id,
                                    "tag": new_tag,
                                    "message": "Tag already exists",
                                    "success": True
                                })
                                successful += 1
                        
                        elif operation_request.operation == "bulk_delete":
                            ticket_repo.delete(ticket_id)
                            
                            # Trigger webhook
                            background_tasks.add_task(
                                self._trigger_webhook,
                                "deleted",
                                self._ticket_to_dict(ticket)
                            )
                            
                            results.append({
                                "ticket_id": ticket_id,
                                "deleted": True,
                                "success": True
                            })
                            successful += 1
                        
                        else:
                            errors.append({
                                "ticket_id": ticket_id,
                                "error": f"Unknown operation: {operation_request.operation}"
                            })
                        
                    except Exception as e:
                        errors.append({
                            "ticket_id": ticket_id,
                            "error": str(e)
                        })
                
                return BatchOperationResponse(
                    total_requested=len(operation_request.ticket_ids),
                    successful=successful,
                    failed=len(errors),
                    errors=errors,
                    results=results
                )
                
            except Exception as e:
                logger.error(f"Failed to perform batch operation: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/tickets/stats", response_model=TicketStatsResponse)
        async def get_ticket_statistics(
            start_date: Optional[datetime] = Query(None),
            end_date: Optional[datetime] = Query(None),
            db: Session = Depends(get_db)
        ):
            """Get ticket statistics."""
            try:
                ticket_repo = get_ticket_repository()
                
                # Get basic statistics
                stats = ticket_repo.get_statistics(start_date=start_date, end_date=end_date)
                
                # Get category distribution
                category_stats = ticket_repo.get_category_distribution(
                    start_date=start_date, 
                    end_date=end_date
                )
                
                # Get priority distribution
                priority_stats = ticket_repo.get_priority_distribution(
                    start_date=start_date, 
                    end_date=end_date
                )
                
                # Get status distribution
                status_stats = ticket_repo.get_status_distribution(
                    start_date=start_date, 
                    end_date=end_date
                )
                
                # Get trending tags
                trending_tags = ticket_repo.get_trending_tags(
                    start_date=start_date, 
                    end_date=end_date,
                    limit=10
                )
                
                return TicketStatsResponse(
                    total_tickets=stats.get("total_tickets", 0),
                    open_tickets=stats.get("open_tickets", 0),
                    in_progress_tickets=stats.get("in_progress_tickets", 0),
                    resolved_tickets=stats.get("resolved_tickets", 0),
                    closed_tickets=stats.get("closed_tickets", 0),
                    avg_resolution_time_hours=stats.get("avg_resolution_time_hours"),
                    avg_response_time_minutes=stats.get("avg_response_time_minutes"),
                    satisfaction_score=stats.get("avg_satisfaction_score"),
                    by_category=category_stats,
                    by_priority=priority_stats,
                    by_status=status_stats,
                    trending_tags=trending_tags
                )
                
            except Exception as e:
                logger.error(f"Failed to get ticket statistics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/tickets/export")
        async def export_tickets(
            format: str = Query("csv", regex="^(csv|json|excel)$"),
            start_date: Optional[datetime] = Query(None),
            end_date: Optional[datetime] = Query(None),
            status: Optional[List[str]] = Query(None),
            category: Optional[List[str]] = Query(None),
            db: Session = Depends(get_db)
        ):
            """Export tickets in various formats."""
            try:
                ticket_repo = get_ticket_repository()
                
                # Build filters
                filters = {}
                if start_date:
                    filters["created_after"] = start_date
                if end_date:
                    filters["created_before"] = end_date
                if status:
                    filters["status"] = status
                if category:
                    filters["category"] = category
                
                # Get tickets
                result = ticket_repo.search(
                    filters=filters,
                    page_size=10000  # Large page size for export
                )
                
                tickets = result.items
                
                if format == "csv":
                    return self._export_csv(tickets)
                elif format == "json":
                    return self._export_json(tickets)
                elif format == "excel":
                    return self._export_excel(tickets)
                
            except Exception as e:
                logger.error(f"Failed to export tickets: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Webhook management endpoints
        @self.app.post("/webhooks")
        async def register_webhook(webhook_config: WebhookConfig):
            """Register a webhook for ticket events."""
            try:
                webhook_id = str(uuid4())
                webhook_data = webhook_config.dict()
                webhook_data["id"] = webhook_id
                webhook_data["created_at"] = datetime.now(timezone.utc)
                
                self.webhooks.append(WebhookConfig(**webhook_data))
                
                return {
                    "id": webhook_id,
                    "message": "Webhook registered successfully",
                    **webhook_data
                }
                
            except Exception as e:
                logger.error(f"Failed to register webhook: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/webhooks")
        async def list_webhooks():
            """List all registered webhooks."""
            return {"webhooks": self.webhooks}
        
        @self.app.delete("/webhooks/{webhook_id}")
        async def unregister_webhook(webhook_id: str):
            """Unregister a webhook."""
            self.webhooks = [w for w in self.webhooks if getattr(w, 'id', None) != webhook_id]
            return {"message": "Webhook unregistered successfully"}
    
    def _ticket_to_response(self, ticket: Ticket) -> TicketResponse:
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
            customer_satisfaction=ticket.customer_satisfaction
        )
    
    def _ticket_to_dict(self, ticket: Ticket) -> Dict[str, Any]:
        """Convert ticket model to dictionary."""
        return {
            "id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status,
            "priority": ticket.priority,
            "category": ticket.category,
            "subcategory": ticket.subcategory,
            "user_id": ticket.user_id,
            "assigned_to": ticket.assigned_to,
            "assigned_group": ticket.assigned_group,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
            "tags": ticket.tags or [],
            "solution": ticket.solution,
            "customer_satisfaction": ticket.customer_satisfaction
        }
    
    async def _trigger_webhook(self, event: str, data: Dict[str, Any]):
        """Trigger webhook notifications."""
        for webhook in self.webhooks:
            if not webhook.active or event not in webhook.events:
                continue
            
            try:
                # In a real implementation, this would make HTTP requests
                # For mock purposes, we'll just log the webhook event
                logger.info(f"Webhook triggered: {webhook.url} - {event}")
                logger.debug(f"Webhook payload: {json.dumps(data, default=str)}")
                
                # Simulate webhook delay
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to trigger webhook {webhook.url}: {e}")
    
    def _export_csv(self, tickets: List[Ticket]) -> StreamingResponse:
        """Export tickets as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Ticket Number', 'Title', 'Status', 'Priority', 'Category',
            'User ID', 'Assigned To', 'Created At', 'Updated At',
            'Resolved At', 'Tags', 'Customer Satisfaction'
        ])
        
        # Write data
        for ticket in tickets:
            writer.writerow([
                ticket.ticket_number,
                ticket.title,
                ticket.status,
                ticket.priority,
                ticket.category,
                ticket.user_id,
                ticket.assigned_to,
                ticket.created_at.isoformat() if ticket.created_at else '',
                ticket.updated_at.isoformat() if ticket.updated_at else '',
                ticket.resolved_at.isoformat() if ticket.resolved_at else '',
                ', '.join(ticket.tags or []),
                ticket.customer_satisfaction
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type='text/csv',
            headers={"Content-Disposition": "attachment; filename=tickets.csv"}
        )
    
    def _export_json(self, tickets: List[Ticket]) -> JSONResponse:
        """Export tickets as JSON."""
        data = [self._ticket_to_dict(ticket) for ticket in tickets]
        
        return JSONResponse(
            content={
                "export_date": datetime.now(timezone.utc).isoformat(),
                "total_tickets": len(tickets),
                "tickets": data
            }
        )
    
    def _export_excel(self, tickets: List[Ticket]) -> StreamingResponse:
        """Export tickets as Excel (placeholder - would need openpyxl)."""
        # For now, return CSV with Excel media type
        # In production, implement proper Excel export with openpyxl
        return self._export_csv(tickets)