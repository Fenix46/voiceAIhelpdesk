"""Celery application configuration with Redis backend."""

import os
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from celery import Celery, Task
from celery.signals import (
    worker_ready, worker_shutdown, task_prerun, task_postrun, 
    task_failure, task_success, task_retry
)
from kombu import Queue, Exchange
import redis.asyncio as redis

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)

# Celery configuration
CELERY_CONFIG = {
    # Broker settings (Redis)
    'broker_url': settings.redis_url or 'redis://localhost:6379/0',
    'result_backend': settings.redis_url or 'redis://localhost:6379/1',
    
    # Task settings
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'timezone': 'UTC',
    'enable_utc': True,
    
    # Task routing and queues
    'task_routes': {
        # Audio processing - high priority, dedicated workers
        'voicehelpdeskai.workers.tasks.process_audio_chunk_task': {
            'queue': 'audio_processing',
            'priority': 9
        },
        'voicehelpdeskai.workers.tasks.transcribe_audio_task': {
            'queue': 'audio_processing', 
            'priority': 8
        },
        'voicehelpdeskai.workers.tasks.generate_voice_response_task': {
            'queue': 'audio_processing',
            'priority': 7
        },
        
        # Ticket management - normal priority
        'voicehelpdeskai.workers.tasks.create_ticket_task': {
            'queue': 'ticket_management',
            'priority': 6
        },
        'voicehelpdeskai.workers.tasks.update_ticket_task': {
            'queue': 'ticket_management',
            'priority': 5
        },
        'voicehelpdeskai.workers.tasks.escalate_ticket_task': {
            'queue': 'ticket_management',
            'priority': 8
        },
        'voicehelpdeskai.workers.tasks.auto_assign_ticket_task': {
            'queue': 'ticket_management',
            'priority': 6
        },
        
        # Notifications - high priority but separate queue
        'voicehelpdeskai.workers.tasks.send_email_notification_task': {
            'queue': 'notifications',
            'priority': 7
        },
        'voicehelpdeskai.workers.tasks.send_sms_notification_task': {
            'queue': 'notifications',
            'priority': 8
        },
        'voicehelpdeskai.workers.tasks.send_webhook_notification_task': {
            'queue': 'notifications',
            'priority': 6
        },
        
        # Analytics - lower priority, can be batched
        'voicehelpdeskai.workers.tasks.compute_analytics_task': {
            'queue': 'analytics',
            'priority': 3
        },
        'voicehelpdeskai.workers.tasks.generate_report_task': {
            'queue': 'analytics',
            'priority': 2
        },
        'voicehelpdeskai.workers.tasks.update_dashboard_metrics_task': {
            'queue': 'analytics',
            'priority': 4
        },
        
        # ML inference - dedicated GPU workers if available
        'voicehelpdeskai.workers.tasks.run_sentiment_analysis_task': {
            'queue': 'ml_inference',
            'priority': 5
        },
        'voicehelpdeskai.workers.tasks.run_intent_classification_task': {
            'queue': 'ml_inference',
            'priority': 5
        },
        'voicehelpdeskai.workers.tasks.run_text_classification_task': {
            'queue': 'ml_inference',
            'priority': 4
        },
        
        # Cleanup - lowest priority, run during off-peak
        'voicehelpdeskai.workers.tasks.cleanup_expired_sessions_task': {
            'queue': 'maintenance',
            'priority': 1
        },
        'voicehelpdeskai.workers.tasks.cleanup_old_files_task': {
            'queue': 'maintenance',
            'priority': 1
        },
        'voicehelpdeskai.workers.tasks.backup_database_task': {
            'queue': 'maintenance',
            'priority': 2
        },
        'voicehelpdeskai.workers.tasks.optimize_database_task': {
            'queue': 'maintenance',
            'priority': 1
        }
    },
    
    # Queue definitions with priority support
    'task_queues': [
        # High-performance audio processing queue
        Queue('audio_processing', 
              Exchange('audio_processing', type='direct'),
              routing_key='audio_processing',
              queue_arguments={'x-max-priority': 10}),
        
        # Ticket management queue
        Queue('ticket_management',
              Exchange('ticket_management', type='direct'),
              routing_key='ticket_management', 
              queue_arguments={'x-max-priority': 10}),
        
        # Notifications queue
        Queue('notifications',
              Exchange('notifications', type='direct'),
              routing_key='notifications',
              queue_arguments={'x-max-priority': 10}),
        
        # Analytics and reporting queue
        Queue('analytics',
              Exchange('analytics', type='direct'), 
              routing_key='analytics',
              queue_arguments={'x-max-priority': 5}),
        
        # ML inference queue
        Queue('ml_inference',
              Exchange('ml_inference', type='direct'),
              routing_key='ml_inference',
              queue_arguments={'x-max-priority': 10}),
        
        # Maintenance and cleanup queue
        Queue('maintenance',
              Exchange('maintenance', type='direct'),
              routing_key='maintenance',
              queue_arguments={'x-max-priority': 3}),
        
        # Dead letter queue for failed tasks
        Queue('dead_letter',
              Exchange('dead_letter', type='direct'),
              routing_key='dead_letter')
    ],
    
    # Worker settings
    'worker_prefetch_multiplier': 1,  # Disable prefetching for priority
    'task_acks_late': True,
    'worker_disable_rate_limits': False,
    'worker_max_tasks_per_child': 1000,
    'worker_max_memory_per_child': 200000,  # 200MB
    
    # Task execution settings
    'task_soft_time_limit': 300,  # 5 minutes soft limit
    'task_time_limit': 600,       # 10 minutes hard limit
    'task_ignore_result': False,
    'task_store_eager_result': True,
    
    # Retry settings
    'task_default_retry_delay': 60,
    'task_max_retries': 3,
    'task_retry_backoff': True,
    'task_retry_backoff_max': 700,
    'task_retry_jitter': True,
    
    # Result backend settings
    'result_expires': 3600,  # 1 hour
    'result_backend_transport_options': {
        'master_name': 'mymaster'
    },
    
    # Monitoring
    'worker_send_task_events': True,
    'task_send_sent_event': True,
    'worker_hijack_root_logger': False,
    'worker_log_color': False,
    
    # Beat scheduler settings
    'beat_schedule': {
        'cleanup-expired-sessions': {
            'task': 'voicehelpdeskai.workers.tasks.cleanup_expired_sessions_task',
            'schedule': timedelta(minutes=30),
        },
        'cleanup-old-files': {
            'task': 'voicehelpdeskai.workers.tasks.cleanup_old_files_task', 
            'schedule': timedelta(hours=6),
        },
        'update-dashboard-metrics': {
            'task': 'voicehelpdeskai.workers.tasks.update_dashboard_metrics_task',
            'schedule': timedelta(minutes=5),
        },
        'database-backup': {
            'task': 'voicehelpdeskai.workers.tasks.backup_database_task',
            'schedule': timedelta(hours=24),
        },
        'database-optimization': {
            'task': 'voicehelpdeskai.workers.tasks.optimize_database_task',
            'schedule': timedelta(hours=168),  # Weekly
        }
    },
    
    # Security
    'worker_enable_remote_control': False,
    'worker_send_task_events': True
}

