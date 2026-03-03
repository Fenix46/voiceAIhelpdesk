"""
Comprehensive logging system for VoiceHelpDeskAI.

Provides structured logging, audit trails, performance logging,
security event tracking, and integration with external systems.
"""

import sys
import json
import time
import uuid
import threading
import traceback
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timezone
from contextlib import contextmanager
from functools import wraps
import asyncio

from loguru import logger
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from ..config import config_manager


class LogLevel(Enum):
    """Log levels with numeric values."""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    SUCCESS = 25
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class EventType(Enum):
    """Types of events for categorization."""
    SYSTEM = "system"
    SECURITY = "security"
    BUSINESS = "business"
    PERFORMANCE = "performance"
    AUDIT = "audit"
    ERROR = "error"
    USER_ACTION = "user_action"
    API_CALL = "api_call"
    MODEL_INFERENCE = "model_inference"
    AUDIO_PROCESSING = "audio_processing"


@dataclass
class LogContext:
    """Context information for structured logging."""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PerformanceMetrics:
    """Performance metrics for logging."""
    duration_ms: float
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    tokens_processed: Optional[int] = None
    requests_per_second: Optional[float] = None
    cache_hit_rate: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SecurityEvent:
    """Security event information."""
    event_type: str
    severity: str
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    attempted_action: Optional[str] = None
    resource: Optional[str] = None
    success: bool = False
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class LoggingSystem:
    """
    Comprehensive logging system with structured logging,
    context management, and external integrations.
    """
    
    def __init__(self):
        self._context_store = threading.local()
        self._log_processors: List[Callable] = []
        self._security_handlers: List[Callable] = []
        self._setup_loguru()
        self._setup_sentry()
        self._setup_custom_handlers()
        
        logger.info("Logging system initialized")
    
    def _setup_loguru(self):
        """Configure Loguru logging."""
        # Remove default handler
        logger.remove()
        
        # Console handler with colors for development
        if config_manager.get('VOICEHELPDESK_ENV') == 'development':
            logger.add(
                sys.stdout,
                format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                       "<level>{level: <8}</level> | "
                       "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                       "<level>{message}</level>",
                level="DEBUG",
                colorize=True,
                enqueue=True
            )
        
        # JSON file handler for production
        log_file = config_manager.get('VOICEHELPDESK_LOG_FILE', '/app/logs/app.log')
        logger.add(
            log_file,
            format=self._json_formatter,
            level=config_manager.get('VOICEHELPDESK_LOG_LEVEL', 'INFO'),
            rotation="100 MB",
            retention="30 days",
            compression="gz",
            enqueue=True,
            serialize=False
        )
        
        # Error file handler
        error_file = config_manager.get('VOICEHELPDESK_ERROR_LOG_FILE', '/app/logs/error.log')
        logger.add(
            error_file,
            format=self._json_formatter,
            level="ERROR",
            rotation="50 MB",
            retention="90 days",
            compression="gz",
            enqueue=True,
            serialize=False
        )
        
        # Performance log handler
        perf_file = config_manager.get('VOICEHELPDESK_PERF_LOG_FILE', '/app/logs/performance.log')
        logger.add(
            perf_file,
            format=self._json_formatter,
            level="INFO",
            rotation="100 MB",
            retention="7 days",
            compression="gz",
            enqueue=True,
            serialize=False,
            filter=lambda record: record["extra"].get("event_type") == "performance"
        )
        
        # Security log handler
        security_file = config_manager.get('VOICEHELPDESK_SECURITY_LOG_FILE', '/app/logs/security.log')
        logger.add(
            security_file,
            format=self._json_formatter,
            level="WARNING",
            rotation="50 MB",
            retention="365 days",
            compression="gz",
            enqueue=True,
            serialize=False,
            filter=lambda record: record["extra"].get("event_type") == "security"
        )
    
    def _setup_sentry(self):
        """Configure Sentry error tracking."""
        sentry_dsn = config_manager.get('SENTRY_DSN')
        if not sentry_dsn:
            logger.warning("Sentry DSN not configured, error tracking disabled")
            return
        
        # Configure Sentry
        sentry_logging = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        )
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                sentry_logging,
                AsyncioIntegration(reraise_exceptions=True)
            ],
            environment=config_manager.get('VOICEHELPDESK_ENV', 'development'),
            release=config_manager.get('VOICEHELPDESK_VERSION', '1.0.0'),
            traces_sample_rate=0.1,  # Performance monitoring
            profiles_sample_rate=0.1,  # Profiling
            attach_stacktrace=True,
            send_default_pii=False,  # Don't send personally identifiable information
            before_send=self._sentry_before_send,
            before_send_transaction=self._sentry_before_send_transaction
        )
        
        logger.info("Sentry error tracking initialized")
    
    def _setup_custom_handlers(self):
        """Setup custom log handlers and processors."""
        # Add custom log processors
        self._log_processors.extend([
            self._add_correlation_id,
            self._add_performance_context,
            self._sanitize_sensitive_data,
            self._enrich_with_system_info
        ])
    
    def _json_formatter(self, record) -> str:
        """Custom JSON formatter for structured logging."""
        # Extract basic record info
        log_entry = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "module": record["module"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
            "thread_id": record["thread"].id,
            "thread_name": record["thread"].name,
            "process_id": record["process"].id,
        }
        
        # Add exception info if present
        if record["exception"]:
            log_entry["exception"] = {
                "type": record["exception"].type.__name__,
                "value": str(record["exception"].value),
                "traceback": record["exception"].traceback
            }
        
        # Add extra fields
        extra = record.get("extra", {})
        if extra:
            log_entry.update(extra)
        
        # Add context if available
        context = self.get_context()
        if context:
            log_entry["context"] = context.to_dict()
        
        # Process through custom processors
        for processor in self._log_processors:
            log_entry = processor(log_entry)
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)
    
    def _sentry_before_send(self, event, hint):
        """Process events before sending to Sentry."""
        # Add custom context
        context = self.get_context()
        if context:
            event.setdefault("extra", {}).update(context.to_dict())
        
        # Filter out noisy errors if needed
        if event.get("logger") == "urllib3.connectionpool":
            return None
        
        return event
    
    def _sentry_before_send_transaction(self, event, hint):
        """Process transactions before sending to Sentry."""
        # Add custom tags
        event.setdefault("tags", {}).update({
            "component": self.get_context().component if self.get_context() else None
        })
        return event
    
    # ==========================================================================
    # Context Management
    # ==========================================================================
    
    def set_context(self, context: LogContext):
        """Set logging context for current thread."""
        self._context_store.context = context
    
    def get_context(self) -> Optional[LogContext]:
        """Get current logging context."""
        return getattr(self._context_store, 'context', None)
    
    def clear_context(self):
        """Clear current logging context."""
        if hasattr(self._context_store, 'context'):
            delattr(self._context_store, 'context')
    
    def update_context(self, **kwargs):
        """Update current context with new values."""
        context = self.get_context()
        if context:
            for key, value in kwargs.items():
                if hasattr(context, key):
                    setattr(context, key, value)
        else:
            self.set_context(LogContext(**kwargs))
    
    @contextmanager
    def context_scope(self, **kwargs):
        """Context manager for temporary context."""
        original_context = self.get_context()
        try:
            if original_context:
                # Update existing context
                new_context = LogContext(**{
                    **asdict(original_context),
                    **kwargs
                })
            else:
                new_context = LogContext(**kwargs)
            self.set_context(new_context)
            yield new_context
        finally:
            if original_context:
                self.set_context(original_context)
            else:
                self.clear_context()
    
    # ==========================================================================
    # Log Processors
    # ==========================================================================
    
    def _add_correlation_id(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Add correlation ID if not present."""
        if "correlation_id" not in log_entry and "context" in log_entry:
            context = log_entry["context"]
            if "correlation_id" not in context:
                context["correlation_id"] = str(uuid.uuid4())
        return log_entry
    
    def _add_performance_context(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Add performance context information."""
        if log_entry.get("event_type") == "performance":
            log_entry["performance_category"] = "application"
        return log_entry
    
    def _sanitize_sensitive_data(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or mask sensitive data from logs."""
        sensitive_fields = [
            "password", "token", "api_key", "secret", "authorization",
            "credit_card", "ssn", "email", "phone"
        ]
        
        def sanitize_dict(obj):
            if isinstance(obj, dict):
                return {
                    k: "***REDACTED***" if any(field in k.lower() for field in sensitive_fields)
                    else sanitize_dict(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [sanitize_dict(item) for item in obj]
            return obj
        
        return sanitize_dict(log_entry)
    
    def _enrich_with_system_info(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich log entry with system information."""
        log_entry["system"] = {
            "hostname": config_manager.get('HOSTNAME', 'unknown'),
            "service": "voicehelpdesk",
            "version": config_manager.get('VOICEHELPDESK_VERSION', '1.0.0'),
            "environment": config_manager.get('VOICEHELPDESK_ENV', 'development')
        }
        return log_entry
    
    # ==========================================================================
    # Structured Logging Methods
    # ==========================================================================
    
    def log_event(self, level: Union[str, LogLevel], message: str, 
                  event_type: EventType, **kwargs):
        """Log a structured event."""
        level_name = level.name if isinstance(level, LogLevel) else level
        
        extra_data = {
            "event_type": event_type.value,
            "event_data": kwargs
        }
        
        logger.bind(**extra_data).log(level_name, message)
    
    def log_api_call(self, method: str, endpoint: str, status_code: int,
                     duration_ms: float, request_size: int = 0,
                     response_size: int = 0, user_id: str = None):
        """Log API call with performance metrics."""
        self.log_event(
            LogLevel.INFO,
            f"{method} {endpoint} {status_code} {duration_ms}ms",
            EventType.API_CALL,
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration_ms=duration_ms,
            request_size=request_size,
            response_size=response_size,
            user_id=user_id
        )
    
    def log_model_inference(self, model_name: str, model_type: str,
                           duration_ms: float, input_tokens: int = 0,
                           output_tokens: int = 0, success: bool = True,
                           error: str = None):
        """Log model inference event."""
        self.log_event(
            LogLevel.INFO if success else LogLevel.ERROR,
            f"Model inference: {model_name} ({duration_ms}ms)",
            EventType.MODEL_INFERENCE,
            model_name=model_name,
            model_type=model_type,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=success,
            error=error
        )
    
    def log_audio_processing(self, processing_type: str, duration_ms: float,
                           audio_format: str, file_size: int = 0,
                           quality_score: float = None, success: bool = True):
        """Log audio processing event."""
        self.log_event(
            LogLevel.INFO if success else LogLevel.ERROR,
            f"Audio processing: {processing_type} ({duration_ms}ms)",
            EventType.AUDIO_PROCESSING,
            processing_type=processing_type,
            duration_ms=duration_ms,
            audio_format=audio_format,
            file_size=file_size,
            quality_score=quality_score,
            success=success
        )
    
    def log_performance(self, operation: str, metrics: PerformanceMetrics):
        """Log performance metrics."""
        self.log_event(
            LogLevel.INFO,
            f"Performance: {operation} ({metrics.duration_ms}ms)",
            EventType.PERFORMANCE,
            operation=operation,
            **metrics.to_dict()
        )
    
    def log_security_event(self, event: SecurityEvent):
        """Log security event."""
        level = LogLevel.CRITICAL if event.severity == "critical" else LogLevel.WARNING
        
        self.log_event(
            level,
            f"Security event: {event.event_type}",
            EventType.SECURITY,
            **event.to_dict()
        )
        
        # Notify security handlers
        for handler in self._security_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Security handler failed: {e}")
    
    def log_business_event(self, event_name: str, **data):
        """Log business event."""
        self.log_event(
            LogLevel.INFO,
            f"Business event: {event_name}",
            EventType.BUSINESS,
            event_name=event_name,
            **data
        )
    
    def log_error(self, error: Exception, context: str = None, **kwargs):
        """Log error with full context."""
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            **kwargs
        }
        
        # Send to Sentry if configured
        if hasattr(sentry_sdk, 'capture_exception'):
            with sentry_sdk.push_scope() as scope:
                for key, value in error_data.items():
                    scope.set_tag(key, value)
                sentry_sdk.capture_exception(error)
        
        self.log_event(
            LogLevel.ERROR,
            f"Error: {error}",
            EventType.ERROR,
            **error_data
        )
    
    # ==========================================================================
    # Decorators
    # ==========================================================================
    
    def log_function_call(self, log_args: bool = True, log_result: bool = False):
        """Decorator to log function calls."""
        def decorator(func):
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                func_name = f"{func.__module__}.{func.__qualname__}"
                start_time = time.time()
                
                log_data = {"function": func_name}
                if log_args:
                    log_data.update({
                        "args": str(args)[:200],  # Truncate long args
                        "kwargs": {k: str(v)[:100] for k, v in kwargs.items()}
                    })
                
                try:
                    result = func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000
                    
                    if log_result:
                        log_data["result"] = str(result)[:200]
                    
                    self.log_performance(
                        func_name,
                        PerformanceMetrics(duration_ms=duration_ms)
                    )
                    
                    return result
                    
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    log_data["error"] = str(e)
                    log_data["duration_ms"] = duration_ms
                    
                    self.log_error(e, f"Function call failed: {func_name}", **log_data)
                    raise
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                func_name = f"{func.__module__}.{func.__qualname__}"
                start_time = time.time()
                
                log_data = {"function": func_name}
                if log_args:
                    log_data.update({
                        "args": str(args)[:200],
                        "kwargs": {k: str(v)[:100] for k, v in kwargs.items()}
                    })
                
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000
                    
                    if log_result:
                        log_data["result"] = str(result)[:200]
                    
                    self.log_performance(
                        func_name,
                        PerformanceMetrics(duration_ms=duration_ms)
                    )
                    
                    return result
                    
                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    log_data["error"] = str(e)
                    log_data["duration_ms"] = duration_ms
                    
                    self.log_error(e, f"Async function call failed: {func_name}", **log_data)
                    raise
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator
    
    @contextmanager
    def performance_context(self, operation: str):
        """Context manager for performance logging."""
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.log_performance(operation, PerformanceMetrics(duration_ms=duration_ms))
    
    # ==========================================================================
    # Handler Management
    # ==========================================================================
    
    def add_security_handler(self, handler: Callable[[SecurityEvent], None]):
        """Add a security event handler."""
        self._security_handlers.append(handler)
    
    def add_log_processor(self, processor: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """Add a custom log processor."""
        self._log_processors.append(processor)


class AuditLogger:
    """
    Specialized logger for audit trails and compliance.
    """
    
    def __init__(self, logging_system: LoggingSystem):
        self.logging_system = logging_system
    
    def log_user_action(self, user_id: str, action: str, resource: str,
                       success: bool = True, details: Dict[str, Any] = None):
        """Log user action for audit trail."""
        self.logging_system.log_event(
            LogLevel.INFO,
            f"User action: {user_id} {action} {resource}",
            EventType.AUDIT,
            user_id=user_id,
            action=action,
            resource=resource,
            success=success,
            details=details or {},
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def log_data_access(self, user_id: str, data_type: str, operation: str,
                       record_count: int = 0, filters: Dict[str, Any] = None):
        """Log data access for compliance."""
        self.logging_system.log_event(
            LogLevel.INFO,
            f"Data access: {user_id} {operation} {data_type}",
            EventType.AUDIT,
            user_id=user_id,
            data_type=data_type,
            operation=operation,
            record_count=record_count,
            filters=filters or {},
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def log_configuration_change(self, user_id: str, component: str,
                               old_value: Any, new_value: Any):
        """Log configuration changes."""
        self.logging_system.log_event(
            LogLevel.WARNING,
            f"Configuration change: {component}",
            EventType.AUDIT,
            user_id=user_id,
            component=component,
            old_value=str(old_value),
            new_value=str(new_value),
            timestamp=datetime.now(timezone.utc).isoformat()
        )


class PerformanceLogger:
    """
    Specialized logger for performance monitoring and analysis.
    """
    
    def __init__(self, logging_system: LoggingSystem):
        self.logging_system = logging_system
        self._performance_thresholds = {
            'api_call': 1000,  # ms
            'model_inference': 5000,  # ms
            'audio_processing': 2000,  # ms
            'database_query': 500,  # ms
        }
    
    def set_threshold(self, operation_type: str, threshold_ms: float):
        """Set performance threshold for operation type."""
        self._performance_thresholds[operation_type] = threshold_ms
    
    def log_slow_operation(self, operation_type: str, operation_name: str,
                          duration_ms: float, details: Dict[str, Any] = None):
        """Log slow operation that exceeds threshold."""
        threshold = self._performance_thresholds.get(operation_type, 1000)
        
        if duration_ms > threshold:
            self.logging_system.log_event(
                LogLevel.WARNING,
                f"Slow operation: {operation_name} ({duration_ms}ms > {threshold}ms)",
                EventType.PERFORMANCE,
                operation_type=operation_type,
                operation_name=operation_name,
                duration_ms=duration_ms,
                threshold_ms=threshold,
                performance_impact="high",
                details=details or {}
            )
    
    def log_resource_usage(self, component: str, cpu_percent: float,
                          memory_mb: float, details: Dict[str, Any] = None):
        """Log resource usage metrics."""
        self.logging_system.log_event(
            LogLevel.INFO,
            f"Resource usage: {component}",
            EventType.PERFORMANCE,
            component=component,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            details=details or {}
        )


# Global logging system instance
logging_system = LoggingSystem()
audit_logger = AuditLogger(logging_system)
performance_logger = PerformanceLogger(logging_system)