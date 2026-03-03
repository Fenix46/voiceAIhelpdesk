"""Background processing system with Celery and Redis."""

from .celery_app import celery_app, task_queue
from .worker_manager import WorkerManager
from .task_monitor import TaskMonitor
from .scheduled_tasks import ScheduledTaskManager
from .circuit_breaker import (
    CircuitBreaker, CircuitBreakerManager, CircuitBreakerConfig,
    circuit_breaker_manager, circuit_breaker,
    get_database_circuit_breaker, get_redis_circuit_breaker,
    get_external_api_circuit_breaker, get_ml_service_circuit_breaker
)
from .task_result_storage import (
    TaskResultStorage, TaskResultManager, GracefulShutdownManager,
    TaskResult, ResultStatus, StorageBackend, task_result_manager
)
from .tasks import (
    # Audio processing
    process_audio_chunk_task,
    transcribe_audio_task,
    generate_voice_response_task,
    
    # Ticket management
    create_ticket_task,
    update_ticket_task,
    escalate_ticket_task,
    auto_assign_ticket_task,
    
    # Notifications
    send_email_notification_task,
    send_sms_notification_task,
    send_webhook_notification_task,
    
    # Analytics
    compute_analytics_task,
    generate_report_task,
    update_dashboard_metrics_task,
    
    # Model inference
    run_sentiment_analysis_task,
    run_intent_classification_task,
    run_text_classification_task,
    
    # Cleanup and maintenance
    cleanup_expired_sessions_task,
    cleanup_old_files_task,
    backup_database_task,
    optimize_database_task
)

__all__ = [
    "celery_app",
    "task_queue", 
    "WorkerManager",
    "TaskMonitor",
    "ScheduledTaskManager",
    # Circuit breaker components
    "CircuitBreaker",
    "CircuitBreakerManager", 
    "CircuitBreakerConfig",
    "circuit_breaker_manager",
    "circuit_breaker",
    "get_database_circuit_breaker",
    "get_redis_circuit_breaker",
    "get_external_api_circuit_breaker",
    "get_ml_service_circuit_breaker",
    # Task result storage components
    "TaskResultStorage",
    "TaskResultManager",
    "GracefulShutdownManager",
    "TaskResult",
    "ResultStatus",
    "StorageBackend",
    "task_result_manager",
    # Audio tasks
    "process_audio_chunk_task",
    "transcribe_audio_task", 
    "generate_voice_response_task",
    # Ticket tasks
    "create_ticket_task",
    "update_ticket_task",
    "escalate_ticket_task", 
    "auto_assign_ticket_task",
    # Notification tasks
    "send_email_notification_task",
    "send_sms_notification_task",
    "send_webhook_notification_task",
    # Analytics tasks
    "compute_analytics_task",
    "generate_report_task",
    "update_dashboard_metrics_task",
    # ML tasks
    "run_sentiment_analysis_task",
    "run_intent_classification_task",
    "run_text_classification_task",
    # Cleanup tasks
    "cleanup_expired_sessions_task",
    "cleanup_old_files_task",
    "backup_database_task",
    "optimize_database_task"
]