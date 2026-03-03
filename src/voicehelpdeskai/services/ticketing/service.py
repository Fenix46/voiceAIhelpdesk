"""Ticketing service with adapter pattern and workflow logic."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable
from uuid import uuid4

from pydantic import BaseModel, Field, validator

from ...database import DatabaseManager, get_user_repository, get_ticket_repository
from ...database.models import Ticket, TicketStatus, TicketPriority, TicketCategory, User

logger = logging.getLogger(__name__)


class WorkflowAction(Enum):
    """Available workflow actions."""
    CREATE = "create"
    UPDATE_STATUS = "update_status"
    ASSIGN = "assign"
    ESCALATE = "escalate"
    RESOLVE = "resolve"
    CLOSE = "close"
    REOPEN = "reopen"
    CANCEL = "cancel"


class NotificationType(Enum):
    """Types of notifications."""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
    SLACK = "slack"


class ValidationError(Exception):
    """Validation error for ticket operations."""
    pass


class WorkflowError(Exception):
    """Workflow execution error."""
    pass


class TicketValidationRule(BaseModel):
    """Rule for ticket validation."""
    field: str
    rule_type: str  # "required", "min_length", "max_length", "regex", "enum"
    value: Any
    message: str


class WorkflowRule(BaseModel):
    """Rule for workflow transitions."""
    from_status: str
    to_status: str
    conditions: List[Dict[str, Any]]
    required_role: Optional[str] = None
    auto_assign: Optional[str] = None
    notification_templates: List[str] = Field(default_factory=list)


class EscalationRule(BaseModel):
    """Rule for automatic escalation."""
    trigger_condition: str  # "time_threshold", "priority_high", "no_response", "customer_complaint"
    threshold_value: Optional[int] = None  # in minutes
    escalate_to: Optional[str] = None  # user_id or group
    escalation_level: int = 1
    notification_message: str = "Ticket has been escalated"


class NotificationTemplate(BaseModel):
    """Template for notifications."""
    name: str
    type: NotificationType
    subject: str
    body: str
    recipients: List[str]  # Can include placeholders like {assigned_to}, {user_email}


class TicketAdapter(ABC):
    """Abstract adapter for different ticketing systems."""
    
    @abstractmethod
    async def create_ticket(self, ticket_data: Dict[str, Any]) -> str:
        """Create ticket in external system."""
        pass
    
    @abstractmethod
    async def update_ticket(self, ticket_id: str, update_data: Dict[str, Any]) -> bool:
        """Update ticket in external system."""
        pass
    
    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get ticket from external system."""
        pass
    
    @abstractmethod
    async def sync_status(self, ticket_id: str) -> bool:
        """Sync ticket status from external system."""
        pass


