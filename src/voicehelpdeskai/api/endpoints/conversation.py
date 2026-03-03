"""REST endpoints for conversation management."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
import uuid

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import JSONResponse

from ...core.logging import get_logger
from ...core.orchestrator.conversation_orchestrator import ConversationOrchestrator
from ...database import get_conversation_repository, get_user_repository
from ..middleware.auth import auth_required
from ..schemas import (
    ConversationStartRequest, ConversationStartResponse,
    ConversationEndRequest, ConversationEndResponse,
    ConversationTranscriptResponse, TranscriptEntry,
    ErrorResponse
)

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/start",
    response_model=ConversationStartResponse,
    summary="Start a new conversation",
    description="Initialize a new conversation session for voice interaction"
)
async def start_conversation(
    request: ConversationStartRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> ConversationStartResponse:
    """
    Start a new conversation session.
    
    Creates a new conversation context, initializes necessary services,
    and returns connection details for real-time communication.
    """
    try:
        # Validate user exists
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
        
        # Initialize conversation orchestrator
        orchestrator = ConversationOrchestrator()
        
        # Create conversation session
        conversation_data = await orchestrator.start_conversation(
            user_id=request.user_id,
            audio_format=request.audio_format.value,
            language=request.language,
            context=request.context,
            session_metadata=request.session_metadata
        )
        
        conversation_id = conversation_data["conversation_id"]
        session_id = conversation_data["session_id"]
        
        # Generate URLs for real-time communication
        base_url = "ws://localhost:8000"  # TODO: Get from settings
        websocket_url = f"{base_url}/ws/audio?session_id={session_id}&user_id={request.user_id}&audio_format={request.audio_format.value}&language={request.language}"
        sse_url = f"http://localhost:8000/api/v1/sse/conversation/{conversation_id}"
        
        # Set expiration (24 hours)
        expires_at = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
        
        # Prepare configuration
        configuration = {
            "audio_format": request.audio_format.value,
            "language": request.language,
            "max_duration_minutes": 60,
            "auto_save_transcript": True,
            "enable_real_time_transcription": True,
            "voice_activity_detection": True
        }
        
        logger.info(
            f"Started conversation {conversation_id} for user {request.user_id}",
            extra={
                "conversation_id": conversation_id,
                "user_id": request.user_id,
                "session_id": session_id,
                "audio_format": request.audio_format.value,
                "language": request.language
            }
        )
        
        return ConversationStartResponse(
            conversation_id=conversation_id,
            session_id=session_id,
            websocket_url=websocket_url,
            sse_url=sse_url,
            expires_at=expires_at,
            configuration=configuration
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start conversation"
        )


@router.post(
    "/end",
    response_model=ConversationEndResponse,
    summary="End a conversation",
    description="End an active conversation and process final results"
)
async def end_conversation(
    request: ConversationEndRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> ConversationEndResponse:
    """
    End an active conversation.
    
    Finalizes the conversation, processes transcripts, generates summaries,
    and handles any resulting actions like ticket creation.
    """
    try:
        # Get conversation
        conversation_repo = get_conversation_repository()
        conversation = conversation_repo.get_by_id(request.conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Check if user owns the conversation or has admin rights
        user_role = current_user.get("role", "")
        if conversation.user_id != current_user.get("user_id") and user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this conversation"
            )
        
        # Initialize orchestrator
        orchestrator = ConversationOrchestrator()
        
        # End conversation and get results
        end_result = await orchestrator.end_conversation(
            conversation_id=request.conversation_id,
            reason=request.reason,
            feedback_score=request.feedback_score,
            feedback_comment=request.feedback_comment,
            user_id=current_user.get("user_id")
        )
        
        # Calculate duration
        duration_seconds = (datetime.now(timezone.utc) - conversation.created_at).total_seconds()
        
        # Get transcript URL if available
        transcript_url = None
        if end_result.get("transcript_available"):
            transcript_url = f"/api/v1/conversation/{request.conversation_id}/transcript"
        
        logger.info(
            f"Ended conversation {request.conversation_id}",
            extra={
                "conversation_id": request.conversation_id,
                "duration_seconds": duration_seconds,
                "reason": request.reason,
                "actions_taken": len(end_result.get("actions_taken", [])),
                "tickets_created": len(end_result.get("created_tickets", []))
            }
        )
        
        return ConversationEndResponse(
            conversation_id=request.conversation_id,
            status=end_result.get("status", "completed"),
            duration_seconds=duration_seconds,
            transcript_url=transcript_url,
            summary=end_result.get("summary"),
            actions_taken=end_result.get("actions_taken", []),
            created_tickets=end_result.get("created_tickets", [])
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to end conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end conversation"
        )


@router.get(
    "/{conversation_id}/transcript",
    response_model=ConversationTranscriptResponse,
    summary="Get conversation transcript",
    description="Retrieve the complete transcript of a conversation"
)
async def get_conversation_transcript(
    conversation_id: str,
    include_metadata: bool = False,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> ConversationTranscriptResponse:
    """
    Get conversation transcript.
    
    Returns the complete transcript with timestamps, confidence scores,
    and optional metadata about the conversation processing.
    """
    try:
        # Get conversation
        conversation_repo = get_conversation_repository()
        conversation = conversation_repo.get_by_id(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Check access permissions
        user_role = current_user.get("role", "")
        if conversation.user_id != current_user.get("user_id") and user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this conversation"
            )
        
        # Initialize orchestrator to get detailed transcript
        orchestrator = ConversationOrchestrator()
        
        # Get transcript data
        transcript_data = await orchestrator.get_conversation_transcript(
            conversation_id=conversation_id,
            include_metadata=include_metadata
        )
        
        # Convert to transcript entries
        transcript_entries = []
        for entry in transcript_data.get("entries", []):
            transcript_entries.append(TranscriptEntry(
                timestamp=datetime.fromisoformat(entry["timestamp"]),
                speaker=entry["speaker"],
                text=entry["text"],
                confidence=entry.get("confidence"),
                language=entry.get("language", conversation.language),
                processing_time_ms=entry.get("processing_time_ms")
            ))
        
        # Calculate total duration and word count
        total_duration = conversation.duration_seconds or 0.0
        word_count = sum(len(entry.text.split()) for entry in transcript_entries)
        
        logger.info(
            f"Retrieved transcript for conversation {conversation_id}",
            extra={
                "conversation_id": conversation_id,
                "transcript_entries": len(transcript_entries),
                "word_count": word_count,
                "total_duration": total_duration
            }
        )
        
        return ConversationTranscriptResponse(
            conversation_id=conversation_id,
            transcript=transcript_entries,
            language=conversation.language,
            total_duration=total_duration,
            word_count=word_count,
            summary=transcript_data.get("summary"),
            sentiment_analysis=transcript_data.get("sentiment_analysis")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get transcript for conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation transcript"
        )


@router.get(
    "/{conversation_id}/status",
    summary="Get conversation status",
    description="Get current status and progress of a conversation"
)
async def get_conversation_status(
    conversation_id: str,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> Dict[str, Any]:
    """Get current conversation status and progress."""
    try:
        # Get conversation
        conversation_repo = get_conversation_repository()
        conversation = conversation_repo.get_by_id(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Check access permissions
        user_role = current_user.get("role", "")
        if conversation.user_id != current_user.get("user_id") and user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this conversation"
            )
        
        # Get orchestrator status
        orchestrator = ConversationOrchestrator()
        status_data = await orchestrator.get_conversation_status(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "status": status_data.get("status", "unknown"),
            "progress": status_data.get("progress", 0.0),
            "current_stage": status_data.get("current_stage", ""),
            "processing_stats": status_data.get("processing_stats", {}),
            "error_info": status_data.get("error_info"),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation status"
        )


@router.post(
    "/{conversation_id}/cancel",
    summary="Cancel conversation",
    description="Cancel an active conversation"
)
async def cancel_conversation(
    conversation_id: str,
    reason: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(auth_required)
) -> Dict[str, str]:
    """Cancel an active conversation."""
    try:
        # Get conversation
        conversation_repo = get_conversation_repository()
        conversation = conversation_repo.get_by_id(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Check access permissions
        user_role = current_user.get("role", "")
        if conversation.user_id != current_user.get("user_id") and user_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this conversation"
            )
        
        # Cancel through orchestrator
        orchestrator = ConversationOrchestrator()
        await orchestrator.cancel_conversation(
            conversation_id=conversation_id,
            reason=reason or "User cancelled",
            user_id=current_user.get("user_id")
        )
        
        logger.info(
            f"Cancelled conversation {conversation_id}",
            extra={
                "conversation_id": conversation_id,
                "reason": reason,
                "cancelled_by": current_user.get("user_id")
            }
        )
        
        return {
            "message": "Conversation cancelled successfully",
            "conversation_id": conversation_id,
            "cancelled_at": datetime.now(timezone.utc).isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel conversation"
        )