"""Worker manager for dynamic scaling, priority handling, and resource management."""

import asyncio
import os
import signal
import time
import psutil
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as redis
from celery import Celery
from celery.events.state import State
from celery.events import Events
from kombu import Connection
from kombu.exceptions import OperationalError

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class WorkerStatus(Enum):
    """Worker status enumeration."""
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class QueuePriority(Enum):
    """Queue priority levels."""
    CRITICAL = 10
    HIGH = 8
    NORMAL = 5
    LOW = 3
    BACKGROUND = 1


@dataclass
class WorkerInfo:
    """Information about a worker."""
    worker_id: str
    hostname: str
    status: WorkerStatus
    queue_names: List[str]
    concurrency: int
    cpu_usage: float
    memory_usage: float
    active_tasks: int
    processed_tasks: int
    failed_tasks: int
    last_heartbeat: datetime
    started_at: datetime


@dataclass
class QueueInfo:
    """Information about a task queue."""
    name: str
    priority: QueuePriority
    length: int
    consumers: int
    messages_ready: int
    messages_unacknowledged: int
    processing_rate: float  # tasks per minute
    avg_processing_time: float  # seconds
    last_updated: datetime


@dataclass
class ResourceLimits:
    """Resource limits configuration."""
    max_memory_mb: int = 512
    max_cpu_percent: float = 80.0
    max_tasks_per_worker: int = 100
    max_task_time_seconds: int = 3600
    max_queue_length: int = 1000


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        self.lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self.lock:
            if self.state == "open":
                if (time.time() - self.last_failure_time) > self.recovery_timeout:
                    self.state = "half-open"
                else:
                    raise Exception("Circuit breaker is open")
            
            try:
                result = func(*args, **kwargs)
                if self.state == "half-open":
                    self.state = "closed"
                    self.failure_count = 0
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                
                raise e


class DeadLetterQueue:
    """Dead letter queue for handling failed tasks."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.dlq_key = "celery:dead_letter_queue"
        self.max_retries = 3
        self.retry_delay = 300  # 5 minutes
    
    async def add_failed_task(self, task_info: Dict[str, Any]):
        """Add failed task to dead letter queue."""
        try:
            task_info['failed_at'] = datetime.now(timezone.utc).isoformat()
            task_info['retry_count'] = task_info.get('retry_count', 0) + 1
            
            await self.redis.lpush(self.dlq_key, json.dumps(task_info))
            logger.warning(f"Task {task_info.get('task_id')} moved to dead letter queue")
        except Exception as e:
            logger.error(f"Failed to add task to dead letter queue: {e}")
    
    async def get_failed_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get failed tasks from dead letter queue."""
        try:
            tasks = []
            for _ in range(min(limit, await self.redis.llen(self.dlq_key))):
                task_data = await self.redis.rpop(self.dlq_key)
                if task_data:
                    tasks.append(json.loads(task_data))
            return tasks
        except Exception as e:
            logger.error(f"Failed to get failed tasks: {e}")
            return []
    
    async def retry_failed_task(self, task_info: Dict[str, Any]) -> bool:
        """Retry a failed task if under retry limit."""
        try:
            if task_info.get('retry_count', 0) < self.max_retries:
                # Re-queue the task
                from .celery_app import celery_app
                celery_app.send_task(
                    task_info['task_name'],
                    args=task_info.get('args', []),
                    kwargs=task_info.get('kwargs', {}),
                    countdown=self.retry_delay
                )
                logger.info(f"Retrying task {task_info.get('task_id')}")
                return True
            else:
                logger.warning(f"Task {task_info.get('task_id')} exceeded max retries")
                return False
        except Exception as e:
            logger.error(f"Failed to retry task: {e}")
            return False


