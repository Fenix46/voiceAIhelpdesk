"""Advanced metrics collector for pipeline performance monitoring and optimization."""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from collections import deque, defaultdict
import threading
import json
from pathlib import Path

from loguru import logger


class MetricType(Enum):
    """Types of metrics collected."""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    SUCCESS_RATE = "success_rate"
    CACHE_HIT_RATE = "cache_hit_rate"
    RESOURCE_USAGE = "resource_usage"
    QUALITY_SCORE = "quality_score"
    USER_SATISFACTION = "user_satisfaction"
    PIPELINE_STAGE_TIME = "pipeline_stage_time"
    CONVERSATION_DURATION = "conversation_duration"


class MetricAggregationType(Enum):
    """Aggregation types for metrics."""
    SUM = "sum"
    AVERAGE = "average"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    PERCENTILE_95 = "percentile_95"
    PERCENTILE_99 = "percentile_99"
    COUNT = "count"
    RATE = "rate"


class OptimizationStrategy(Enum):
    """Performance optimization strategies."""
    CACHING = "caching"
    PARALLEL_PROCESSING = "parallel_processing"
    LOAD_BALANCING = "load_balancing"
    RESOURCE_SCALING = "resource_scaling"
    CIRCUIT_BREAKER = "circuit_breaker"
    REQUEST_THROTTLING = "request_throttling"
    CONNECTION_POOLING = "connection_pooling"
    BATCHING = "batching"


