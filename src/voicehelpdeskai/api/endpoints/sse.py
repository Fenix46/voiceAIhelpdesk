"""Server-Sent Events endpoints for real-time updates and notifications."""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set, AsyncGenerator

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from ...core.logging import get_logger
from ...core.orchestrator.conversation_orchestrator import ConversationOrchestrator
from ...database import get_conversation_repository, get_ticket_repository
from ..middleware.auth import auth_required

logger = get_logger(__name__)

router = APIRouter()


class SSEConnection:
    """Represents an active SSE connection."""
    
    def __init__(self, connection_id: str, user_id: str, connection_type: str):
        self.connection_id = connection_id
        self.user_id = user_id
        self.connection_type = connection_type
        self.connected_at = datetime.now(timezone.utc)
        self.last_heartbeat = time.time()
        self.is_active = True
        self.filters = {}


class SSEConnectionManager:
    """Manages Server-Sent Events connections."""
    
    def __init__(self):
        self.connections: Dict[str, SSEConnection] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.conversation_connections: Dict[str, Set[str]] = {}  # conversation_id -> connection_ids
        self.ticket_connections: Dict[str, Set[str]] = {}  # ticket_id -> connection_ids
        self.heartbeat_interval = 30  # seconds
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_stale_connections())
    
    def add_connection(
        self, 
        connection_id: str, 
        user_id: str, 
        connection_type: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> SSEConnection:
        """Add a new SSE connection."""
        connection = SSEConnection(connection_id, user_id, connection_type)
        connection.filters = filters or {}
        
        self.connections[connection_id] = connection
        
        # Add to user mapping
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        # Add to specific mappings based on filters
        if filters:
            if "conversation_id" in filters:
                conv_id = filters["conversation_id"]
                if conv_id not in self.conversation_connections:
                    self.conversation_connections[conv_id] = set()
                self.conversation_connections[conv_id].add(connection_id)
            
            if "ticket_id" in filters:
                ticket_id = filters["ticket_id"]
                if ticket_id not in self.ticket_connections:
                    self.ticket_connections[ticket_id] = set()
                self.ticket_connections[ticket_id].add(connection_id)
        
        logger.info(f"SSE connection added: {connection_id} (user: {user_id}, type: {connection_type})")
        return connection
    
    def remove_connection(self, connection_id: str):
        """Remove SSE connection."""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        # Remove from user mapping
        if connection.user_id in self.user_connections:
            self.user_connections[connection.user_id].discard(connection_id)
            if not self.user_connections[connection.user_id]:
                del self.user_connections[connection.user_id]
        
        # Remove from conversation mapping
        for conv_id, conn_ids in list(self.conversation_connections.items()):
            conn_ids.discard(connection_id)
            if not conn_ids:
                del self.conversation_connections[conv_id]
        
        # Remove from ticket mapping
        for ticket_id, conn_ids in list(self.ticket_connections.items()):
            conn_ids.discard(connection_id)
            if not conn_ids:
                del self.ticket_connections[ticket_id]
        
        # Remove connection
        del self.connections[connection_id]
        
        logger.info(f"SSE connection removed: {connection_id}")
    
    async def send_to_connection(self, connection_id: str, event_type: str, data: Dict[str, Any]):
        """Send event to specific connection (used by external services)."""
        if connection_id in self.connections:
            # Store the event for the connection to pick up
            if not hasattr(self.connections[connection_id], 'pending_events'):
                self.connections[connection_id].pending_events = []
            
            self.connections[connection_id].pending_events.append({
                "event": event_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    async def send_to_user(self, user_id: str, event_type: str, data: Dict[str, Any]):
        """Send event to all connections for a user."""
        if user_id in self.user_connections:
            for connection_id in list(self.user_connections[user_id]):
                await self.send_to_connection(connection_id, event_type, data)
    
    async def send_to_conversation(self, conversation_id: str, event_type: str, data: Dict[str, Any]):
        """Send event to all connections listening to a conversation."""
        if conversation_id in self.conversation_connections:
            for connection_id in list(self.conversation_connections[conversation_id]):
                await self.send_to_connection(connection_id, event_type, data)
    
    async def send_to_ticket(self, ticket_id: str, event_type: str, data: Dict[str, Any]):
        """Send event to all connections listening to a ticket."""
        if ticket_id in self.ticket_connections:
            for connection_id in list(self.ticket_connections[ticket_id]):
                await self.send_to_connection(connection_id, event_type, data)
    
    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all connections."""
        for connection_id in list(self.connections.keys()):
            await self.send_to_connection(connection_id, event_type, data)
    
    async def _cleanup_stale_connections(self):
        """Clean up stale connections periodically."""
        while True:
            try:
                current_time = time.time()
                stale_connections = []
                
                for connection_id, connection in self.connections.items():
                    if current_time - connection.last_heartbeat > self.heartbeat_interval * 3:
                        stale_connections.append(connection_id)
                
                # Remove stale connections
                for connection_id in stale_connections:
                    self.remove_connection(connection_id)
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"SSE cleanup task error: {e}")
                await asyncio.sleep(5)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "users_connected": len(self.user_connections),
            "conversation_listeners": len(self.conversation_connections),
            "ticket_listeners": len(self.ticket_connections),
            "connections_by_type": self._get_type_stats()
        }
    
    def _get_type_stats(self) -> Dict[str, int]:
        """Get statistics by connection type."""
        type_stats = {}
        for connection in self.connections.values():
            conn_type = connection.connection_type
            type_stats[conn_type] = type_stats.get(conn_type, 0) + 1
        return type_stats


# Global SSE connection manager
sse_manager = SSEConnectionManager()


@router.get("/conversation/{conversation_id}")
async def conversation_events(
    conversation_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> StreamingResponse:
    """
    Subscribe to real-time updates for a specific conversation.
    
    Events include:
    - Transcription updates (partial and final)
    - Processing status changes
    - AI responses
    - Error notifications
    """
    try:
        # Validate conversation exists and user has access
        conversation_repo = get_conversation_repository()
        conversation = conversation_repo.get_by_id(conversation_id)
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Check access permissions
        user_role = current_user.get("role", "")
        if conversation.user_id != current_user.get("user_id") and user_role != "admin":
            raise HTTPException(status_code=403, detail="Access denied to this conversation")
        
        # Create connection
        connection_id = f"conv_{uuid.uuid4().hex[:8]}"
        connection = sse_manager.add_connection(
            connection_id=connection_id,
            user_id=current_user.get("user_id"),
            connection_type="conversation",
            filters={"conversation_id": conversation_id}
        )
        
        async def event_stream():
            try:
                # Send initial connection event
                yield _format_sse_event("connected", {
                    "connection_id": connection_id,
                    "conversation_id": conversation_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
                # Event loop
                while True:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        break
                    
                    # Update heartbeat
                    connection.last_heartbeat = time.time()
                    
                    # Send pending events
                    if hasattr(connection, 'pending_events') and connection.pending_events:
                        for event in connection.pending_events:
                            yield _format_sse_event(event["event"], event["data"])
                        connection.pending_events.clear()
                    
                    # Send periodic heartbeat
                    if time.time() - connection.last_heartbeat > sse_manager.heartbeat_interval:
                        yield _format_sse_event("heartbeat", {
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    
                    await asyncio.sleep(1)  # Check for events every second
            
            finally:
                sse_manager.remove_connection(connection_id)
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create conversation SSE stream: {e}")
        raise HTTPException(status_code=500, detail="Failed to create event stream")


@router.get("/ticket/{ticket_id}")
async def ticket_events(
    ticket_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> StreamingResponse:
    """
    Subscribe to real-time updates for a specific ticket.
    
    Events include:
    - Status changes
    - Assignment updates
    - New comments
    - Priority changes
    - Resolution updates
    """
    try:
        # Validate ticket exists and user has access
        ticket_repo = get_ticket_repository()
        ticket = ticket_repo.get_by_id(ticket_id)
        
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        # Check access permissions
        if not _can_access_ticket(ticket, current_user):
            raise HTTPException(status_code=403, detail="Access denied to this ticket")
        
        # Create connection
        connection_id = f"ticket_{uuid.uuid4().hex[:8]}"
        connection = sse_manager.add_connection(
            connection_id=connection_id,
            user_id=current_user.get("user_id"),
            connection_type="ticket",
            filters={"ticket_id": ticket_id}
        )
        
        async def event_stream():
            try:
                # Send initial connection event
                yield _format_sse_event("connected", {
                    "connection_id": connection_id,
                    "ticket_id": ticket_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
                # Event loop
                while True:
                    if await request.is_disconnected():
                        break
                    
                    connection.last_heartbeat = time.time()
                    
                    # Send pending events
                    if hasattr(connection, 'pending_events') and connection.pending_events:
                        for event in connection.pending_events:
                            yield _format_sse_event(event["event"], event["data"])
                        connection.pending_events.clear()
                    
                    # Heartbeat
                    if time.time() - connection.last_heartbeat > sse_manager.heartbeat_interval:
                        yield _format_sse_event("heartbeat", {
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    
                    await asyncio.sleep(1)
            
            finally:
                sse_manager.remove_connection(connection_id)
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create ticket SSE stream: {e}")
        raise HTTPException(status_code=500, detail="Failed to create event stream")


@router.get("/system")
async def system_events(
    request: Request,
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> StreamingResponse:
    """
    Subscribe to system-wide real-time updates.
    
    Events include:
    - Queue position updates
    - System alerts
    - Maintenance notifications
    - Service status changes
    """
    try:
        user_role = current_user.get("role", "")
        
        # Parse event type filters
        event_filter = None
        if event_types:
            event_filter = [t.strip() for t in event_types.split(",")]
        
        # Create connection
        connection_id = f"system_{uuid.uuid4().hex[:8]}"
        connection = sse_manager.add_connection(
            connection_id=connection_id,
            user_id=current_user.get("user_id"),
            connection_type="system",
            filters={"event_types": event_filter}
        )
        
        async def event_stream():
            try:
                # Send initial connection event
                yield _format_sse_event("connected", {
                    "connection_id": connection_id,
                    "user_role": user_role,
                    "event_filter": event_filter,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
                # Event loop
                while True:
                    if await request.is_disconnected():
                        break
                    
                    connection.last_heartbeat = time.time()
                    
                    # Send pending events (filtered by event_types if specified)
                    if hasattr(connection, 'pending_events') and connection.pending_events:
                        for event in connection.pending_events:
                            if not event_filter or event["event"] in event_filter:
                                yield _format_sse_event(event["event"], event["data"])
                        connection.pending_events.clear()
                    
                    # Send queue position updates for regular users
                    if user_role not in ["admin", "support"]:
                        queue_info = await _get_user_queue_position(current_user.get("user_id"))
                        if queue_info:
                            yield _format_sse_event("queue_update", queue_info)
                    
                    # Heartbeat
                    if time.time() - connection.last_heartbeat > sse_manager.heartbeat_interval:
                        yield _format_sse_event("heartbeat", {
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    
                    await asyncio.sleep(2)  # System events check every 2 seconds
            
            finally:
                sse_manager.remove_connection(connection_id)
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    except Exception as e:
        logger.error(f"Failed to create system SSE stream: {e}")
        raise HTTPException(status_code=500, detail="Failed to create event stream")


@router.get("/admin/monitor")
async def admin_monitor_events(
    request: Request,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> StreamingResponse:
    """
    Admin monitoring SSE stream for system oversight.
    
    Provides real-time monitoring data for administrators.
    """
    try:
        user_role = current_user.get("role", "")
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Create connection
        connection_id = f"admin_{uuid.uuid4().hex[:8]}"
        connection = sse_manager.add_connection(
            connection_id=connection_id,
            user_id=current_user.get("user_id"),
            connection_type="admin_monitor"
        )
        
        async def event_stream():
            try:
                # Send initial connection event
                yield _format_sse_event("connected", {
                    "connection_id": connection_id,
                    "monitor_type": "admin",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
                # Event loop
                while True:
                    if await request.is_disconnected():
                        break
                    
                    connection.last_heartbeat = time.time()
                    
                    # Send system statistics every 10 seconds
                    if int(time.time()) % 10 == 0:
                        stats = await _get_system_statistics()
                        yield _format_sse_event("system_stats", stats)
                    
                    # Send SSE connection statistics
                    sse_stats = sse_manager.get_connection_stats()
                    yield _format_sse_event("sse_stats", sse_stats)
                    
                    # Send pending events
                    if hasattr(connection, 'pending_events') and connection.pending_events:
                        for event in connection.pending_events:
                            yield _format_sse_event(event["event"], event["data"])
                        connection.pending_events.clear()
                    
                    # Heartbeat
                    if time.time() - connection.last_heartbeat > sse_manager.heartbeat_interval:
                        yield _format_sse_event("heartbeat", {
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    
                    await asyncio.sleep(1)
            
            finally:
                sse_manager.remove_connection(connection_id)
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create admin monitor SSE stream: {e}")
        raise HTTPException(status_code=500, detail="Failed to create event stream")


# Helper functions

def _format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format data as Server-Sent Event."""
    json_data = json.dumps(data)
    return f"event: {event_type}\ndata: {json_data}\n\n"


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
    
    # Support team members can access
    if user_role in ["support", "technician"]:
        return True
    
    return False


async def _get_user_queue_position(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user's queue position information."""
    try:
        # Mock queue position - in production, integrate with actual queueing system
        return {
            "position": 3,
            "estimated_wait_time": 120,  # seconds
            "queue_type": "general_support",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get queue position for user {user_id}: {e}")
        return None


async def _get_system_statistics() -> Dict[str, Any]:
    """Get current system statistics."""
    try:
        # Mock system statistics - in production, integrate with monitoring systems
        return {
            "active_conversations": 15,
            "active_tickets": 42,
            "system_load": {
                "cpu_percent": 35.2,
                "memory_percent": 68.4,
                "disk_percent": 45.7
            },
            "service_status": {
                "api": "healthy",
                "database": "healthy",
                "redis": "healthy",
                "websocket": "healthy",
                "audio_processing": "healthy"
            },
            "queue_sizes": {
                "audio_processing": 3,
                "ticket_assignment": 1,
                "notification_delivery": 0
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system statistics: {e}")
        return {"error": "Failed to get statistics"}


# Function to send events from external services (used by other parts of the application)
async def send_conversation_update(conversation_id: str, event_type: str, data: Dict[str, Any]):
    """Send conversation update to all listening SSE connections."""
    await sse_manager.send_to_conversation(conversation_id, event_type, data)


async def send_ticket_update(ticket_id: str, event_type: str, data: Dict[str, Any]):
    """Send ticket update to all listening SSE connections."""
    await sse_manager.send_to_ticket(ticket_id, event_type, data)


async def send_system_alert(event_type: str, data: Dict[str, Any]):
    """Send system-wide alert to all connections."""
    await sse_manager.broadcast(event_type, data)


async def send_user_notification(user_id: str, event_type: str, data: Dict[str, Any]):
    """Send notification to specific user."""
    await sse_manager.send_to_user(user_id, event_type, data)