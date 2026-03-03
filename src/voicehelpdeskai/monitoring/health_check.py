"""
Comprehensive health check system for VoiceHelpDeskAI.

Monitors service health, model availability, resource usage,
and external dependencies.
"""

import asyncio
import time
import psutil
import redis
import sqlite3
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import subprocess
import threading
from pathlib import Path

import httpx
import torch
from loguru import logger

from ..config import config_manager
from .logging_system import logging_system, LogLevel, EventType


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Types of health checks."""
    CRITICAL = "critical"
    IMPORTANT = "important"
    INFORMATIONAL = "informational"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    check_type: CheckType = CheckType.IMPORTANT
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'duration_ms': self.duration_ms,
            'timestamp': self.timestamp.isoformat(),
            'check_type': self.check_type.value
        }


@dataclass
class SystemHealth:
    """Overall system health summary."""
    status: HealthStatus
    checks: List[HealthCheckResult]
    summary: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'status': self.status.value,
            'checks': [check.to_dict() for check in self.checks],
            'summary': self.summary,
            'timestamp': self.timestamp.isoformat()
        }


class HealthCheck:
    """Base class for health checks."""
    
    def __init__(self, name: str, check_type: CheckType = CheckType.IMPORTANT,
                 timeout: float = 10.0):
        self.name = name
        self.check_type = check_type
        self.timeout = timeout
    
    async def check(self) -> HealthCheckResult:
        """Perform the health check."""
        start_time = time.time()
        
        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                self._perform_check(),
                timeout=self.timeout
            )
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                name=self.name,
                status=result.get('status', HealthStatus.UNKNOWN),
                message=result.get('message', 'Check completed'),
                details=result.get('details', {}),
                duration_ms=duration_ms,
                check_type=self.check_type
            )
            
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f'Check timed out after {self.timeout}s',
                duration_ms=duration_ms,
                check_type=self.check_type
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f'Check failed: {str(e)}',
                details={'error': str(e)},
                duration_ms=duration_ms,
                check_type=self.check_type
            )
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Override this method to implement the actual check."""
        raise NotImplementedError


