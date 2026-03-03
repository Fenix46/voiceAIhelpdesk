"""Repository pattern implementation for all database entities with advanced features."""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Type, Tuple, Generic, TypeVar
from dataclasses import dataclass
from enum import Enum
import json
from sqlalchemy.orm import Session, Query, joinedload, selectinload
from sqlalchemy import and_, or_, func, text, desc, asc, case, exists
from sqlalchemy.exc import IntegrityError, NoResultFound
from loguru import logger

from .models import (
    Base, User, Ticket, Conversation, KnowledgeBase, SystemLog, 
    UserPreference, TicketComment, ConversationMessage,
    TicketStatus, TicketPriority, TicketCategory, ConversationSentiment,
    SystemLogSeverity
)
from .manager import DatabaseManager

T = TypeVar('T', bound=Base)


class SortDirection(Enum):
    """Sort direction enumeration."""
    ASC = "asc"
    DESC = "desc"


class FilterOperator(Enum):
    """Filter operator enumeration."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_EQUAL = "lte"
    LIKE = "like"
    ILIKE = "ilike"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"


@dataclass
class FilterCriteria:
    """Filter criteria for queries."""
    field: str
    operator: FilterOperator
    value: Any
    case_sensitive: bool = True


@dataclass
class SortCriteria:
    """Sort criteria for queries."""
    field: str
    direction: SortDirection = SortDirection.ASC


@dataclass
class PaginationInfo:
    """Pagination information."""
    page: int = 1
    page_size: int = 50
    total_items: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_prev: bool = False


@dataclass
class SearchResult(Generic[T]):
    """Search result with pagination."""
    items: List[T]
    pagination: PaginationInfo
    filters_applied: List[FilterCriteria]
    sort_applied: List[SortCriteria]
    execution_time: float = 0.0


class BaseRepository(Generic[T], ABC):
    """Base repository class with common CRUD operations."""
    
    def __init__(self, model_class: Type[T], db_manager: DatabaseManager):
        """Initialize repository.
        
        Args:
            model_class: SQLAlchemy model class
            db_manager: Database manager instance
        """
        self.model_class = model_class
        self.db_manager = db_manager
        self.table_name = model_class.__tablename__
    
    def create(self, **kwargs) -> T:
        """Create new entity.
        
        Args:
            **kwargs: Entity attributes
            
        Returns:
            Created entity
        """
        with self.db_manager.get_transaction() as session:
            entity = self.model_class(**kwargs)
            session.add(entity)
            session.flush()  # Get the ID without committing
            return entity
    
    def get_by_id(self, entity_id: str, include_deleted: bool = False) -> Optional[T]:
        """Get entity by ID.
        
        Args:
            entity_id: Entity ID
            include_deleted: Include soft-deleted records
            
        Returns:
            Entity or None
        """
        with self.db_manager.get_session() as session:
            query = session.query(self.model_class).filter(self.model_class.id == entity_id)
            
            if hasattr(self.model_class, 'is_deleted') and not include_deleted:
                query = query.filter(self.model_class.is_deleted == False)
            
            return query.first()
    
    def get_all(self, 
               include_deleted: bool = False,
               limit: Optional[int] = None,
               offset: int = 0) -> List[T]:
        """Get all entities.
        
        Args:
            include_deleted: Include soft-deleted records
            limit: Maximum number of records
            offset: Number of records to skip
            
        Returns:
            List of entities
        """
        with self.db_manager.get_session() as session:
            query = session.query(self.model_class)
            
            if hasattr(self.model_class, 'is_deleted') and not include_deleted:
                query = query.filter(self.model_class.is_deleted == False)
            
            if offset > 0:
                query = query.offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    def update(self, entity_id: str, **kwargs) -> Optional[T]:
        """Update entity.
        
        Args:
            entity_id: Entity ID
            **kwargs: Attributes to update
            
        Returns:
            Updated entity or None
        """
        with self.db_manager.get_transaction() as session:
            entity = session.query(self.model_class).filter(self.model_class.id == entity_id).first()
            
            if not entity:
                return None
            
            # Update attributes
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            # Update timestamp if available
            if hasattr(entity, 'updated_at'):
                entity.updated_at = datetime.now()
            
            return entity
    
    def delete(self, entity_id: str, soft_delete: bool = True, deleted_by: Optional[str] = None) -> bool:
        """Delete entity.
        
        Args:
            entity_id: Entity ID
            soft_delete: Use soft delete if available
            deleted_by: User who performed deletion
            
        Returns:
            True if deleted successfully
        """
        with self.db_manager.get_transaction() as session:
            entity = session.query(self.model_class).filter(self.model_class.id == entity_id).first()
            
            if not entity:
                return False
            
            if soft_delete and hasattr(entity, 'is_deleted'):
                # Soft delete
                entity.is_deleted = True
                entity.deleted_at = datetime.now()
                if hasattr(entity, 'deleted_by') and deleted_by:
                    entity.deleted_by = deleted_by
            else:
                # Hard delete
                session.delete(entity)
            
            return True
    
    def restore(self, entity_id: str) -> bool:
        """Restore soft-deleted entity.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            True if restored successfully
        """
        if not hasattr(self.model_class, 'is_deleted'):
            return False
        
        with self.db_manager.get_transaction() as session:
            entity = session.query(self.model_class).filter(
                and_(
                    self.model_class.id == entity_id,
                    self.model_class.is_deleted == True
                )
            ).first()
            
            if not entity:
                return False
            
            entity.is_deleted = False
            entity.deleted_at = None
            entity.deleted_by = None
            
            return True
    
    def count(self, include_deleted: bool = False, filters: Optional[List[FilterCriteria]] = None) -> int:
        """Count entities.
        
        Args:
            include_deleted: Include soft-deleted records
            filters: Additional filter criteria
            
        Returns:
            Count of entities
        """
        with self.db_manager.get_session() as session:
            query = session.query(func.count(self.model_class.id))
            
            if hasattr(self.model_class, 'is_deleted') and not include_deleted:
                query = query.filter(self.model_class.is_deleted == False)
            
            if filters:
                query = self._apply_filters(query, filters)
            
            return query.scalar()
    
    def search(self,
              filters: Optional[List[FilterCriteria]] = None,
              sort_by: Optional[List[SortCriteria]] = None,
              page: int = 1,
              page_size: int = 50,
              include_deleted: bool = False) -> SearchResult[T]:
        """Advanced search with filtering, sorting, and pagination.
        
        Args:
            filters: Filter criteria
            sort_by: Sort criteria
            page: Page number (1-based)
            page_size: Items per page
            include_deleted: Include soft-deleted records
            
        Returns:
            Search result with pagination
        """
        start_time = time.time()
        
        with self.db_manager.get_session() as session:
            # Build base query
            query = session.query(self.model_class)
            
            if hasattr(self.model_class, 'is_deleted') and not include_deleted:
                query = query.filter(self.model_class.is_deleted == False)
            
            # Apply filters
            if filters:
                query = self._apply_filters(query, filters)
            
            # Count total items
            total_items = query.count()
            
            # Apply sorting
            if sort_by:
                query = self._apply_sorting(query, sort_by)
            else:
                # Default sorting
                if hasattr(self.model_class, 'created_at'):
                    query = query.order_by(desc(self.model_class.created_at))
            
            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)
            
            # Execute query
            items = query.all()
            
            # Calculate pagination info
            total_pages = (total_items + page_size - 1) // page_size
            pagination = PaginationInfo(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1
            )
            
            execution_time = time.time() - start_time
            
            return SearchResult(
                items=items,
                pagination=pagination,
                filters_applied=filters or [],
                sort_applied=sort_by or [],
                execution_time=execution_time
            )
    
    def _apply_filters(self, query: Query, filters: List[FilterCriteria]) -> Query:
        """Apply filter criteria to query.
        
        Args:
            query: SQLAlchemy query
            filters: Filter criteria
            
        Returns:
            Modified query
        """
        for filter_criteria in filters:
            column = getattr(self.model_class, filter_criteria.field, None)
            if not column:
                continue
            
            if filter_criteria.operator == FilterOperator.EQUALS:
                query = query.filter(column == filter_criteria.value)
            elif filter_criteria.operator == FilterOperator.NOT_EQUALS:
                query = query.filter(column != filter_criteria.value)
            elif filter_criteria.operator == FilterOperator.GREATER_THAN:
                query = query.filter(column > filter_criteria.value)
            elif filter_criteria.operator == FilterOperator.GREATER_EQUAL:
                query = query.filter(column >= filter_criteria.value)
            elif filter_criteria.operator == FilterOperator.LESS_THAN:
                query = query.filter(column < filter_criteria.value)
            elif filter_criteria.operator == FilterOperator.LESS_EQUAL:
                query = query.filter(column <= filter_criteria.value)
            elif filter_criteria.operator == FilterOperator.LIKE:
                if filter_criteria.case_sensitive:
                    query = query.filter(column.like(f"%{filter_criteria.value}%"))
                else:
                    query = query.filter(column.ilike(f"%{filter_criteria.value}%"))
            elif filter_criteria.operator == FilterOperator.IN:
                query = query.filter(column.in_(filter_criteria.value))
            elif filter_criteria.operator == FilterOperator.NOT_IN:
                query = query.filter(~column.in_(filter_criteria.value))
            elif filter_criteria.operator == FilterOperator.IS_NULL:
                query = query.filter(column.is_(None))
            elif filter_criteria.operator == FilterOperator.IS_NOT_NULL:
                query = query.filter(column.isnot(None))
            elif filter_criteria.operator == FilterOperator.BETWEEN:
                if isinstance(filter_criteria.value, (list, tuple)) and len(filter_criteria.value) == 2:
                    query = query.filter(column.between(filter_criteria.value[0], filter_criteria.value[1]))
        
        return query
    
    def _apply_sorting(self, query: Query, sort_criteria: List[SortCriteria]) -> Query:
        """Apply sort criteria to query.
        
        Args:
            query: SQLAlchemy query
            sort_criteria: Sort criteria
            
        Returns:
            Modified query
        """
        for sort in sort_criteria:
            column = getattr(self.model_class, sort.field, None)
            if not column:
                continue
            
            if sort.direction == SortDirection.DESC:
                query = query.order_by(desc(column))
            else:
                query = query.order_by(asc(column))
        
        return query


class UserRepository(BaseRepository[User]):
    """Repository for User entity with specialized operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(User, db_manager)
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username.
        
        Args:
            username: Username
            
        Returns:
            User or None
        """
        with self.db_manager.get_session() as session:
            return session.query(User).filter(
                and_(
                    User.username == username,
                    User.is_deleted == False,
                    User.is_active == True
                )
            ).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.
        
        Args:
            email: Email address
            
        Returns:
            User or None
        """
        with self.db_manager.get_session() as session:
            return session.query(User).filter(
                and_(
                    User.email == email,
                    User.is_deleted == False,
                    User.is_active == True
                )
            ).first()
    
    def get_by_department(self, department: str, active_only: bool = True) -> List[User]:
        """Get users by department.
        
        Args:
            department: Department name
            active_only: Include only active users
            
        Returns:
            List of users
        """
        with self.db_manager.get_session() as session:
            query = session.query(User).filter(
                and_(
                    User.department == department,
                    User.is_deleted == False
                )
            )
            
            if active_only:
                query = query.filter(User.is_active == True)
            
            return query.order_by(User.full_name).all()
    
    def update_last_activity(self, user_id: str) -> bool:
        """Update user's last activity timestamp.
        
        Args:
            user_id: User ID
            
        Returns:
            True if updated successfully
        """
        with self.db_manager.get_transaction() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                user.last_activity = datetime.now()
                return True
            return False
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user preferences.
        
        Args:
            user_id: User ID
            
        Returns:
            User preferences dictionary
        """
        with self.db_manager.get_session() as session:
            preferences = session.query(UserPreference).filter(
                UserPreference.user_id == user_id
            ).all()
            
            result = {}
            for pref in preferences:
                if pref.preference_category not in result:
                    result[pref.preference_category] = {}
                result[pref.preference_category][pref.preference_key] = pref.preference_value
            
            return result
    
    def set_user_preference(self, 
                           user_id: str, 
                           category: str, 
                           key: str, 
                           value: Any,
                           description: Optional[str] = None) -> bool:
        """Set user preference.
        
        Args:
            user_id: User ID
            category: Preference category
            key: Preference key
            value: Preference value
            description: Optional description
            
        Returns:
            True if set successfully
        """
        with self.db_manager.get_transaction() as session:
            # Check if preference exists
            preference = session.query(UserPreference).filter(
                and_(
                    UserPreference.user_id == user_id,
                    UserPreference.preference_category == category,
                    UserPreference.preference_key == key
                )
            ).first()
            
            if preference:
                # Update existing
                preference.preference_value = value
                preference.usage_count += 1
                preference.last_used = datetime.now()
                if description:
                    preference.description = description
            else:
                # Create new
                preference = UserPreference(
                    user_id=user_id,
                    preference_category=category,
                    preference_key=key,
                    preference_value=value,
                    description=description,
                    usage_count=1,
                    last_used=datetime.now()
                )
                session.add(preference)
            
            return True
    
    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive user statistics.
        
        Args:
            user_id: User ID
            
        Returns:
            User statistics
        """
        with self.db_manager.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return {}
            
            # Get ticket statistics
            ticket_stats = session.query(
                Ticket.status,
                func.count(Ticket.id).label('count')
            ).filter(Ticket.user_id == user_id).group_by(Ticket.status).all()
            
            # Get conversation statistics
            conversation_stats = session.query(
                func.count(Conversation.id).label('total'),
                func.avg(Conversation.user_satisfaction).label('avg_satisfaction'),
                func.sum(Conversation.duration_seconds).label('total_duration')
            ).filter(Conversation.user_id == user_id).first()
            
            return {
                'user_id': user_id,
                'total_tickets': user.total_tickets,
                'total_conversations': user.total_conversations,
                'satisfaction_score': user.satisfaction_score,
                'last_activity': user.last_activity.isoformat() if user.last_activity else None,
                'ticket_breakdown': {status: count for status, count in ticket_stats},
                'conversation_stats': {
                    'total': conversation_stats.total or 0,
                    'average_satisfaction': float(conversation_stats.avg_satisfaction or 0),
                    'total_duration_minutes': (conversation_stats.total_duration or 0) / 60
                }
            }


