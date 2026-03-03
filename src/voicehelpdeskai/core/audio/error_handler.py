"""Robust error handling and recovery system for audio processing."""

import functools
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from loguru import logger

from voicehelpdeskai.core.audio.exceptions import (
    AudioError,
    AudioDeviceError,
    AudioFormatError,
    AudioProcessingError,
    VoiceActivityError,
    StreamingError,
    AudioQueueError,
)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(Enum):
    """Recovery actions for different error types."""
    RETRY = "retry"
    FALLBACK = "fallback"
    RESET = "reset"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class ErrorContext:
    """Context information for error handling."""
    function_name: str
    module: str
    args: tuple
    kwargs: dict
    timestamp: float
    attempt_count: int
    max_attempts: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "function": self.function_name,
            "module": self.module,
            "timestamp": self.timestamp,
            "attempt": self.attempt_count,
            "max_attempts": self.max_attempts,
        }


@dataclass
class ErrorRecord:
    """Record of an error occurrence."""
    error_type: Type[Exception]
    error_message: str
    severity: ErrorSeverity
    context: ErrorContext
    traceback: str
    recovery_action: Optional[RecoveryAction] = None
    recovery_successful: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "error_type": self.error_type.__name__,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "context": self.context.to_dict(),
            "recovery_action": self.recovery_action.value if self.recovery_action else None,
            "recovery_successful": self.recovery_successful,
            "traceback": self.traceback,
        }