class DatabaseHealthCheck(HealthCheck):
    """Health check for database connectivity."""
    
    def __init__(self):
        super().__init__("database", CheckType.CRITICAL)
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check database connectivity."""
        db_url = config_manager.get('VOICEHELPDESK_DATABASE_URL')
        
        if not db_url:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': 'Database URL not configured'
            }
        
        try:
            if db_url.startswith('sqlite'):
                # SQLite check
                db_path = db_url.replace('sqlite:///', '')
                if not Path(db_path).exists():
                    return {
                        'status': HealthStatus.UNHEALTHY,
                        'message': f'SQLite database file not found: {db_path}'
                    }
                
                # Test connection
                conn = sqlite3.connect(db_path, timeout=5)
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                result = cursor.fetchone()
                conn.close()
                
                if result and result[0] == 1:
                    return {
                        'status': HealthStatus.HEALTHY,
                        'message': 'Database connection successful',
                        'details': {'type': 'sqlite', 'path': db_path}
                    }
            
            # Add PostgreSQL/MySQL checks here if needed
            
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': 'Unsupported database type'
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f'Database connection failed: {str(e)}',
                'details': {'error': str(e)}
            }


class RedisHealthCheck(HealthCheck):
    """Health check for Redis connectivity."""
    
    def __init__(self):
        super().__init__("redis", CheckType.CRITICAL)
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check Redis connectivity."""
        redis_url = config_manager.get('VOICEHELPDESK_REDIS_URL')
        
        if not redis_url:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': 'Redis URL not configured'
            }
        
        try:
            redis_client = redis.from_url(redis_url, socket_timeout=5)
            
            # Test basic connectivity
            ping_result = redis_client.ping()
            if not ping_result:
                return {
                    'status': HealthStatus.UNHEALTHY,
                    'message': 'Redis ping failed'
                }
            
            # Test read/write
            test_key = 'health_check_test'
            test_value = str(time.time())
            redis_client.set(test_key, test_value, ex=10)
            retrieved_value = redis_client.get(test_key)
            
            if retrieved_value.decode() != test_value:
                return {
                    'status': HealthStatus.DEGRADED,
                    'message': 'Redis read/write test failed'
                }
            
            # Get Redis info
            info = redis_client.info()
            
            return {
                'status': HealthStatus.HEALTHY,
                'message': 'Redis connection successful',
                'details': {
                    'version': info.get('redis_version'),
                    'connected_clients': info.get('connected_clients'),
                    'used_memory': info.get('used_memory'),
                    'uptime_in_seconds': info.get('uptime_in_seconds')
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f'Redis connection failed: {str(e)}',
                'details': {'error': str(e)}
            }


class ModelHealthCheck(HealthCheck):
    """Health check for AI model availability."""
    
    def __init__(self, model_name: str, model_type: str):
        super().__init__(f"model_{model_name}", CheckType.IMPORTANT)
        self.model_name = model_name
        self.model_type = model_type
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check model availability and basic functionality."""
        try:
            model_path = config_manager.get('VOICEHELPDESK_MODEL_PATH', '/app/models')
            
            if self.model_type == 'whisper':
                return await self._check_whisper_model()
            elif self.model_type == 'piper':
                return await self._check_piper_model()
            elif self.model_type == 'llm':
                return await self._check_llm_model()
            else:
                return {
                    'status': HealthStatus.UNKNOWN,
                    'message': f'Unknown model type: {self.model_type}'
                }
                
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f'Model check failed: {str(e)}',
                'details': {'error': str(e)}
            }
    
    async def _check_whisper_model(self) -> Dict[str, Any]:
        """Check Whisper model availability."""
        model_path = config_manager.get('VOICEHELPDESK_MODEL_PATH', '/app/models')
        whisper_path = Path(model_path) / 'whisper' / f'{self.model_name}.pt'
        
        if not whisper_path.exists():
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f'Whisper model file not found: {whisper_path}'
            }
        
        # Check file size (basic validity check)
        file_size = whisper_path.stat().st_size
        if file_size < 1024 * 1024:  # Less than 1MB is suspicious
            return {
                'status': HealthStatus.DEGRADED,
                'message': f'Whisper model file suspiciously small: {file_size} bytes'
            }
        
        return {
            'status': HealthStatus.HEALTHY,
            'message': 'Whisper model available',
            'details': {
                'path': str(whisper_path),
                'size_mb': round(file_size / (1024 * 1024), 2)
            }
        }
    
    async def _check_piper_model(self) -> Dict[str, Any]:
        """Check Piper TTS model availability."""
        model_path = config_manager.get('VOICEHELPDESK_MODEL_PATH', '/app/models')
        piper_onnx = Path(model_path) / 'piper' / f'{self.model_name}.onnx'
        piper_json = Path(model_path) / 'piper' / f'{self.model_name}.onnx.json'
        
        if not piper_onnx.exists():
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f'Piper ONNX model not found: {piper_onnx}'
            }
        
        if not piper_json.exists():
            return {
                'status': HealthStatus.DEGRADED,
                'message': f'Piper config file not found: {piper_json}'
            }
        
        return {
            'status': HealthStatus.HEALTHY,
            'message': 'Piper model available',
            'details': {
                'onnx_path': str(piper_onnx),
                'config_path': str(piper_json),
                'onnx_size_mb': round(piper_onnx.stat().st_size / (1024 * 1024), 2)
            }
        }
    
    async def _check_llm_model(self) -> Dict[str, Any]:
        """Check LLM model availability."""
        llm_provider = config_manager.get('VOICEHELPDESK_LLM_PROVIDER', 'openai')
        
        if llm_provider == 'openai':
            api_key = config_manager.get('OPENAI_API_KEY')
            if not api_key:
                return {
                    'status': HealthStatus.UNHEALTHY,
                    'message': 'OpenAI API key not configured'
                }
            
            # Test API connectivity
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        'https://api.openai.com/v1/models',
                        headers={'Authorization': f'Bearer {api_key}'},
                        timeout=5.0
                    )
                    
                    if response.status_code == 200:
                        return {
                            'status': HealthStatus.HEALTHY,
                            'message': 'OpenAI API accessible',
                            'details': {'provider': 'openai'}
                        }
                    else:
                        return {
                            'status': HealthStatus.DEGRADED,
                            'message': f'OpenAI API returned status {response.status_code}'
                        }
            except Exception as e:
                return {
                    'status': HealthStatus.UNHEALTHY,
                    'message': f'OpenAI API test failed: {str(e)}'
                }
        
        return {
            'status': HealthStatus.UNKNOWN,
            'message': f'Unsupported LLM provider: {llm_provider}'
        }


class ResourceHealthCheck(HealthCheck):
    """Health check for system resources."""
    
    def __init__(self):
        super().__init__("resources", CheckType.IMPORTANT)
        self.memory_threshold = 0.9  # 90%
        self.cpu_threshold = 0.95    # 95%
        self.disk_threshold = 0.9    # 90%
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            # Memory check
            memory = psutil.virtual_memory()
            memory_usage = memory.percent / 100
            
            # CPU check
            cpu_usage = psutil.cpu_percent(interval=1) / 100
            
            # Disk check
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent / 100
            
            # Process-specific memory
            process = psutil.Process()
            process_memory = process.memory_info().rss / (1024 * 1024 * 1024)  # GB
            
            # Determine overall status
            if (memory_usage > self.memory_threshold or 
                cpu_usage > self.cpu_threshold or 
                disk_usage > self.disk_threshold):
                status = HealthStatus.UNHEALTHY
                message = 'Resource usage critical'
            elif (memory_usage > 0.8 or cpu_usage > 0.8 or disk_usage > 0.8):
                status = HealthStatus.DEGRADED
                message = 'Resource usage high'
            else:
                status = HealthStatus.HEALTHY
                message = 'Resource usage normal'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'memory': {
                        'usage_percent': round(memory_usage * 100, 2),
                        'available_gb': round(memory.available / (1024**3), 2),
                        'total_gb': round(memory.total / (1024**3), 2)
                    },
                    'cpu': {
                        'usage_percent': round(cpu_usage * 100, 2),
                        'count': psutil.cpu_count()
                    },
                    'disk': {
                        'usage_percent': round(disk_usage * 100, 2),
                        'free_gb': round(disk.free / (1024**3), 2),
                        'total_gb': round(disk.total / (1024**3), 2)
                    },
                    'process': {
                        'memory_gb': round(process_memory, 2),
                        'cpu_percent': round(process.cpu_percent(), 2)
                    }
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f'Resource check failed: {str(e)}',
                'details': {'error': str(e)}
            }


class GPUHealthCheck(HealthCheck):
    """Health check for GPU availability and health."""
    
    def __init__(self):
        super().__init__("gpu", CheckType.INFORMATIONAL)
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check GPU availability and status."""
        try:
            if not torch.cuda.is_available():
                return {
                    'status': HealthStatus.HEALTHY,
                    'message': 'CUDA not available (CPU mode)',
                    'details': {'cuda_available': False}
                }
            
            gpu_count = torch.cuda.device_count()
            if gpu_count == 0:
                return {
                    'status': HealthStatus.HEALTHY,
                    'message': 'No CUDA devices found (CPU mode)',
                    'details': {'cuda_available': True, 'device_count': 0}
                }
            
            gpu_details = []
            for i in range(gpu_count):
                props = torch.cuda.get_device_properties(i)
                memory_allocated = torch.cuda.memory_allocated(i) / (1024**3)  # GB
                memory_cached = torch.cuda.memory_reserved(i) / (1024**3)  # GB
                memory_total = props.total_memory / (1024**3)  # GB
                
                gpu_details.append({
                    'device': i,
                    'name': props.name,
                    'total_memory_gb': round(memory_total, 2),
                    'allocated_gb': round(memory_allocated, 2),
                    'cached_gb': round(memory_cached, 2),
                    'utilization_percent': round((memory_allocated / memory_total) * 100, 2)
                })
            
            # Check if any GPU has high utilization
            max_utilization = max(gpu['utilization_percent'] for gpu in gpu_details)
            
            if max_utilization > 95:
                status = HealthStatus.DEGRADED
                message = f'High GPU utilization: {max_utilization}%'
            else:
                status = HealthStatus.HEALTHY
                message = f'{gpu_count} GPU(s) available'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'cuda_available': True,
                    'device_count': gpu_count,
                    'devices': gpu_details
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNKNOWN,
                'message': f'GPU check failed: {str(e)}',
                'details': {'error': str(e)}
            }


