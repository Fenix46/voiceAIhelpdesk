"""WebSocket endpoints for real-time audio streaming and communication."""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set
import base64

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from starlette.websockets import WebSocketState

from ...core.logging import get_logger
from ...core.orchestrator.conversation_orchestrator import ConversationOrchestrator
from ..schemas import (
    WebSocketMessage, AudioChunkMessage, TranscriptionMessage, 
    StatusUpdateMessage, ErrorMessage, HeartbeatMessage,
    AudioFormat, ProcessingStatus
)

logger = get_logger(__name__)

router = APIRouter()


class AudioConnection:
    """Represents an active audio WebSocket connection."""
    
    def __init__(
        self,
        websocket: WebSocket,
        connection_id: str,
        session_id: str,
        user_id: str,
        audio_format: AudioFormat = AudioFormat.WAV
    ):
        self.websocket = websocket
        self.connection_id = connection_id
        self.session_id = session_id
        self.user_id = user_id
        self.audio_format = audio_format
        self.connected_at = datetime.now(timezone.utc)
        self.last_heartbeat = time.time()
        self.is_active = True
        self.conversation_id: Optional[str] = None
        
        # Audio streaming state
        self.is_streaming = False
        self.audio_sequence = 0
        self.total_audio_chunks = 0
        self.total_bytes_received = 0
        
        # Processing state
        self.processing_status = ProcessingStatus.QUEUED
        self.current_transcription = ""
        self.is_partial_transcription = False


