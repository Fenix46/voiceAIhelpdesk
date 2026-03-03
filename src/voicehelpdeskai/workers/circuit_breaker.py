"""Circuit breaker implementation for protecting against cascading failures."""

import asyncio
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, Optional
from enum import Enum
from dataclasses import dataclass

from ..core.logging import get_logger

logger = get_logger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5          # Number of failures before opening
    recovery_timeout: int = 60          # Seconds before trying half-open
    success_threshold: int = 3          # Successes needed to close from half-open
    timeout_duration: int = 30          # Timeout for individual calls
    monitor_interval: int = 10          # Health check interval
    failure_rate_threshold: float = 50.0  # Percentage failure rate to open


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State management
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._last_success_time = None
        self._next_attempt = None
        
        # Statistics
        self._total_calls = 0
        self._total_successes = 0
        self._total_failures = 0
        self._total_timeouts = 0
        self._total_circuit_open = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Sliding window for failure rate calculation
        self._call_history = []
        self._window_size = 100  # Keep last 100 calls
    
    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        with self._lock:
            return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed (normal operation)."""
        return self.state == CircuitBreakerState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open (failing)."""
        return self.state == CircuitBreakerState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open (testing)."""
        return self.state == CircuitBreakerState.HALF_OPEN
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap functions with circuit breaker."""
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            # Check if we should reject the call
            if self._should_reject_call():
                self._total_circuit_open += 1
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is {self._state.value}, "
                    f"failure count: {self._failure_count}"
                )
            
            self._total_calls += 1
            start_time = time.time()
        
        try:
            # Execute the function with timeout
            if asyncio.iscoroutinefunction(func):
                result = asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.timeout_duration
                )
            else:
                # For sync functions, we can't easily implement timeout
                # without threading, so we just call it directly
                result = func(*args, **kwargs)
            
            execution_time = time.time() - start_time
            self._record_success(execution_time)
            return result
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            self._record_timeout(execution_time)
            raise
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._record_failure(e, execution_time)
            raise
    
    async def async_call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        with self._lock:
            if self._should_reject_call():
                self._total_circuit_open += 1
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is {self._state.value}, "
                    f"failure count: {self._failure_count}"
                )
            
            self._total_calls += 1
            start_time = time.time()
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout_duration
            )
            
            execution_time = time.time() - start_time
            self._record_success(execution_time)
            return result
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            self._record_timeout(execution_time)
            raise
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._record_failure(e, execution_time)
            raise
    
    def _should_reject_call(self) -> bool:
        """Determine if the call should be rejected."""
        current_time = time.time()
        
        if self._state == CircuitBreakerState.CLOSED:
            return False
        
        elif self._state == CircuitBreakerState.OPEN:
            # Check if we should transition to half-open
            if (self._last_failure_time and 
                current_time - self._last_failure_time >= self.config.recovery_timeout):
                self._state = CircuitBreakerState.HALF_OPEN
                self._success_count = 0
                logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                return False
            return True
        
        elif self._state == CircuitBreakerState.HALF_OPEN:
            return False
        
        return False
    
    def _record_success(self, execution_time: float):
        """Record a successful call."""
        with self._lock:
            current_time = time.time()
            
            self._total_successes += 1
            self._last_success_time = current_time
            
            # Add to call history
            self._call_history.append({
                'timestamp': current_time,
                'success': True,
                'execution_time': execution_time
            })
            self._trim_call_history()
            
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                
                # Check if we should close the circuit
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' CLOSED after recovery")
            
            elif self._state == CircuitBreakerState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0
    
    def _record_failure(self, exception: Exception, execution_time: float):
        """Record a failed call."""
        with self._lock:
            current_time = time.time()
            
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = current_time
            
            # Add to call history
            self._call_history.append({
                'timestamp': current_time,
                'success': False,
                'execution_time': execution_time,
                'exception': str(exception)
            })
            self._trim_call_history()
            
            # Check if we should open the circuit
            if self._state == CircuitBreakerState.CLOSED:
                if self._should_open_circuit():
                    self._state = CircuitBreakerState.OPEN
                    self._next_attempt = current_time + self.config.recovery_timeout
                    logger.warning(
                        f"Circuit breaker '{self.name}' OPENED due to failures. "
                        f"Failure count: {self._failure_count}, "
                        f"Failure rate: {self._calculate_failure_rate():.1f}%"
                    )
            
            elif self._state == CircuitBreakerState.HALF_OPEN:
                # Any failure in half-open state opens the circuit again
                self._state = CircuitBreakerState.OPEN
                self._next_attempt = current_time + self.config.recovery_timeout
                logger.warning(f"Circuit breaker '{self.name}' OPENED from half-open state")
    
    def _record_timeout(self, execution_time: float):
        """Record a timeout."""
        with self._lock:
            self._total_timeouts += 1
            # Treat timeouts as failures
            self._record_failure(Exception("Timeout"), execution_time)
    
    def _should_open_circuit(self) -> bool:
        """Determine if the circuit should be opened."""
        # Open if we exceed the failure threshold
        if self._failure_count >= self.config.failure_threshold:
            return True
        
        # Open if failure rate is too high (with minimum call count)
        if len(self._call_history) >= 10:  # Minimum calls for rate calculation
            failure_rate = self._calculate_failure_rate()
            if failure_rate >= self.config.failure_rate_threshold:
                return True
        
        return False
    
    def _calculate_failure_rate(self) -> float:
        """Calculate current failure rate."""
        if not self._call_history:
            return 0.0
        
        failures = sum(1 for call in self._call_history if not call['success'])
        return (failures / len(self._call_history)) * 100
    
    def _trim_call_history(self):
        """Trim call history to maintain window size."""
        if len(self._call_history) > self._window_size:
            self._call_history = self._call_history[-self._window_size:]
    
    def reset(self):
        """Reset the circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._last_success_time = None
            self._call_history.clear()
            logger.info(f"Circuit breaker '{self.name}' has been reset")
    
    def force_open(self):
        """Force the circuit breaker to open state."""
        with self._lock:
            self._state = CircuitBreakerState.OPEN
            self._next_attempt = time.time() + self.config.recovery_timeout
            logger.warning(f"Circuit breaker '{self.name}' forced OPEN")
    
    def force_close(self):
        """Force the circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            logger.info(f"Circuit breaker '{self.name}' forced CLOSED")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            failure_rate = self._calculate_failure_rate()
            
            return {
                'name': self.name,
                'state': self._state.value,
                'failure_count': self._failure_count,
                'success_count': self._success_count,
                'total_calls': self._total_calls,
                'total_successes': self._total_successes,
                'total_failures': self._total_failures,
                'total_timeouts': self._total_timeouts,
                'total_circuit_open': self._total_circuit_open,
                'failure_rate': round(failure_rate, 2),
                'last_failure_time': self._last_failure_time,
                'last_success_time': self._last_success_time,
                'next_attempt': self._next_attempt,
                'config': {
                    'failure_threshold': self.config.failure_threshold,
                    'recovery_timeout': self.config.recovery_timeout,
                    'success_threshold': self.config.success_threshold,
                    'timeout_duration': self.config.timeout_duration,
                    'failure_rate_threshold': self.config.failure_rate_threshold
                }
            }


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""
    
    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def get_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        with self._lock:
            if name not in self._circuit_breakers:
                self._circuit_breakers[name] = CircuitBreaker(name, config)
            return self._circuit_breakers[name]
    
    def create_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Create a new circuit breaker."""
        with self._lock:
            circuit_breaker = CircuitBreaker(name, config)
            self._circuit_breakers[name] = circuit_breaker
            return circuit_breaker
    
    def remove_circuit_breaker(self, name: str) -> bool:
        """Remove a circuit breaker."""
        with self._lock:
            if name in self._circuit_breakers:
                del self._circuit_breakers[name]
                return True
            return False
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        with self._lock:
            return {name: cb.get_stats() for name, cb in self._circuit_breakers.items()}
    
    def reset_all(self):
        """Reset all circuit breakers."""
        with self._lock:
            for circuit_breaker in self._circuit_breakers.values():
                circuit_breaker.reset()
    
    def get_circuit_breaker_names(self) -> List[str]:
        """Get names of all circuit breakers."""
        with self._lock:
            return list(self._circuit_breakers.keys())


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


def circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """Decorator to add circuit breaker protection to functions."""
    def decorator(func: Callable):
        cb = circuit_breaker_manager.get_circuit_breaker(name, config)
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                return await cb.async_call(func, *args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                return cb.call(func, *args, **kwargs)
            return sync_wrapper
    
    return decorator


# Pre-configured circuit breakers for common services
def get_database_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for database operations."""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30,
        success_threshold=2,
        timeout_duration=10,
        failure_rate_threshold=30.0
    )
    return circuit_breaker_manager.get_circuit_breaker('database', config)


def get_redis_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Redis operations."""
    config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=15,
        success_threshold=3,
        timeout_duration=5,
        failure_rate_threshold=40.0
    )
    return circuit_breaker_manager.get_circuit_breaker('redis', config)


def get_external_api_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for external API calls."""
    config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60,
        success_threshold=3,
        timeout_duration=30,
        failure_rate_threshold=25.0
    )
    return circuit_breaker_manager.get_circuit_breaker('external_api', config)


def get_ml_service_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for ML service calls."""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=120,
        success_threshold=2,
        timeout_duration=60,
        failure_rate_threshold=20.0
    )
    return circuit_breaker_manager.get_circuit_breaker('ml_service', config)