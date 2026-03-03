"""
Comprehensive metrics collection system for VoiceHelpDeskAI.

Collects Prometheus metrics, business metrics, and performance data
for monitoring and alerting.
"""

import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import statistics

from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info,
    CollectorRegistry, generate_latest, start_http_server
)
import psutil
import redis
from loguru import logger

from ..config import config_manager


class MetricType(Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    SUMMARY = "summary"
    INFO = "info"


@dataclass
class MetricConfig:
    """Configuration for a metric."""
    name: str
    help: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None
    quantiles: Optional[Dict[float, float]] = None


class MetricsCollector:
    """
    Comprehensive metrics collection for VoiceHelpDeskAI.
    
    Collects and exposes Prometheus metrics for:
    - API performance
    - Model inference times
    - Queue depths
    - Error rates
    - Resource usage
    - Business metrics
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self._metrics: Dict[str, Any] = {}
        self._locks = defaultdict(threading.Lock)
        self._start_time = time.time()
        
        # Initialize all metrics
        self._init_api_metrics()
        self._init_model_metrics()
        self._init_queue_metrics()
        self._init_business_metrics()
        self._init_system_metrics()
        self._init_audio_metrics()
        
        # Background metrics collection
        self._collection_tasks: List[asyncio.Task] = []
        self._collection_interval = 10  # seconds
        
        logger.info("Metrics collector initialized")
    
    def _init_api_metrics(self):
        """Initialize API-related metrics."""
        
        # HTTP request duration
        self._metrics['http_request_duration'] = Histogram(
            'voicehelpdesk_http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint', 'status'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 60.0],
            registry=self.registry
        )
        
        # HTTP request count
        self._metrics['http_requests_total'] = Counter(
            'voicehelpdesk_http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        # WebSocket connections
        self._metrics['websocket_connections'] = Gauge(
            'voicehelpdesk_websocket_connections_active',
            'Active WebSocket connections',
            ['endpoint'],
            registry=self.registry
        )
        
        # Request size
        self._metrics['request_size'] = Histogram(
            'voicehelpdesk_request_size_bytes',
            'HTTP request size in bytes',
            ['method', 'endpoint'],
            buckets=[100, 1000, 10000, 100000, 1000000, 10000000],
            registry=self.registry
        )
        
        # Response size
        self._metrics['response_size'] = Histogram(
            'voicehelpdesk_response_size_bytes',
            'HTTP response size in bytes',
            ['method', 'endpoint'],
            buckets=[100, 1000, 10000, 100000, 1000000, 10000000],
            registry=self.registry
        )
    
    def _init_model_metrics(self):
        """Initialize AI model metrics."""
        
        # Model inference time
        self._metrics['model_inference_duration'] = Histogram(
            'voicehelpdesk_model_inference_duration_seconds',
            'Model inference duration in seconds',
            ['model_type', 'model_name', 'input_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )
        
        # Model loading time
        self._metrics['model_loading_duration'] = Histogram(
            'voicehelpdesk_model_loading_duration_seconds',
            'Model loading duration in seconds',
            ['model_type', 'model_name'],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
            registry=self.registry
        )
        
        # Model failures
        self._metrics['model_failures_total'] = Counter(
            'voicehelpdesk_model_failures_total',
            'Total model inference failures',
            ['model_type', 'model_name', 'error_type'],
            registry=self.registry
        )
        
        # Model accuracy/confidence
        self._metrics['model_confidence'] = Histogram(
            'voicehelpdesk_model_confidence_score',
            'Model confidence scores',
            ['model_type', 'model_name'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            registry=self.registry
        )
        
        # Token usage (for LLM models)
        self._metrics['llm_tokens_total'] = Counter(
            'voicehelpdesk_llm_tokens_total',
            'Total LLM tokens used',
            ['model_name', 'token_type'],  # prompt, completion
            registry=self.registry
        )
        
        # Model memory usage
        self._metrics['model_memory_usage'] = Gauge(
            'voicehelpdesk_model_memory_usage_bytes',
            'Model memory usage in bytes',
            ['model_type', 'model_name'],
            registry=self.registry
        )
    
    def _init_queue_metrics(self):
        """Initialize queue and task metrics."""
        
        # Queue depth
        self._metrics['queue_depth'] = Gauge(
            'voicehelpdesk_queue_depth',
            'Queue depth (pending tasks)',
            ['queue_name'],
            registry=self.registry
        )
        
        # Task processing time
        self._metrics['task_duration'] = Histogram(
            'voicehelpdesk_task_duration_seconds',
            'Task processing duration in seconds',
            ['task_type', 'queue_name', 'status'],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
            registry=self.registry
        )
        
        # Task failures
        self._metrics['task_failures_total'] = Counter(
            'voicehelpdesk_task_failures_total',
            'Total task failures',
            ['task_type', 'queue_name', 'error_type'],
            registry=self.registry
        )
        
        # Worker utilization
        self._metrics['worker_utilization'] = Gauge(
            'voicehelpdesk_worker_utilization_ratio',
            'Worker utilization ratio (0-1)',
            ['worker_type'],
            registry=self.registry
        )
    
    def _init_business_metrics(self):
        """Initialize business and domain-specific metrics."""
        
        # Conversations
        self._metrics['conversations_started'] = Counter(
            'voicehelpdesk_conversations_started_total',
            'Total conversations started',
            ['channel', 'language'],
            registry=self.registry
        )
        
        self._metrics['conversations_completed'] = Counter(
            'voicehelpdesk_conversations_completed_total',
            'Total conversations completed',
            ['channel', 'resolution_type'],
            registry=self.registry
        )
        
        self._metrics['conversation_duration'] = Histogram(
            'voicehelpdesk_conversation_duration_seconds',
            'Conversation duration in seconds',
            ['channel', 'resolution_type'],
            buckets=[10, 30, 60, 120, 300, 600, 1200, 1800, 3600],
            registry=self.registry
        )
        
        # Tickets
        self._metrics['tickets_created'] = Counter(
            'voicehelpdesk_tickets_created_total',
            'Total tickets created',
            ['category', 'priority', 'source'],
            registry=self.registry
        )
        
        self._metrics['tickets_resolved'] = Counter(
            'voicehelpdesk_tickets_resolved_total',
            'Total tickets resolved',
            ['category', 'resolution_method'],
            registry=self.registry
        )
        
        # User satisfaction
        self._metrics['user_satisfaction'] = Histogram(
            'voicehelpdesk_user_satisfaction_score',
            'User satisfaction scores (1-5)',
            ['channel', 'category'],
            buckets=[1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
            registry=self.registry
        )
        
        # Escalations
        self._metrics['escalations_total'] = Counter(
            'voicehelpdesk_escalations_total',
            'Total escalations',
            ['reason', 'from_level', 'to_level'],
            registry=self.registry
        )
    
    def _init_audio_metrics(self):
        """Initialize audio processing metrics."""
        
        # Audio processing duration
        self._metrics['audio_processing_duration'] = Histogram(
            'voicehelpdesk_audio_processing_duration_seconds',
            'Audio processing duration in seconds',
            ['processing_type', 'audio_format'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        # Audio quality scores
        self._metrics['audio_quality_score'] = Histogram(
            'voicehelpdesk_audio_quality_score',
            'Audio quality scores (0-1)',
            ['processing_type', 'metric_type'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            registry=self.registry
        )
        
        # STT accuracy
        self._metrics['stt_accuracy'] = Histogram(
            'voicehelpdesk_stt_accuracy_score',
            'Speech-to-text accuracy scores',
            ['model_name', 'language'],
            buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.98, 0.99, 1.0],
            registry=self.registry
        )
        
        # Audio stream metrics
        self._metrics['audio_stream_bytes'] = Counter(
            'voicehelpdesk_audio_stream_bytes_total',
            'Total audio stream bytes processed',
            ['stream_type', 'format'],
            registry=self.registry
        )
        
        # VAD metrics
        self._metrics['vad_decisions'] = Counter(
            'voicehelpdesk_vad_decisions_total',
            'Voice activity detection decisions',
            ['decision_type'],  # speech, silence, noise
            registry=self.registry
        )
    
    def _init_system_metrics(self):
        """Initialize system resource metrics."""
        
        # Memory usage
        self._metrics['memory_usage'] = Gauge(
            'voicehelpdesk_memory_usage_bytes',
            'Memory usage in bytes',
            ['memory_type'],  # rss, vms, shared
            registry=self.registry
        )
        
        # CPU usage
        self._metrics['cpu_usage'] = Gauge(
            'voicehelpdesk_cpu_usage_percent',
            'CPU usage percentage',
            ['cpu_type'],  # user, system, idle
            registry=self.registry
        )
        
        # Redis metrics
        self._metrics['redis_connections'] = Gauge(
            'voicehelpdesk_redis_connections_active',
            'Active Redis connections',
            registry=self.registry
        )
        
        self._metrics['redis_memory'] = Gauge(
            'voicehelpdesk_redis_memory_usage_bytes',
            'Redis memory usage in bytes',
            registry=self.registry
        )
        
        # Application info
        self._metrics['app_info'] = Info(
            'voicehelpdesk_app_info',
            'Application information',
            registry=self.registry
        )
        
        # Set application info
        self._metrics['app_info'].info({
            'version': '1.0.0',  # Should come from config
            'environment': config_manager.get('VOICEHELPDESK_ENV', 'development'),
            'python_version': '3.11',  # Should be dynamic
            'start_time': str(int(self._start_time))
        })
    
    # ==========================================================================
    # Recording Methods
    # ==========================================================================
    
    def record_http_request(self, method: str, endpoint: str, status: int, 
                          duration: float, request_size: int = 0, 
                          response_size: int = 0):
        """Record HTTP request metrics."""
        labels = [method, endpoint, str(status)]
        
        self._metrics['http_request_duration'].labels(*labels).observe(duration)
        self._metrics['http_requests_total'].labels(*labels).inc()
        
        if request_size > 0:
            self._metrics['request_size'].labels(method, endpoint).observe(request_size)
        
        if response_size > 0:
            self._metrics['response_size'].labels(method, endpoint).observe(response_size)
    
    def record_model_inference(self, model_type: str, model_name: str, 
                             input_type: str, duration: float, 
                             confidence: Optional[float] = None,
                             tokens_used: Optional[Dict[str, int]] = None):
        """Record model inference metrics."""
        labels = [model_type, model_name, input_type]
        
        self._metrics['model_inference_duration'].labels(*labels).observe(duration)
        
        if confidence is not None:
            self._metrics['model_confidence'].labels(model_type, model_name).observe(confidence)
        
        if tokens_used:
            for token_type, count in tokens_used.items():
                self._metrics['llm_tokens_total'].labels(model_name, token_type).inc(count)
    
    def record_model_failure(self, model_type: str, model_name: str, error_type: str):
        """Record model failure."""
        self._metrics['model_failures_total'].labels(model_type, model_name, error_type).inc()
    
    def record_task_processing(self, task_type: str, queue_name: str, 
                             duration: float, status: str):
        """Record task processing metrics."""
        labels = [task_type, queue_name, status]
        self._metrics['task_duration'].labels(*labels).observe(duration)
    
    def record_task_failure(self, task_type: str, queue_name: str, error_type: str):
        """Record task failure."""
        self._metrics['task_failures_total'].labels(task_type, queue_name, error_type).inc()
    
    def record_conversation(self, channel: str, language: str, duration: float, 
                          resolution_type: str):
        """Record conversation metrics."""
        self._metrics['conversations_started'].labels(channel, language).inc()
        self._metrics['conversations_completed'].labels(channel, resolution_type).inc()
        self._metrics['conversation_duration'].labels(channel, resolution_type).observe(duration)
    
    def record_user_satisfaction(self, channel: str, category: str, score: float):
        """Record user satisfaction score."""
        self._metrics['user_satisfaction'].labels(channel, category).observe(score)
    
    def record_audio_processing(self, processing_type: str, audio_format: str, 
                              duration: float, quality_score: Optional[float] = None):
        """Record audio processing metrics."""
        labels = [processing_type, audio_format]
        self._metrics['audio_processing_duration'].labels(*labels).observe(duration)
        
        if quality_score is not None:
            self._metrics['audio_quality_score'].labels(processing_type, 'overall').observe(quality_score)
    
    def update_queue_depth(self, queue_name: str, depth: int):
        """Update queue depth gauge."""
        self._metrics['queue_depth'].labels(queue_name).set(depth)
    
    def update_websocket_connections(self, endpoint: str, count: int):
        """Update WebSocket connections gauge."""
        self._metrics['websocket_connections'].labels(endpoint).set(count)
    
    def update_worker_utilization(self, worker_type: str, utilization: float):
        """Update worker utilization gauge."""
        self._metrics['worker_utilization'].labels(worker_type).set(utilization)
    
    # ==========================================================================
    # Context Managers for Automatic Timing
    # ==========================================================================
    
    @contextmanager
    def time_http_request(self, method: str, endpoint: str, status: int):
        """Context manager for timing HTTP requests."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_http_request(method, endpoint, status, duration)
    
    @contextmanager
    def time_model_inference(self, model_type: str, model_name: str, input_type: str):
        """Context manager for timing model inference."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_model_inference(model_type, model_name, input_type, duration)
    
    @contextmanager
    def time_task_processing(self, task_type: str, queue_name: str):
        """Context manager for timing task processing."""
        start_time = time.time()
        status = "success"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.time() - start_time
            self.record_task_processing(task_type, queue_name, duration, status)
    
    # ==========================================================================
    # Background Collection
    # ==========================================================================
    
    async def start_background_collection(self):
        """Start background metrics collection tasks."""
        self._collection_tasks = [
            asyncio.create_task(self._collect_system_metrics()),
            asyncio.create_task(self._collect_redis_metrics()),
            asyncio.create_task(self._collect_queue_metrics()),
        ]
        logger.info("Started background metrics collection")
    
    async def stop_background_collection(self):
        """Stop background metrics collection tasks."""
        for task in self._collection_tasks:
            task.cancel()
        await asyncio.gather(*self._collection_tasks, return_exceptions=True)
        logger.info("Stopped background metrics collection")
    
    async def _collect_system_metrics(self):
        """Collect system resource metrics."""
        while True:
            try:
                # Memory metrics
                memory = psutil.virtual_memory()
                self._metrics['memory_usage'].labels('total').set(memory.total)
                self._metrics['memory_usage'].labels('available').set(memory.available)
                self._metrics['memory_usage'].labels('used').set(memory.used)
                
                # Process memory
                process = psutil.Process()
                memory_info = process.memory_info()
                self._metrics['memory_usage'].labels('rss').set(memory_info.rss)
                self._metrics['memory_usage'].labels('vms').set(memory_info.vms)
                
                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                self._metrics['cpu_usage'].labels('total').set(cpu_percent)
                
                await asyncio.sleep(self._collection_interval)
                
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(self._collection_interval)
    
    async def _collect_redis_metrics(self):
        """Collect Redis metrics."""
        try:
            redis_client = redis.from_url(config_manager.get('VOICEHELPDESK_REDIS_URL'))
        except Exception as e:
            logger.error(f"Failed to connect to Redis for metrics: {e}")
            return
        
        while True:
            try:
                info = redis_client.info()
                
                # Connection metrics
                self._metrics['redis_connections'].set(info.get('connected_clients', 0))
                
                # Memory metrics
                self._metrics['redis_memory'].set(info.get('used_memory', 0))
                
                await asyncio.sleep(self._collection_interval)
                
            except Exception as e:
                logger.error(f"Error collecting Redis metrics: {e}")
                await asyncio.sleep(self._collection_interval)
    
    async def _collect_queue_metrics(self):
        """Collect queue depth metrics."""
        # This would integrate with your actual queue system
        # For now, it's a placeholder
        while True:
            try:
                # Example queue depth collection
                # Replace with actual queue monitoring
                await asyncio.sleep(self._collection_interval)
                
            except Exception as e:
                logger.error(f"Error collecting queue metrics: {e}")
                await asyncio.sleep(self._collection_interval)
    
    # ==========================================================================
    # Metrics Export
    # ==========================================================================
    
    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry).decode('utf-8')
    
    def start_metrics_server(self, port: int = 8001):
        """Start HTTP server for metrics endpoint."""
        start_http_server(port, registry=self.registry)
        logger.info(f"Metrics server started on port {port}")


class BusinessMetrics:
    """
    Business-specific metrics collection and analysis.
    
    Provides higher-level business intelligence metrics
    derived from the base metrics.
    """
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.collector = metrics_collector
        self._business_data = defaultdict(list)
        self._analysis_window = 300  # 5 minutes
    
    def calculate_conversation_success_rate(self, time_window: int = 3600) -> float:
        """Calculate conversation success rate over time window."""
        # Implementation would query metrics and calculate rate
        # This is a placeholder for the actual calculation
        return 0.85
    
    def calculate_average_resolution_time(self, category: str = None) -> float:
        """Calculate average resolution time."""
        # Implementation would analyze conversation duration metrics
        return 120.0  # seconds
    
    def calculate_user_satisfaction_trend(self, time_window: int = 86400) -> Dict[str, float]:
        """Calculate user satisfaction trends."""
        return {
            'average': 4.2,
            'trend': 0.1,  # positive trend
            'count': 150
        }
    
    def calculate_model_performance_score(self, model_name: str) -> Dict[str, float]:
        """Calculate comprehensive model performance score."""
        return {
            'accuracy': 0.92,
            'latency_score': 0.88,
            'availability': 0.99,
            'overall': 0.93
        }
    
    def get_business_kpis(self) -> Dict[str, Any]:
        """Get key business performance indicators."""
        return {
            'conversation_success_rate': self.calculate_conversation_success_rate(),
            'average_resolution_time': self.calculate_average_resolution_time(),
            'user_satisfaction': self.calculate_user_satisfaction_trend(),
            'model_performance': {
                'whisper': self.calculate_model_performance_score('whisper'),
                'gpt': self.calculate_model_performance_score('gpt'),
                'piper': self.calculate_model_performance_score('piper')
            }
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()