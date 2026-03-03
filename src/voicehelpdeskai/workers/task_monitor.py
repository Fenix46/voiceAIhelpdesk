"""Task monitoring system for tracking execution metrics, failures, and performance."""

import asyncio
import json
import statistics
import time
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as redis
from celery import Celery
from celery.events.state import State
from celery.events import Events

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "PENDING"
    RECEIVED = "RECEIVED"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskExecutionMetrics:
    """Metrics for a task execution."""
    task_id: str
    task_name: str
    worker_id: str
    queue_name: str
    status: TaskStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    execution_time: Optional[float]  # seconds
    args: List[Any]
    kwargs: Dict[str, Any]
    result: Optional[Any]
    exception: Optional[str]
    traceback: Optional[str]
    retry_count: int
    memory_usage: Optional[float]  # MB
    cpu_time: Optional[float]  # seconds
    timestamp: datetime


@dataclass
class TaskStatistics:
    """Statistics for a task type."""
    task_name: str
    total_count: int
    success_count: int
    failure_count: int
    retry_count: int
    avg_execution_time: float
    min_execution_time: float
    max_execution_time: float
    p95_execution_time: float
    p99_execution_time: float
    success_rate: float
    failure_rate: float
    avg_memory_usage: float
    total_cpu_time: float
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    recent_errors: List[str]


@dataclass
class WorkerStatistics:
    """Statistics for a worker."""
    worker_id: str
    hostname: str
    total_tasks: int
    active_tasks: int
    processed_tasks: int
    failed_tasks: int
    avg_execution_time: float
    cpu_usage: float
    memory_usage: float
    load_average: float
    uptime: float
    last_heartbeat: datetime
    task_types: Dict[str, int]


@dataclass
class SystemAlert:
    """System alert for monitoring issues."""
    alert_id: str
    alert_type: str
    severity: AlertSeverity
    title: str
    message: str
    task_name: Optional[str]
    worker_id: Optional[str]
    queue_name: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    acknowledged: bool
    resolved: bool
    resolved_at: Optional[datetime]