class AudioErrorHandler:
    """Centralized error handling and recovery system."""
    
    def __init__(self):
        """Initialize error handler."""
        self.error_history: List[ErrorRecord] = []
        self.error_counts: Dict[str, int] = {}
        self.recovery_strategies: Dict[Type[Exception], RecoveryAction] = {
            AudioDeviceError: RecoveryAction.RETRY,
            AudioFormatError: RecoveryAction.FALLBACK,
            AudioProcessingError: RecoveryAction.RETRY,
            VoiceActivityError: RecoveryAction.SKIP,
            StreamingError: RecoveryAction.RESET,
            AudioQueueError: RecoveryAction.RETRY,
            ConnectionError: RecoveryAction.RETRY,
            TimeoutError: RecoveryAction.RETRY,
            MemoryError: RecoveryAction.ABORT,
        }
        
        self.severity_mapping: Dict[Type[Exception], ErrorSeverity] = {
            AudioDeviceError: ErrorSeverity.HIGH,
            AudioFormatError: ErrorSeverity.MEDIUM,
            AudioProcessingError: ErrorSeverity.LOW,
            VoiceActivityError: ErrorSeverity.LOW,
            StreamingError: ErrorSeverity.HIGH,
            AudioQueueError: ErrorSeverity.MEDIUM,
            ConnectionError: ErrorSeverity.HIGH,
            TimeoutError: ErrorSeverity.MEDIUM,
            MemoryError: ErrorSeverity.CRITICAL,
            ValueError: ErrorSeverity.LOW,
            RuntimeError: ErrorSeverity.MEDIUM,
        }
        
        # Circuit breaker thresholds
        self.circuit_breaker_thresholds = {
            ErrorSeverity.LOW: 10,
            ErrorSeverity.MEDIUM: 5,
            ErrorSeverity.HIGH: 3,
            ErrorSeverity.CRITICAL: 1,
        }
        
        # Circuit breaker state
        self.circuit_breaker_open = False
        self.circuit_breaker_open_time = None
        self.circuit_breaker_timeout = 60.0  # seconds
        
        logger.info("AudioErrorHandler initialized")
    
    def get_error_severity(self, error: Exception) -> ErrorSeverity:
        """Get error severity level.
        
        Args:
            error: Exception instance
            
        Returns:
            Error severity level
        """
        error_type = type(error)
        
        # Check exact type first
        if error_type in self.severity_mapping:
            return self.severity_mapping[error_type]
        
        # Check parent types
        for registered_type, severity in self.severity_mapping.items():
            if isinstance(error, registered_type):
                return severity
        
        # Default severity
        return ErrorSeverity.MEDIUM
    
    def get_recovery_action(self, error: Exception) -> RecoveryAction:
        """Get recovery action for error.
        
        Args:
            error: Exception instance
            
        Returns:
            Recovery action
        """
        error_type = type(error)
        
        # Check exact type first
        if error_type in self.recovery_strategies:
            return self.recovery_strategies[error_type]
        
        # Check parent types
        for registered_type, action in self.recovery_strategies.items():
            if isinstance(error, registered_type):
                return action
        
        # Default action
        return RecoveryAction.RETRY
    
    def record_error(self, 
                    error: Exception,
                    context: ErrorContext,
                    recovery_action: Optional[RecoveryAction] = None,
                    recovery_successful: bool = False):
        """Record an error occurrence.
        
        Args:
            error: Exception instance
            context: Error context
            recovery_action: Recovery action taken
            recovery_successful: Whether recovery was successful
        """
        error_record = ErrorRecord(
            error_type=type(error),
            error_message=str(error),
            severity=self.get_error_severity(error),
            context=context,
            traceback=traceback.format_exc(),
            recovery_action=recovery_action,
            recovery_successful=recovery_successful,
        )
        
        # Add to history (keep last 1000 errors)
        self.error_history.append(error_record)
        if len(self.error_history) > 1000:
            self.error_history.pop(0)
        
        # Update error counts
        error_key = f"{error_record.error_type.__name__}:{context.function_name}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Check circuit breaker
        self._check_circuit_breaker(error_record)
        
        # Log error
        logger.error(
            "Audio error recorded",
            error_record=error_record.to_dict()
        )
    
    def _check_circuit_breaker(self, error_record: ErrorRecord):
        """Check if circuit breaker should be triggered.
        
        Args:
            error_record: Error record to check
        """
        severity = error_record.severity
        threshold = self.circuit_breaker_thresholds.get(severity, 5)
        
        # Count recent errors of this severity
        current_time = time.time()
        recent_errors = [
            err for err in self.error_history[-100:]  # Check last 100 errors
            if (err.severity == severity and 
                current_time - err.context.timestamp < 300)  # Last 5 minutes
        ]
        
        if len(recent_errors) >= threshold:
            self.circuit_breaker_open = True
            self.circuit_breaker_open_time = current_time
            logger.critical(
                f"Circuit breaker opened due to {len(recent_errors)} {severity.value} errors"
            )
    
    def is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is currently open.
        
        Returns:
            True if circuit breaker is open
        """
        if not self.circuit_breaker_open:
            return False
        
        if self.circuit_breaker_open_time is None:
            return False
        
        # Check if timeout has passed
        if time.time() - self.circuit_breaker_open_time > self.circuit_breaker_timeout:
            self.circuit_breaker_open = False
            self.circuit_breaker_open_time = None
            logger.info("Circuit breaker closed after timeout")
            return False
        
        return True
    
    def handle_error(self, 
                    error: Exception,
                    context: ErrorContext,
                    fallback_result: Any = None) -> tuple[bool, Any]:
        """Handle an error with appropriate recovery action.
        
        Args:
            error: Exception instance
            context: Error context
            fallback_result: Result to return if recovery fails
            
        Returns:
            Tuple of (recovery_successful, result)
        """
        # Check circuit breaker
        if self.is_circuit_breaker_open():
            logger.error("Circuit breaker is open, failing fast")
            self.record_error(error, context, RecoveryAction.ABORT, False)
            return False, fallback_result
        
        # Get recovery action
        recovery_action = self.get_recovery_action(error)
        
        # Record error
        self.record_error(error, context, recovery_action, False)
        
        # Attempt recovery based on action
        try:
            if recovery_action == RecoveryAction.RETRY:
                # Retry will be handled by decorator
                return False, fallback_result
            
            elif recovery_action == RecoveryAction.FALLBACK:
                # Use fallback result
                logger.info("Using fallback result for error recovery")
                # Update record to show successful recovery
                if self.error_history:
                    self.error_history[-1].recovery_successful = True
                return True, fallback_result
            
            elif recovery_action == RecoveryAction.SKIP:
                # Skip and continue with None result
                logger.info("Skipping operation due to error")
                if self.error_history:
                    self.error_history[-1].recovery_successful = True
                return True, None
            
            elif recovery_action == RecoveryAction.RESET:
                # Signal that a reset is needed
                logger.warning("Reset required for error recovery")
                return False, fallback_result
            
            elif recovery_action == RecoveryAction.ABORT:
                # Abort operation
                logger.error("Aborting operation due to critical error")
                return False, fallback_result
            
        except Exception as recovery_error:
            logger.error(f"Error during recovery: {recovery_error}")
            return False, fallback_result
        
        return False, fallback_result
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics.
        
        Returns:
            Dictionary with error statistics
        """
        if not self.error_history:
            return {
                "total_errors": 0,
                "error_types": {},
                "severity_distribution": {},
                "recent_errors": 0,
                "circuit_breaker_open": self.circuit_breaker_open,
            }
        
        # Count by error type
        error_types = {}
        severity_counts = {severity.value: 0 for severity in ErrorSeverity}
        
        current_time = time.time()
        recent_errors = 0
        
        for error_record in self.error_history:
            # Count by type
            error_type = error_record.error_type.__name__
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
            # Count by severity
            severity_counts[error_record.severity.value] += 1
            
            # Count recent errors (last hour)
            if current_time - error_record.context.timestamp < 3600:
                recent_errors += 1
        
        return {
            "total_errors": len(self.error_history),
            "error_types": error_types,
            "severity_distribution": severity_counts,
            "recent_errors": recent_errors,
            "circuit_breaker_open": self.circuit_breaker_open,
            "most_common_errors": sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5],
        }
    
    def clear_error_history(self):
        """Clear error history."""
        self.error_history.clear()
        self.error_counts.clear()
        logger.info("Error history cleared")
    
    def reset_circuit_breaker(self):
        """Manually reset circuit breaker."""
        self.circuit_breaker_open = False
        self.circuit_breaker_open_time = None
        logger.info("Circuit breaker manually reset")