class QueueHealthCheck(HealthCheck):
    """Health check for message queues."""
    
    def __init__(self):
        super().__init__("queues", CheckType.IMPORTANT)
        self.queue_threshold = 100  # Maximum queue depth
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check queue health and depth."""
        try:
            redis_url = config_manager.get('CELERY_BROKER_URL')
            if not redis_url:
                return {
                    'status': HealthStatus.UNHEALTHY,
                    'message': 'Celery broker URL not configured'
                }
            
            redis_client = redis.from_url(redis_url)
            
            # Check common Celery queues
            queues = ['celery', 'audio', 'ai', 'notifications']
            queue_details = {}
            max_depth = 0
            
            for queue_name in queues:
                depth = redis_client.llen(queue_name)
                queue_details[queue_name] = depth
                max_depth = max(max_depth, depth)
            
            # Determine status based on queue depths
            if max_depth > self.queue_threshold:
                status = HealthStatus.UNHEALTHY
                message = f'Queue backlog critical: {max_depth} messages'
            elif max_depth > self.queue_threshold * 0.5:
                status = HealthStatus.DEGRADED
                message = f'Queue backlog high: {max_depth} messages'
            else:
                status = HealthStatus.HEALTHY
                message = 'Queue depths normal'
            
            return {
                'status': status,
                'message': message,
                'details': {
                    'queues': queue_details,
                    'max_depth': max_depth,
                    'threshold': self.queue_threshold
                }
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f'Queue check failed: {str(e)}',
                'details': {'error': str(e)}
            }


class ExternalServiceHealthCheck(HealthCheck):
    """Health check for external services."""
    
    def __init__(self, service_name: str, url: str, timeout: float = 5.0):
        super().__init__(f"external_{service_name}", CheckType.INFORMATIONAL, timeout)
        self.service_name = service_name
        self.url = url
    
    async def _perform_check(self) -> Dict[str, Any]:
        """Check external service availability."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.url,
                    timeout=self.timeout,
                    follow_redirects=True
                )
                
                if response.status_code < 400:
                    return {
                        'status': HealthStatus.HEALTHY,
                        'message': f'{self.service_name} is accessible',
                        'details': {
                            'status_code': response.status_code,
                            'response_time_ms': response.elapsed.total_seconds() * 1000
                        }
                    }
                else:
                    return {
                        'status': HealthStatus.DEGRADED,
                        'message': f'{self.service_name} returned {response.status_code}',
                        'details': {'status_code': response.status_code}
                    }
                    
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'message': f'{self.service_name} is unreachable: {str(e)}',
                'details': {'error': str(e)}
            }


