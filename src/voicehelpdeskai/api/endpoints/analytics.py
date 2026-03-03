"""REST endpoints for analytics and reporting."""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse

from ...core.logging import get_logger
from ...services.ticketing.analytics import TicketAnalytics, TrendPeriod
from ...database import get_conversation_repository, get_ticket_repository
from ..middleware.auth import auth_required, admin_required
from ..schemas import (
    AnalyticsPeriod, AnalyticsDashboardResponse, DashboardMetrics, MetricValue
)

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=AnalyticsDashboardResponse,
    summary="Get analytics dashboard",
    description="Get comprehensive analytics dashboard with key metrics and charts"
)
async def get_analytics_dashboard(
    period: AnalyticsPeriod = Query(default=AnalyticsPeriod.WEEK, description="Analysis period"),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> AnalyticsDashboardResponse:
    """
    Get comprehensive analytics dashboard.
    
    Provides key metrics, trends, and performance indicators for
    conversations, tickets, user satisfaction, and system health.
    """
    try:
        # Calculate date range based on period
        if not start_date or not end_date:
            end_date = datetime.now(timezone.utc)
            
            if period == AnalyticsPeriod.HOUR:
                start_date = end_date - timedelta(hours=1)
            elif period == AnalyticsPeriod.DAY:
                start_date = end_date - timedelta(days=1)
            elif period == AnalyticsPeriod.WEEK:
                start_date = end_date - timedelta(weeks=1)
            elif period == AnalyticsPeriod.MONTH:
                start_date = end_date - timedelta(days=30)
            elif period == AnalyticsPeriod.QUARTER:
                start_date = end_date - timedelta(days=90)
            elif period == AnalyticsPeriod.YEAR:
                start_date = end_date - timedelta(days=365)
        
        # Initialize analytics service
        analytics = TicketAnalytics()
        
        # Get conversation statistics
        conversation_repo = get_conversation_repository()
        conversation_stats = await _get_conversation_statistics(
            conversation_repo, start_date, end_date
        )
        
        # Get ticket statistics
        ticket_stats = analytics.get_resolution_rate_metrics(
            start_date=start_date,
            end_date=end_date
        )
        
        # Get performance metrics
        performance_metrics = await _get_performance_metrics(start_date, end_date)
        
        # Get user satisfaction metrics
        satisfaction_metrics = analytics.get_user_satisfaction_analysis(
            start_date=start_date,
            end_date=end_date
        )
        
        # Get trending issues
        trending_issues = await _get_trending_issues(analytics, start_date, end_date)
        
        # Get system health
        system_health = await _get_system_health()
        
        # Prepare dashboard metrics
        dashboard_metrics = DashboardMetrics(
            conversation_stats=conversation_stats,
            ticket_stats=ticket_stats.get("overall", {}),
            performance_metrics=performance_metrics,
            user_satisfaction=satisfaction_metrics if not satisfaction_metrics.get("error") else {},
            trending_issues=trending_issues,
            system_health=system_health
        )
        
        # Get chart data
        charts_data = await _get_charts_data(analytics, start_date, end_date, period)
        
        logger.info(
            f"Generated analytics dashboard for period {period.value}",
            extra={
                "period": period.value,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "requested_by": current_user.get("user_id")
            }
        )
        
        return AnalyticsDashboardResponse(
            period=period,
            start_date=start_date,
            end_date=end_date,
            metrics=dashboard_metrics,
            charts_data=charts_data
        )
    
    except Exception as e:
        logger.error(f"Failed to generate analytics dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate analytics dashboard"
        )


@router.get(
    "/tickets/response-time",
    summary="Get response time metrics",
    description="Get detailed response time analysis for tickets"
)
async def get_response_time_metrics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[int] = Query(None),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> Dict[str, Any]:
    """Get response time metrics with filtering options."""
    try:
        analytics = TicketAnalytics()
        
        metrics = analytics.get_response_time_metrics(
            start_date=start_date,
            end_date=end_date,
            category=category,
            priority=priority
        )
        
        return {
            "metric_type": metrics.metric_type.value,
            "value": metrics.value,
            "unit": metrics.unit,
            "period_start": metrics.period_start.isoformat(),
            "period_end": metrics.period_end.isoformat(),
            "metadata": metrics.metadata
        }
    
    except Exception as e:
        logger.error(f"Failed to get response time metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get response time metrics"
        )


@router.get(
    "/tickets/resolution-rate",
    summary="Get resolution rate metrics",
    description="Get ticket resolution rate analysis"
)
async def get_resolution_rate_metrics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    group_by: str = Query("category", regex="^(category|priority|assignee)$"),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> Dict[str, Any]:
    """Get resolution rate metrics grouped by specified field."""
    try:
        analytics = TicketAnalytics()
        
        metrics = analytics.get_resolution_rate_metrics(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by
        )
        
        return metrics
    
    except Exception as e:
        logger.error(f"Failed to get resolution rate metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get resolution rate metrics"
        )


@router.get(
    "/tickets/satisfaction",
    summary="Get user satisfaction analysis",
    description="Get detailed user satisfaction metrics and trends"
)
async def get_user_satisfaction_analysis(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> Dict[str, Any]:
    """Get user satisfaction analysis."""
    try:
        analytics = TicketAnalytics()
        
        analysis = analytics.get_user_satisfaction_analysis(
            start_date=start_date,
            end_date=end_date
        )
        
        return analysis
    
    except Exception as e:
        logger.error(f"Failed to get satisfaction analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get satisfaction analysis"
        )


@router.get(
    "/tickets/trends",
    summary="Get trend analysis",
    description="Get trend analysis for specified metrics"
)
async def get_trend_analysis(
    metric: str = Query(..., description="Metric to analyze"),
    period: str = Query("weekly", regex="^(daily|weekly|monthly|quarterly)$"),
    lookback_days: int = Query(90, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(auth_required)
) -> Dict[str, Any]:
    """Get trend analysis for specified metric."""
    try:
        analytics = TicketAnalytics()
        
        # Convert period string to enum
        period_mapping = {
            "daily": TrendPeriod.DAILY,
            "weekly": TrendPeriod.WEEKLY,
            "monthly": TrendPeriod.MONTHLY,
            "quarterly": TrendPeriod.QUARTERLY
        }
        
        trend_period = period_mapping.get(period, TrendPeriod.WEEKLY)
        
        trend_analysis = analytics.get_trend_analysis(
            metric=metric,
            period=trend_period,
            lookback_days=lookback_days
        )
        
        return {
            "metric": trend_analysis.metric,
            "period": trend_analysis.period.value,
            "trend_direction": trend_analysis.trend_direction,
            "trend_strength": trend_analysis.trend_strength,
            "data_points": trend_analysis.data_points,
            "prediction": trend_analysis.prediction
        }
    
    except Exception as e:
        logger.error(f"Failed to get trend analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trend analysis"
        )


@router.get(
    "/tickets/workload-prediction",
    summary="Get workload prediction",
    description="Get ML-based workload predictions"
)
async def get_workload_prediction(
    forecast_days: int = Query(7, ge=1, le=30),
    confidence_interval: float = Query(0.95, ge=0.5, le=0.99),
    current_user: Dict[str, Any] = Depends(admin_required)
) -> Dict[str, Any]:
    """Get ML-based workload predictions (admin only)."""
    try:
        analytics = TicketAnalytics()
        
        prediction = analytics.predict_workload(
            forecast_days=forecast_days,
            confidence_interval=confidence_interval
        )
        
        return prediction
    
    except Exception as e:
        logger.error(f"Failed to get workload prediction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get workload prediction"
        )


@router.get(
    "/performance/system",
    summary="Get system performance metrics",
    description="Get detailed system performance analysis"
)
async def get_system_performance(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: Dict[str, Any] = Depends(admin_required)
) -> Dict[str, Any]:
    """Get system performance metrics (admin only)."""
    try:
        # Get performance data from various sources
        performance_data = await _get_detailed_performance_metrics(start_date, end_date)
        
        return performance_data
    
    except Exception as e:
        logger.error(f"Failed to get system performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system performance"
        )


# Helper functions

async def _get_conversation_statistics(
    conversation_repo,
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """Get conversation statistics."""
    try:
        # Get conversations in date range
        filters = {
            "created_after": start_date,
            "created_before": end_date
        }
        
        result = conversation_repo.search(filters=filters, page_size=10000)
        conversations = result.items
        
        if not conversations:
            return {
                "total_conversations": 0,
                "avg_duration": 0.0,
                "success_rate": 0.0,
                "avg_satisfaction": 0.0
            }
        
        # Calculate statistics
        total_conversations = len(conversations)
        successful_conversations = len([c for c in conversations if c.status == "completed"])
        success_rate = (successful_conversations / total_conversations) * 100
        
        durations = [c.duration_seconds for c in conversations if c.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        satisfactions = [c.user_satisfaction for c in conversations if c.user_satisfaction]
        avg_satisfaction = sum(satisfactions) / len(satisfactions) if satisfactions else 0.0
        
        return {
            "total_conversations": total_conversations,
            "successful_conversations": successful_conversations,
            "success_rate": round(success_rate, 2),
            "avg_duration": round(avg_duration, 2),
            "avg_satisfaction": round(avg_satisfaction, 2)
        }
    
    except Exception as e:
        logger.error(f"Failed to get conversation statistics: {e}")
        return {}


async def _get_performance_metrics(start_date: datetime, end_date: datetime) -> Dict[str, float]:
    """Get system performance metrics."""
    try:
        # Mock performance metrics - in production, get from monitoring systems
        return {
            "avg_response_time_ms": 250.5,
            "avg_processing_time_ms": 1200.3,
            "system_uptime_percentage": 99.8,
            "error_rate_percentage": 0.2,
            "throughput_requests_per_second": 45.2,
            "memory_usage_percentage": 68.5,
            "cpu_usage_percentage": 42.1,
            "disk_usage_percentage": 35.7
        }
    
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        return {}


async def _get_trending_issues(
    analytics: TicketAnalytics,
    start_date: datetime,
    end_date: datetime
) -> List[Dict[str, Any]]:
    """Get trending issues analysis."""
    try:
        # Get category distribution analysis
        category_analysis = analytics.get_category_distribution_analysis(
            start_date=start_date,
            end_date=end_date
        )
        
        # Convert to trending issues format
        trending = []
        for analysis in category_analysis[:5]:  # Top 5
            trending.append({
                "issue": analysis.category,
                "count": analysis.ticket_count,
                "percentage": analysis.percentage,
                "trend": analysis.trend,
                "avg_resolution_time": analysis.avg_resolution_time,
                "avg_satisfaction": analysis.avg_satisfaction
            })
        
        return trending
    
    except Exception as e:
        logger.error(f"Failed to get trending issues: {e}")
        return []


async def _get_system_health() -> Dict[str, str]:
    """Get system health status."""
    try:
        # Mock system health - in production, check actual services
        return {
            "api_server": "healthy",
            "database": "healthy",
            "redis": "healthy",
            "websocket_service": "healthy",
            "audio_processing": "healthy",
            "ml_services": "healthy",
            "external_integrations": "healthy"
        }
    
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        return {"overall": "unknown"}


async def _get_charts_data(
    analytics: TicketAnalytics,
    start_date: datetime,
    end_date: datetime,
    period: AnalyticsPeriod
) -> Dict[str, List[MetricValue]]:
    """Get data for dashboard charts."""
    try:
        charts_data = {}
        
        # Tickets over time
        trend_period_mapping = {
            AnalyticsPeriod.HOUR: TrendPeriod.DAILY,
            AnalyticsPeriod.DAY: TrendPeriod.DAILY,
            AnalyticsPeriod.WEEK: TrendPeriod.DAILY,
            AnalyticsPeriod.MONTH: TrendPeriod.WEEKLY,
            AnalyticsPeriod.QUARTER: TrendPeriod.WEEKLY,
            AnalyticsPeriod.YEAR: TrendPeriod.MONTHLY
        }
        
        trend_period = trend_period_mapping.get(period, TrendPeriod.DAILY)
        
        # Get ticket trend
        ticket_trend = analytics.get_trend_analysis(
            metric="tickets",
            period=trend_period,
            lookback_days=(end_date - start_date).days
        )
        
        # Convert to chart format
        charts_data["tickets_over_time"] = []
        for point in ticket_trend.data_points:
            charts_data["tickets_over_time"].append(
                MetricValue(
                    timestamp=datetime.fromisoformat(point["period_start"]),
                    value=float(point["value"])
                )
            )
        
        # Response time trend (mock data)
        charts_data["response_time_trend"] = []
        for i in range(7):  # Last 7 days
            date = end_date - timedelta(days=6-i)
            charts_data["response_time_trend"].append(
                MetricValue(
                    timestamp=date,
                    value=30.0 + (i * 2.5)  # Mock trending data
                )
            )
        
        # Satisfaction trend (mock data)
        charts_data["satisfaction_trend"] = []
        for i in range(7):
            date = end_date - timedelta(days=6-i)
            charts_data["satisfaction_trend"].append(
                MetricValue(
                    timestamp=date,
                    value=4.2 + (0.1 * (i % 3))  # Mock data
                )
            )
        
        return charts_data
    
    except Exception as e:
        logger.error(f"Failed to get charts data: {e}")
        return {}


async def _get_detailed_performance_metrics(
    start_date: Optional[datetime],
    end_date: Optional[datetime]
) -> Dict[str, Any]:
    """Get detailed system performance metrics."""
    try:
        # In production, integrate with monitoring systems like Prometheus, Grafana, etc.
        return {
            "api_performance": {
                "avg_response_time_ms": 235.2,
                "p95_response_time_ms": 450.1,
                "p99_response_time_ms": 850.3,
                "error_rate": 0.15,
                "requests_per_second": 42.8
            },
            "websocket_performance": {
                "active_connections": 127,
                "avg_connection_duration": 245.6,
                "messages_per_second": 156.3,
                "connection_success_rate": 99.2
            },
            "audio_processing": {
                "avg_transcription_time_ms": 1250.4,
                "transcription_accuracy": 96.8,
                "audio_chunks_processed": 45623,
                "processing_queue_size": 12
            },
            "database_performance": {
                "avg_query_time_ms": 45.2,
                "connection_pool_usage": 65.4,
                "cache_hit_rate": 89.7,
                "active_connections": 23
            },
            "system_resources": {
                "cpu_usage_percent": 42.1,
                "memory_usage_percent": 68.5,
                "disk_io_ops_per_sec": 234.5,
                "network_throughput_mbps": 15.8
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to get detailed performance metrics: {e}")
        return {}