class ProgressTracker:
    """Track task progress and provide updates."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.progress_key_prefix = "task_progress:"
        self.progress_ttl = 3600  # 1 hour
    
    async def update_progress(self, task_id: str, progress: float, 
                            stage: str = None, metadata: Dict[str, Any] = None):
        """Update task progress information."""
        try:
            progress_data = {
                'task_id': task_id,
                'progress': min(100, max(0, progress)),
                'stage': stage,
                'metadata': metadata or {},
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            key = f"{self.progress_key_prefix}{task_id}"
            await self.redis.setex(key, self.progress_ttl, json.dumps(progress_data))
            
        except Exception as e:
            logger.error(f"Failed to update task progress: {e}")
    
    async def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task progress information."""
        try:
            key = f"{self.progress_key_prefix}{task_id}"
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get task progress: {e}")
            return None
    
    async def cleanup_completed_progress(self):
        """Clean up progress data for completed tasks."""
        try:
            pattern = f"{self.progress_key_prefix}*"
            keys = await self.redis.keys(pattern)
            
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    progress_info = json.loads(data)
                    # Remove if progress is 100% and older than 1 hour
                    if (progress_info.get('progress', 0) >= 100 and 
                        datetime.fromisoformat(progress_info['updated_at']) < 
                        datetime.now(timezone.utc) - timedelta(hours=1)):
                        await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Failed to cleanup progress data: {e}")