class HealthCheckSystem:
    """
    Comprehensive health check system that orchestrates
    all individual health checks.
    """
    
    def __init__(self):
        self.checks: List[HealthCheck] = []
        self.background_task: Optional[asyncio.Task] = None
        self.check_interval = 30  # seconds
        self.last_results: List[HealthCheckResult] = []
        self._lock = asyncio.Lock()
        
        # Initialize standard health checks
        self._initialize_checks()
        
        logger.info("Health check system initialized")
    
    def _initialize_checks(self):
        """Initialize all health checks."""
        # Critical infrastructure checks
        self.checks.extend([
            DatabaseHealthCheck(),
            RedisHealthCheck(),
            ResourceHealthCheck(),
            QueueHealthCheck()
        ])
        
        # Model availability checks
        whisper_model = config_manager.get('VOICEHELPDESK_WHISPER_MODEL', 'base')
        piper_model = config_manager.get('VOICEHELPDESK_PIPER_MODEL', 'en_US-amy-medium')
        
        self.checks.extend([
            ModelHealthCheck(whisper_model, 'whisper'),
            ModelHealthCheck(piper_model, 'piper'),
            ModelHealthCheck('gpt', 'llm')
        ])
        
        # Optional checks
        self.checks.append(GPUHealthCheck())
        
        # External service checks (if configured)
        ticketing_url = config_manager.get('VOICEHELPDESK_TICKETING_API_URL')
        if ticketing_url:
            self.checks.append(
                ExternalServiceHealthCheck('ticketing_api', f'{ticketing_url}/health')
            )
    
    def add_check(self, check: HealthCheck):
        """Add a custom health check."""
        self.checks.append(check)
    
    async def run_all_checks(self) -> SystemHealth:
        """Run all health checks and return system health."""
        async with self._lock:
            start_time = time.time()
            
            # Run all checks concurrently
            tasks = [check.check() for check in self.checks]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            check_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Handle check that threw exception
                    check_results.append(HealthCheckResult(
                        name=self.checks[i].name,
                        status=HealthStatus.UNHEALTHY,
                        message=f'Check failed with exception: {str(result)}',
                        check_type=self.checks[i].check_type
                    ))
                else:
                    check_results.append(result)
            
            self.last_results = check_results
            
            # Calculate overall system health
            overall_status = self._calculate_overall_status(check_results)
            
            # Generate summary
            summary = self._generate_summary(check_results, time.time() - start_time)
            
            system_health = SystemHealth(
                status=overall_status,
                checks=check_results,
                summary=summary
            )
            
            # Log health check results
            self._log_health_results(system_health)
            
            return system_health
    
    def _calculate_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """Calculate overall system health status."""
        critical_checks = [r for r in results if r.check_type == CheckType.CRITICAL]
        important_checks = [r for r in results if r.check_type == CheckType.IMPORTANT]
        
        # If any critical check is unhealthy, system is unhealthy
        critical_unhealthy = any(r.status == HealthStatus.UNHEALTHY for r in critical_checks)
        if critical_unhealthy:
            return HealthStatus.UNHEALTHY
        
        # If any critical check is degraded, or many important checks are unhealthy
        critical_degraded = any(r.status == HealthStatus.DEGRADED for r in critical_checks)
        important_unhealthy = sum(1 for r in important_checks if r.status == HealthStatus.UNHEALTHY)
        
        if critical_degraded or important_unhealthy > len(important_checks) * 0.3:
            return HealthStatus.DEGRADED
        
        # Otherwise healthy
        return HealthStatus.HEALTHY
    
    def _generate_summary(self, results: List[HealthCheckResult], duration: float) -> Dict[str, Any]:
        """Generate health check summary."""
        total_checks = len(results)
        healthy_count = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
        degraded_count = sum(1 for r in results if r.status == HealthStatus.DEGRADED)
        unhealthy_count = sum(1 for r in results if r.status == HealthStatus.UNHEALTHY)
        
        return {
            'total_checks': total_checks,
            'healthy': healthy_count,
            'degraded': degraded_count,
            'unhealthy': unhealthy_count,
            'success_rate': round((healthy_count / total_checks) * 100, 2) if total_checks > 0 else 0,
            'check_duration_ms': round(duration * 1000, 2),
            'timestamp': datetime.now().isoformat()
        }
    
    def _log_health_results(self, system_health: SystemHealth):
        """Log health check results."""
        # Log overall status
        log_level = LogLevel.INFO
        if system_health.status == HealthStatus.UNHEALTHY:
            log_level = LogLevel.ERROR
        elif system_health.status == HealthStatus.DEGRADED:
            log_level = LogLevel.WARNING
        
        logging_system.log_event(
            log_level,
            f"System health: {system_health.status.value}",
            EventType.SYSTEM,
            health_status=system_health.status.value,
            summary=system_health.summary
        )
        
        # Log individual check failures
        for check in system_health.checks:
            if check.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
                logging_system.log_event(
                    LogLevel.WARNING if check.status == HealthStatus.DEGRADED else LogLevel.ERROR,
                    f"Health check failed: {check.name} - {check.message}",
                    EventType.SYSTEM,
                    check_name=check.name,
                    check_status=check.status.value,
                    check_details=check.details
                )
    
    async def start_background_checks(self):
        """Start background health checks."""
        if self.background_task and not self.background_task.done():
            logger.warning("Background health checks already running")
            return
        
        self.background_task = asyncio.create_task(self._background_check_loop())
        logger.info(f"Started background health checks (interval: {self.check_interval}s)")
    
    async def stop_background_checks(self):
        """Stop background health checks."""
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped background health checks")
    
    async def _background_check_loop(self):
        """Background loop for periodic health checks."""
        while True:
            try:
                await self.run_all_checks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background health check failed: {e}")
                await asyncio.sleep(self.check_interval)
    
    def get_last_results(self) -> List[HealthCheckResult]:
        """Get the last health check results."""
        return self.last_results.copy()
    
    async def get_quick_status(self) -> Dict[str, Any]:
        """Get a quick health status without running full checks."""
        if not self.last_results:
            return {
                'status': 'unknown',
                'message': 'No health checks have been run yet'
            }
        
        # Use last results to determine status
        system_health = SystemHealth(
            status=self._calculate_overall_status(self.last_results),
            checks=self.last_results,
            summary=self._generate_summary(self.last_results, 0)
        )
        
        return {
            'status': system_health.status.value,
            'message': f'System is {system_health.status.value}',
            'last_check': self.last_results[0].timestamp.isoformat() if self.last_results else None,
            'summary': system_health.summary
        }


# Global health check system instance
health_check_system = HealthCheckSystem()