class TicketRepository(BaseRepository[Ticket]):
    """Repository for Ticket entity with specialized operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(Ticket, db_manager)
    
    def get_by_ticket_number(self, ticket_number: str) -> Optional[Ticket]:
        """Get ticket by ticket number.
        
        Args:
            ticket_number: Ticket number
            
        Returns:
            Ticket or None
        """
        with self.db_manager.get_session() as session:
            return session.query(Ticket).filter(
                and_(
                    Ticket.ticket_number == ticket_number,
                    Ticket.is_deleted == False
                )
            ).first()
    
    def get_user_tickets(self, 
                        user_id: str, 
                        status_filter: Optional[List[TicketStatus]] = None,
                        limit: Optional[int] = None) -> List[Ticket]:
        """Get tickets for user.
        
        Args:
            user_id: User ID
            status_filter: Filter by ticket statuses
            limit: Maximum number of tickets
            
        Returns:
            List of tickets
        """
        with self.db_manager.get_session() as session:
            query = session.query(Ticket).filter(
                and_(
                    Ticket.user_id == user_id,
                    Ticket.is_deleted == False
                )
            )
            
            if status_filter:
                status_values = [status.value for status in status_filter]
                query = query.filter(Ticket.status.in_(status_values))
            
            query = query.order_by(desc(Ticket.created_at))
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    def get_assigned_tickets(self, 
                           assignee_id: str, 
                           include_group_assignments: bool = True) -> List[Ticket]:
        """Get tickets assigned to user.
        
        Args:
            assignee_id: Assignee user ID
            include_group_assignments: Include group assignments
            
        Returns:
            List of assigned tickets
        """
        with self.db_manager.get_session() as session:
            query = session.query(Ticket).filter(
                and_(
                    Ticket.assigned_to == assignee_id,
                    Ticket.status.in_([TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value]),
                    Ticket.is_deleted == False
                )
            )
            
            return query.order_by(desc(Ticket.priority), Ticket.created_at).all()
    
    def get_tickets_by_priority(self, 
                              priority: TicketPriority,
                              include_resolved: bool = False) -> List[Ticket]:
        """Get tickets by priority.
        
        Args:
            priority: Ticket priority
            include_resolved: Include resolved/closed tickets
            
        Returns:
            List of tickets
        """
        with self.db_manager.get_session() as session:
            query = session.query(Ticket).filter(
                and_(
                    Ticket.priority == priority.value,
                    Ticket.is_deleted == False
                )
            )
            
            if not include_resolved:
                query = query.filter(
                    Ticket.status.in_([
                        TicketStatus.OPEN.value,
                        TicketStatus.IN_PROGRESS.value,
                        TicketStatus.PENDING_USER.value,
                        TicketStatus.PENDING_VENDOR.value
                    ])
                )
            
            return query.order_by(Ticket.created_at).all()
    
    def get_overdue_tickets(self) -> List[Ticket]:
        """Get overdue tickets.
        
        Returns:
            List of overdue tickets
        """
        with self.db_manager.get_session() as session:
            now = datetime.now()
            return session.query(Ticket).filter(
                and_(
                    Ticket.resolution_deadline < now,
                    Ticket.status.in_([
                        TicketStatus.OPEN.value,
                        TicketStatus.IN_PROGRESS.value,
                        TicketStatus.PENDING_USER.value,
                        TicketStatus.PENDING_VENDOR.value
                    ]),
                    Ticket.is_deleted == False
                )
            ).order_by(Ticket.resolution_deadline).all()
    
    def get_ticket_statistics(self, 
                            start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get comprehensive ticket statistics.
        
        Args:
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            Ticket statistics
        """
        with self.db_manager.get_session() as session:
            # Base query
            query = session.query(Ticket).filter(Ticket.is_deleted == False)
            
            if start_date:
                query = query.filter(Ticket.created_at >= start_date)
            if end_date:
                query = query.filter(Ticket.created_at <= end_date)
            
            # Status distribution
            status_stats = session.query(
                Ticket.status,
                func.count(Ticket.id).label('count')
            ).filter(Ticket.is_deleted == False)
            
            if start_date:
                status_stats = status_stats.filter(Ticket.created_at >= start_date)
            if end_date:
                status_stats = status_stats.filter(Ticket.created_at <= end_date)
            
            status_stats = status_stats.group_by(Ticket.status).all()
            
            # Priority distribution
            priority_stats = session.query(
                Ticket.priority,
                func.count(Ticket.id).label('count')
            ).filter(Ticket.is_deleted == False)
            
            if start_date:
                priority_stats = priority_stats.filter(Ticket.created_at >= start_date)
            if end_date:
                priority_stats = priority_stats.filter(Ticket.created_at <= end_date)
            
            priority_stats = priority_stats.group_by(Ticket.priority).all()
            
            # Category distribution
            category_stats = session.query(
                Ticket.category,
                func.count(Ticket.id).label('count')
            ).filter(Ticket.is_deleted == False)
            
            if start_date:
                category_stats = category_stats.filter(Ticket.created_at >= start_date)
            if end_date:
                category_stats = category_stats.filter(Ticket.created_at <= end_date)
            
            category_stats = category_stats.group_by(Ticket.category).all()
            
            # Resolution metrics
            resolved_tickets = query.filter(Ticket.resolved_at.isnot(None))
            avg_resolution_time = resolved_tickets.with_entities(
                func.avg(Ticket.actual_resolution_time)
            ).scalar()
            
            total_tickets = query.count()
            resolved_count = resolved_tickets.count()
            
            return {
                'total_tickets': total_tickets,
                'resolved_tickets': resolved_count,
                'resolution_rate': (resolved_count / total_tickets * 100) if total_tickets > 0 else 0,
                'average_resolution_time_minutes': float(avg_resolution_time or 0),
                'status_distribution': {status: count for status, count in status_stats},
                'priority_distribution': {priority: count for priority, count in priority_stats},
                'category_distribution': {category: count for category, count in category_stats},
                'period': {
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                }
            }
    
    def search_tickets(self, 
                      search_term: str,
                      search_fields: Optional[List[str]] = None,
                      limit: int = 50) -> List[Ticket]:
        """Search tickets by text.
        
        Args:
            search_term: Search term
            search_fields: Fields to search in (default: title, description)
            limit: Maximum results
            
        Returns:
            List of matching tickets
        """
        if not search_fields:
            search_fields = ['title', 'description']
        
        with self.db_manager.get_session() as session:
            # Build search conditions
            search_conditions = []
            for field in search_fields:
                if hasattr(Ticket, field):
                    column = getattr(Ticket, field)
                    search_conditions.append(column.ilike(f"%{search_term}%"))
            
            if not search_conditions:
                return []
            
            return session.query(Ticket).filter(
                and_(
                    or_(*search_conditions),
                    Ticket.is_deleted == False
                )
            ).order_by(desc(Ticket.updated_at)).limit(limit).all()
    
    def add_comment(self, 
                   ticket_id: str, 
                   user_id: str, 
                   content: str,
                   comment_type: str = "comment",
                   is_internal: bool = False) -> Optional[TicketComment]:
        """Add comment to ticket.
        
        Args:
            ticket_id: Ticket ID
            user_id: User ID who added comment
            content: Comment content
            comment_type: Type of comment
            is_internal: Internal comment flag
            
        Returns:
            Created comment or None
        """
        with self.db_manager.get_transaction() as session:
            ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                return None
            
            comment = TicketComment(
                ticket_id=ticket_id,
                user_id=user_id,
                content=content,
                comment_type=comment_type,
                is_internal=is_internal
            )
            
            session.add(comment)
            
            # Update ticket's updated_at timestamp
            ticket.updated_at = datetime.now()
            
            return comment
    
    def get_ticket_comments(self, ticket_id: str, include_internal: bool = True) -> List[TicketComment]:
        """Get ticket comments.
        
        Args:
            ticket_id: Ticket ID
            include_internal: Include internal comments
            
        Returns:
            List of comments
        """
        with self.db_manager.get_session() as session:
            query = session.query(TicketComment).filter(TicketComment.ticket_id == ticket_id)
            
            if not include_internal:
                query = query.filter(TicketComment.is_internal == False)
            
            return query.order_by(TicketComment.created_at).all()


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for Conversation entity with specialized operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(Conversation, db_manager)
    
    def get_by_session_id(self, session_id: str) -> Optional[Conversation]:
        """Get conversation by session ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Conversation or None
        """
        with self.db_manager.get_session() as session:
            return session.query(Conversation).filter(
                and_(
                    Conversation.session_id == session_id,
                    Conversation.is_deleted == False
                )
            ).order_by(desc(Conversation.created_at)).first()
    
    def get_user_conversations(self, 
                             user_id: str, 
                             limit: Optional[int] = None,
                             include_ticket_conversations: bool = True) -> List[Conversation]:
        """Get conversations for user.
        
        Args:
            user_id: User ID
            limit: Maximum number of conversations
            include_ticket_conversations: Include ticket-related conversations
            
        Returns:
            List of conversations
        """
        with self.db_manager.get_session() as session:
            query = session.query(Conversation).filter(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.is_deleted == False
                )
            )
            
            if not include_ticket_conversations:
                query = query.filter(Conversation.ticket_id.is_(None))
            
            query = query.order_by(desc(Conversation.created_at))
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    def get_ticket_conversations(self, ticket_id: str) -> List[Conversation]:
        """Get conversations for ticket.
        
        Args:
            ticket_id: Ticket ID
            
        Returns:
            List of conversations
        """
        with self.db_manager.get_session() as session:
            return session.query(Conversation).filter(
                and_(
                    Conversation.ticket_id == ticket_id,
                    Conversation.is_deleted == False
                )
            ).order_by(Conversation.created_at).all()
    
    def get_conversations_by_sentiment(self, 
                                     sentiment: ConversationSentiment,
                                     start_date: Optional[datetime] = None,
                                     end_date: Optional[datetime] = None) -> List[Conversation]:
        """Get conversations by sentiment.
        
        Args:
            sentiment: Conversation sentiment
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of conversations
        """
        with self.db_manager.get_session() as session:
            query = session.query(Conversation).filter(
                and_(
                    Conversation.sentiment == sentiment.value,
                    Conversation.is_deleted == False
                )
            )
            
            if start_date:
                query = query.filter(Conversation.created_at >= start_date)
            if end_date:
                query = query.filter(Conversation.created_at <= end_date)
            
            return query.order_by(desc(Conversation.created_at)).all()
    
    def add_message(self, 
                   conversation_id: str,
                   message_type: str,
                   content: str,
                   metadata: Optional[Dict[str, Any]] = None) -> Optional[ConversationMessage]:
        """Add message to conversation.
        
        Args:
            conversation_id: Conversation ID
            message_type: Message type (user, assistant, system)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Created message or None
        """
        with self.db_manager.get_transaction() as session:
            conversation = session.query(Conversation).filter(Conversation.id == conversation_id).first()
            if not conversation:
                return None
            
            message = ConversationMessage(
                conversation_id=conversation_id,
                message_type=message_type,
                content=content
            )
            
            # Add metadata if provided
            if metadata:
                for key, value in metadata.items():
                    if hasattr(message, key):
                        setattr(message, key, value)
            
            session.add(message)
            
            # Update conversation turn count
            conversation.turn_count += 1
            conversation.updated_at = datetime.now()
            
            return message
    
    def get_conversation_messages(self, conversation_id: str) -> List[ConversationMessage]:
        """Get conversation messages.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            List of messages
        """
        with self.db_manager.get_session() as session:
            return session.query(ConversationMessage).filter(
                ConversationMessage.conversation_id == conversation_id
            ).order_by(ConversationMessage.created_at).all()
    
    def get_conversation_analytics(self, 
                                 start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get conversation analytics.
        
        Args:
            start_date: Start date for analytics
            end_date: End date for analytics
            
        Returns:
            Conversation analytics
        """
        with self.db_manager.get_session() as session:
            # Base query
            query = session.query(Conversation).filter(Conversation.is_deleted == False)
            
            if start_date:
                query = query.filter(Conversation.created_at >= start_date)
            if end_date:
                query = query.filter(Conversation.created_at <= end_date)
            
            # Sentiment distribution
            sentiment_stats = session.query(
                Conversation.sentiment,
                func.count(Conversation.id).label('count')
            ).filter(Conversation.is_deleted == False)
            
            if start_date:
                sentiment_stats = sentiment_stats.filter(Conversation.created_at >= start_date)
            if end_date:
                sentiment_stats = sentiment_stats.filter(Conversation.created_at <= end_date)
            
            sentiment_stats = sentiment_stats.group_by(Conversation.sentiment).all()
            
            # Quality metrics
            quality_metrics = query.with_entities(
                func.avg(Conversation.confidence_score).label('avg_confidence'),
                func.avg(Conversation.transcription_quality).label('avg_transcription_quality'),
                func.avg(Conversation.response_quality).label('avg_response_quality'),
                func.avg(Conversation.user_satisfaction).label('avg_user_satisfaction'),
                func.avg(Conversation.duration_seconds).label('avg_duration'),
                func.count().label('total_conversations')
            ).first()
            
            # Escalation rate
            escalated_count = query.filter(Conversation.escalated_to_human == True).count()
            total_conversations = quality_metrics.total_conversations or 0
            escalation_rate = (escalated_count / total_conversations * 100) if total_conversations > 0 else 0
            
            return {
                'total_conversations': total_conversations,
                'escalated_conversations': escalated_count,
                'escalation_rate': escalation_rate,
                'average_confidence_score': float(quality_metrics.avg_confidence or 0),
                'average_transcription_quality': float(quality_metrics.avg_transcription_quality or 0),
                'average_response_quality': float(quality_metrics.avg_response_quality or 0),
                'average_user_satisfaction': float(quality_metrics.avg_user_satisfaction or 0),
                'average_duration_seconds': float(quality_metrics.avg_duration or 0),
                'sentiment_distribution': {sentiment: count for sentiment, count in sentiment_stats},
                'period': {
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                }
            }


class KnowledgeRepository(BaseRepository[KnowledgeBase]):
    """Repository for KnowledgeBase entity with specialized operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(KnowledgeBase, db_manager)
    
    def search_by_keywords(self, 
                          keywords: List[str], 
                          category_filter: Optional[List[str]] = None,
                          limit: int = 10) -> List[KnowledgeBase]:
        """Search knowledge base by keywords.
        
        Args:
            keywords: Search keywords
            category_filter: Filter by categories
            limit: Maximum results
            
        Returns:
            List of matching articles
        """
        with self.db_manager.get_session() as session:
            query = session.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.status == "published",
                    KnowledgeBase.is_deleted == False
                )
            )
            
            # Add keyword search
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.extend([
                    KnowledgeBase.title.ilike(f"%{keyword}%"),
                    KnowledgeBase.problem_description.ilike(f"%{keyword}%"),
                    KnowledgeBase.solution.ilike(f"%{keyword}%")
                ])
            
            if keyword_conditions:
                query = query.filter(or_(*keyword_conditions))
            
            # Add category filter
            if category_filter:
                query = query.filter(KnowledgeBase.category.in_(category_filter))
            
            return query.order_by(
                desc(KnowledgeBase.search_rank),
                desc(KnowledgeBase.success_rate),
                desc(KnowledgeBase.usage_count)
            ).limit(limit).all()
    
    def get_by_category(self, 
                       category: str, 
                       include_subcategory: Optional[str] = None,
                       status_filter: str = "published") -> List[KnowledgeBase]:
        """Get articles by category.
        
        Args:
            category: Article category
            include_subcategory: Specific subcategory
            status_filter: Status filter
            
        Returns:
            List of articles
        """
        with self.db_manager.get_session() as session:
            query = session.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.category == category,
                    KnowledgeBase.status == status_filter,
                    KnowledgeBase.is_deleted == False
                )
            )
            
            if include_subcategory:
                query = query.filter(KnowledgeBase.subcategory == include_subcategory)
            
            return query.order_by(
                desc(KnowledgeBase.success_rate),
                desc(KnowledgeBase.usage_count)
            ).all()
    
    def get_featured_articles(self, limit: int = 5) -> List[KnowledgeBase]:
        """Get featured articles.
        
        Args:
            limit: Maximum articles
            
        Returns:
            List of featured articles
        """
        with self.db_manager.get_session() as session:
            return session.query(KnowledgeBase).filter(
                and_(
                    KnowledgeBase.is_featured == True,
                    KnowledgeBase.status == "published",
                    KnowledgeBase.is_deleted == False
                )
            ).order_by(
                desc(KnowledgeBase.success_rate),
                desc(KnowledgeBase.view_count)
            ).limit(limit).all()
    
    def update_usage_stats(self, 
                          article_id: str, 
                          success: Optional[bool] = None,
                          rating: Optional[float] = None) -> bool:
        """Update article usage statistics.
        
        Args:
            article_id: Article ID
            success: Whether the solution was successful
            rating: User rating (1-5)
            
        Returns:
            True if updated successfully
        """
        with self.db_manager.get_transaction() as session:
            article = session.query(KnowledgeBase).filter(KnowledgeBase.id == article_id).first()
            if not article:
                return False
            
            # Update usage count
            article.usage_count += 1
            
            # Update success stats
            if success is not None:
                article.total_votes += 1
                if success:
                    article.success_votes += 1
                
                # Recalculate success rate
                article.success_rate = article.success_votes / article.total_votes
            
            # Update rating
            if rating is not None and 1 <= rating <= 5:
                # Simple average rating calculation (in production, might want more sophisticated approach)
                if article.average_rating:
                    # Weighted average with existing rating
                    total_ratings = article.total_votes
                    article.average_rating = ((article.average_rating * (total_ratings - 1)) + rating) / total_ratings
                else:
                    article.average_rating = rating
            
            return True
    
    def increment_view_count(self, article_id: str) -> bool:
        """Increment article view count.
        
        Args:
            article_id: Article ID
            
        Returns:
            True if updated successfully
        """
        with self.db_manager.get_transaction() as session:
            article = session.query(KnowledgeBase).filter(KnowledgeBase.id == article_id).first()
            if article:
                article.view_count += 1
                return True
            return False
    
    def get_articles_needing_review(self) -> List[KnowledgeBase]:
        """Get articles that need review.
        
        Returns:
            List of articles needing review
        """
        with self.db_manager.get_session() as session:
            cutoff_date = datetime.now()
            return session.query(KnowledgeBase).filter(
                and_(
                    or_(
                        KnowledgeBase.review_due_date < cutoff_date,
                        KnowledgeBase.last_reviewed.is_(None)
                    ),
                    KnowledgeBase.status == "published",
                    KnowledgeBase.is_deleted == False
                )
            ).order_by(KnowledgeBase.review_due_date).all()
    
    def get_knowledge_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics.
        
        Returns:
            Knowledge base statistics
        """
        with self.db_manager.get_session() as session:
            # Category distribution
            category_stats = session.query(
                KnowledgeBase.category,
                func.count(KnowledgeBase.id).label('count')
            ).filter(
                and_(
                    KnowledgeBase.status == "published",
                    KnowledgeBase.is_deleted == False
                )
            ).group_by(KnowledgeBase.category).all()
            
            # Status distribution
            status_stats = session.query(
                KnowledgeBase.status,
                func.count(KnowledgeBase.id).label('count')
            ).filter(KnowledgeBase.is_deleted == False).group_by(KnowledgeBase.status).all()
            
            # Quality metrics
            quality_metrics = session.query(
                func.avg(KnowledgeBase.success_rate).label('avg_success_rate'),
                func.avg(KnowledgeBase.average_rating).label('avg_rating'),
                func.sum(KnowledgeBase.view_count).label('total_views'),
                func.sum(KnowledgeBase.usage_count).label('total_usage'),
                func.count().label('total_articles')
            ).filter(
                and_(
                    KnowledgeBase.status == "published",
                    KnowledgeBase.is_deleted == False
                )
            ).first()
            
            # Articles needing review
            review_needed = len(self.get_articles_needing_review())
            
            return {
                'total_articles': quality_metrics.total_articles or 0,
                'total_views': quality_metrics.total_views or 0,
                'total_usage': quality_metrics.total_usage or 0,
                'average_success_rate': float(quality_metrics.avg_success_rate or 0),
                'average_rating': float(quality_metrics.avg_rating or 0),
                'articles_needing_review': review_needed,
                'category_distribution': {category: count for category, count in category_stats},
                'status_distribution': {status: count for status, count in status_stats}
            }


class SystemLogRepository(BaseRepository[SystemLog]):
    """Repository for SystemLog entity with specialized operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(SystemLog, db_manager)
    
    def log_event(self, 
                 event_type: str,
                 message: str,
                 severity: SystemLogSeverity = SystemLogSeverity.INFO,
                 source: str = "system",
                 details: Optional[Dict[str, Any]] = None,
                 **kwargs) -> SystemLog:
        """Log system event.
        
        Args:
            event_type: Event type
            message: Log message
            severity: Log severity
            source: Event source
            details: Additional details
            **kwargs: Additional log fields
            
        Returns:
            Created log entry
        """
        with self.db_manager.get_transaction() as session:
            log_entry = SystemLog(
                event_type=event_type,
                message=message,
                severity=severity.value,
                source=source,
                details=details or {},
                **kwargs
            )
            
            session.add(log_entry)
            return log_entry
    
    def get_logs_by_severity(self, 
                           severity: SystemLogSeverity,
                           hours_back: int = 24,
                           limit: int = 1000) -> List[SystemLog]:
        """Get logs by severity level.
        
        Args:
            severity: Log severity
            hours_back: Hours back from now
            limit: Maximum logs
            
        Returns:
            List of log entries
        """
        with self.db_manager.get_session() as session:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            return session.query(SystemLog).filter(
                and_(
                    SystemLog.severity == severity.value,
                    SystemLog.timestamp >= cutoff_time
                )
            ).order_by(desc(SystemLog.timestamp)).limit(limit).all()
    
    def get_error_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get error summary for specified time period.
        
        Args:
            hours_back: Hours back from now
            
        Returns:
            Error summary statistics
        """
        with self.db_manager.get_session() as session:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            # Error count by severity
            error_stats = session.query(
                SystemLog.severity,
                func.count(SystemLog.id).label('count')
            ).filter(
                and_(
                    SystemLog.timestamp >= cutoff_time,
                    SystemLog.severity.in_([
                        SystemLogSeverity.WARNING.value,
                        SystemLogSeverity.ERROR.value,
                        SystemLogSeverity.CRITICAL.value
                    ])
                )
            ).group_by(SystemLog.severity).all()
            
            # Error count by source
            source_stats = session.query(
                SystemLog.source,
                func.count(SystemLog.id).label('count')
            ).filter(
                and_(
                    SystemLog.timestamp >= cutoff_time,
                    SystemLog.severity.in_([
                        SystemLogSeverity.ERROR.value,
                        SystemLogSeverity.CRITICAL.value
                    ])
                )
            ).group_by(SystemLog.source).order_by(desc('count')).limit(10).all()
            
            total_errors = sum(count for _, count in error_stats)
            
            return {
                'total_errors': total_errors,
                'period_hours': hours_back,
                'severity_breakdown': {severity: count for severity, count in error_stats},
                'top_error_sources': {source: count for source, count in source_stats}
            }
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """Clean up old log entries.
        
        Args:
            days_to_keep: Number of days to keep
            
        Returns:
            Number of deleted log entries
        """
        with self.db_manager.get_transaction() as session:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            deleted_count = session.query(SystemLog).filter(
                SystemLog.timestamp < cutoff_date
            ).delete()
            
            return deleted_count
    
    def get_performance_logs(self, hours_back: int = 1) -> List[SystemLog]:
        """Get performance-related logs.
        
        Args:
            hours_back: Hours back from now
            
        Returns:
            List of performance log entries
        """
        with self.db_manager.get_session() as session:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            return session.query(SystemLog).filter(
                and_(
                    SystemLog.timestamp >= cutoff_time,
                    or_(
                        SystemLog.event_type.like('%performance%'),
                        SystemLog.event_type.like('%latency%'),
                        SystemLog.event_type.like('%slow%'),
                        SystemLog.response_time_ms > 1000
                    )
                )
            ).order_by(desc(SystemLog.response_time_ms)).all()


# Repository factory for easy access
class RepositoryFactory:
    """Factory class for creating repository instances."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._repositories = {}
    
    def get_user_repository(self) -> UserRepository:
        """Get user repository instance."""
        if 'user' not in self._repositories:
            self._repositories['user'] = UserRepository(self.db_manager)
        return self._repositories['user']
    
    def get_ticket_repository(self) -> TicketRepository:
        """Get ticket repository instance."""
        if 'ticket' not in self._repositories:
            self._repositories['ticket'] = TicketRepository(self.db_manager)
        return self._repositories['ticket']
    
    def get_conversation_repository(self) -> ConversationRepository:
        """Get conversation repository instance."""
        if 'conversation' not in self._repositories:
            self._repositories['conversation'] = ConversationRepository(self.db_manager)
        return self._repositories['conversation']
    
    def get_knowledge_repository(self) -> KnowledgeRepository:
        """Get knowledge repository instance."""
        if 'knowledge' not in self._repositories:
            self._repositories['knowledge'] = KnowledgeRepository(self.db_manager)
        return self._repositories['knowledge']
    
    def get_system_log_repository(self) -> SystemLogRepository:
        """Get system log repository instance."""
        if 'system_log' not in self._repositories:
            self._repositories['system_log'] = SystemLogRepository(self.db_manager)
        return self._repositories['system_log']


# Global repository factory
_repository_factory: Optional[RepositoryFactory] = None


def get_repository_factory(db_manager: Optional[DatabaseManager] = None) -> RepositoryFactory:
    """Get global repository factory instance."""
    global _repository_factory
    if _repository_factory is None:
        if not db_manager:
            from .manager import get_database_manager
            db_manager = get_database_manager()
        _repository_factory = RepositoryFactory(db_manager)
    return _repository_factory