class WorkerManager:
    """Manages Celery workers with dynamic scaling and resource monitoring."""
    
    def __init__(self, celery_app: Celery):
        self.celery_app = celery_app
        self.redis_client = None
        self.workers: Dict[str, WorkerInfo] = {}
        self.queues: Dict[str, QueueInfo] = {}
        self.resource_limits = ResourceLimits()
        self.circuit_breaker = CircuitBreaker()
        self.dead_letter_queue = None
        self.progress_tracker = None
        
        self.is_running = False
        self.monitor_thread = None
        self.scaling_enabled = True
        self.min_workers = settings.min_workers or 1
        self.max_workers = settings.max_workers or 10
        
        self.shutdown_event = threading.Event()
        
        # Metrics
        self.metrics = {
            'workers_started': 0,
            'workers_stopped': 0,
            'tasks_processed': 0,
            'tasks_failed': 0,
            'scaling_events': 0,
            'circuit_breaker_trips': 0
        }
    
    async def initialize(self):
        """Initialize the worker manager."""
        try:
            # Initialize Redis connection
            redis_url = settings.redis_url or 'redis://localhost:6379/0'
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            await self.redis_client.ping()
            
            # Initialize components
            self.dead_letter_queue = DeadLetterQueue(self.redis_client)
            self.progress_tracker = ProgressTracker(self.redis_client)
            
            # Set up signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            logger.info("WorkerManager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize WorkerManager: {e}")
            raise
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_event.set()
        asyncio.create_task(self.shutdown())
    
    async def start(self):
        """Start the worker manager."""
        try:
            if self.is_running:
                logger.warning("WorkerManager is already running")
                return
            
            self.is_running = True
            
            # Start monitoring thread
            self.monitor_thread = threading.Thread(target=self._run_monitor, daemon=True)
            self.monitor_thread.start()
            
            # Start initial workers
            await self._ensure_minimum_workers()
            
            logger.info("WorkerManager started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start WorkerManager: {e}")
            self.is_running = False
            raise
    
    async def shutdown(self):
        """Gracefully shutdown the worker manager."""
        try:
            if not self.is_running:
                return
            
            logger.info("Shutting down WorkerManager...")
            self.is_running = False
            self.shutdown_event.set()
            
            # Stop all workers gracefully
            await self._stop_all_workers()
            
            # Wait for monitor thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=30)
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info("WorkerManager shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during WorkerManager shutdown: {e}")
    
    def _run_monitor(self):
        """Run the monitoring loop in a separate thread."""
        while self.is_running and not self.shutdown_event.is_set():
            try:
                # Run monitoring tasks
                asyncio.run(self._monitor_workers())
                asyncio.run(self._monitor_queues())
                asyncio.run(self._check_scaling_needs())
                asyncio.run(self._cleanup_stale_data())
                
                # Sleep for monitoring interval
                time.sleep(settings.worker_monitor_interval or 30)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(5)  # Brief pause before retry
    
    async def _monitor_workers(self):
        """Monitor worker status and health."""
        try:
            # Get active workers from Celery
            inspect = self.celery_app.control.inspect()
            active_workers = inspect.active()
            stats = inspect.stats()
            
            current_workers = set()
            
            if active_workers:
                for worker_name, tasks in active_workers.items():
                    current_workers.add(worker_name)
                    
                    # Get worker stats
                    worker_stats = stats.get(worker_name, {}) if stats else {}
                    
                    # Update worker info
                    worker_info = WorkerInfo(
                        worker_id=worker_name,
                        hostname=worker_stats.get('hostname', 'unknown'),
                        status=WorkerStatus.RUNNING,
                        queue_names=self._get_worker_queues(worker_name),
                        concurrency=worker_stats.get('pool', {}).get('max-concurrency', 1),
                        cpu_usage=self._get_worker_cpu_usage(worker_name),
                        memory_usage=self._get_worker_memory_usage(worker_name),
                        active_tasks=len(tasks),
                        processed_tasks=worker_stats.get('total', {}).get('tasks.worker.done', 0),
                        failed_tasks=worker_stats.get('total', {}).get('tasks.worker.failure', 0),
                        last_heartbeat=datetime.now(timezone.utc),
                        started_at=datetime.fromisoformat(
                            worker_stats.get('clock', {}).get('time_start', 
                            datetime.now(timezone.utc).isoformat())
                        ) if worker_stats.get('clock', {}).get('time_start') else datetime.now(timezone.utc)
                    )
                    
                    self.workers[worker_name] = worker_info
            
            # Remove dead workers
            dead_workers = set(self.workers.keys()) - current_workers
            for worker_id in dead_workers:
                logger.warning(f"Worker {worker_id} appears to be dead, removing from tracking")
                del self.workers[worker_id]
            
        except Exception as e:
            logger.error(f"Failed to monitor workers: {e}")
    
    async def _monitor_queues(self):
        """Monitor queue lengths and processing rates."""
        try:
            # Get queue information from Redis/RabbitMQ
            connection = Connection(settings.redis_url or 'redis://localhost:6379/0')
            
            queue_names = [
                'audio_processing', 'ticket_management', 'notifications',
                'analytics', 'ml_inference', 'maintenance'
            ]
            
            for queue_name in queue_names:
                try:
                    # Get queue length
                    queue_length = await self.redis_client.llen(f"celery.{queue_name}")
                    
                    # Calculate processing rate (simplified)
                    processing_rate = self._calculate_processing_rate(queue_name)
                    
                    queue_info = QueueInfo(
                        name=queue_name,
                        priority=self._get_queue_priority(queue_name),
                        length=queue_length,
                        consumers=self._count_queue_consumers(queue_name),
                        messages_ready=queue_length,
                        messages_unacknowledged=0,  # TODO: Get from broker
                        processing_rate=processing_rate,
                        avg_processing_time=self._get_avg_processing_time(queue_name),
                        last_updated=datetime.now(timezone.utc)
                    )
                    
                    self.queues[queue_name] = queue_info
                    
                except Exception as e:
                    logger.warning(f"Failed to get info for queue {queue_name}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to monitor queues: {e}")
    
    async def _check_scaling_needs(self):
        """Check if worker scaling is needed."""
        try:
            if not self.scaling_enabled:
                return
            
            current_worker_count = len(self.workers)
            total_queue_length = sum(queue.length for queue in self.queues.values())
            avg_cpu_usage = sum(worker.cpu_usage for worker in self.workers.values()) / max(1, current_worker_count)
            avg_memory_usage = sum(worker.memory_usage for worker in self.workers.values()) / max(1, current_worker_count)
            
            # Scale up conditions
            should_scale_up = (
                (total_queue_length > 50 and current_worker_count < self.max_workers) or
                (avg_cpu_usage > 80 and current_worker_count < self.max_workers) or
                (any(queue.length > 100 for queue in self.queues.values()) and 
                 current_worker_count < self.max_workers)
            )
            
            # Scale down conditions
            should_scale_down = (
                total_queue_length < 10 and 
                avg_cpu_usage < 30 and 
                current_worker_count > self.min_workers and
                current_worker_count > 1
            )
            
            if should_scale_up:
                await self._scale_up()
            elif should_scale_down:
                await self._scale_down()
            
        except Exception as e:
            logger.error(f"Failed to check scaling needs: {e}")
    
    async def _scale_up(self):
        """Scale up workers."""
        try:
            # Find the queue with highest load
            busiest_queue = max(self.queues.values(), key=lambda q: q.length)
            
            # Start new worker focused on busy queue
            new_worker_id = f"worker_{int(time.time())}"
            success = await self._start_worker(new_worker_id, [busiest_queue.name])
            
            if success:
                self.metrics['scaling_events'] += 1
                self.metrics['workers_started'] += 1
                logger.info(f"Scaled up: started worker {new_worker_id} for queue {busiest_queue.name}")
            
        except Exception as e:
            logger.error(f"Failed to scale up: {e}")
    
    async def _scale_down(self):
        """Scale down workers."""
        try:
            # Find worker with least load
            if not self.workers:
                return
            
            least_busy_worker = min(self.workers.values(), key=lambda w: w.active_tasks)
            
            if least_busy_worker.active_tasks == 0:
                success = await self._stop_worker(least_busy_worker.worker_id)
                
                if success:
                    self.metrics['scaling_events'] += 1
                    self.metrics['workers_stopped'] += 1
                    logger.info(f"Scaled down: stopped worker {least_busy_worker.worker_id}")
            
        except Exception as e:
            logger.error(f"Failed to scale down: {e}")
    
    async def _start_worker(self, worker_id: str, queue_names: List[str]) -> bool:
        """Start a new worker."""
        try:
            # Build worker command
            concurrency = self._calculate_optimal_concurrency()
            queue_list = ','.join(queue_names)
            
            cmd = [
                'celery', 'worker',
                '--app', 'voicehelpdeskai.workers.celery_app:celery_app',
                '--hostname', f'{worker_id}@%h',
                '--queues', queue_list,
                '--concurrency', str(concurrency),
                '--loglevel', 'info',
                '--without-heartbeat',
                '--without-mingle'
            ]
            
            # Add resource limits
            if self.resource_limits.max_memory_mb:
                cmd.extend(['--max-memory-per-child', str(self.resource_limits.max_memory_mb * 1024)])
            
            if self.resource_limits.max_tasks_per_worker:
                cmd.extend(['--max-tasks-per-child', str(self.resource_limits.max_tasks_per_worker)])
            
            # Start worker process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Give worker time to start
            await asyncio.sleep(5)
            
            # Check if worker started successfully
            if process.returncode is None:  # Still running
                logger.info(f"Started worker {worker_id} for queues: {queue_list}")
                return True
            else:
                stderr = await process.stderr.read()
                logger.error(f"Worker {worker_id} failed to start: {stderr.decode()}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to start worker {worker_id}: {e}")
            return False
    
    async def _stop_worker(self, worker_id: str) -> bool:
        """Stop a worker gracefully."""
        try:
            # Send shutdown signal to worker
            self.celery_app.control.shutdown([worker_id])
            
            # Wait for graceful shutdown
            timeout = 30
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if worker_id not in self.workers:
                    logger.info(f"Worker {worker_id} stopped gracefully")
                    return True
                await asyncio.sleep(1)
            
            # Force termination if needed
            logger.warning(f"Worker {worker_id} did not stop gracefully, forcing termination")
            # TODO: Implement force termination via process management
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop worker {worker_id}: {e}")
            return False
    
    async def _ensure_minimum_workers(self):
        """Ensure minimum number of workers are running."""
        try:
            current_count = len(self.workers)
            
            while current_count < self.min_workers:
                worker_id = f"worker_{int(time.time())}_{current_count}"
                success = await self._start_worker(worker_id, ['audio_processing', 'ticket_management'])
                
                if success:
                    current_count += 1
                    await asyncio.sleep(5)  # Stagger worker starts
                else:
                    logger.error("Failed to start minimum worker, retrying in 10 seconds")
                    await asyncio.sleep(10)
                    break
            
        except Exception as e:
            logger.error(f"Failed to ensure minimum workers: {e}")
    
    async def _stop_all_workers(self):
        """Stop all managed workers."""
        try:
            worker_ids = list(self.workers.keys())
            
            for worker_id in worker_ids:
                await self._stop_worker(worker_id)
            
            # Wait for all workers to stop
            timeout = 60
            start_time = time.time()
            
            while self.workers and (time.time() - start_time) < timeout:
                await asyncio.sleep(1)
            
            if self.workers:
                logger.warning(f"Some workers did not stop gracefully: {list(self.workers.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to stop all workers: {e}")
    
    async def _cleanup_stale_data(self):
        """Clean up stale monitoring data."""
        try:
            # Clean up old progress data
            if self.progress_tracker:
                await self.progress_tracker.cleanup_completed_progress()
            
            # Clean up old worker entries
            current_time = datetime.now(timezone.utc)
            stale_workers = []
            
            for worker_id, worker_info in self.workers.items():
                if (current_time - worker_info.last_heartbeat).total_seconds() > 300:  # 5 minutes
                    stale_workers.append(worker_id)
            
            for worker_id in stale_workers:
                logger.warning(f"Removing stale worker: {worker_id}")
                del self.workers[worker_id]
            
        except Exception as e:
            logger.error(f"Failed to cleanup stale data: {e}")
    
    # Helper methods
    
    def _get_worker_queues(self, worker_name: str) -> List[str]:
        """Get queue names for a worker."""
        # TODO: Implement actual queue detection
        return ['default']
    
    def _get_worker_cpu_usage(self, worker_name: str) -> float:
        """Get CPU usage for a worker."""
        try:
            # TODO: Implement actual CPU monitoring
            return psutil.cpu_percent(interval=None)
        except:
            return 0.0
    
    def _get_worker_memory_usage(self, worker_name: str) -> float:
        """Get memory usage for a worker."""
        try:
            # TODO: Implement actual memory monitoring  
            return psutil.virtual_memory().percent
        except:
            return 0.0
    
    def _get_queue_priority(self, queue_name: str) -> QueuePriority:
        """Get priority for a queue."""
        priority_map = {
            'audio_processing': QueuePriority.CRITICAL,
            'notifications': QueuePriority.HIGH,
            'ticket_management': QueuePriority.HIGH,
            'ml_inference': QueuePriority.NORMAL,
            'analytics': QueuePriority.LOW,
            'maintenance': QueuePriority.BACKGROUND
        }
        return priority_map.get(queue_name, QueuePriority.NORMAL)
    
    def _calculate_processing_rate(self, queue_name: str) -> float:
        """Calculate processing rate for a queue."""
        # TODO: Implement actual rate calculation
        return 10.0  # tasks per minute
    
    def _count_queue_consumers(self, queue_name: str) -> int:
        """Count consumers for a queue."""
        # TODO: Implement actual consumer counting
        return len([w for w in self.workers.values() if queue_name in w.queue_names])
    
    def _get_avg_processing_time(self, queue_name: str) -> float:
        """Get average processing time for a queue."""
        # TODO: Implement actual processing time calculation
        return 30.0  # seconds
    
    def _calculate_optimal_concurrency(self) -> int:
        """Calculate optimal concurrency based on system resources."""
        try:
            cpu_count = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024**3)
            
            # Conservative calculation
            concurrency = min(cpu_count * 2, int(memory_gb / 0.5), 20)
            return max(1, concurrency)
        except:
            return 4  # Default fallback
    
    # Public API methods
    
    async def get_worker_status(self) -> Dict[str, Any]:
        """Get comprehensive worker status."""
        return {
            'total_workers': len(self.workers),
            'running_workers': len([w for w in self.workers.values() if w.status == WorkerStatus.RUNNING]),
            'workers': [
                {
                    'id': worker.worker_id,
                    'hostname': worker.hostname,
                    'status': worker.status.value,
                    'queues': worker.queue_names,
                    'concurrency': worker.concurrency,
                    'cpu_usage': worker.cpu_usage,
                    'memory_usage': worker.memory_usage,
                    'active_tasks': worker.active_tasks,
                    'processed_tasks': worker.processed_tasks,
                    'failed_tasks': worker.failed_tasks,
                    'started_at': worker.started_at.isoformat()
                }
                for worker in self.workers.values()
            ],
            'queues': [
                {
                    'name': queue.name,
                    'priority': queue.priority.value,
                    'length': queue.length,
                    'consumers': queue.consumers,
                    'processing_rate': queue.processing_rate,
                    'avg_processing_time': queue.avg_processing_time
                }
                for queue in self.queues.values()
            ],
            'metrics': self.metrics,
            'resource_limits': {
                'max_memory_mb': self.resource_limits.max_memory_mb,
                'max_cpu_percent': self.resource_limits.max_cpu_percent,
                'max_tasks_per_worker': self.resource_limits.max_tasks_per_worker,
                'max_task_time_seconds': self.resource_limits.max_task_time_seconds
            },
            'scaling': {
                'enabled': self.scaling_enabled,
                'min_workers': self.min_workers,
                'max_workers': self.max_workers
            }
        }
    
    async def pause_worker(self, worker_id: str) -> bool:
        """Pause a specific worker."""
        try:
            self.celery_app.control.cancel_consumer([worker_id])
            if worker_id in self.workers:
                self.workers[worker_id].status = WorkerStatus.PAUSED
            logger.info(f"Paused worker: {worker_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause worker {worker_id}: {e}")
            return False
    
    async def resume_worker(self, worker_id: str) -> bool:
        """Resume a paused worker."""
        try:
            self.celery_app.control.add_consumer([worker_id])
            if worker_id in self.workers:
                self.workers[worker_id].status = WorkerStatus.RUNNING
            logger.info(f"Resumed worker: {worker_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume worker {worker_id}: {e}")
            return False
    
    async def set_worker_concurrency(self, worker_id: str, concurrency: int) -> bool:
        """Set worker concurrency level."""
        try:
            self.celery_app.control.pool_grow([worker_id], n=concurrency)
            if worker_id in self.workers:
                self.workers[worker_id].concurrency = concurrency
            logger.info(f"Set worker {worker_id} concurrency to {concurrency}")
            return True
        except Exception as e:
            logger.error(f"Failed to set worker concurrency: {e}")
            return False
    
    def enable_scaling(self):
        """Enable automatic worker scaling."""
        self.scaling_enabled = True
        logger.info("Worker auto-scaling enabled")
    
    def disable_scaling(self):
        """Disable automatic worker scaling."""
        self.scaling_enabled = False
        logger.info("Worker auto-scaling disabled")
    
    async def purge_queue(self, queue_name: str) -> int:
        """Purge all tasks from a queue."""
        try:
            purged = self.celery_app.control.purge(queue=queue_name)
            logger.warning(f"Purged {purged} tasks from queue {queue_name}")
            return purged
        except Exception as e:
            logger.error(f"Failed to purge queue {queue_name}: {e}")
            return 0


# JSON import for dead letter queue
import json