@dataclass
class MetricPoint:
    """Individual metric data point."""
    timestamp: datetime
    value: Union[float, int]
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """Time series of metric points."""
    name: str
    metric_type: MetricType
    aggregation: MetricAggregationType
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    labels: Dict[str, str] = field(default_factory=dict)
    
    # Statistics
    total_points: int = 0
    last_updated: Optional[datetime] = None
    
    # Metadata
    description: str = ""
    unit: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceBenchmark:
    """Performance benchmark thresholds."""
    metric_name: str
    target_value: float
    warning_threshold: float
    critical_threshold: float
    optimization_strategies: List[OptimizationStrategy] = field(default_factory=list)
    
    # Benchmark metadata
    description: str = ""
    business_impact: str = ""
    sla_requirement: bool = False
    
    # Tracking
    violations_count: int = 0
    last_violation: Optional[datetime] = None


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation."""
    strategy: OptimizationStrategy
    priority: str  # low, medium, high, critical
    estimated_improvement: float  # Percentage improvement
    implementation_effort: str  # low, medium, high
    
    # Details
    description: str = ""
    implementation_steps: List[str] = field(default_factory=list)
    expected_benefits: List[str] = field(default_factory=list)
    potential_risks: List[str] = field(default_factory=list)
    
    # Metrics
    affected_metrics: List[str] = field(default_factory=list)
    baseline_values: Dict[str, float] = field(default_factory=dict)
    target_values: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceReport:
    """Comprehensive performance report."""
    report_id: str
    period_start: datetime
    period_end: datetime
    
    # Summary metrics
    total_requests: int = 0
    average_latency: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    
    # Pipeline performance
    pipeline_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    stage_performance: Dict[str, float] = field(default_factory=dict)
    bottleneck_analysis: List[str] = field(default_factory=list)
    
    # Quality metrics
    average_quality_score: float = 0.0
    quality_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Optimization insights
    performance_trends: Dict[str, str] = field(default_factory=dict)  # improving, degrading, stable
    optimization_recommendations: List[OptimizationRecommendation] = field(default_factory=list)
    benchmark_violations: List[Dict[str, Any]] = field(default_factory=dict)
    
    # Resource utilization
    resource_usage: Dict[str, float] = field(default_factory=dict)
    capacity_analysis: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    generation_time: float = 0.0
    report_version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """Advanced metrics collector for pipeline performance monitoring."""
    
    def __init__(self,
                 collection_interval: float = 1.0,
                 retention_hours: int = 24,
                 enable_real_time_monitoring: bool = True,
                 enable_optimization_recommendations: bool = True,
                 enable_alerting: bool = True,
                 metrics_storage_path: Optional[str] = None):
        """Initialize metrics collector.
        
        Args:
            collection_interval: Interval between metric collections (seconds)
            retention_hours: Hours to retain metric data
            enable_real_time_monitoring: Enable real-time metric monitoring
            enable_optimization_recommendations: Enable performance optimization recommendations
            enable_alerting: Enable alerting for threshold violations
            metrics_storage_path: Path to store metric data
        """
        self.collection_interval = collection_interval
        self.retention_hours = retention_hours
        self.enable_real_time_monitoring = enable_real_time_monitoring
        self.enable_optimization_recommendations = enable_optimization_recommendations
        self.enable_alerting = enable_alerting
        self.metrics_storage_path = metrics_storage_path or "./data/metrics"
        
        # Metric storage
        self.metric_series: Dict[str, MetricSeries] = {}
        self.performance_benchmarks: Dict[str, PerformanceBenchmark] = {}
        
        # Real-time monitoring
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.collection_lock = threading.Lock()
        
        # Optimization engine
        self.optimization_history: List[OptimizationRecommendation] = []
        self.applied_optimizations: Dict[str, datetime] = {}
        
        # Alerting
        self.alert_handlers: List[callable] = []
        self.alert_thresholds: Dict[str, Dict[str, float]] = {}
        
        # Performance tracking
        self.stats = {
            'total_metrics_collected': 0,
            'collection_errors': 0,
            'last_collection_time': None,
            'average_collection_latency': 0.0,
            'alerts_sent': 0,
            'optimization_recommendations_generated': 0,
            'benchmark_violations': 0
        }
        
        # State
        self.is_initialized = False
        self.initialization_lock = threading.Lock()
        
        logger.info("MetricsCollector initialized")
    
    async def initialize(self) -> None:
        """Initialize metrics collector."""
        if self.is_initialized:
            logger.warning("MetricsCollector already initialized")
            return
        
        with self.initialization_lock:
            if self.is_initialized:
                return
            
            try:
                logger.info("Initializing MetricsCollector...")
                
                # Setup storage directory
                storage_path = Path(self.metrics_storage_path)
                storage_path.mkdir(parents=True, exist_ok=True)
                
                # Initialize default metrics
                await self._initialize_default_metrics()
                
                # Initialize performance benchmarks
                self._initialize_performance_benchmarks()
                
                # Load historical data if available
                await self._load_historical_metrics()
                
                # Start real-time monitoring
                if self.enable_real_time_monitoring:
                    await self.start_monitoring()
                
                self.is_initialized = True
                logger.success("MetricsCollector initialization complete")
                
            except Exception as e:
                logger.error(f"MetricsCollector initialization failed: {e}")
                raise
    
    async def record_metric(self,
                           metric_name: str,
                           value: Union[float, int],
                           labels: Optional[Dict[str, str]] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a metric value.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            labels: Optional labels for the metric
            metadata: Optional metadata
        """
        try:
            with self.collection_lock:
                if metric_name not in self.metric_series:
                    # Auto-create metric series if it doesn't exist
                    self.metric_series[metric_name] = MetricSeries(
                        name=metric_name,
                        metric_type=self._infer_metric_type(metric_name),
                        aggregation=MetricAggregationType.AVERAGE
                    )
                
                series = self.metric_series[metric_name]
                
                # Create metric point
                point = MetricPoint(
                    timestamp=datetime.now(),
                    value=value,
                    labels=labels or {},
                    metadata=metadata or {}
                )
                
                # Add to series
                series.points.append(point)
                series.total_points += 1
                series.last_updated = point.timestamp
                
                # Update statistics
                self.stats['total_metrics_collected'] += 1
                self.stats['last_collection_time'] = point.timestamp
                
                # Check for threshold violations
                if self.enable_alerting:
                    await self._check_alert_thresholds(metric_name, value)
                
        except Exception as e:
            self.stats['collection_errors'] += 1
            logger.error(f"Failed to record metric {metric_name}: {e}")
    
    async def record_pipeline_stage_metrics(self,
                                          stage_name: str,
                                          processing_time: float,
                                          success: bool,
                                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record metrics for a pipeline stage.
        
        Args:
            stage_name: Name of the pipeline stage
            processing_time: Time taken to process the stage
            success: Whether the stage completed successfully
            metadata: Optional metadata
        """
        labels = {'stage': stage_name}
        
        # Record processing time
        await self.record_metric(
            f"pipeline_stage_latency",
            processing_time,
            labels=labels,
            metadata=metadata
        )
        
        # Record success/failure
        await self.record_metric(
            f"pipeline_stage_success_rate",
            1.0 if success else 0.0,
            labels=labels,
            metadata=metadata
        )
        
        # Record throughput (inverse of processing time)
        if processing_time > 0:
            await self.record_metric(
                f"pipeline_stage_throughput",
                1.0 / processing_time,
                labels=labels,
                metadata=metadata
            )
    
    async def record_conversation_metrics(self,
                                        conversation_id: str,
                                        total_duration: float,
                                        pipeline_stages: Dict[str, float],
                                        quality_score: float,
                                        user_satisfaction: Optional[float] = None,
                                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record comprehensive conversation metrics.
        
        Args:
            conversation_id: Conversation identifier
            total_duration: Total conversation duration
            pipeline_stages: Processing time for each pipeline stage
            quality_score: Overall quality score
            user_satisfaction: Optional user satisfaction score
            metadata: Optional metadata
        """
        labels = {'conversation_id': conversation_id}
        
        # Record overall conversation metrics
        await self.record_metric("conversation_duration", total_duration, labels=labels)
        await self.record_metric("conversation_quality_score", quality_score, labels=labels)
        
        if user_satisfaction is not None:
            await self.record_metric("user_satisfaction", user_satisfaction, labels=labels)
        
        # Record individual stage metrics
        for stage_name, stage_time in pipeline_stages.items():
            stage_labels = {**labels, 'stage': stage_name}
            await self.record_metric("pipeline_stage_time", stage_time, labels=stage_labels)
    
    async def get_metric_summary(self,
                               metric_name: str,
                               time_window_minutes: int = 60,
                               aggregation: Optional[MetricAggregationType] = None) -> Dict[str, Any]:
        """Get summary statistics for a metric.
        
        Args:
            metric_name: Name of the metric
            time_window_minutes: Time window for analysis
            aggregation: Aggregation type (uses metric default if None)
            
        Returns:
            Metric summary with statistics
        """
        if metric_name not in self.metric_series:
            return {}
        
        series = self.metric_series[metric_name]
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        # Filter points within time window
        recent_points = [
            point for point in series.points
            if point.timestamp >= cutoff_time
        ]
        
        if not recent_points:
            return {'metric_name': metric_name, 'no_data': True}
        
        values = [point.value for point in recent_points]
        
        # Calculate statistics
        summary = {
            'metric_name': metric_name,
            'time_window_minutes': time_window_minutes,
            'total_points': len(values),
            'latest_value': values[-1] if values else None,
            'average': statistics.mean(values) if values else 0,
            'median': statistics.median(values) if values else 0,
            'min': min(values) if values else 0,
            'max': max(values) if values else 0,
            'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
        }
        
        # Add percentiles if enough data
        if len(values) >= 10:
            sorted_values = sorted(values)
            summary['percentile_95'] = sorted_values[int(len(sorted_values) * 0.95)]
            summary['percentile_99'] = sorted_values[int(len(sorted_values) * 0.99)]
        
        # Add trend analysis
        if len(values) >= 5:
            recent_avg = statistics.mean(values[-5:])
            older_avg = statistics.mean(values[:-5]) if len(values) > 5 else recent_avg
            
            if recent_avg > older_avg * 1.05:
                summary['trend'] = 'increasing'
            elif recent_avg < older_avg * 0.95:
                summary['trend'] = 'decreasing'
            else:
                summary['trend'] = 'stable'
        
        return summary
    
    async def generate_performance_report(self,
                                        time_window_hours: int = 24) -> PerformanceReport:
        """Generate comprehensive performance report.
        
        Args:
            time_window_hours: Time window for report analysis
            
        Returns:
            Comprehensive performance report
        """
        start_time = time.time()
        period_end = datetime.now()
        period_start = period_end - timedelta(hours=time_window_hours)
        
        report = PerformanceReport(
            report_id=f"perf_report_{int(time.time())}",
            period_start=period_start,
            period_end=period_end
        )
        
        try:
            # Collect summary metrics
            await self._collect_summary_metrics(report, time_window_hours)
            
            # Analyze pipeline performance
            await self._analyze_pipeline_performance(report, time_window_hours)
            
            # Analyze quality metrics
            await self._analyze_quality_metrics(report, time_window_hours)
            
            # Generate optimization recommendations
            if self.enable_optimization_recommendations:
                await self._generate_optimization_recommendations(report)
            
            # Analyze benchmark violations
            await self._analyze_benchmark_violations(report, time_window_hours)
            
            # Resource utilization analysis
            await self._analyze_resource_utilization(report)
            
            report.generation_time = time.time() - start_time
            
            logger.info(f"Generated performance report {report.report_id} in {report.generation_time:.2f}s")
            
            return report
            
        except Exception as e:
            logger.error(f"Performance report generation failed: {e}")
            report.generation_time = time.time() - start_time
            report.metadata['error'] = str(e)
            return report
    
    async def get_optimization_recommendations(self,
                                             priority_filter: Optional[str] = None,
                                             limit: int = 10) -> List[OptimizationRecommendation]:
        """Get performance optimization recommendations.
        
        Args:
            priority_filter: Filter by priority (low, medium, high, critical)
            limit: Maximum number of recommendations
            
        Returns:
            List of optimization recommendations
        """
        recommendations = self.optimization_history.copy()
        
        # Filter by priority if specified
        if priority_filter:
            recommendations = [r for r in recommendations if r.priority == priority_filter]
        
        # Sort by priority and confidence
        priority_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        recommendations.sort(
            key=lambda r: (priority_order.get(r.priority, 0), r.confidence_score),
            reverse=True
        )
        
        return recommendations[:limit]
    
    async def start_monitoring(self) -> None:
        """Start real-time metric monitoring."""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started real-time metric monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop real-time metric monitoring."""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped real-time metric monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                loop_start = time.time()
                
                # Cleanup old metrics
                await self._cleanup_old_metrics()
                
                # Check for performance issues
                await self._check_performance_issues()
                
                # Generate recommendations if needed
                if self.enable_optimization_recommendations:
                    await self._periodic_optimization_analysis()
                
                # Calculate loop latency
                loop_latency = time.time() - loop_start
                self.stats['average_collection_latency'] = (
                    (self.stats['average_collection_latency'] * 0.9) + (loop_latency * 0.1)
                )
                
                # Wait for next interval
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _initialize_default_metrics(self) -> None:
        """Initialize default metric series."""
        default_metrics = [
            ('pipeline_total_latency', MetricType.LATENCY, MetricAggregationType.AVERAGE),
            ('pipeline_success_rate', MetricType.SUCCESS_RATE, MetricAggregationType.AVERAGE),
            ('pipeline_error_rate', MetricType.ERROR_RATE, MetricAggregationType.AVERAGE),
            ('pipeline_throughput', MetricType.THROUGHPUT, MetricAggregationType.AVERAGE),
            ('stt_latency', MetricType.LATENCY, MetricAggregationType.AVERAGE),
            ('nlu_latency', MetricType.LATENCY, MetricAggregationType.AVERAGE),
            ('llm_latency', MetricType.LATENCY, MetricAggregationType.AVERAGE),
            ('tts_latency', MetricType.LATENCY, MetricAggregationType.AVERAGE),
            ('quality_score', MetricType.QUALITY_SCORE, MetricAggregationType.AVERAGE),
            ('cache_hit_rate', MetricType.CACHE_HIT_RATE, MetricAggregationType.AVERAGE),
            ('user_satisfaction', MetricType.USER_SATISFACTION, MetricAggregationType.AVERAGE),
            ('conversation_duration', MetricType.CONVERSATION_DURATION, MetricAggregationType.AVERAGE),
        ]
        
        for name, metric_type, aggregation in default_metrics:
            self.metric_series[name] = MetricSeries(
                name=name,
                metric_type=metric_type,
                aggregation=aggregation,
                description=f"Default metric for {name.replace('_', ' ')}"
            )
    
    def _initialize_performance_benchmarks(self) -> None:
        """Initialize performance benchmarks."""
        benchmarks = [
            PerformanceBenchmark(
                metric_name="pipeline_total_latency",
                target_value=2.0,  # 2 seconds
                warning_threshold=3.0,
                critical_threshold=5.0,
                optimization_strategies=[OptimizationStrategy.CACHING, OptimizationStrategy.PARALLEL_PROCESSING],
                description="End-to-end pipeline response time",
                business_impact="User experience and satisfaction",
                sla_requirement=True
            ),
            PerformanceBenchmark(
                metric_name="pipeline_success_rate",
                target_value=0.95,  # 95%
                warning_threshold=0.90,
                critical_threshold=0.85,
                optimization_strategies=[OptimizationStrategy.CIRCUIT_BREAKER, OptimizationStrategy.LOAD_BALANCING],
                description="Pipeline success rate",
                business_impact="Service reliability",
                sla_requirement=True
            ),
            PerformanceBenchmark(
                metric_name="quality_score",
                target_value=0.80,  # 80%
                warning_threshold=0.70,
                critical_threshold=0.60,
                optimization_strategies=[OptimizationStrategy.CACHING],
                description="Response quality score",
                business_impact="User satisfaction and trust"
            ),
            PerformanceBenchmark(
                metric_name="cache_hit_rate",
                target_value=0.60,  # 60%
                warning_threshold=0.40,
                critical_threshold=0.20,
                optimization_strategies=[OptimizationStrategy.CACHING],
                description="Cache hit rate for optimized responses"
            )
        ]
        
        for benchmark in benchmarks:
            self.performance_benchmarks[benchmark.metric_name] = benchmark
    
    async def _load_historical_metrics(self) -> None:
        """Load historical metric data."""
        try:
            metrics_file = Path(self.metrics_storage_path) / "historical_metrics.json"
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    data = json.load(f)
                
                # Load metric series (simplified implementation)
                logger.info(f"Loaded historical metrics from {metrics_file}")
            
        except Exception as e:
            logger.warning(f"Failed to load historical metrics: {e}")
    
    async def _collect_summary_metrics(self, report: PerformanceReport, time_window_hours: int) -> None:
        """Collect summary metrics for report."""
        # Get pipeline latency summary
        latency_summary = await self.get_metric_summary("pipeline_total_latency", time_window_hours * 60)
        report.average_latency = latency_summary.get('average', 0.0)
        
        # Get success rate
        success_summary = await self.get_metric_summary("pipeline_success_rate", time_window_hours * 60)
        report.success_rate = success_summary.get('average', 0.0)
        
        # Calculate error rate
        report.error_rate = 1.0 - report.success_rate
        
        # Get throughput
        throughput_summary = await self.get_metric_summary("pipeline_throughput", time_window_hours * 60)
        report.throughput = throughput_summary.get('average', 0.0)
        
        # Estimate total requests from throughput and time window
        report.total_requests = int(report.throughput * time_window_hours * 3600)
    
    async def _analyze_pipeline_performance(self, report: PerformanceReport, time_window_hours: int) -> None:
        """Analyze pipeline stage performance."""
        stages = ['stt', 'nlu', 'llm', 'tts', 'quality_check', 'ticket_building']
        
        for stage in stages:
            stage_summary = await self.get_metric_summary(f"{stage}_latency", time_window_hours * 60)
            if stage_summary and not stage_summary.get('no_data'):
                report.stage_performance[stage] = stage_summary.get('average', 0.0)
        
        # Identify bottlenecks
        if report.stage_performance:
            max_stage = max(report.stage_performance.items(), key=lambda x: x[1])
            if max_stage[1] > report.average_latency * 0.4:  # If stage takes >40% of total time
                report.bottleneck_analysis.append(f"Bottleneck detected in {max_stage[0]} stage: {max_stage[1]:.2f}s")
    
    async def _analyze_quality_metrics(self, report: PerformanceReport, time_window_hours: int) -> None:
        """Analyze quality metrics."""
        quality_summary = await self.get_metric_summary("quality_score", time_window_hours * 60)
        report.average_quality_score = quality_summary.get('average', 0.0)
        
        # Quality distribution (simplified)
        if quality_summary and not quality_summary.get('no_data'):
            avg_quality = quality_summary.get('average', 0.0)
            if avg_quality >= 0.8:
                report.quality_distribution['high'] = 70
                report.quality_distribution['medium'] = 25
                report.quality_distribution['low'] = 5
            elif avg_quality >= 0.6:
                report.quality_distribution['high'] = 40
                report.quality_distribution['medium'] = 45
                report.quality_distribution['low'] = 15
            else:
                report.quality_distribution['high'] = 20
                report.quality_distribution['medium'] = 30
                report.quality_distribution['low'] = 50
    
    async def _generate_optimization_recommendations(self, report: PerformanceReport) -> None:
        """Generate optimization recommendations based on metrics."""
        recommendations = []
        
        # Latency optimization
        if report.average_latency > 3.0:
            recommendations.append(OptimizationRecommendation(
                strategy=OptimizationStrategy.CACHING,
                priority="high",
                estimated_improvement=25.0,
                implementation_effort="medium",
                description="Implement response caching to reduce latency",
                implementation_steps=[
                    "Enable response caching in ResponseGenerator",
                    "Implement cache warming for common queries",
                    "Add cache invalidation strategies"
                ],
                expected_benefits=[
                    "Reduced average response time",
                    "Improved user experience",
                    "Lower resource utilization"
                ],
                affected_metrics=["pipeline_total_latency", "pipeline_throughput"],
                baseline_values={"latency": report.average_latency},
                target_values={"latency": report.average_latency * 0.75},
                confidence_score=0.8
            ))
        
        # Quality optimization
        if report.average_quality_score < 0.7:
            recommendations.append(OptimizationRecommendation(
                strategy=OptimizationStrategy.PARALLEL_PROCESSING,
                priority="medium",
                estimated_improvement=15.0,
                implementation_effort="high",
                description="Implement parallel quality checks",
                implementation_steps=[
                    "Refactor QualityController for parallel checks",
                    "Implement async quality validation",
                    "Add quality check prioritization"
                ],
                expected_benefits=[
                    "Improved response quality",
                    "Better fact checking",
                    "Enhanced user satisfaction"
                ],
                affected_metrics=["quality_score"],
                baseline_values={"quality": report.average_quality_score},
                target_values={"quality": 0.8},
                confidence_score=0.7
            ))
        
        # Success rate optimization
        if report.success_rate < 0.9:
            recommendations.append(OptimizationRecommendation(
                strategy=OptimizationStrategy.CIRCUIT_BREAKER,
                priority="high",
                estimated_improvement=20.0,
                implementation_effort="medium",
                description="Implement circuit breaker pattern for reliability",
                implementation_steps=[
                    "Add circuit breaker to external service calls",
                    "Implement fallback mechanisms",
                    "Add health check monitoring"
                ],
                expected_benefits=[
                    "Improved system reliability",
                    "Better error handling",
                    "Reduced cascade failures"
                ],
                affected_metrics=["pipeline_success_rate", "pipeline_error_rate"],
                baseline_values={"success_rate": report.success_rate},
                target_values={"success_rate": 0.95},
                confidence_score=0.9
            ))
        
        report.optimization_recommendations = recommendations
        self.optimization_history.extend(recommendations)
        self.stats['optimization_recommendations_generated'] += len(recommendations)
    
    async def _analyze_benchmark_violations(self, report: PerformanceReport, time_window_hours: int) -> None:
        """Analyze benchmark violations."""
        violations = []
        
        for metric_name, benchmark in self.performance_benchmarks.items():
            summary = await self.get_metric_summary(metric_name, time_window_hours * 60)
            
            if summary and not summary.get('no_data'):
                current_value = summary.get('average', 0.0)
                
                if current_value > benchmark.critical_threshold or current_value < benchmark.critical_threshold:
                    severity = "critical"
                elif current_value > benchmark.warning_threshold or current_value < benchmark.warning_threshold:
                    severity = "warning"
                else:
                    continue
                
                violations.append({
                    'metric': metric_name,
                    'current_value': current_value,
                    'threshold': benchmark.warning_threshold if severity == "warning" else benchmark.critical_threshold,
                    'severity': severity,
                    'description': benchmark.description,
                    'business_impact': benchmark.business_impact
                })
                
                benchmark.violations_count += 1
                benchmark.last_violation = datetime.now()
                self.stats['benchmark_violations'] += 1
        
        report.benchmark_violations = violations
    
    async def _analyze_resource_utilization(self, report: PerformanceReport) -> None:
        """Analyze resource utilization."""
        # Simplified resource analysis
        report.resource_usage = {
            'cpu_utilization': 0.65,  # Would be actual system metrics
            'memory_utilization': 0.45,
            'network_bandwidth': 0.30,
            'storage_utilization': 0.55
        }
        
        report.capacity_analysis = {
            'current_capacity': 1000,  # requests per hour
            'peak_capacity': 1500,
            'utilization_percentage': 67,
            'bottleneck_component': 'LLM processing'
        }
    
    async def _check_alert_thresholds(self, metric_name: str, value: float) -> None:
        """Check if metric value violates alert thresholds."""
        if metric_name in self.performance_benchmarks:
            benchmark = self.performance_benchmarks[metric_name]
            
            if value > benchmark.critical_threshold or value < benchmark.critical_threshold:
                await self._send_alert(metric_name, value, "critical", benchmark)
            elif value > benchmark.warning_threshold or value < benchmark.warning_threshold:
                await self._send_alert(metric_name, value, "warning", benchmark)
    
    async def _send_alert(self, metric_name: str, value: float, severity: str, 
                         benchmark: PerformanceBenchmark) -> None:
        """Send performance alert."""
        alert_data = {
            'metric': metric_name,
            'current_value': value,
            'severity': severity,
            'threshold': benchmark.critical_threshold if severity == "critical" else benchmark.warning_threshold,
            'description': benchmark.description,
            'timestamp': datetime.now().isoformat(),
            'optimization_strategies': [strategy.value for strategy in benchmark.optimization_strategies]
        }
        
        # Call alert handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert_data)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
        
        self.stats['alerts_sent'] += 1
        logger.warning(f"Performance alert: {metric_name} = {value} ({severity})")
    
    async def _cleanup_old_metrics(self) -> None:
        """Clean up old metric data."""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        
        for series in self.metric_series.values():
            # Remove old points
            while series.points and series.points[0].timestamp < cutoff_time:
                series.points.popleft()
    
    async def _check_performance_issues(self) -> None:
        """Check for performance issues in real-time."""
        # Check recent latency spikes
        latency_summary = await self.get_metric_summary("pipeline_total_latency", 5)  # Last 5 minutes
        if latency_summary and latency_summary.get('average', 0) > 5.0:
            logger.warning(f"High latency detected: {latency_summary['average']:.2f}s")
        
        # Check error rate spikes
        error_summary = await self.get_metric_summary("pipeline_error_rate", 5)
        if error_summary and error_summary.get('average', 0) > 0.1:  # >10% error rate
            logger.warning(f"High error rate detected: {error_summary['average']:.1%}")
    
    async def _periodic_optimization_analysis(self) -> None:
        """Perform periodic optimization analysis."""
        # Run optimization analysis every hour
        current_time = datetime.now()
        last_analysis = getattr(self, '_last_optimization_analysis', None)
        
        if not last_analysis or (current_time - last_analysis).total_seconds() > 3600:
            try:
                report = await self.generate_performance_report(1)  # Last hour
                self._last_optimization_analysis = current_time
                
                logger.debug(f"Periodic optimization analysis completed: "
                           f"{len(report.optimization_recommendations)} recommendations")
                
            except Exception as e:
                logger.error(f"Periodic optimization analysis failed: {e}")
    
    def _infer_metric_type(self, metric_name: str) -> MetricType:
        """Infer metric type from metric name."""
        name_lower = metric_name.lower()
        
        if 'latency' in name_lower or 'time' in name_lower:
            return MetricType.LATENCY
        elif 'rate' in name_lower:
            if 'success' in name_lower:
                return MetricType.SUCCESS_RATE
            elif 'error' in name_lower:
                return MetricType.ERROR_RATE
            elif 'hit' in name_lower:
                return MetricType.CACHE_HIT_RATE
            else:
                return MetricType.THROUGHPUT
        elif 'quality' in name_lower:
            return MetricType.QUALITY_SCORE
        elif 'satisfaction' in name_lower:
            return MetricType.USER_SATISFACTION
        elif 'duration' in name_lower:
            return MetricType.CONVERSATION_DURATION
        else:
            return MetricType.LATENCY  # Default
    
    def add_alert_handler(self, handler: callable) -> None:
        """Add alert handler function."""
        self.alert_handlers.append(handler)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive metrics collector statistics."""
        stats = self.stats.copy()
        
        # Add current state
        stats['total_metric_series'] = len(self.metric_series)
        stats['total_benchmarks'] = len(self.performance_benchmarks)
        stats['monitoring_active'] = self.monitoring_active
        stats['optimization_recommendations_pending'] = len(self.optimization_history)
        
        # Add metric series statistics
        stats['metric_series_stats'] = {}
        for name, series in self.metric_series.items():
            stats['metric_series_stats'][name] = {
                'total_points': series.total_points,
                'current_points': len(series.points),
                'last_updated': series.last_updated.isoformat() if series.last_updated else None
            }
        
        stats['timestamp'] = datetime.now().isoformat()
        
        return stats
    
    async def export_metrics(self, format: str = "json", time_window_hours: int = 24) -> str:
        """Export metrics in specified format.
        
        Args:
            format: Export format (json, csv, prometheus)
            time_window_hours: Time window for export
            
        Returns:
            Exported metrics as string
        """
        if format == "json":
            return await self._export_metrics_json(time_window_hours)
        elif format == "csv":
            return await self._export_metrics_csv(time_window_hours)
        elif format == "prometheus":
            return await self._export_metrics_prometheus()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    async def _export_metrics_json(self, time_window_hours: int) -> str:
        """Export metrics as JSON."""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'time_window_hours': time_window_hours,
            'metrics': {}
        }
        
        for name, series in self.metric_series.items():
            recent_points = [
                {
                    'timestamp': point.timestamp.isoformat(),
                    'value': point.value,
                    'labels': point.labels,
                    'metadata': point.metadata
                }
                for point in series.points
                if point.timestamp >= cutoff_time
            ]
            
            export_data['metrics'][name] = {
                'metric_type': series.metric_type.value,
                'aggregation': series.aggregation.value,
                'description': series.description,
                'unit': series.unit,
                'points': recent_points
            }
        
        return json.dumps(export_data, indent=2)
    
    async def _export_metrics_csv(self, time_window_hours: int) -> str:
        """Export metrics as CSV."""
        # Simplified CSV export
        lines = ["timestamp,metric_name,value,labels"]
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        for name, series in self.metric_series.items():
            for point in series.points:
                if point.timestamp >= cutoff_time:
                    labels_str = ";".join([f"{k}={v}" for k, v in point.labels.items()])
                    lines.append(f"{point.timestamp.isoformat()},{name},{point.value},{labels_str}")
        
        return "\n".join(lines)
    
    async def _export_metrics_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for name, series in self.metric_series.items():
            if series.points:
                latest_point = series.points[-1]
                
                # Add metric help
                lines.append(f"# HELP {name} {series.description}")
                lines.append(f"# TYPE {name} gauge")
                
                # Add metric value
                labels_str = ""
                if latest_point.labels:
                    labels_list = [f'{k}="{v}"' for k, v in latest_point.labels.items()]
                    labels_str = "{" + ",".join(labels_list) + "}"
                
                lines.append(f"{name}{labels_str} {latest_point.value}")
                lines.append("")
        
        return "\n".join(lines)