class MockAdapter(TicketAdapter):
    """Mock adapter for testing purposes."""
    
    def __init__(self):
        self.external_tickets = {}
    
    async def create_ticket(self, ticket_data: Dict[str, Any]) -> str:
        """Create ticket in mock external system."""
        external_id = f"EXT-{uuid4().hex[:8].upper()}"
        self.external_tickets[external_id] = {
            **ticket_data,
            "external_id": external_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        logger.info(f"Created ticket in external system: {external_id}")
        return external_id
    
    async def update_ticket(self, ticket_id: str, update_data: Dict[str, Any]) -> bool:
        """Update ticket in mock external system."""
        if ticket_id in self.external_tickets:
            self.external_tickets[ticket_id].update(update_data)
            self.external_tickets[ticket_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Updated external ticket: {ticket_id}")
            return True
        return False
    
    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get ticket from mock external system."""
        return self.external_tickets.get(ticket_id)
    
    async def sync_status(self, ticket_id: str) -> bool:
        """Sync ticket status from mock external system."""
        # Mock sync - in reality would check external system
        logger.info(f"Synced status for ticket: {ticket_id}")
        return True


class JiraAdapter(TicketAdapter):
    """Adapter for Jira integration (placeholder)."""
    
    def __init__(self, api_url: str, username: str, api_token: str):
        self.api_url = api_url
        self.username = username
        self.api_token = api_token
    
    async def create_ticket(self, ticket_data: Dict[str, Any]) -> str:
        """Create ticket in Jira."""
        # Placeholder - would implement actual Jira API calls
        logger.info("Would create ticket in Jira")
        return f"JIRA-{uuid4().hex[:8].upper()}"
    
    async def update_ticket(self, ticket_id: str, update_data: Dict[str, Any]) -> bool:
        """Update ticket in Jira."""
        logger.info(f"Would update Jira ticket: {ticket_id}")
        return True
    
    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get ticket from Jira."""
        logger.info(f"Would get Jira ticket: {ticket_id}")
        return None
    
    async def sync_status(self, ticket_id: str) -> bool:
        """Sync ticket status from Jira."""
        logger.info(f"Would sync Jira ticket status: {ticket_id}")
        return True


class ServiceNowAdapter(TicketAdapter):
    """Adapter for ServiceNow integration (placeholder)."""
    
    def __init__(self, instance_url: str, username: str, password: str):
        self.instance_url = instance_url
        self.username = username
        self.password = password
    
    async def create_ticket(self, ticket_data: Dict[str, Any]) -> str:
        """Create ticket in ServiceNow."""
        logger.info("Would create ticket in ServiceNow")
        return f"INC{uuid4().hex[:10].upper()}"
    
    async def update_ticket(self, ticket_id: str, update_data: Dict[str, Any]) -> bool:
        """Update ticket in ServiceNow."""
        logger.info(f"Would update ServiceNow ticket: {ticket_id}")
        return True
    
    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get ticket from ServiceNow."""
        logger.info(f"Would get ServiceNow ticket: {ticket_id}")
        return None
    
    async def sync_status(self, ticket_id: str) -> bool:
        """Sync ticket status from ServiceNow."""
        logger.info(f"Would sync ServiceNow ticket status: {ticket_id}")
        return True


class TicketingService:
    """
    Main ticketing service with workflow management and external system integration.
    
    Features:
    - Ticket validation and creation
    - Workflow state management
    - Automatic escalation
    - Notification handling
    - External system integration via adapters
    """
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        external_adapter: Optional[TicketAdapter] = None
    ):
        """Initialize ticketing service."""
        self.db_manager = db_manager or DatabaseManager()
        self.external_adapter = external_adapter or MockAdapter()
        
        # Validation rules
        self.validation_rules = self._get_default_validation_rules()
        
        # Workflow rules
        self.workflow_rules = self._get_default_workflow_rules()
        
        # Escalation rules
        self.escalation_rules = self._get_default_escalation_rules()
        
        # Notification templates
        self.notification_templates = self._get_default_notification_templates()
        
        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        logger.info("TicketingService initialized")
    
    def _get_default_validation_rules(self) -> List[TicketValidationRule]:
        """Get default validation rules."""
        return [
            TicketValidationRule(
                field="title",
                rule_type="required",
                value=True,
                message="Title is required"
            ),
            TicketValidationRule(
                field="title",
                rule_type="min_length",
                value=5,
                message="Title must be at least 5 characters"
            ),
            TicketValidationRule(
                field="title",
                rule_type="max_length",
                value=500,
                message="Title cannot exceed 500 characters"
            ),
            TicketValidationRule(
                field="description",
                rule_type="required",
                value=True,
                message="Description is required"
            ),
            TicketValidationRule(
                field="description",
                rule_type="min_length",
                value=10,
                message="Description must be at least 10 characters"
            ),
            TicketValidationRule(
                field="priority",
                rule_type="enum",
                value=[1, 2, 3, 4, 5],
                message="Priority must be between 1 and 5"
            ),
            TicketValidationRule(
                field="category",
                rule_type="enum",
                value=[e.value for e in TicketCategory],
                message=f"Category must be one of: {[e.value for e in TicketCategory]}"
            )
        ]
    
    def _get_default_workflow_rules(self) -> List[WorkflowRule]:
        """Get default workflow rules."""
        return [
            # New to In Progress
            WorkflowRule(
                from_status=TicketStatus.OPEN.value,
                to_status=TicketStatus.IN_PROGRESS.value,
                conditions=[{"field": "assigned_to", "operator": "is_not_null"}],
                notification_templates=["ticket_assigned"]
            ),
            # In Progress to Pending User
            WorkflowRule(
                from_status=TicketStatus.IN_PROGRESS.value,
                to_status=TicketStatus.PENDING_USER.value,
                conditions=[],
                notification_templates=["ticket_pending_user"]
            ),
            # In Progress to Resolved
            WorkflowRule(
                from_status=TicketStatus.IN_PROGRESS.value,
                to_status=TicketStatus.RESOLVED.value,
                conditions=[{"field": "solution", "operator": "is_not_null"}],
                notification_templates=["ticket_resolved"]
            ),
            # Resolved to Closed
            WorkflowRule(
                from_status=TicketStatus.RESOLVED.value,
                to_status=TicketStatus.CLOSED.value,
                conditions=[],
                notification_templates=["ticket_closed"]
            ),
            # Any status to Cancelled
            WorkflowRule(
                from_status="any",
                to_status=TicketStatus.CANCELLED.value,
                conditions=[],
                required_role="admin",
                notification_templates=["ticket_cancelled"]
            )
        ]
    
    def _get_default_escalation_rules(self) -> List[EscalationRule]:
        """Get default escalation rules."""
        return [
            EscalationRule(
                trigger_condition="time_threshold",
                threshold_value=240,  # 4 hours
                escalation_level=1,
                notification_message="Ticket has been escalated due to time threshold"
            ),
            EscalationRule(
                trigger_condition="priority_high",
                threshold_value=120,  # 2 hours for high priority
                escalation_level=1,
                notification_message="High priority ticket requires attention"
            ),
            EscalationRule(
                trigger_condition="no_response",
                threshold_value=480,  # 8 hours with no updates
                escalation_level=2,
                notification_message="Ticket escalated due to lack of response"
            )
        ]
    
    def _get_default_notification_templates(self) -> List[NotificationTemplate]:
        """Get default notification templates."""
        return [
            NotificationTemplate(
                name="ticket_created",
                type=NotificationType.EMAIL,
                subject="New Ticket Created: {ticket_number}",
                body="A new ticket has been created: {title}\n\nDescription: {description}",
                recipients=["{user_email}"]
            ),
            NotificationTemplate(
                name="ticket_assigned",
                type=NotificationType.EMAIL,
                subject="Ticket Assigned: {ticket_number}",
                body="Ticket {ticket_number} has been assigned to you.\n\nTitle: {title}",
                recipients=["{assigned_to_email}"]
            ),
            NotificationTemplate(
                name="ticket_resolved",
                type=NotificationType.EMAIL,
                subject="Ticket Resolved: {ticket_number}",
                body="Your ticket has been resolved.\n\nSolution: {solution}",
                recipients=["{user_email}"]
            ),
            NotificationTemplate(
                name="ticket_escalated",
                type=NotificationType.EMAIL,
                subject="Ticket Escalated: {ticket_number}",
                body="Ticket {ticket_number} has been escalated.\n\nReason: {escalation_reason}",
                recipients=["{escalated_to_email}"]
            )
        ]
    
    def validate_ticket_data(self, ticket_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate ticket data against defined rules.
        
        Args:
            ticket_data: Ticket data to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        for rule in self.validation_rules:
            field_value = ticket_data.get(rule.field)
            
            if rule.rule_type == "required":
                if rule.value and not field_value:
                    errors.append(rule.message)
            
            elif rule.rule_type == "min_length":
                if field_value and len(str(field_value)) < rule.value:
                    errors.append(rule.message)
            
            elif rule.rule_type == "max_length":
                if field_value and len(str(field_value)) > rule.value:
                    errors.append(rule.message)
            
            elif rule.rule_type == "enum":
                if field_value and field_value not in rule.value:
                    errors.append(rule.message)
            
            elif rule.rule_type == "regex":
                import re
                if field_value and not re.match(rule.value, str(field_value)):
                    errors.append(rule.message)
        
        return len(errors) == 0, errors
    
    async def create_ticket(
        self,
        ticket_data: Dict[str, Any],
        auto_assign: bool = True,
        sync_external: bool = True
    ) -> Ticket:
        """
        Create a new ticket with validation and workflow processing.
        
        Args:
            ticket_data: Ticket data
            auto_assign: Whether to auto-assign the ticket
            sync_external: Whether to sync with external system
            
        Returns:
            Created ticket
        """
        try:
            # Validate ticket data
            is_valid, errors = self.validate_ticket_data(ticket_data)
            if not is_valid:
                raise ValidationError(f"Validation failed: {', '.join(errors)}")
            
            # Auto-assign if enabled
            if auto_assign:
                assigned_user = await self._auto_assign_ticket(ticket_data)
                if assigned_user:
                    ticket_data["assigned_to"] = assigned_user.id
                    ticket_data["assigned_group"] = assigned_user.department
            
            # Create ticket in database
            ticket_repo = get_ticket_repository()
            ticket = ticket_repo.create(ticket_data)
            
            # Sync with external system
            if sync_external:
                try:
                    external_id = await self.external_adapter.create_ticket(ticket_data)
                    ticket_repo.update(ticket.id, {"external_ticket_id": external_id})
                except Exception as e:
                    logger.error(f"Failed to sync ticket with external system: {e}")
            
            # Trigger notifications
            await self._send_notifications("ticket_created", ticket)
            
            # Trigger event handlers
            await self._trigger_event_handlers("ticket_created", ticket)
            
            logger.info(f"Created ticket: {ticket.ticket_number}")
            return ticket
            
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            raise
    
    async def update_ticket_status(
        self,
        ticket_id: str,
        new_status: str,
        user_id: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Ticket:
        """
        Update ticket status with workflow validation.
        
        Args:
            ticket_id: Ticket ID
            new_status: New status
            user_id: User making the change
            comment: Optional comment
            
        Returns:
            Updated ticket
        """
        try:
            ticket_repo = get_ticket_repository()
            ticket = ticket_repo.get_by_id(ticket_id)
            
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            
            # Validate workflow transition
            if not self._validate_workflow_transition(ticket.status, new_status, user_id):
                raise WorkflowError(f"Invalid transition from {ticket.status} to {new_status}")
            
            old_status = ticket.status
            
            # Update ticket
            update_data = {"status": new_status}
            
            # Set resolution/closure timestamps
            if new_status == TicketStatus.RESOLVED.value:
                update_data["resolved_at"] = datetime.now(timezone.utc)
            elif new_status == TicketStatus.CLOSED.value:
                update_data["closed_at"] = datetime.now(timezone.utc)
            
            updated_ticket = ticket_repo.update(ticket_id, update_data)
            
            # Add comment if provided
            if comment:
                await self._add_ticket_comment(ticket_id, user_id, comment, "status_change")
            
            # Sync with external system
            try:
                if updated_ticket.external_ticket_id:
                    await self.external_adapter.update_ticket(
                        updated_ticket.external_ticket_id,
                        {"status": new_status}
                    )
            except Exception as e:
                logger.error(f"Failed to sync status change with external system: {e}")
            
            # Send notifications
            await self._send_status_change_notifications(updated_ticket, old_status, new_status)
            
            # Trigger event handlers
            await self._trigger_event_handlers("status_changed", updated_ticket, {
                "old_status": old_status,
                "new_status": new_status
            })
            
            logger.info(f"Updated ticket {ticket.ticket_number} status: {old_status} -> {new_status}")
            return updated_ticket
            
        except Exception as e:
            logger.error(f"Failed to update ticket status: {e}")
            raise
    
    async def assign_ticket(
        self,
        ticket_id: str,
        assigned_to: Optional[str] = None,
        assigned_group: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Ticket:
        """
        Assign ticket to user or group.
        
        Args:
            ticket_id: Ticket ID
            assigned_to: User ID to assign to
            assigned_group: Group to assign to
            user_id: User making the assignment
            
        Returns:
            Updated ticket
        """
        try:
            ticket_repo = get_ticket_repository()
            ticket = ticket_repo.get_by_id(ticket_id)
            
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            
            # Validate assignment
            if assigned_to:
                user_repo = get_user_repository()
                assigned_user = user_repo.get_by_id(assigned_to)
                if not assigned_user:
                    raise ValueError(f"Assigned user {assigned_to} not found")
            
            # Update assignment
            update_data = {}
            if assigned_to:
                update_data["assigned_to"] = assigned_to
            if assigned_group:
                update_data["assigned_group"] = assigned_group
            
            # Auto-update status if needed
            if ticket.status == TicketStatus.OPEN.value and (assigned_to or assigned_group):
                update_data["status"] = TicketStatus.IN_PROGRESS.value
            
            updated_ticket = ticket_repo.update(ticket_id, update_data)
            
            # Add assignment comment
            if user_id:
                comment = f"Ticket assigned to {assigned_to or assigned_group}"
                await self._add_ticket_comment(ticket_id, user_id, comment, "assignment")
            
            # Send notifications
            await self._send_notifications("ticket_assigned", updated_ticket)
            
            # Trigger event handlers
            await self._trigger_event_handlers("ticket_assigned", updated_ticket)
            
            logger.info(f"Assigned ticket {ticket.ticket_number} to {assigned_to or assigned_group}")
            return updated_ticket
            
        except Exception as e:
            logger.error(f"Failed to assign ticket: {e}")
            raise
    
    async def escalate_ticket(
        self,
        ticket_id: str,
        escalation_level: int = 1,
        escalation_reason: Optional[str] = None,
        escalated_to: Optional[str] = None
    ) -> Ticket:
        """
        Escalate ticket to higher level.
        
        Args:
            ticket_id: Ticket ID
            escalation_level: Level of escalation
            escalation_reason: Reason for escalation
            escalated_to: User to escalate to
            
        Returns:
            Updated ticket
        """
        try:
            ticket_repo = get_ticket_repository()
            ticket = ticket_repo.get_by_id(ticket_id)
            
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            
            # Determine escalation target
            if not escalated_to:
                escalated_to = await self._find_escalation_target(ticket, escalation_level)
            
            # Update ticket
            update_data = {
                "escalation_level": escalation_level,
                "escalation_reason": escalation_reason,
                "escalated_at": datetime.now(timezone.utc),
                "escalated_to": escalated_to,
                "priority": min(5, ticket.priority + 1)  # Increase priority
            }
            
            updated_ticket = ticket_repo.update(ticket_id, update_data)
            
            # Send escalation notifications
            await self._send_escalation_notifications(updated_ticket)
            
            # Trigger event handlers
            await self._trigger_event_handlers("ticket_escalated", updated_ticket)
            
            logger.info(f"Escalated ticket {ticket.ticket_number} to level {escalation_level}")
            return updated_ticket
            
        except Exception as e:
            logger.error(f"Failed to escalate ticket: {e}")
            raise
    
    async def check_escalation_rules(self) -> List[str]:
        """
        Check all tickets against escalation rules and escalate if needed.
        
        Returns:
            List of escalated ticket IDs
        """
        escalated_tickets = []
        
        try:
            ticket_repo = get_ticket_repository()
            
            # Get active tickets
            active_tickets = ticket_repo.get_active_tickets()
            
            for ticket in active_tickets:
                for rule in self.escalation_rules:
                    if await self._should_escalate_ticket(ticket, rule):
                        try:
                            await self.escalate_ticket(
                                ticket.id,
                                escalation_level=rule.escalation_level,
                                escalation_reason=rule.notification_message,
                                escalated_to=rule.escalate_to
                            )
                            escalated_tickets.append(ticket.id)
                            break  # Only escalate once per check
                        except Exception as e:
                            logger.error(f"Failed to escalate ticket {ticket.id}: {e}")
            
            if escalated_tickets:
                logger.info(f"Auto-escalated {len(escalated_tickets)} tickets")
            
            return escalated_tickets
            
        except Exception as e:
            logger.error(f"Failed to check escalation rules: {e}")
            return []
    
    def add_event_handler(self, event: str, handler: Callable):
        """Add event handler for ticket events."""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
    
    async def _auto_assign_ticket(self, ticket_data: Dict[str, Any]) -> Optional[User]:
        """Auto-assign ticket based on rules."""
        try:
            user_repo = get_user_repository()
            category = ticket_data.get("category", "general")
            
            # Simple auto-assignment logic - assign to least busy user in relevant department
            if category == "software":
                department = "IT Software"
            elif category == "hardware":
                department = "IT Hardware"
            elif category == "network":
                department = "IT Network"
            else:
                department = "IT Support"
            
            # Get available users in department
            available_users = user_repo.get_available_users_by_department(department)
            
            if available_users:
                # Return user with least active tickets
                return min(available_users, key=lambda u: u.total_tickets or 0)
            
            return None
            
        except Exception as e:
            logger.error(f"Auto-assignment failed: {e}")
            return None
    
    def _validate_workflow_transition(
        self,
        from_status: str,
        to_status: str,
        user_id: Optional[str] = None
    ) -> bool:
        """Validate if workflow transition is allowed."""
        for rule in self.workflow_rules:
            if (rule.from_status == from_status or rule.from_status == "any") and rule.to_status == to_status:
                # Check required role if specified
                if rule.required_role and user_id:
                    user_repo = get_user_repository()
                    user = user_repo.get_by_id(user_id)
                    if not user or user.role != rule.required_role:
                        return False
                
                # Check conditions
                # For simplicity, assuming conditions are met
                # In production, implement proper condition checking
                return True
        
        return False
    
    async def _should_escalate_ticket(self, ticket: Ticket, rule: EscalationRule) -> bool:
        """Check if ticket should be escalated based on rule."""
        now = datetime.now(timezone.utc)
        
        if rule.trigger_condition == "time_threshold":
            if ticket.created_at:
                time_diff = now - ticket.created_at
                return time_diff.total_seconds() / 60 > rule.threshold_value
        
        elif rule.trigger_condition == "priority_high":
            return ticket.priority >= 4 and rule.threshold_value
        
        elif rule.trigger_condition == "no_response":
            if ticket.updated_at:
                time_diff = now - ticket.updated_at
                return time_diff.total_seconds() / 60 > rule.threshold_value
        
        return False
    
    async def _find_escalation_target(self, ticket: Ticket, level: int) -> Optional[str]:
        """Find appropriate escalation target."""
        try:
            user_repo = get_user_repository()
            
            # Simple escalation logic - find manager or admin
            if ticket.assigned_to:
                assigned_user = user_repo.get_by_id(ticket.assigned_to)
                if assigned_user and assigned_user.manager_id:
                    return assigned_user.manager_id
            
            # Fallback to admin user
            admin_users = user_repo.get_admin_users()
            if admin_users:
                return admin_users[0].id
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to find escalation target: {e}")
            return None
    
    async def _add_ticket_comment(
        self,
        ticket_id: str,
        user_id: Optional[str],
        content: str,
        comment_type: str = "comment"
    ):
        """Add comment to ticket."""
        # This would use TicketComment model from the database
        # For now, just log the comment
        logger.info(f"Comment added to ticket {ticket_id} by {user_id}: {content}")
    
    async def _send_notifications(self, template_name: str, ticket: Ticket):
        """Send notifications based on template."""
        template = next((t for t in self.notification_templates if t.name == template_name), None)
        if not template:
            return
        
        # Mock notification sending
        logger.info(f"Notification sent: {template.subject} for ticket {ticket.ticket_number}")
    
    async def _send_status_change_notifications(self, ticket: Ticket, old_status: str, new_status: str):
        """Send notifications for status changes."""
        logger.info(f"Status change notification for {ticket.ticket_number}: {old_status} -> {new_status}")
    
    async def _send_escalation_notifications(self, ticket: Ticket):
        """Send escalation notifications."""
        logger.info(f"Escalation notification for ticket {ticket.ticket_number}")
    
    async def _trigger_event_handlers(self, event: str, ticket: Ticket, extra_data: Optional[Dict] = None):
        """Trigger registered event handlers."""
        handlers = self.event_handlers.get(event, [])
        for handler in handlers:
            try:
                await handler(ticket, extra_data or {})
            except Exception as e:
                logger.error(f"Event handler failed for {event}: {e}")