# Global error handler instance
_error_handler = AudioErrorHandler()


def get_error_handler() -> AudioErrorHandler:
    """Get global error handler instance."""
    return _error_handler


def with_error_handling(max_retries: int = 3,
                       retry_delay: float = 1.0,
                       fallback_result: Any = None,
                       exceptions: tuple = None):
    """Decorator for automatic error handling and retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        fallback_result: Result to return if all retries fail
        exceptions: Tuple of exceptions to catch (None for all)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = get_error_handler()
            
            # Check circuit breaker
            if error_handler.is_circuit_breaker_open():
                logger.warning(f"Circuit breaker open, skipping {func.__name__}")
                return fallback_result
            
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except Exception as e:
                    last_exception = e
                    
                    # Check if we should catch this exception
                    if exceptions and not isinstance(e, exceptions):
                        raise
                    
                    # Create error context
                    context = ErrorContext(
                        function_name=func.__name__,
                        module=func.__module__,
                        args=args,
                        kwargs=kwargs,
                        timestamp=time.time(),
                        attempt_count=attempt + 1,
                        max_attempts=max_retries + 1,
                    )
                    
                    # Handle error
                    if attempt < max_retries:
                        # Log retry attempt
                        logger.warning(
                            f"Error in {func.__name__}, attempt {attempt + 1}/{max_retries + 1}: {e}"
                        )
                        
                        # Record error for retry
                        error_handler.record_error(e, context, RecoveryAction.RETRY, False)
                        
                        # Wait before retry
                        if retry_delay > 0:
                            time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    
                    else:
                        # Final attempt failed
                        logger.error(f"All retry attempts failed for {func.__name__}: {e}")
                        
                        # Handle error with fallback
                        recovery_successful, result = error_handler.handle_error(
                            e, context, fallback_result
                        )
                        
                        if recovery_successful:
                            return result
                        
                        # If recovery failed and no fallback, re-raise
                        if fallback_result is None:
                            raise
                        
                        return fallback_result
            
            # This should not be reached, but just in case
            if last_exception:
                raise last_exception
            
            return fallback_result
        
        return wrapper
    return decorator


@contextmanager
def error_context(operation_name: str, **context_data):
    """Context manager for error handling with additional context.
    
    Args:
        operation_name: Name of the operation
        **context_data: Additional context data
    """
    start_time = time.time()
    error_handler = get_error_handler()
    
    try:
        logger.debug(f"Starting operation: {operation_name}")
        yield
        
    except Exception as e:
        # Create error context
        context = ErrorContext(
            function_name=operation_name,
            module=__name__,
            args=(),
            kwargs=context_data,
            timestamp=start_time,
            attempt_count=1,
            max_attempts=1,
        )
        
        # Handle error
        error_handler.handle_error(e, context)
        raise
    
    finally:
        duration = time.time() - start_time
        logger.debug(f"Operation completed: {operation_name} (took {duration:.3f}s)")


def safe_call(func: Callable, 
             *args,
             fallback_result: Any = None,
             log_errors: bool = True,
             **kwargs) -> Any:
    """Safely call a function with error handling.
    
    Args:
        func: Function to call
        *args: Function arguments
        fallback_result: Result to return on error
        log_errors: Whether to log errors
        **kwargs: Function keyword arguments
        
    Returns:
        Function result or fallback_result on error
    """
    try:
        return func(*args, **kwargs)
    
    except Exception as e:
        if log_errors:
            logger.error(f"Error in safe_call to {func.__name__}: {e}")
        
        error_handler = get_error_handler()
        context = ErrorContext(
            function_name=func.__name__,
            module=getattr(func, '__module__', 'unknown'),
            args=args,
            kwargs=kwargs,
            timestamp=time.time(),
            attempt_count=1,
            max_attempts=1,
        )
        
        error_handler.record_error(e, context, RecoveryAction.FALLBACK, True)
        return fallback_result


class AudioOperationMonitor:
    """Monitor for audio operations with timeout and health checking."""
    
    def __init__(self, timeout: float = 30.0):
        """Initialize operation monitor.
        
        Args:
            timeout: Operation timeout in seconds
        """
        self.timeout = timeout
        self.active_operations: Dict[str, float] = {}
        self.operation_stats: Dict[str, Dict[str, Any]] = {}
    
    @contextmanager
    def monitor_operation(self, operation_id: str):
        """Monitor an audio operation.
        
        Args:
            operation_id: Unique operation identifier
        """
        start_time = time.time()
        self.active_operations[operation_id] = start_time
        
        try:
            # Initialize stats if needed
            if operation_id not in self.operation_stats:
                self.operation_stats[operation_id] = {
                    'total_calls': 0,
                    'total_time': 0.0,
                    'success_count': 0,
                    'error_count': 0,
                    'avg_duration': 0.0,
                }
            
            stats = self.operation_stats[operation_id]
            stats['total_calls'] += 1
            
            yield
            
            # Operation succeeded
            duration = time.time() - start_time
            stats['success_count'] += 1
            stats['total_time'] += duration
            stats['avg_duration'] = stats['total_time'] / stats['total_calls']
            
            logger.debug(f"Operation {operation_id} completed in {duration:.3f}s")
            
        except Exception as e:
            # Operation failed
            duration = time.time() - start_time
            stats = self.operation_stats[operation_id]
            stats['error_count'] += 1
            stats['total_time'] += duration
            stats['avg_duration'] = stats['total_time'] / stats['total_calls']
            
            logger.error(f"Operation {operation_id} failed after {duration:.3f}s: {e}")
            raise
            
        finally:
            # Remove from active operations
            if operation_id in self.active_operations:
                del self.active_operations[operation_id]
    
    def check_timeouts(self) -> List[str]:
        """Check for timed out operations.
        
        Returns:
            List of timed out operation IDs
        """
        current_time = time.time()
        timed_out = []
        
        for operation_id, start_time in list(self.active_operations.items()):
            if current_time - start_time > self.timeout:
                timed_out.append(operation_id)
                del self.active_operations[operation_id]
                logger.warning(f"Operation {operation_id} timed out")
        
        return timed_out
    
    def get_stats(self) -> Dict[str, Any]:
        """Get operation statistics.
        
        Returns:
            Dictionary with operation statistics
        """
        return {
            'active_operations': len(self.active_operations),
            'operation_stats': self.operation_stats.copy(),
            'longest_running': max(
                [(op_id, time.time() - start_time) 
                 for op_id, start_time in self.active_operations.items()],
                key=lambda x: x[1],
                default=('none', 0.0)
            ),
        }


# Global operation monitor
_operation_monitor = AudioOperationMonitor()


def get_operation_monitor() -> AudioOperationMonitor:
    """Get global operation monitor instance."""
    return _operation_monitor