class ConnectionManager:
    """Advanced WebSocket connection manager with room and session support."""
    
    def __init__(self):
        self.connections: Dict[str, AudioConnection] = {}
        self.sessions: Dict[str, Set[str]] = {}  # session_id -> connection_ids
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> connection_ids
        self.heartbeat_interval = 30  # seconds
        self.max_connections_per_user = 3
        
        # Start heartbeat task
        asyncio.create_task(self._heartbeat_monitor())
    
    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
        audio_format: AudioFormat = AudioFormat.WAV
    ) -> AudioConnection:
        """Accept and register a new WebSocket connection."""
        connection_id = f"conn_{uuid.uuid4().hex[:8]}"
        
        # Check connection limits
        user_conn_count = len(self.user_connections.get(user_id, set()))
        if user_conn_count >= self.max_connections_per_user:
            await websocket.close(code=4003, reason="Too many connections")
            raise HTTPException(status_code=429, detail="Too many connections")
        
        await websocket.accept()
        
        # Create connection object
        connection = AudioConnection(
            websocket=websocket,
            connection_id=connection_id,
            session_id=session_id,
            user_id=user_id,
            audio_format=audio_format
        )
        
        # Register connection
        self.connections[connection_id] = connection
        
        # Update session mapping
        if session_id not in self.sessions:
            self.sessions[session_id] = set()
        self.sessions[session_id].add(connection_id)
        
        # Update user mapping
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        logger.info(f"WebSocket connected: {connection_id} (session: {session_id}, user: {user_id})")
        
        # Send connection confirmation
        await self._send_to_connection(connection_id, {
            "type": "connection_established",
            "connection_id": connection_id,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "audio_format": audio_format.value
        })
        
        return connection
    
    async def disconnect(self, connection_id: str, reason: str = "client_disconnect"):
        """Disconnect and cleanup connection."""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        try:
            # Close WebSocket if still open
            if connection.websocket.client_state != WebSocketState.DISCONNECTED:
                await connection.websocket.close(code=1000, reason=reason)
        except Exception as e:
            logger.error(f"Error closing WebSocket {connection_id}: {e}")
        
        # Cleanup mappings
        self._remove_connection(connection_id)
        
        logger.info(f"WebSocket disconnected: {connection_id} (reason: {reason})")
    
    def _remove_connection(self, connection_id: str):
        """Remove connection from all mappings."""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        # Remove from sessions
        if connection.session_id in self.sessions:
            self.sessions[connection.session_id].discard(connection_id)
            if not self.sessions[connection.session_id]:
                del self.sessions[connection.session_id]
        
        # Remove from user connections
        if connection.user_id in self.user_connections:
            self.user_connections[connection.user_id].discard(connection_id)
            if not self.user_connections[connection.user_id]:
                del self.user_connections[connection.user_id]
        
        # Remove connection
        del self.connections[connection_id]
    
    async def _send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific connection."""
        if connection_id not in self.connections:
            return False
        
        connection = self.connections[connection_id]
        
        try:
            if connection.websocket.client_state == WebSocketState.CONNECTED:
                await connection.websocket.send_text(json.dumps(message))
                return True
            else:
                await self.disconnect(connection_id, "connection_closed")
                return False
        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            await self.disconnect(connection_id, "send_error")
            return False
    
    async def send_to_session(self, session_id: str, message: Dict[str, Any]):
        """Send message to all connections in a session."""
        if session_id not in self.sessions:
            return
        
        connection_ids = list(self.sessions[session_id])
        for connection_id in connection_ids:
            await self._send_to_connection(connection_id, message)
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """Send message to all connections for a user."""
        if user_id not in self.user_connections:
            return
        
        connection_ids = list(self.user_connections[user_id])
        for connection_id in connection_ids:
            await self._send_to_connection(connection_id, message)
    
    async def broadcast(self, message: Dict[str, Any], exclude_connection: Optional[str] = None):
        """Broadcast message to all connections."""
        connection_ids = list(self.connections.keys())
        for connection_id in connection_ids:
            if connection_id != exclude_connection:
                await self._send_to_connection(connection_id, message)
    
    async def _heartbeat_monitor(self):
        """Monitor connection heartbeats and cleanup stale connections."""
        while True:
            try:
                current_time = time.time()
                stale_connections = []
                
                for connection_id, connection in self.connections.items():
                    if current_time - connection.last_heartbeat > self.heartbeat_interval * 2:
                        stale_connections.append(connection_id)
                
                # Disconnect stale connections
                for connection_id in stale_connections:
                    await self.disconnect(connection_id, "heartbeat_timeout")
                
                # Send heartbeat requests
                for connection in self.connections.values():
                    if current_time - connection.last_heartbeat > self.heartbeat_interval:
                        await self._send_to_connection(connection.connection_id, {
                            "type": "ping",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")
                await asyncio.sleep(5)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "total_sessions": len(self.sessions),
            "total_users": len(self.user_connections),
            "connections_by_format": self._get_format_stats(),
            "active_streams": len([c for c in self.connections.values() if c.is_streaming])
        }
    
    def _get_format_stats(self) -> Dict[str, int]:
        """Get statistics by audio format."""
        format_stats = {}
        for connection in self.connections.values():
            format_name = connection.audio_format.value
            format_stats[format_name] = format_stats.get(format_name, 0) + 1
        return format_stats


# Global connection manager
manager = ConnectionManager()


@router.websocket("/audio")
async def audio_websocket(
    websocket: WebSocket,
    session_id: str = Query(..., description="Session ID"),
    user_id: str = Query(..., description="User ID"),
    audio_format: AudioFormat = Query(default=AudioFormat.WAV, description="Audio format"),
    language: str = Query(default="it", description="Language code")
):
    """
    WebSocket endpoint for real-time audio streaming and processing.
    
    Features:
    - Binary audio chunk streaming
    - Real-time transcription
    - Status updates and progress tracking
    - Heartbeat monitoring
    - Graceful disconnection handling
    """
    try:
        # Connect and get connection object
        connection = await manager.connect(websocket, session_id, user_id, audio_format)
        
        # Initialize conversation orchestrator
        orchestrator = ConversationOrchestrator()
        
        try:
            while True:
                # Receive message (text or binary)
                try:
                    # Try to receive text message first
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await handle_text_message(connection, message, orchestrator)
                except:
                    # Try to receive binary data
                    try:
                        binary_data = await websocket.receive_bytes()
                        await handle_audio_chunk(connection, binary_data, orchestrator)
                    except Exception as e:
                        logger.error(f"Error receiving WebSocket data: {e}")
                        break
        
        except WebSocketDisconnect:
            logger.info(f"Client {connection.connection_id} disconnected normally")
        except Exception as e:
            logger.error(f"WebSocket error for {connection.connection_id}: {e}")
        finally:
            await manager.disconnect(connection.connection_id, "session_ended")
    
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=4000, reason="Connection failed")


async def handle_text_message(
    connection: AudioConnection,
    message: Dict[str, Any],
    orchestrator: ConversationOrchestrator
):
    """Handle incoming text messages."""
    message_type = message.get("type")
    
    try:
        if message_type == "ping":
            connection.last_heartbeat = time.time()
            await manager._send_to_connection(connection.connection_id, {
                "type": "pong",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        elif message_type == "start_streaming":
            connection.is_streaming = True
            connection.audio_sequence = 0
            connection.total_audio_chunks = 0
            connection.total_bytes_received = 0
            
            # Start conversation if not exists
            if not connection.conversation_id:
                conversation_data = await orchestrator.start_conversation(
                    user_id=connection.user_id,
                    session_id=connection.session_id,
                    audio_format=connection.audio_format.value,
                    language=message.get("language", "it")
                )
                connection.conversation_id = conversation_data.get("conversation_id")
            
            await manager._send_to_connection(connection.connection_id, {
                "type": "streaming_started",
                "conversation_id": connection.conversation_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"Started audio streaming for {connection.connection_id}")
        
        elif message_type == "stop_streaming":
            connection.is_streaming = False
            
            await manager._send_to_connection(connection.connection_id, {
                "type": "streaming_stopped",
                "total_chunks": connection.total_audio_chunks,
                "total_bytes": connection.total_bytes_received,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"Stopped audio streaming for {connection.connection_id}")
        
        elif message_type == "text_input":
            # Handle direct text input (for chat-based interaction)
            text = message.get("text", "")
            if text.strip() and connection.conversation_id:
                
                # Process text through orchestrator
                response_data = await orchestrator.process_text_message(
                    conversation_id=connection.conversation_id,
                    text=text,
                    user_id=connection.user_id
                )
                
                await manager._send_to_connection(connection.connection_id, {
                    "type": "text_response",
                    "text": response_data.get("response", ""),
                    "conversation_id": connection.conversation_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        elif message_type == "get_status":
            # Return current connection status
            await manager._send_to_connection(connection.connection_id, {
                "type": "status_update",
                "status": connection.processing_status.value,
                "is_streaming": connection.is_streaming,
                "conversation_id": connection.conversation_id,
                "total_chunks": connection.total_audio_chunks,
                "total_bytes": connection.total_bytes_received,
                "connected_duration": (datetime.now(timezone.utc) - connection.connected_at).total_seconds(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        else:
            await manager._send_to_connection(connection.connection_id, {
                "type": "error",
                "error_code": "UNKNOWN_MESSAGE_TYPE",
                "message": f"Unknown message type: {message_type}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    except Exception as e:
        logger.error(f"Error handling text message: {e}")
        await manager._send_to_connection(connection.connection_id, {
            "type": "error",
            "error_code": "MESSAGE_PROCESSING_ERROR",
            "message": "Failed to process message",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


async def handle_audio_chunk(
    connection: AudioConnection,
    binary_data: bytes,
    orchestrator: ConversationOrchestrator
):
    """Handle incoming audio chunks."""
    if not connection.is_streaming:
        await manager._send_to_connection(connection.connection_id, {
            "type": "error",
            "error_code": "STREAMING_NOT_ACTIVE",
            "message": "Audio streaming not started",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return
    
    try:
        connection.audio_sequence += 1
        connection.total_audio_chunks += 1
        connection.total_bytes_received += len(binary_data)
        
        # Process audio chunk through orchestrator
        if connection.conversation_id:
            processing_result = await orchestrator.process_audio_chunk(
                conversation_id=connection.conversation_id,
                audio_data=binary_data,
                sequence=connection.audio_sequence,
                format=connection.audio_format.value
            )
            
            # Send transcription updates
            if processing_result.get("transcription"):
                transcription_data = processing_result["transcription"]
                
                await manager._send_to_connection(connection.connection_id, {
                    "type": "transcription",
                    "text": transcription_data.get("text", ""),
                    "is_partial": transcription_data.get("is_partial", False),
                    "confidence": transcription_data.get("confidence", 0.0),
                    "language": transcription_data.get("language", "it"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            # Send processing status updates
            if processing_result.get("status_update"):
                status_data = processing_result["status_update"]
                connection.processing_status = ProcessingStatus(status_data.get("status", "processing"))
                
                await manager._send_to_connection(connection.connection_id, {
                    "type": "status_update",
                    "status": connection.processing_status.value,
                    "progress": status_data.get("progress", 0.0),
                    "message": status_data.get("message", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            # Send AI responses
            if processing_result.get("response"):
                response_data = processing_result["response"]
                
                await manager._send_to_connection(connection.connection_id, {
                    "type": "ai_response",
                    "text": response_data.get("text", ""),
                    "audio_url": response_data.get("audio_url"),
                    "actions": response_data.get("actions", []),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        # Send chunk acknowledgment (every 10 chunks to reduce traffic)
        if connection.audio_sequence % 10 == 0:
            await manager._send_to_connection(connection.connection_id, {
                "type": "chunk_ack",
                "sequence": connection.audio_sequence,
                "total_chunks": connection.total_audio_chunks,
                "total_bytes": connection.total_bytes_received,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")
        await manager._send_to_connection(connection.connection_id, {
            "type": "error",
            "error_code": "AUDIO_PROCESSING_ERROR",
            "message": "Failed to process audio chunk",
            "details": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


@router.websocket("/admin")
async def admin_websocket(websocket: WebSocket):
    """Admin WebSocket for monitoring connections and system status."""
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "get_stats":
                stats = manager.get_connection_stats()
                await websocket.send_text(json.dumps({
                    "type": "stats_update",
                    "stats": stats,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
            
            elif message.get("type") == "get_connections":
                connections_info = []
                for conn_id, conn in manager.connections.items():
                    connections_info.append({
                        "connection_id": conn_id,
                        "session_id": conn.session_id,
                        "user_id": conn.user_id,
                        "connected_at": conn.connected_at.isoformat(),
                        "is_streaming": conn.is_streaming,
                        "audio_format": conn.audio_format.value,
                        "total_chunks": conn.total_audio_chunks,
                        "total_bytes": conn.total_bytes_received
                    })
                
                await websocket.send_text(json.dumps({
                    "type": "connections_list",
                    "connections": connections_info,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
    
    except WebSocketDisconnect:
        logger.info("Admin WebSocket disconnected")
    except Exception as e:
        logger.error(f"Admin WebSocket error: {e}")