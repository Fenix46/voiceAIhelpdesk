"""Celery task definitions for background processing."""

import asyncio
import io
import json
import os
import shutil
import time
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path

import numpy as np
from celery import current_task
from celery.exceptions import Ignore, Retry
import soundfile as sf
import librosa
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .celery_app import celery_app
from ..core.config import settings
from ..core.logging import get_logger
from ..core.orchestrator.conversation_orchestrator import ConversationOrchestrator
from ..services.ticketing import TicketingService
from ..services.audio_processing import AudioProcessor
from ..services.ai.text_analysis import TextAnalysisService
from ..database import (
    get_conversation_repository, get_ticket_repository, 
    get_user_repository, get_feedback_repository,
    DatabaseManager
)

logger = get_logger(__name__)

# Constants
MAX_AUDIO_CHUNK_SIZE = 1024 * 1024  # 1MB
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 300  # 5 minutes


# =============================================================================
# AUDIO PROCESSING TASKS
# =============================================================================

@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.process_audio_chunk_task')
def process_audio_chunk_task(self, audio_data: bytes, conversation_id: str, 
                           sequence: int, format: str, **kwargs) -> Dict[str, Any]:
    """Process audio chunk for real-time transcription."""
    try:
        start_time = time.time()
        
        # Update task progress
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'initializing', 'sequence': sequence}
        )
        
        # Validate audio data
        if not audio_data or len(audio_data) > MAX_AUDIO_CHUNK_SIZE:
            raise ValueError(f"Invalid audio data size: {len(audio_data) if audio_data else 0}")
        
        # Initialize audio processor
        audio_processor = AudioProcessor()
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 20, 'stage': 'audio_validation', 'sequence': sequence}
        )
        
        # Process audio chunk
        processed_audio = audio_processor.process_chunk(
            audio_data=audio_data,
            format=format,
            sequence=sequence
        )
        current_task.update_state(
            state='PROCESSING', 
            meta={'progress': 60, 'stage': 'audio_processing', 'sequence': sequence}
        )
        
        # Transcribe audio
        transcription_result = audio_processor.transcribe_chunk(
            processed_audio,
            language=kwargs.get('language', 'it')
        )
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 90, 'stage': 'transcription', 'sequence': sequence}
        )
        
        processing_time = time.time() - start_time
        
        result = {
            'conversation_id': conversation_id,
            'sequence': sequence,
            'transcription': transcription_result,
            'processing_time_ms': processing_time * 1000,
            'audio_format': format,
            'chunk_size_bytes': len(audio_data),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Processed audio chunk {sequence} for conversation {conversation_id}")
        return result
        
    except Exception as e:
        logger.error(f"Audio processing failed for chunk {sequence}: {e}")
        logger.error(traceback.format_exc())
        
        # Update task state with error
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'sequence': sequence, 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.transcribe_audio_task')
def transcribe_audio_task(self, audio_file_path: str, conversation_id: str, **kwargs) -> Dict[str, Any]:
    """Transcribe complete audio file."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'loading_audio'}
        )
        
        # Load audio file
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
        
        audio_processor = AudioProcessor()
        
        # Load and validate audio
        audio_data, sample_rate = sf.read(audio_file_path)
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 20, 'stage': 'audio_loaded', 'duration': len(audio_data) / sample_rate}
        )
        
        # Process complete audio
        processed_audio = audio_processor.process_complete_audio(audio_data, sample_rate)
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 50, 'stage': 'audio_processed'}
        )
        
        # Full transcription
        transcription_result = audio_processor.transcribe_complete(
            processed_audio,
            language=kwargs.get('language', 'it')
        )
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 90, 'stage': 'transcription_complete'}
        )
        
        result = {
            'conversation_id': conversation_id,
            'audio_file_path': audio_file_path,
            'transcription': transcription_result,
            'duration_seconds': len(audio_data) / sample_rate,
            'word_count': len(transcription_result.get('text', '').split()),
            'confidence_score': transcription_result.get('confidence', 0.0),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Transcribed audio file for conversation {conversation_id}")
        return result
        
    except Exception as e:
        logger.error(f"Audio transcription failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.generate_voice_response_task')
def generate_voice_response_task(self, text: str, conversation_id: str, **kwargs) -> Dict[str, Any]:
    """Generate voice response from text."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'initializing'}
        )
        
        # Initialize TTS service
        from ..services.ai.text_to_speech import TTSService
        tts_service = TTSService()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 30, 'stage': 'tts_generation'}
        )
        
        # Generate audio
        audio_result = tts_service.generate_speech(
            text=text,
            voice=kwargs.get('voice', 'default'),
            language=kwargs.get('language', 'it')
        )
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 80, 'stage': 'saving_audio'}
        )
        
        # Save audio file
        timestamp = int(time.time())
        audio_filename = f"response_{conversation_id}_{timestamp}.wav"
        audio_path = os.path.join(settings.audio_output_dir, audio_filename)
        
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        sf.write(audio_path, audio_result['audio_data'], audio_result['sample_rate'])
        
        result = {
            'conversation_id': conversation_id,
            'text': text,
            'audio_file_path': audio_path,
            'audio_url': f"/audio/{audio_filename}",
            'duration_seconds': len(audio_result['audio_data']) / audio_result['sample_rate'],
            'sample_rate': audio_result['sample_rate'],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Generated voice response for conversation {conversation_id}")
        return result
        
    except Exception as e:
        logger.error(f"Voice generation failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


# =============================================================================
# TICKET MANAGEMENT TASKS  
# =============================================================================

@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.create_ticket_task')
def create_ticket_task(self, ticket_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Create a new support ticket."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'validating_data'}
        )
        
        # Initialize ticketing service
        ticketing_service = TicketingService()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 30, 'stage': 'creating_ticket'}
        )
        
        # Create ticket
        ticket = ticketing_service.create_ticket(ticket_data)
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 70, 'stage': 'auto_assignment'}
        )
        
        # Auto-assign if enabled
        if kwargs.get('auto_assign', True):
            assignment_result = ticketing_service.auto_assign_ticket(ticket.id)
            if assignment_result:
                current_task.update_state(
                    state='PROCESSING',
                    meta={'progress': 90, 'stage': 'sending_notifications'}
                )
                
                # Send notification to assigned user
                send_email_notification_task.delay(
                    recipient=assignment_result.get('assigned_user_email'),
                    subject=f"New Ticket Assigned: {ticket.ticket_number}",
                    template='ticket_assigned',
                    context={'ticket': ticket, 'assignment': assignment_result}
                )
        
        result = {
            'ticket_id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'status': ticket.status,
            'priority': ticket.priority,
            'created_at': ticket.created_at.isoformat(),
            'auto_assigned': kwargs.get('auto_assign', True)
        }
        
        logger.info(f"Created ticket {ticket.ticket_number}")
        return result
        
    except Exception as e:
        logger.error(f"Ticket creation failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.update_ticket_task')
def update_ticket_task(self, ticket_id: str, updates: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Update ticket with given data."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'loading_ticket'}
        )
        
        ticketing_service = TicketingService()
        ticket_repo = get_ticket_repository()
        
        # Get existing ticket
        ticket = ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket not found: {ticket_id}")
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 30, 'stage': 'applying_updates'}
        )
        
        # Apply updates
        old_status = ticket.status
        updated_ticket = ticket_repo.update(ticket_id, updates)
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 70, 'stage': 'post_update_processing'}
        )
        
        # Handle status change notifications
        if 'status' in updates and updates['status'] != old_status:
            # Send status change notification
            send_email_notification_task.delay(
                recipient=updated_ticket.user_id,
                subject=f"Ticket Status Updated: {updated_ticket.ticket_number}",
                template='ticket_status_changed',
                context={
                    'ticket': updated_ticket,
                    'old_status': old_status,
                    'new_status': updates['status']
                }
            )
        
        result = {
            'ticket_id': ticket_id,
            'updates_applied': list(updates.keys()),
            'status': updated_ticket.status,
            'updated_at': updated_ticket.updated_at.isoformat()
        }
        
        logger.info(f"Updated ticket {updated_ticket.ticket_number}")
        return result
        
    except Exception as e:
        logger.error(f"Ticket update failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.escalate_ticket_task')
def escalate_ticket_task(self, ticket_id: str, escalation_level: int, 
                        reason: str, **kwargs) -> Dict[str, Any]:
    """Escalate ticket to higher support level."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'loading_ticket'}
        )
        
        ticketing_service = TicketingService()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 30, 'stage': 'escalating'}
        )
        
        # Perform escalation
        escalation_result = ticketing_service.escalate_ticket(
            ticket_id=ticket_id,
            escalation_level=escalation_level,
            reason=reason,
            escalated_by=kwargs.get('user_id')
        )
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 80, 'stage': 'sending_notifications'}
        )
        
        # Send escalation notifications
        if escalation_result.get('escalated_to'):
            send_email_notification_task.delay(
                recipient=escalation_result['escalated_to'],
                subject=f"Ticket Escalated: {escalation_result['ticket_number']}",
                template='ticket_escalated',
                context={
                    'ticket': escalation_result['ticket'],
                    'escalation_level': escalation_level,
                    'reason': reason
                }
            )
        
        logger.info(f"Escalated ticket {escalation_result['ticket_number']} to level {escalation_level}")
        return escalation_result
        
    except Exception as e:
        logger.error(f"Ticket escalation failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.auto_assign_ticket_task')
def auto_assign_ticket_task(self, ticket_id: str, **kwargs) -> Dict[str, Any]:
    """Auto-assign ticket to available technician."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'analyzing_ticket'}
        )
        
        ticketing_service = TicketingService()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 50, 'stage': 'finding_technician'}
        )
        
        # Perform auto-assignment
        assignment_result = ticketing_service.auto_assign_ticket(ticket_id)
        
        if assignment_result:
            current_task.update_state(
                state='PROCESSING',
                meta={'progress': 80, 'stage': 'sending_notification'}
            )
            
            # Send assignment notification
            send_email_notification_task.delay(
                recipient=assignment_result['assigned_user_email'],
                subject=f"Ticket Assigned: {assignment_result['ticket_number']}",
                template='ticket_assigned',
                context=assignment_result
            )
        
        logger.info(f"Auto-assigned ticket {ticket_id}")
        return assignment_result or {'assigned': False, 'reason': 'No suitable technician found'}
        
    except Exception as e:
        logger.error(f"Auto-assignment failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


# =============================================================================
# NOTIFICATION TASKS
# =============================================================================

@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.send_email_notification_task')
def send_email_notification_task(self, recipient: str, subject: str, 
                                template: str = None, context: Dict[str, Any] = None,
                                **kwargs) -> Dict[str, Any]:
    """Send email notification."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'preparing_email'}
        )
        
        # Prepare email content
        if template and context:
            from ..services.notifications.email_service import EmailService
            email_service = EmailService()
            content = email_service.render_template(template, context)
        else:
            content = kwargs.get('body', subject)
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 30, 'stage': 'connecting_smtp'}
        )
        
        # Configure SMTP
        smtp_server = settings.smtp_server or 'localhost'
        smtp_port = settings.smtp_port or 587
        smtp_user = settings.smtp_username
        smtp_password = settings.smtp_password
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = settings.from_email or 'noreply@voicehelpdeskai.com'
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(content, 'html' if template else 'plain'))
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 70, 'stage': 'sending_email'}
        )
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if smtp_user and smtp_password:
                server.starttls()
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        result = {
            'recipient': recipient,
            'subject': subject,
            'template': template,
            'sent_at': datetime.now(timezone.utc).isoformat(),
            'status': 'sent'
        }
        
        logger.info(f"Email sent to {recipient}")
        return result
        
    except Exception as e:
        logger.error(f"Email notification failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.send_sms_notification_task')
def send_sms_notification_task(self, phone_number: str, message: str, **kwargs) -> Dict[str, Any]:
    """Send SMS notification."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'validating_phone'}
        )
        
        # Validate phone number format
        if not phone_number.startswith('+'):
            raise ValueError("Phone number must include country code")
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 30, 'stage': 'sending_sms'}
        )
        
        # Send SMS (using Twilio or similar service)
        # This is a mock implementation - replace with actual SMS service
        if settings.sms_provider == 'twilio':
            from twilio.rest import Client
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            
            sms_result = client.messages.create(
                body=message,
                from_=settings.twilio_phone_number,
                to=phone_number
            )
            
            result = {
                'phone_number': phone_number,
                'message': message,
                'sms_sid': sms_result.sid,
                'sent_at': datetime.now(timezone.utc).isoformat(),
                'status': 'sent'
            }
        else:
            # Mock SMS sending
            result = {
                'phone_number': phone_number,
                'message': message,
                'sent_at': datetime.now(timezone.utc).isoformat(),
                'status': 'sent_mock'
            }
        
        logger.info(f"SMS sent to {phone_number}")
        return result
        
    except Exception as e:
        logger.error(f"SMS notification failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.send_webhook_notification_task')
def send_webhook_notification_task(self, webhook_url: str, payload: Dict[str, Any], 
                                  **kwargs) -> Dict[str, Any]:
    """Send webhook notification."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'preparing_payload'}
        )
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'VoiceHelpDeskAI/1.0'
        }
        
        # Add authentication if provided
        if kwargs.get('webhook_secret'):
            import hmac
            import hashlib
            signature = hmac.new(
                kwargs['webhook_secret'].encode('utf-8'),
                json.dumps(payload).encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            headers['X-Webhook-Signature'] = f"sha256={signature}"
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 50, 'stage': 'sending_webhook'}
        )
        
        # Send webhook
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        result = {
            'webhook_url': webhook_url,
            'payload_keys': list(payload.keys()),
            'status_code': response.status_code,
            'response_headers': dict(response.headers),
            'sent_at': datetime.now(timezone.utc).isoformat(),
            'status': 'sent'
        }
        
        logger.info(f"Webhook sent to {webhook_url}")
        return result
        
    except Exception as e:
        logger.error(f"Webhook notification failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


# =============================================================================
# ANALYTICS TASKS
# =============================================================================

@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.compute_analytics_task')
def compute_analytics_task(self, analytics_type: str, **kwargs) -> Dict[str, Any]:
    """Compute analytics metrics."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'initializing'}
        )
        
        from ..services.ticketing.analytics import TicketAnalytics
        analytics = TicketAnalytics()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 30, 'stage': f'computing_{analytics_type}'}
        )
        
        # Compute specific analytics
        if analytics_type == 'dashboard_metrics':
            result = analytics.compute_dashboard_metrics(**kwargs)
        elif analytics_type == 'response_time':
            result = analytics.get_response_time_metrics(**kwargs)
        elif analytics_type == 'resolution_rate':
            result = analytics.get_resolution_rate_metrics(**kwargs)
        elif analytics_type == 'satisfaction_analysis':
            result = analytics.get_user_satisfaction_analysis(**kwargs)
        elif analytics_type == 'trend_analysis':
            result = analytics.get_trend_analysis(**kwargs)
        else:
            raise ValueError(f"Unknown analytics type: {analytics_type}")
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 90, 'stage': 'storing_results'}
        )
        
        # Store results in cache
        from ..core.cache import CacheManager
        cache_manager = CacheManager()
        cache_key = f"analytics:{analytics_type}:{hash(str(kwargs))}"
        cache_manager.set(cache_key, result, expire=3600)  # 1 hour cache
        
        logger.info(f"Computed analytics: {analytics_type}")
        return {
            'analytics_type': analytics_type,
            'computed_at': datetime.now(timezone.utc).isoformat(),
            'cache_key': cache_key,
            'data': result
        }
        
    except Exception as e:
        logger.error(f"Analytics computation failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.generate_report_task')
def generate_report_task(self, report_type: str, **kwargs) -> Dict[str, Any]:
    """Generate analytics report."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'initializing_report'}
        )
        
        from ..services.reporting import ReportGenerator
        report_generator = ReportGenerator()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 40, 'stage': 'generating_report'}
        )
        
        # Generate report
        report_data = report_generator.generate_report(report_type, **kwargs)
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 80, 'stage': 'saving_report'}
        )
        
        # Save report file
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_report_{timestamp}.pdf"
        filepath = os.path.join(settings.reports_dir, filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        report_generator.save_report(report_data, filepath)
        
        result = {
            'report_type': report_type,
            'filename': filename,
            'filepath': filepath,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'file_size_bytes': os.path.getsize(filepath)
        }
        
        logger.info(f"Generated report: {report_type}")
        return result
        
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.update_dashboard_metrics_task')
def update_dashboard_metrics_task(self, **kwargs) -> Dict[str, Any]:
    """Update real-time dashboard metrics."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'collecting_metrics'}
        )
        
        from ..core.metrics import MetricsCollector
        metrics_collector = MetricsCollector()
        
        # Collect current metrics
        metrics = {
            'active_conversations': metrics_collector.get_active_conversations(),
            'pending_tickets': metrics_collector.get_pending_tickets(), 
            'avg_response_time': metrics_collector.get_avg_response_time(),
            'system_health': metrics_collector.get_system_health(),
            'worker_status': metrics_collector.get_worker_status()
        }
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 70, 'stage': 'updating_cache'}
        )
        
        # Update cache
        from ..core.cache import CacheManager
        cache_manager = CacheManager()
        cache_manager.set('dashboard:metrics', metrics, expire=300)  # 5 minute cache
        
        # Send to SSE clients
        from ..api.endpoints.sse import send_system_alert
        asyncio.create_task(send_system_alert('dashboard_update', metrics))
        
        logger.info("Updated dashboard metrics")
        return {
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'metrics': metrics
        }
        
    except Exception as e:
        logger.error(f"Dashboard metrics update failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


# =============================================================================
# ML INFERENCE TASKS
# =============================================================================

@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.run_sentiment_analysis_task')
def run_sentiment_analysis_task(self, text_data: Union[str, List[str]], **kwargs) -> Dict[str, Any]:
    """Run sentiment analysis on text data."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'loading_model'}
        )
        
        text_analysis = TextAnalysisService()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 40, 'stage': 'running_analysis'}
        )
        
        # Run sentiment analysis
        if isinstance(text_data, str):
            results = [text_analysis.analyze_sentiment(text_data)]
        else:
            results = [text_analysis.analyze_sentiment(text) for text in text_data]
        
        result = {
            'analysis_type': 'sentiment',
            'input_count': len(results),
            'results': results,
            'processed_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Completed sentiment analysis on {len(results)} items")
        return result
        
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        current_task.update_state(
            state='FAILURE', 
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.run_intent_classification_task')
def run_intent_classification_task(self, text_data: Union[str, List[str]], **kwargs) -> Dict[str, Any]:
    """Run intent classification on text data."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'loading_model'}
        )
        
        text_analysis = TextAnalysisService()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 40, 'stage': 'running_classification'}
        )
        
        # Run intent classification
        if isinstance(text_data, str):
            results = [text_analysis.classify_intent(text_data)]
        else:
            results = [text_analysis.classify_intent(text) for text in text_data]
        
        result = {
            'analysis_type': 'intent_classification',
            'input_count': len(results),
            'results': results,
            'processed_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Completed intent classification on {len(results)} items")
        return result
        
    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.run_text_classification_task') 
def run_text_classification_task(self, text_data: Union[str, List[str]], 
                                classification_type: str, **kwargs) -> Dict[str, Any]:
    """Run text classification task."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'loading_model'}
        )
        
        text_analysis = TextAnalysisService()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 40, 'stage': 'running_classification'}
        )
        
        # Run classification
        if isinstance(text_data, str):
            results = [text_analysis.classify_text(text_data, classification_type)]
        else:
            results = [text_analysis.classify_text(text, classification_type) for text in text_data]
        
        result = {
            'analysis_type': f'text_classification_{classification_type}',
            'input_count': len(results),
            'results': results,
            'processed_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Completed text classification ({classification_type}) on {len(results)} items")
        return result
        
    except Exception as e:
        logger.error(f"Text classification failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


# =============================================================================
# CLEANUP AND MAINTENANCE TASKS
# =============================================================================

@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.cleanup_expired_sessions_task')
def cleanup_expired_sessions_task(self, **kwargs) -> Dict[str, Any]:
    """Clean up expired conversation sessions."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'finding_expired_sessions'}
        )
        
        conversation_repo = get_conversation_repository()
        
        # Find expired sessions (older than 24 hours and not completed)
        expiry_time = datetime.now(timezone.utc) - timedelta(hours=24)
        expired_sessions = conversation_repo.find_expired_sessions(expiry_time)
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 50, 'stage': 'cleaning_sessions', 'found': len(expired_sessions)}
        )
        
        cleaned_count = 0
        for session in expired_sessions:
            try:
                # Mark as expired and clean up resources
                conversation_repo.update(session.id, {
                    'status': 'expired',
                    'ended_at': datetime.now(timezone.utc)
                })
                
                # Clean up associated files
                if session.audio_file_path and os.path.exists(session.audio_file_path):
                    os.remove(session.audio_file_path)
                
                cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup session {session.id}: {e}")
        
        result = {
            'total_found': len(expired_sessions),
            'cleaned': cleaned_count,
            'cleaned_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Cleaned up {cleaned_count} expired sessions")
        return result
        
    except Exception as e:
        logger.error(f"Session cleanup failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.cleanup_old_files_task')
def cleanup_old_files_task(self, **kwargs) -> Dict[str, Any]:
    """Clean up old audio and temporary files."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'scanning_directories'}
        )
        
        # Directories to clean
        cleanup_dirs = [
            settings.audio_upload_dir,
            settings.audio_output_dir,
            settings.temp_dir
        ]
        
        # Files older than this will be deleted
        cutoff_time = time.time() - (7 * 24 * 3600)  # 7 days
        
        total_files = 0
        total_size = 0
        deleted_files = 0
        deleted_size = 0
        
        for directory in cleanup_dirs:
            if not os.path.exists(directory):
                continue
                
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_stat = os.stat(file_path)
                        total_files += 1
                        total_size += file_stat.st_size
                        
                        if file_stat.st_mtime < cutoff_time:
                            os.remove(file_path)
                            deleted_files += 1
                            deleted_size += file_stat.st_size
                    except Exception as e:
                        logger.warning(f"Failed to process file {file_path}: {e}")
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 80, 'stage': 'cleaning_empty_directories'}
        )
        
        # Remove empty directories
        empty_dirs = 0
        for directory in cleanup_dirs:
            if os.path.exists(directory):
                for root, dirs, files in os.walk(directory, topdown=False):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        try:
                            if not os.listdir(dir_path):
                                os.rmdir(dir_path)
                                empty_dirs += 1
                        except Exception:
                            pass
        
        result = {
            'total_files_scanned': total_files,
            'total_size_bytes': total_size,
            'files_deleted': deleted_files,
            'size_freed_bytes': deleted_size,
            'empty_dirs_removed': empty_dirs,
            'cleaned_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Cleaned up {deleted_files} files, freed {deleted_size} bytes")
        return result
        
    except Exception as e:
        logger.error(f"File cleanup failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.backup_database_task')
def backup_database_task(self, **kwargs) -> Dict[str, Any]:
    """Create database backup."""
    try:
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 0, 'stage': 'initializing_backup'}
        )
        
        db_manager = DatabaseManager()
        
        # Create backup filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"voicehelpdesk_backup_{timestamp}.sql"
        backup_path = os.path.join(settings.backup_dir, backup_filename)
        
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 50, 'stage': 'creating_backup'}
        )
        
        # Create database backup
        backup_info = db_manager.create_backup(backup_path)
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 90, 'stage': 'compressing_backup'}
        )
        
        # Compress backup
        compressed_path = f"{backup_path}.gz"
        import gzip
        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove uncompressed version
        os.remove(backup_path)
        
        result = {
            'backup_filename': f"{backup_filename}.gz",
            'backup_path': compressed_path,
            'file_size_bytes': os.path.getsize(compressed_path),
            'tables_backed_up': backup_info.get('tables', 0),
            'records_backed_up': backup_info.get('records', 0),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Created database backup: {backup_filename}.gz")
        return result
        
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise


@celery_app.task(bind=True, name='voicehelpdeskai.workers.tasks.optimize_database_task')
def optimize_database_task(self, **kwargs) -> Dict[str, Any]:
    """Optimize database performance."""
    try:
        current_task.update_state(
            state='PROCESSING', 
            meta={'progress': 0, 'stage': 'analyzing_database'}
        )
        
        db_manager = DatabaseManager()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 30, 'stage': 'optimizing_tables'}
        )
        
        # Run database optimization
        optimization_result = db_manager.optimize_database()
        
        current_task.update_state(
            state='PROCESSING',
            meta={'progress': 80, 'stage': 'updating_statistics'}
        )
        
        # Update database statistics
        stats_result = db_manager.update_statistics()
        
        result = {
            'optimization_result': optimization_result,
            'statistics_updated': stats_result,
            'optimized_at': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info("Completed database optimization")
        return result
        
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'traceback': traceback.format_exc()}
        )
        raise