# Create Celery app
celery_app = Celery('voicehelpdeskai')
celery_app.config_from_object(CELERY_CONFIG)

# Import tasks to register them
from . import tasks


class BaseTaskWithRetry(Task):
    """Base task class with enhanced retry logic and circuit breaker."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_backoff_max = 700
    retry_jitter = True
    
    def __init__(self):
        super().__init__()
        self.circuit_breaker_failures = {}
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 300  # 5 minutes
    
    def apply_async(self, args=None, kwargs=None, **options):
        """Override apply_async to add circuit breaker logic."""
        task_name = self.name
        
        # Check circuit breaker
        if self._is_circuit_open(task_name):
            logger.warning(f"Circuit breaker open for task {task_name}")
            raise Exception(f"Circuit breaker open for task {task_name}")
        
        try:
            result = super().apply_async(args, kwargs, **options)
            self._record_success(task_name)
            return result
        except Exception as e:
            self._record_failure(task_name)
            raise e
    
    def _is_circuit_open(self, task_name: str) -> bool:
        """Check if circuit breaker is open for task."""
        if task_name not in self.circuit_breaker_failures:
            return False
        
        failure_info = self.circuit_breaker_failures[task_name]
        failure_count = failure_info.get('count', 0)
        last_failure = failure_info.get('last_failure', 0)
        
        if failure_count >= self.circuit_breaker_threshold:
            if time.time() - last_failure < self.circuit_breaker_timeout:
                return True
            else:
                # Reset circuit breaker after timeout
                self.circuit_breaker_failures[task_name] = {'count': 0, 'last_failure': 0}
        
        return False
    
    def _record_failure(self, task_name: str):
        """Record task failure for circuit breaker."""
        if task_name not in self.circuit_breaker_failures:
            self.circuit_breaker_failures[task_name] = {'count': 0, 'last_failure': 0}
        
        self.circuit_breaker_failures[task_name]['count'] += 1
        self.circuit_breaker_failures[task_name]['last_failure'] = time.time()
    
    def _record_success(self, task_name: str):
        """Record task success - reset circuit breaker if needed."""
        if task_name in self.circuit_breaker_failures:
            self.circuit_breaker_failures[task_name] = {'count': 0, 'last_failure': 0}


class TaskQueue:
    """High-level task queue interface."""
    
    def __init__(self, celery_instance: Celery):
        self.celery = celery_instance
        self.redis_client = None
        
    async def initialize(self):
        """Initialize Redis client for queue operations."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url or 'redis://localhost:6379/0',
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("TaskQueue Redis client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize TaskQueue Redis client: {e}")
    
    def enqueue_audio_processing(self, audio_data: bytes, conversation_id: str, 
                                sequence: int, format: str, **kwargs) -> str:
        """Enqueue audio processing task with high priority."""
        task = celery_app.send_task(
            'voicehelpdeskai.workers.tasks.process_audio_chunk_task',
            args=[audio_data, conversation_id, sequence, format],
            kwargs=kwargs,
            priority=9,
            queue='audio_processing'
        )
        logger.info(f"Enqueued audio processing task: {task.id}")
        return task.id
    
    def enqueue_ticket_creation(self, ticket_data: Dict[str, Any], **kwargs) -> str:
        """Enqueue ticket creation task."""
        task = celery_app.send_task(
            'voicehelpdeskai.workers.tasks.create_ticket_task',
            args=[ticket_data],
            kwargs=kwargs,
            priority=6,
            queue='ticket_management'
        )
        logger.info(f"Enqueued ticket creation task: {task.id}")
        return task.id
    
    def enqueue_notification(self, notification_type: str, recipient: str,
                           message: str, **kwargs) -> str:
        """Enqueue notification task."""
        task_name = f'voicehelpdeskai.workers.tasks.send_{notification_type}_notification_task'
        task = celery_app.send_task(
            task_name,
            args=[recipient, message],
            kwargs=kwargs,
            priority=7,
            queue='notifications'
        )
        logger.info(f"Enqueued {notification_type} notification task: {task.id}")
        return task.id
    
    def enqueue_analytics(self, analytics_type: str, **kwargs) -> str:
        """Enqueue analytics computation task."""
        task = celery_app.send_task(
            'voicehelpdeskai.workers.tasks.compute_analytics_task',
            args=[analytics_type],
            kwargs=kwargs,
            priority=3,
            queue='analytics'
        )
        logger.info(f"Enqueued analytics task: {task.id}")
        return task.id
    
    def enqueue_ml_inference(self, model_type: str, data: Any, **kwargs) -> str:
        """Enqueue ML inference task."""
        task_name = f'voicehelpdeskai.workers.tasks.run_{model_type}_task'
        task = celery_app.send_task(
            task_name,
            args=[data],
            kwargs=kwargs,
            priority=5,
            queue='ml_inference'
        )
        logger.info(f"Enqueued ML inference task: {task.id}")
        return task.id
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status and result."""
        try:
            result = celery_app.AsyncResult(task_id)
            return {
                'task_id': task_id,
                'status': result.status,
                'result': result.result,
                'traceback': result.traceback,
                'date_done': result.date_done,
                'successful': result.successful(),
                'failed': result.failed()
            }
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return {'task_id': task_id, 'status': 'UNKNOWN', 'error': str(e)}
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        try:
            celery_app.control.revoke(task_id, terminate=True)
            logger.info(f"Cancelled task: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False
    
    async def get_queue_length(self, queue_name: str) -> int:
        """Get current queue length."""
        try:
            if self.redis_client:
                return await self.redis_client.llen(f"celery.{queue_name}")
            return 0
        except Exception as e:
            logger.error(f"Failed to get queue length for {queue_name}: {e}")
            return 0
    
    async def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get list of active tasks across all workers."""
        try:
            inspect = celery_app.control.inspect()
            active = inspect.active()
            
            if not active:
                return []
            
            active_tasks = []
            for worker, tasks in active.items():
                for task in tasks:
                    active_tasks.append({
                        'worker': worker,
                        'task_id': task['id'],
                        'name': task['name'],
                        'args': task['args'],
                        'kwargs': task['kwargs'],
                        'time_start': task.get('time_start')
                    })
            
            return active_tasks
        except Exception as e:
            logger.error(f"Failed to get active tasks: {e}")
            return []
    
    async def purge_queue(self, queue_name: str) -> int:
        """Purge all tasks from a queue."""
        try:
            return celery_app.control.purge()
        except Exception as e:
            logger.error(f"Failed to purge queue {queue_name}: {e}")
            return 0


# Global task queue instance
task_queue = TaskQueue(celery_app)


# Celery signal handlers for monitoring and logging
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handle worker ready signal."""
    logger.info(f"Worker {sender} is ready")


@worker_shutdown.connect 
def worker_shutdown_handler(sender=None, **kwargs):
    """Handle worker shutdown signal."""
    logger.info(f"Worker {sender} is shutting down")


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task prerun signal."""
    logger.info(f"Task {task.name}[{task_id}] starting with args={args}, kwargs={kwargs}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, 
                        kwargs=None, retval=None, state=None, **kwds):
    """Handle task postrun signal."""
    logger.info(f"Task {task.name}[{task_id}] completed with state={state}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Handle task failure signal."""
    logger.error(f"Task {sender.name}[{task_id}] failed: {exception}")
    logger.error(f"Traceback: {traceback}")


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Handle task success signal."""
    logger.info(f"Task {sender.name} succeeded with result: {result}")


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwargs):
    """Handle task retry signal."""
    logger.warning(f"Task {sender.name}[{task_id}] retrying due to: {reason}")


# Set base task class
celery_app.Task = BaseTaskWithRetry