class TaskMonitor:
    """Comprehensive task monitoring and analytics system."""
    
    def __init__(self, celery_app: Celery):
        self.celery_app = celery_app
        self.redis_client = None
        self.state = State()
        self.event_monitor = None
        
        # Metrics storage
        self.task_metrics: Dict[str, TaskExecutionMetrics] = {}
        self.task_statistics: Dict[str, TaskStatistics] = {}
        self.worker_statistics: Dict[str, WorkerStatistics] = {}
        self.system_alerts: Dict[str, SystemAlert] = {}
        
        # Ring buffers for recent data
        self.recent_tasks = deque(maxlen=1000)
        self.recent_failures = deque(maxlen=100)
        self.recent_performance = deque(maxlen=500)
        
        # Monitoring configuration
        self.metrics_retention_days = 7
        self.alert_thresholds = {
            'high_failure_rate': 20.0,  # percentage
            'slow_execution_time': 300.0,  # seconds
            'high_memory_usage': 500.0,  # MB
            'queue_backlog': 100,  # tasks
            'worker_unresponsive': 300.0  # seconds
        }
        
        self.is_running = False
        self.monitoring_tasks = []
    
    async def initialize(self):
        """Initialize the task monitor."""
        try:
            # Initialize Redis connection
            redis_url = settings.redis_url or 'redis://localhost:6379/0'
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            await self.redis_client.ping()
            
            # Load historical data
            await self._load_historical_data()
            
            logger.info("TaskMonitor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize TaskMonitor: {e}")
            raise
    
    async def start(self):
        """Start the task monitoring system."""
        try:
            if self.is_running:
                logger.warning("TaskMonitor is already running")
                return
            
            self.is_running = True
            
            # Start monitoring tasks
            self.monitoring_tasks = [
                asyncio.create_task(self._monitor_events()),
                asyncio.create_task(self._collect_worker_stats()),
                asyncio.create_task(self._analyze_performance()),
                asyncio.create_task(self._check_alerts()),
                asyncio.create_task(self._cleanup_old_data())
            ]
            
            logger.info("TaskMonitor started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start TaskMonitor: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop the task monitoring system."""
        try:
            self.is_running = False
            
            # Cancel monitoring tasks
            for task in self.monitoring_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            if self.monitoring_tasks:
                await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
            
            # Save current state
            await self._save_historical_data()
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info("TaskMonitor stopped")
            
        except Exception as e:
            logger.error(f"Error stopping TaskMonitor: {e}")
    
    async def _monitor_events(self):
        """Monitor Celery events in real-time."""
        while self.is_running:
            try:
                # Get Celery events
                with self.celery_app.events.State() as state:
                    def on_event(event):
                        asyncio.create_task(self._process_event(event))
                    
                    # Start event capture
                    with self.celery_app.events.default_dispatcher() as dispatcher:
                        dispatcher.capture(callback=on_event)
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error monitoring events: {e}")
                await asyncio.sleep(5)
    
    async def _process_event(self, event: Dict[str, Any]):
        """Process a Celery event."""
        try:
            event_type = event.get('type')
            task_id = event.get('uuid')
            
            if not task_id:
                return
            
            # Get or create task metrics
            if task_id not in self.task_metrics:
                self.task_metrics[task_id] = TaskExecutionMetrics(
                    task_id=task_id,
                    task_name=event.get('task', 'unknown'),
                    worker_id=event.get('hostname', 'unknown'),
                    queue_name=event.get('queue', 'default'),
                    status=TaskStatus.PENDING,
                    start_time=None,
                    end_time=None,
                    execution_time=None,
                    args=event.get('args', []),
                    kwargs=event.get('kwargs', {}),
                    result=None,
                    exception=None,
                    traceback=None,
                    retry_count=event.get('retries', 0),
                    memory_usage=None,
                    cpu_time=None,
                    timestamp=datetime.now(timezone.utc)
                )
            
            task_metrics = self.task_metrics[task_id]
            
            # Update metrics based on event type
            if event_type == 'task-received':
                task_metrics.status = TaskStatus.RECEIVED
                task_metrics.timestamp = datetime.fromtimestamp(event['timestamp'], timezone.utc)
            
            elif event_type == 'task-started':
                task_metrics.status = TaskStatus.STARTED
                task_metrics.start_time = datetime.fromtimestamp(event['timestamp'], timezone.utc)
            
            elif event_type == 'task-succeeded':
                task_metrics.status = TaskStatus.SUCCESS
                task_metrics.end_time = datetime.fromtimestamp(event['timestamp'], timezone.utc)
                task_metrics.result = event.get('result')
                
                if task_metrics.start_time:
                    task_metrics.execution_time = (task_metrics.end_time - task_metrics.start_time).total_seconds()
                
                # Add to recent successful tasks
                self.recent_tasks.append(task_metrics)
            
            elif event_type == 'task-failed':
                task_metrics.status = TaskStatus.FAILURE
                task_metrics.end_time = datetime.fromtimestamp(event['timestamp'], timezone.utc)
                task_metrics.exception = event.get('exception')
                task_metrics.traceback = event.get('traceback')
                
                if task_metrics.start_time:
                    task_metrics.execution_time = (task_metrics.end_time - task_metrics.start_time).total_seconds()
                
                # Add to recent failures
                self.recent_failures.append(task_metrics)
                
                # Create alert for high priority failures
                if task_metrics.task_name in ['process_audio_chunk_task', 'create_ticket_task']:
                    await self._create_alert(
                        alert_type='task_failure',
                        severity=AlertSeverity.HIGH,
                        title=f'Critical task failed: {task_metrics.task_name}',
                        message=f'Task {task_id} failed: {task_metrics.exception}',
                        task_name=task_metrics.task_name,
                        worker_id=task_metrics.worker_id
                    )
            
            elif event_type == 'task-retried':
                task_metrics.status = TaskStatus.RETRY
                task_metrics.retry_count = event.get('retries', task_metrics.retry_count + 1)
            
            elif event_type == 'task-revoked':
                task_metrics.status = TaskStatus.REVOKED
                task_metrics.end_time = datetime.fromtimestamp(event['timestamp'], timezone.utc)
            
            # Update task statistics
            await self._update_task_statistics(task_metrics)
            
            # Store metrics
            await self._store_task_metrics(task_metrics)
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
    
    async def _collect_worker_stats(self):
        """Collect worker statistics periodically."""
        while self.is_running:
            try:
                # Get worker information from Celery
                inspect = self.celery_app.control.inspect()
                active_tasks = inspect.active() or {}
                registered_tasks = inspect.registered() or {}
                stats = inspect.stats() or {}
                
                for worker_id, tasks in active_tasks.items():
                    worker_stats = stats.get(worker_id, {})
                    
                    # Calculate statistics
                    total_tasks = len(tasks)
                    task_types = defaultdict(int)
                    
                    for task in tasks:
                        task_name = task.get('name', 'unknown')
                        task_types[task_name] += 1
                    
                    # Create worker statistics
                    worker_statistics = WorkerStatistics(
                        worker_id=worker_id,
                        hostname=worker_stats.get('hostname', 'unknown'),
                        total_tasks=worker_stats.get('total', {}).get('tasks.worker.received', 0),
                        active_tasks=total_tasks,
                        processed_tasks=worker_stats.get('total', {}).get('tasks.worker.done', 0),
                        failed_tasks=worker_stats.get('total', {}).get('tasks.worker.failure', 0),
                        avg_execution_time=0.0,  # TODO: Calculate from recent tasks
                        cpu_usage=0.0,  # TODO: Get from system metrics
                        memory_usage=0.0,  # TODO: Get from system metrics
                        load_average=0.0,  # TODO: Get from system metrics
                        uptime=0.0,  # TODO: Calculate uptime
                        last_heartbeat=datetime.now(timezone.utc),
                        task_types=dict(task_types)
                    )
                    
                    self.worker_statistics[worker_id] = worker_statistics
                    
                    # Store worker statistics
                    await self._store_worker_statistics(worker_statistics)
                
                await asyncio.sleep(60)  # Collect every minute
                
            except Exception as e:
                logger.error(f"Error collecting worker stats: {e}")
                await asyncio.sleep(60)
    
    async def _analyze_performance(self):
        """Analyze task performance and identify issues."""
        while self.is_running:
            try:
                # Analyze recent task performance
                if len(self.recent_tasks) > 10:
                    recent_execution_times = [
                        t.execution_time for t in self.recent_tasks 
                        if t.execution_time is not None
                    ]
                    
                    if recent_execution_times:
                        avg_time = statistics.mean(recent_execution_times)
                        p95_time = statistics.quantiles(recent_execution_times, n=20)[18]  # 95th percentile
                        
                        # Check for performance degradation
                        if avg_time > self.alert_thresholds['slow_execution_time']:
                            await self._create_alert(
                                alert_type='performance_degradation',
                                severity=AlertSeverity.MEDIUM,
                                title='Task performance degradation detected',
                                message=f'Average execution time is {avg_time:.2f}s',
                                metadata={'avg_time': avg_time, 'p95_time': p95_time}
                            )
                        
                        # Store performance metrics
                        self.recent_performance.append({
                            'timestamp': datetime.now(timezone.utc),
                            'avg_execution_time': avg_time,
                            'p95_execution_time': p95_time,
                            'active_tasks': sum(ws.active_tasks for ws in self.worker_statistics.values())
                        })
                
                await asyncio.sleep(300)  # Analyze every 5 minutes
                
            except Exception as e:
                logger.error(f"Error analyzing performance: {e}")
                await asyncio.sleep(300)
    
    async def _check_alerts(self):
        """Check for alert conditions."""
        while self.is_running:
            try:
                # Check failure rates
                await self._check_failure_rates()
                
                # Check queue backlogs
                await self._check_queue_backlogs()
                
                # Check worker responsiveness
                await self._check_worker_responsiveness()
                
                # Check resource usage
                await self._check_resource_usage()
                
                await asyncio.sleep(120)  # Check every 2 minutes
                
            except Exception as e:
                logger.error(f"Error checking alerts: {e}")
                await asyncio.sleep(120)
    
    async def _check_failure_rates(self):
        """Check task failure rates."""
        try:
            current_time = datetime.now(timezone.utc)
            one_hour_ago = current_time - timedelta(hours=1)
            
            for task_name, stats in self.task_statistics.items():
                if stats.total_count > 10:  # Only check if we have enough samples
                    if stats.failure_rate > self.alert_thresholds['high_failure_rate']:
                        await self._create_alert(
                            alert_type='high_failure_rate',
                            severity=AlertSeverity.HIGH,
                            title=f'High failure rate for {task_name}',
                            message=f'Failure rate: {stats.failure_rate:.1f}%',
                            task_name=task_name,
                            metadata={'failure_rate': stats.failure_rate, 'total_count': stats.total_count}
                        )
        
        except Exception as e:
            logger.error(f"Error checking failure rates: {e}")
    
    async def _check_queue_backlogs(self):
        """Check for queue backlogs."""
        try:
            if self.redis_client:
                queue_names = [
                    'audio_processing', 'ticket_management', 'notifications',
                    'analytics', 'ml_inference', 'maintenance'
                ]
                
                for queue_name in queue_names:
                    try:
                        queue_length = await self.redis_client.llen(f"celery.{queue_name}")
                        
                        if queue_length > self.alert_thresholds['queue_backlog']:
                            await self._create_alert(
                                alert_type='queue_backlog',
                                severity=AlertSeverity.MEDIUM,
                                title=f'Queue backlog detected: {queue_name}',
                                message=f'Queue length: {queue_length} tasks',
                                queue_name=queue_name,
                                metadata={'queue_length': queue_length}
                            )
                    
                    except Exception as e:
                        logger.warning(f"Failed to check queue {queue_name}: {e}")
        
        except Exception as e:
            logger.error(f"Error checking queue backlogs: {e}")
    
    async def _check_worker_responsiveness(self):
        """Check worker responsiveness."""
        try:
            current_time = datetime.now(timezone.utc)
            unresponsive_threshold = timedelta(seconds=self.alert_thresholds['worker_unresponsive'])
            
            for worker_id, stats in self.worker_statistics.items():
                if (current_time - stats.last_heartbeat) > unresponsive_threshold:
                    await self._create_alert(
                        alert_type='worker_unresponsive',
                        severity=AlertSeverity.HIGH,
                        title=f'Worker unresponsive: {worker_id}',
                        message=f'Last heartbeat: {stats.last_heartbeat.isoformat()}',
                        worker_id=worker_id,
                        metadata={'last_heartbeat': stats.last_heartbeat.isoformat()}
                    )
        
        except Exception as e:
            logger.error(f"Error checking worker responsiveness: {e}")
    
    async def _check_resource_usage(self):
        """Check resource usage."""
        try:
            for worker_id, stats in self.worker_statistics.items():
                if stats.memory_usage > self.alert_thresholds['high_memory_usage']:
                    await self._create_alert(
                        alert_type='high_memory_usage',
                        severity=AlertSeverity.MEDIUM,
                        title=f'High memory usage: {worker_id}',
                        message=f'Memory usage: {stats.memory_usage:.1f}MB',
                        worker_id=worker_id,
                        metadata={'memory_usage': stats.memory_usage}
                    )
        
        except Exception as e:
            logger.error(f"Error checking resource usage: {e}")
    
    async def _cleanup_old_data(self):
        """Clean up old monitoring data."""
        while self.is_running:
            try:
                current_time = datetime.now(timezone.utc)
                cutoff_time = current_time - timedelta(days=self.metrics_retention_days)
                
                # Clean up old task metrics
                old_task_ids = []
                for task_id, metrics in self.task_metrics.items():
                    if metrics.timestamp < cutoff_time:
                        old_task_ids.append(task_id)
                
                for task_id in old_task_ids:
                    del self.task_metrics[task_id]
                
                # Clean up old alerts
                old_alert_ids = []
                for alert_id, alert in self.system_alerts.items():
                    if alert.resolved and (current_time - alert.created_at).days > 30:
                        old_alert_ids.append(alert_id)
                
                for alert_id in old_alert_ids:
                    del self.system_alerts[alert_id]
                
                # Save cleaned data
                await self._save_historical_data()
                
                logger.info(f"Cleaned up {len(old_task_ids)} old task metrics and {len(old_alert_ids)} old alerts")
                
                await asyncio.sleep(3600)  # Clean up every hour
                
            except Exception as e:
                logger.error(f"Error cleaning up old data: {e}")
                await asyncio.sleep(3600)
    
    async def _create_alert(self, alert_type: str, severity: AlertSeverity,
                          title: str, message: str, task_name: Optional[str] = None,
                          worker_id: Optional[str] = None, queue_name: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new system alert."""
        try:
            alert_id = f"alert_{int(time.time())}_{len(self.system_alerts)}"
            
            # Check if similar alert already exists (prevent spam)
            existing_alert = None
            for existing_id, existing in self.system_alerts.items():
                if (existing.alert_type == alert_type and
                    existing.task_name == task_name and
                    existing.worker_id == worker_id and
                    existing.queue_name == queue_name and
                    not existing.resolved):
                    existing_alert = existing
                    break
            
            if existing_alert:
                # Update existing alert
                existing_alert.message = message
                existing_alert.metadata.update(metadata or {})
                return existing_alert.alert_id
            
            alert = SystemAlert(
                alert_id=alert_id,
                alert_type=alert_type,
                severity=severity,
                title=title,
                message=message,
                task_name=task_name,
                worker_id=worker_id,
                queue_name=queue_name,
                metadata=metadata or {},
                created_at=datetime.now(timezone.utc),
                acknowledged=False,
                resolved=False,
                resolved_at=None
            )
            
            self.system_alerts[alert_id] = alert
            
            # Store alert
            await self._store_alert(alert)
            
            # Send notification for high/critical alerts
            if severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
                await self._send_alert_notification(alert)
            
            logger.warning(f"Created alert: {title} ({alert_id})")
            return alert_id
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return ""
    
    async def _send_alert_notification(self, alert: SystemAlert):
        """Send alert notification."""
        try:
            # Send via webhook or email
            from ..workers.tasks import send_email_notification_task
            
            if settings.alert_webhook_url:
                # Send webhook notification
                from ..workers.tasks import send_webhook_notification_task
                send_webhook_notification_task.delay(
                    webhook_url=settings.alert_webhook_url,
                    payload=asdict(alert)
                )
            
            if settings.admin_email:
                # Send email notification
                send_email_notification_task.delay(
                    recipient=settings.admin_email,
                    subject=f"[{alert.severity.value.upper()}] {alert.title}",
                    body=f"{alert.message}\n\nAlert ID: {alert.alert_id}\nCreated: {alert.created_at}"
                )
        
        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")
    
    async def _update_task_statistics(self, task_metrics: TaskExecutionMetrics):
        """Update task statistics."""
        try:
            task_name = task_metrics.task_name
            
            if task_name not in self.task_statistics:
                self.task_statistics[task_name] = TaskStatistics(
                    task_name=task_name,
                    total_count=0,
                    success_count=0,
                    failure_count=0,
                    retry_count=0,
                    avg_execution_time=0.0,
                    min_execution_time=float('inf'),
                    max_execution_time=0.0,
                    p95_execution_time=0.0,
                    p99_execution_time=0.0,
                    success_rate=0.0,
                    failure_rate=0.0,
                    avg_memory_usage=0.0,
                    total_cpu_time=0.0,
                    last_success=None,
                    last_failure=None,
                    recent_errors=[]
                )
            
            stats = self.task_statistics[task_name]
            
            # Update counts
            if task_metrics.status == TaskStatus.SUCCESS:
                stats.success_count += 1
                stats.last_success = task_metrics.end_time
            elif task_metrics.status == TaskStatus.FAILURE:
                stats.failure_count += 1
                stats.last_failure = task_metrics.end_time
                
                # Add to recent errors
                if task_metrics.exception:
                    stats.recent_errors.append(task_metrics.exception)
                    if len(stats.recent_errors) > 10:
                        stats.recent_errors.pop(0)
            elif task_metrics.status == TaskStatus.RETRY:
                stats.retry_count += 1
            
            # Update execution time stats
            if task_metrics.execution_time is not None:
                stats.min_execution_time = min(stats.min_execution_time, task_metrics.execution_time)
                stats.max_execution_time = max(stats.max_execution_time, task_metrics.execution_time)
                
                # Update average (simple moving average)
                if stats.total_count > 0:
                    stats.avg_execution_time = (
                        (stats.avg_execution_time * stats.total_count + task_metrics.execution_time) /
                        (stats.total_count + 1)
                    )
                else:
                    stats.avg_execution_time = task_metrics.execution_time
            
            stats.total_count += 1
            
            # Calculate rates
            if stats.total_count > 0:
                stats.success_rate = (stats.success_count / stats.total_count) * 100
                stats.failure_rate = (stats.failure_count / stats.total_count) * 100
            
            # Update memory usage
            if task_metrics.memory_usage is not None:
                if stats.total_count > 1:
                    stats.avg_memory_usage = (
                        (stats.avg_memory_usage * (stats.total_count - 1) + task_metrics.memory_usage) /
                        stats.total_count
                    )
                else:
                    stats.avg_memory_usage = task_metrics.memory_usage
            
            # Calculate percentiles (simplified)
            # TODO: Implement proper percentile calculation with historical data
            stats.p95_execution_time = stats.max_execution_time * 0.95
            stats.p99_execution_time = stats.max_execution_time * 0.99
        
        except Exception as e:
            logger.error(f"Error updating task statistics: {e}")
    
    # Storage methods
    
    async def _store_task_metrics(self, metrics: TaskExecutionMetrics):
        """Store task metrics in Redis."""
        try:
            if self.redis_client:
                key = f"task_metrics:{metrics.task_id}"
                data = {
                    'task_id': metrics.task_id,
                    'task_name': metrics.task_name,
                    'worker_id': metrics.worker_id,
                    'queue_name': metrics.queue_name,
                    'status': metrics.status.value,
                    'start_time': metrics.start_time.isoformat() if metrics.start_time else None,
                    'end_time': metrics.end_time.isoformat() if metrics.end_time else None,
                    'execution_time': metrics.execution_time,
                    'result': str(metrics.result) if metrics.result else None,
                    'exception': metrics.exception,
                    'retry_count': metrics.retry_count,
                    'memory_usage': metrics.memory_usage,
                    'timestamp': metrics.timestamp.isoformat()
                }
                
                await self.redis_client.setex(
                    key,
                    86400 * self.metrics_retention_days,  # TTL based on retention
                    json.dumps(data)
                )
        
        except Exception as e:
            logger.error(f"Error storing task metrics: {e}")
    
    async def _store_worker_statistics(self, stats: WorkerStatistics):
        """Store worker statistics in Redis."""
        try:
            if self.redis_client:
                key = f"worker_stats:{stats.worker_id}"
                data = asdict(stats)
                data['last_heartbeat'] = stats.last_heartbeat.isoformat()
                
                await self.redis_client.setex(key, 300, json.dumps(data))  # 5 minute TTL
        
        except Exception as e:
            logger.error(f"Error storing worker statistics: {e}")
    
    async def _store_alert(self, alert: SystemAlert):
        """Store alert in Redis."""
        try:
            if self.redis_client:
                key = f"alert:{alert.alert_id}"
                data = asdict(alert)
                data['created_at'] = alert.created_at.isoformat()
                data['resolved_at'] = alert.resolved_at.isoformat() if alert.resolved_at else None
                data['severity'] = alert.severity.value
                
                await self.redis_client.setex(
                    key,
                    86400 * 30,  # 30 days TTL
                    json.dumps(data)
                )
        
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
    
    async def _load_historical_data(self):
        """Load historical monitoring data."""
        try:
            if not self.redis_client:
                return
            
            # Load task statistics
            stats_pattern = "task_stats:*"
            stats_keys = await self.redis_client.keys(stats_pattern)
            
            for key in stats_keys:
                try:
                    data = await self.redis_client.get(key)
                    if data:
                        stats_data = json.loads(data)
                        task_name = key.split(':')[1]
                        # Reconstruct TaskStatistics object
                        # TODO: Implement proper deserialization
                except Exception as e:
                    logger.warning(f"Failed to load task statistics from {key}: {e}")
            
            # Load alerts
            alert_pattern = "alert:*"
            alert_keys = await self.redis_client.keys(alert_pattern)
            
            for key in alert_keys:
                try:
                    data = await self.redis_client.get(key)
                    if data:
                        alert_data = json.loads(data)
                        # Reconstruct SystemAlert object
                        # TODO: Implement proper deserialization
                except Exception as e:
                    logger.warning(f"Failed to load alert from {key}: {e}")
        
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
    
    async def _save_historical_data(self):
        """Save current monitoring data."""
        try:
            if not self.redis_client:
                return
            
            # Save task statistics
            for task_name, stats in self.task_statistics.items():
                key = f"task_stats:{task_name}"
                data = asdict(stats)
                data['last_success'] = stats.last_success.isoformat() if stats.last_success else None
                data['last_failure'] = stats.last_failure.isoformat() if stats.last_failure else None
                
                await self.redis_client.setex(
                    key,
                    86400 * self.metrics_retention_days,
                    json.dumps(data)
                )
        
        except Exception as e:
            logger.error(f"Error saving historical data: {e}")
    
    # Public API methods
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive monitoring dashboard data."""
        try:
            current_time = datetime.now(timezone.utc)
            
            # Task statistics summary
            total_tasks = sum(stats.total_count for stats in self.task_statistics.values())
            total_success = sum(stats.success_count for stats in self.task_statistics.values())
            total_failures = sum(stats.failure_count for stats in self.task_statistics.values())
            
            overall_success_rate = (total_success / max(1, total_tasks)) * 100
            overall_failure_rate = (total_failures / max(1, total_tasks)) * 100
            
            # Worker statistics summary
            active_workers = len(self.worker_statistics)
            total_active_tasks = sum(stats.active_tasks for stats in self.worker_statistics.values())
            
            # Recent performance
            recent_perf = list(self.recent_performance)[-10:] if self.recent_performance else []
            
            # Active alerts
            active_alerts = [
                {
                    'alert_id': alert.alert_id,
                    'alert_type': alert.alert_type,
                    'severity': alert.severity.value,
                    'title': alert.title,
                    'message': alert.message,
                    'created_at': alert.created_at.isoformat(),
                    'acknowledged': alert.acknowledged
                }
                for alert in self.system_alerts.values()
                if not alert.resolved
            ]
            
            # Top failing tasks
            top_failing_tasks = sorted(
                [
                    {
                        'task_name': stats.task_name,
                        'failure_rate': stats.failure_rate,
                        'total_count': stats.total_count,
                        'recent_errors': stats.recent_errors[-3:]  # Last 3 errors
                    }
                    for stats in self.task_statistics.values()
                    if stats.failure_rate > 5.0  # Only tasks with > 5% failure rate
                ],
                key=lambda x: x['failure_rate'],
                reverse=True
            )[:10]
            
            # Queue statistics
            queue_stats = {}
            if self.redis_client:
                queue_names = [
                    'audio_processing', 'ticket_management', 'notifications',
                    'analytics', 'ml_inference', 'maintenance'
                ]
                
                for queue_name in queue_names:
                    try:
                        queue_length = await self.redis_client.llen(f"celery.{queue_name}")
                        queue_stats[queue_name] = queue_length
                    except:
                        queue_stats[queue_name] = 0
            
            return {
                'summary': {
                    'total_tasks': total_tasks,
                    'success_rate': round(overall_success_rate, 2),
                    'failure_rate': round(overall_failure_rate, 2),
                    'active_workers': active_workers,
                    'active_tasks': total_active_tasks,
                    'active_alerts': len(active_alerts),
                    'last_updated': current_time.isoformat()
                },
                'task_statistics': [
                    {
                        'task_name': stats.task_name,
                        'total_count': stats.total_count,
                        'success_count': stats.success_count,
                        'failure_count': stats.failure_count,
                        'success_rate': round(stats.success_rate, 2),
                        'failure_rate': round(stats.failure_rate, 2),
                        'avg_execution_time': round(stats.avg_execution_time, 3),
                        'p95_execution_time': round(stats.p95_execution_time, 3)
                    }
                    for stats in self.task_statistics.values()
                ],
                'worker_statistics': [
                    {
                        'worker_id': stats.worker_id,
                        'hostname': stats.hostname,
                        'active_tasks': stats.active_tasks,
                        'processed_tasks': stats.processed_tasks,
                        'failed_tasks': stats.failed_tasks,
                        'avg_execution_time': round(stats.avg_execution_time, 3),
                        'memory_usage': round(stats.memory_usage, 1),
                        'last_heartbeat': stats.last_heartbeat.isoformat()
                    }
                    for stats in self.worker_statistics.values()
                ],
                'recent_performance': [
                    {
                        'timestamp': perf['timestamp'].isoformat(),
                        'avg_execution_time': round(perf['avg_execution_time'], 3),
                        'p95_execution_time': round(perf['p95_execution_time'], 3),
                        'active_tasks': perf['active_tasks']
                    }
                    for perf in recent_perf
                ],
                'active_alerts': active_alerts,
                'top_failing_tasks': top_failing_tasks,
                'queue_statistics': queue_stats
            }
        
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {}
    
    async def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific task."""
        try:
            if task_id in self.task_metrics:
                metrics = self.task_metrics[task_id]
                return {
                    'task_id': metrics.task_id,
                    'task_name': metrics.task_name,
                    'worker_id': metrics.worker_id,
                    'queue_name': metrics.queue_name,
                    'status': metrics.status.value,
                    'start_time': metrics.start_time.isoformat() if metrics.start_time else None,
                    'end_time': metrics.end_time.isoformat() if metrics.end_time else None,
                    'execution_time': metrics.execution_time,
                    'args': metrics.args,
                    'kwargs': metrics.kwargs,
                    'result': str(metrics.result) if metrics.result else None,
                    'exception': metrics.exception,
                    'traceback': metrics.traceback,
                    'retry_count': metrics.retry_count,
                    'memory_usage': metrics.memory_usage,
                    'timestamp': metrics.timestamp.isoformat()
                }
            
            # Try to load from Redis
            if self.redis_client:
                key = f"task_metrics:{task_id}"
                data = await self.redis_client.get(key)
                if data:
                    return json.loads(data)
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting task details: {e}")
            return None
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        try:
            if alert_id in self.system_alerts:
                self.system_alerts[alert_id].acknowledged = True
                await self._store_alert(self.system_alerts[alert_id])
                logger.info(f"Acknowledged alert: {alert_id}")
                return True
            return False
        
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        try:
            if alert_id in self.system_alerts:
                alert = self.system_alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                await self._store_alert(alert)
                logger.info(f"Resolved alert: {alert_id}")
                return True
            return False
        
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return False
    
    async def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over specified time period."""
        try:
            # Get historical performance data
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            # For now, return recent performance data
            # TODO: Implement proper historical querying
            
            recent_data = list(self.recent_performance)
            
            if not recent_data:
                return {}
            
            # Calculate trends
            execution_times = [p['avg_execution_time'] for p in recent_data]
            active_tasks = [p['active_tasks'] for p in recent_data]
            
            return {
                'period': f"{start_time.isoformat()} to {end_time.isoformat()}",
                'data_points': len(recent_data),
                'execution_time_trend': {
                    'current': execution_times[-1] if execution_times else 0,
                    'avg': statistics.mean(execution_times) if execution_times else 0,
                    'min': min(execution_times) if execution_times else 0,
                    'max': max(execution_times) if execution_times else 0,
                    'trend': 'stable'  # TODO: Calculate actual trend
                },
                'throughput_trend': {
                    'current_active_tasks': active_tasks[-1] if active_tasks else 0,
                    'avg_active_tasks': statistics.mean(active_tasks) if active_tasks else 0,
                    'max_concurrent_tasks': max(active_tasks) if active_tasks else 0
                },
                'time_series': [
                    {
                        'timestamp': p['timestamp'].isoformat(),
                        'avg_execution_time': p['avg_execution_time'],
                        'active_tasks': p['active_tasks']
                    }
                    for p in recent_data
                ]
            }
        
        except Exception as e:
            logger.error(f"Error getting performance trends: {e}")
            return {}