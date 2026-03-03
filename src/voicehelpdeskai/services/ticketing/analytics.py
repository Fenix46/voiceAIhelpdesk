"""Ticket analytics for metrics, trends, and predictive analysis."""

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

from ...database import DatabaseManager, get_ticket_repository, get_user_repository
from ...database.models import Ticket, TicketStatus, TicketPriority, TicketCategory, User

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics."""
    RESPONSE_TIME = "response_time"
    RESOLUTION_TIME = "resolution_time"
    SATISFACTION = "satisfaction"
    WORKLOAD = "workload"
    TREND = "trend"


class TrendPeriod(Enum):
    """Trend analysis periods."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


@dataclass
class MetricResult:
    """Result of a metric calculation."""
    metric_type: MetricType
    value: float
    unit: str
    period_start: datetime
    period_end: datetime
    metadata: Dict[str, Any]


@dataclass
class TrendAnalysis:
    """Trend analysis result."""
    metric: str
    period: TrendPeriod
    trend_direction: str  # "increasing", "decreasing", "stable"
    trend_strength: float  # 0.0 to 1.0
    data_points: List[Dict[str, Any]]
    prediction: Optional[Dict[str, Any]] = None


@dataclass
class CategoryAnalysis:
    """Category distribution analysis."""
    category: str
    ticket_count: int
    percentage: float
    avg_resolution_time: Optional[float]
    avg_satisfaction: Optional[float]
    trend: str


@dataclass
class UserPerformance:
    """User performance metrics."""
    user_id: str
    username: str
    department: str
    tickets_handled: int
    avg_resolution_time: Optional[float]
    avg_satisfaction: Optional[float]
    efficiency_score: float
    workload_balance: float


@dataclass
class PredictiveModel:
    """Predictive model for workload forecasting."""
    model_type: str
    accuracy: float
    features_used: List[str]
    prediction_horizon: int  # days
    last_trained: datetime


class TicketAnalytics:
    """
    Comprehensive analytics system for ticket metrics and predictions.
    
    Features:
    - Response time and resolution time analysis
    - User satisfaction tracking
    - Category and priority distribution
    - Trend analysis with forecasting
    - User performance evaluation
    - Predictive workload modeling
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Initialize ticket analytics system."""
        self.db_manager = db_manager or DatabaseManager()
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_timestamps = {}
        
        # ML models for prediction
        self._models = {}
        self._scalers = {}
        
        logger.info("TicketAnalytics initialized")
    
    def get_response_time_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
        priority: Optional[int] = None
    ) -> MetricResult:
        """
        Calculate response time metrics.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            category: Filter by category
            priority: Filter by priority
            
        Returns:
            Response time metrics
        """
        try:
            cache_key = f"response_time_{start_date}_{end_date}_{category}_{priority}"
            
            # Check cache
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]
            
            ticket_repo = get_ticket_repository()
            
            # Build filters
            filters = {}
            if start_date:
                filters["created_after"] = start_date
            if end_date:
                filters["created_before"] = end_date
            if category:
                filters["category"] = [category]
            if priority:
                filters["priority"] = [priority]
            
            # Get tickets with response times
            result = ticket_repo.search(filters=filters, page_size=10000)
            tickets = result.items
            
            response_times = []
            for ticket in tickets:
                if ticket.first_response_time is not None:
                    response_times.append(ticket.first_response_time)
            
            if not response_times:
                metric = MetricResult(
                    metric_type=MetricType.RESPONSE_TIME,
                    value=0.0,
                    unit="minutes",
                    period_start=start_date or datetime.min.replace(tzinfo=timezone.utc),
                    period_end=end_date or datetime.now(timezone.utc),
                    metadata={"count": 0}
                )
            else:
                avg_response_time = statistics.mean(response_times)
                median_response_time = statistics.median(response_times)
                
                metric = MetricResult(
                    metric_type=MetricType.RESPONSE_TIME,
                    value=avg_response_time,
                    unit="minutes",
                    period_start=start_date or datetime.min.replace(tzinfo=timezone.utc),
                    period_end=end_date or datetime.now(timezone.utc),
                    metadata={
                        "count": len(response_times),
                        "median": median_response_time,
                        "min": min(response_times),
                        "max": max(response_times),
                        "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0
                    }
                )
            
            # Cache result
            self._cache[cache_key] = metric
            self._cache_timestamps[cache_key] = datetime.now()
            
            return metric
            
        except Exception as e:
            logger.error(f"Failed to calculate response time metrics: {e}")
            raise
    
    def get_resolution_rate_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "category"
    ) -> Dict[str, Any]:
        """
        Calculate resolution rate metrics.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            group_by: Group results by "category", "priority", or "assignee"
            
        Returns:
            Resolution rate metrics grouped by specified field
        """
        try:
            cache_key = f"resolution_rate_{start_date}_{end_date}_{group_by}"
            
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]
            
            ticket_repo = get_ticket_repository()
            
            # Build filters
            filters = {}
            if start_date:
                filters["created_after"] = start_date
            if end_date:
                filters["created_before"] = end_date
            
            # Get all tickets in period
            result = ticket_repo.search(filters=filters, page_size=10000)
            tickets = result.items
            
            # Group tickets by specified field
            grouped_data = defaultdict(lambda: {"total": 0, "resolved": 0, "avg_time": [], "satisfaction": []})
            
            for ticket in tickets:
                group_key = getattr(ticket, group_by, "unknown")
                grouped_data[group_key]["total"] += 1
                
                if ticket.status in [TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value]:
                    grouped_data[group_key]["resolved"] += 1
                    
                    if ticket.actual_resolution_time:
                        grouped_data[group_key]["avg_time"].append(ticket.actual_resolution_time)
                
                if ticket.customer_satisfaction:
                    grouped_data[group_key]["satisfaction"].append(ticket.customer_satisfaction)
            
            # Calculate metrics for each group
            metrics = {}
            for group_key, data in grouped_data.items():
                resolution_rate = (data["resolved"] / data["total"]) * 100 if data["total"] > 0 else 0
                avg_resolution_time = statistics.mean(data["avg_time"]) if data["avg_time"] else None
                avg_satisfaction = statistics.mean(data["satisfaction"]) if data["satisfaction"] else None
                
                metrics[group_key] = {
                    "total_tickets": data["total"],
                    "resolved_tickets": data["resolved"],
                    "resolution_rate": round(resolution_rate, 2),
                    "avg_resolution_time_hours": round(avg_resolution_time / 60, 2) if avg_resolution_time else None,
                    "avg_satisfaction": round(avg_satisfaction, 2) if avg_satisfaction else None
                }
            
            result = {
                "period_start": start_date.isoformat() if start_date else None,
                "period_end": end_date.isoformat() if end_date else None,
                "group_by": group_by,
                "metrics": metrics,
                "overall": {
                    "total_tickets": sum(data["total"] for data in grouped_data.values()),
                    "resolved_tickets": sum(data["resolved"] for data in grouped_data.values()),
                    "overall_resolution_rate": round(
                        (sum(data["resolved"] for data in grouped_data.values()) /
                         sum(data["total"] for data in grouped_data.values())) * 100
                        if sum(data["total"] for data in grouped_data.values()) > 0 else 0, 2
                    )
                }
            }
            
            self._cache[cache_key] = result
            self._cache_timestamps[cache_key] = datetime.now()
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to calculate resolution rate metrics: {e}")
            raise
    
    def get_user_satisfaction_analysis(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Analyze user satisfaction scores.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            User satisfaction analysis
        """
        try:
            cache_key = f"satisfaction_{start_date}_{end_date}"
            
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]
            
            ticket_repo = get_ticket_repository()
            
            # Build filters
            filters = {"has_satisfaction": True}
            if start_date:
                filters["created_after"] = start_date
            if end_date:
                filters["created_before"] = end_date
            
            result = ticket_repo.search(filters=filters, page_size=10000)
            tickets = result.items
            
            if not tickets:
                return {"error": "No tickets with satisfaction scores found"}
            
            # Extract satisfaction scores
            satisfaction_scores = [ticket.customer_satisfaction for ticket in tickets if ticket.customer_satisfaction]
            
            if not satisfaction_scores:
                return {"error": "No valid satisfaction scores found"}
            
            # Calculate statistics
            avg_satisfaction = statistics.mean(satisfaction_scores)
            median_satisfaction = statistics.median(satisfaction_scores)
            
            # Distribution analysis
            distribution = {i: satisfaction_scores.count(i) for i in range(1, 6)}
            
            # Category breakdown
            category_satisfaction = defaultdict(list)
            for ticket in tickets:
                if ticket.customer_satisfaction:
                    category_satisfaction[ticket.category].append(ticket.customer_satisfaction)
            
            category_analysis = {}
            for category, scores in category_satisfaction.items():
                if scores:
                    category_analysis[category] = {
                        "count": len(scores),
                        "avg_satisfaction": round(statistics.mean(scores), 2),
                        "distribution": {i: scores.count(i) for i in range(1, 6)}
                    }
            
            analysis = {
                "period_start": start_date.isoformat() if start_date else None,
                "period_end": end_date.isoformat() if end_date else None,
                "total_responses": len(satisfaction_scores),
                "avg_satisfaction": round(avg_satisfaction, 2),
                "median_satisfaction": median_satisfaction,
                "distribution": distribution,
                "satisfaction_rate": round((sum(1 for s in satisfaction_scores if s >= 4) / len(satisfaction_scores)) * 100, 2),
                "category_breakdown": category_analysis,
                "trends": self._calculate_satisfaction_trends(tickets)
            }
            
            self._cache[cache_key] = analysis
            self._cache_timestamps[cache_key] = datetime.now()
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze user satisfaction: {e}")
            raise
    
    def get_category_distribution_analysis(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[CategoryAnalysis]:
        """
        Analyze ticket distribution by category.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            List of category analyses
        """
        try:
            ticket_repo = get_ticket_repository()
            
            # Build filters
            filters = {}
            if start_date:
                filters["created_after"] = start_date
            if end_date:
                filters["created_before"] = end_date
            
            result = ticket_repo.search(filters=filters, page_size=10000)
            tickets = result.items
            
            if not tickets:
                return []
            
            total_tickets = len(tickets)
            
            # Group by category
            category_data = defaultdict(lambda: {
                "count": 0,
                "resolution_times": [],
                "satisfaction_scores": []
            })
            
            for ticket in tickets:
                category = ticket.category
                category_data[category]["count"] += 1
                
                if ticket.actual_resolution_time:
                    category_data[category]["resolution_times"].append(ticket.actual_resolution_time)
                
                if ticket.customer_satisfaction:
                    category_data[category]["satisfaction_scores"].append(ticket.customer_satisfaction)
            
            # Calculate trends for each category
            category_trends = self._calculate_category_trends(tickets)
            
            # Build analysis results
            analyses = []
            for category, data in category_data.items():
                avg_resolution_time = statistics.mean(data["resolution_times"]) if data["resolution_times"] else None
                avg_satisfaction = statistics.mean(data["satisfaction_scores"]) if data["satisfaction_scores"] else None
                
                analysis = CategoryAnalysis(
                    category=category,
                    ticket_count=data["count"],
                    percentage=round((data["count"] / total_tickets) * 100, 2),
                    avg_resolution_time=round(avg_resolution_time / 60, 2) if avg_resolution_time else None,
                    avg_satisfaction=round(avg_satisfaction, 2) if avg_satisfaction else None,
                    trend=category_trends.get(category, "stable")
                )
                analyses.append(analysis)
            
            # Sort by ticket count descending
            analyses.sort(key=lambda x: x.ticket_count, reverse=True)
            
            return analyses
            
        except Exception as e:
            logger.error(f"Failed to analyze category distribution: {e}")
            raise
    
    def get_trend_analysis(
        self,
        metric: str,
        period: TrendPeriod = TrendPeriod.WEEKLY,
        lookback_days: int = 90
    ) -> TrendAnalysis:
        """
        Perform trend analysis on specified metric.
        
        Args:
            metric: Metric to analyze ("tickets", "resolution_time", "satisfaction")
            period: Period for trend analysis
            lookback_days: Number of days to look back
            
        Returns:
            Trend analysis result
        """
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=lookback_days)
            
            ticket_repo = get_ticket_repository()
            
            filters = {
                "created_after": start_date,
                "created_before": end_date
            }
            
            result = ticket_repo.search(filters=filters, page_size=10000)
            tickets = result.items
            
            # Group data by period
            data_points = self._group_tickets_by_period(tickets, period, start_date, end_date)
            
            # Extract values for trend calculation
            values = [point["value"] for point in data_points]
            
            if len(values) < 3:
                return TrendAnalysis(
                    metric=metric,
                    period=period,
                    trend_direction="insufficient_data",
                    trend_strength=0.0,
                    data_points=data_points
                )
            
            # Calculate trend
            x = np.arange(len(values)).reshape(-1, 1)
            y = np.array(values)
            
            model = LinearRegression()
            model.fit(x, y)
            
            # Determine trend direction and strength
            slope = model.coef_[0]
            score = model.score(x, y)  # R-squared
            
            if abs(slope) < 0.01:
                direction = "stable"
            elif slope > 0:
                direction = "increasing"
            else:
                direction = "decreasing"
            
            # Generate prediction
            future_x = np.array([[len(values)], [len(values) + 1]])
            prediction_values = model.predict(future_x)
            
            prediction = {
                "next_period": float(prediction_values[0]),
                "following_period": float(prediction_values[1]),
                "confidence": score
            }
            
            return TrendAnalysis(
                metric=metric,
                period=period,
                trend_direction=direction,
                trend_strength=score,
                data_points=data_points,
                prediction=prediction
            )
            
        except Exception as e:
            logger.error(f"Failed to perform trend analysis: {e}")
            raise
    
    def get_user_performance_analysis(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        department: Optional[str] = None
    ) -> List[UserPerformance]:
        """
        Analyze user performance metrics.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            department: Filter by department
            
        Returns:
            List of user performance analyses
        """
        try:
            ticket_repo = get_ticket_repository()
            user_repo = get_user_repository()
            
            # Build filters
            filters = {"assigned_only": True}
            if start_date:
                filters["created_after"] = start_date
            if end_date:
                filters["created_before"] = end_date
            
            result = ticket_repo.search(filters=filters, page_size=10000)
            tickets = result.items
            
            # Group tickets by assigned user
            user_data = defaultdict(lambda: {
                "tickets": [],
                "resolution_times": [],
                "satisfaction_scores": []
            })
            
            for ticket in tickets:
                if ticket.assigned_to:
                    user_data[ticket.assigned_to]["tickets"].append(ticket)
                    
                    if ticket.actual_resolution_time:
                        user_data[ticket.assigned_to]["resolution_times"].append(ticket.actual_resolution_time)
                    
                    if ticket.customer_satisfaction:
                        user_data[ticket.assigned_to]["satisfaction_scores"].append(ticket.customer_satisfaction)
            
            # Calculate performance metrics
            performances = []
            all_resolution_times = [t.actual_resolution_time for t in tickets if t.actual_resolution_time]
            avg_system_resolution = statistics.mean(all_resolution_times) if all_resolution_times else None
            
            for user_id, data in user_data.items():
                user = user_repo.get_by_id(user_id)
                if not user or (department and user.department != department):
                    continue
                
                tickets_handled = len(data["tickets"])
                avg_resolution_time = statistics.mean(data["resolution_times"]) if data["resolution_times"] else None
                avg_satisfaction = statistics.mean(data["satisfaction_scores"]) if data["satisfaction_scores"] else None
                
                # Calculate efficiency score (relative to system average)
                efficiency_score = 1.0
                if avg_resolution_time and avg_system_resolution:
                    efficiency_score = max(0.0, min(2.0, avg_system_resolution / avg_resolution_time))
                
                # Calculate workload balance (relative to team average)
                workload_balance = 1.0  # Placeholder - would calculate based on team averages
                
                performance = UserPerformance(
                    user_id=user_id,
                    username=user.username,
                    department=user.department or "Unknown",
                    tickets_handled=tickets_handled,
                    avg_resolution_time=round(avg_resolution_time / 60, 2) if avg_resolution_time else None,
                    avg_satisfaction=round(avg_satisfaction, 2) if avg_satisfaction else None,
                    efficiency_score=round(efficiency_score, 2),
                    workload_balance=round(workload_balance, 2)
                )
                performances.append(performance)
            
            # Sort by efficiency score descending
            performances.sort(key=lambda x: x.efficiency_score, reverse=True)
            
            return performances
            
        except Exception as e:
            logger.error(f"Failed to analyze user performance: {e}")
            raise
    
    def predict_workload(
        self,
        forecast_days: int = 7,
        confidence_interval: float = 0.95
    ) -> Dict[str, Any]:
        """
        Predict future ticket workload using machine learning.
        
        Args:
            forecast_days: Number of days to forecast
            confidence_interval: Confidence interval for predictions
            
        Returns:
            Workload predictions with confidence intervals
        """
        try:
            # Get historical data
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=180)  # 6 months of data
            
            ticket_repo = get_ticket_repository()
            filters = {
                "created_after": start_date,
                "created_before": end_date
            }
            
            result = ticket_repo.search(filters=filters, page_size=10000)
            tickets = result.items
            
            if len(tickets) < 50:  # Need sufficient data
                return {"error": "Insufficient historical data for prediction"}
            
            # Prepare features
            features_data = self._prepare_features_for_prediction(tickets)
            
            if not features_data:
                return {"error": "Failed to prepare features for prediction"}
            
            # Train or use existing model
            model = self._get_or_train_workload_model(features_data)
            
            # Generate predictions
            predictions = self._generate_workload_predictions(model, forecast_days)
            
            return {
                "forecast_days": forecast_days,
                "predictions": predictions,
                "model_info": {
                    "type": model.get("type", "unknown"),
                    "accuracy": model.get("accuracy", 0.0),
                    "last_trained": model.get("last_trained", "unknown")
                },
                "confidence_interval": confidence_interval
            }
            
        except Exception as e:
            logger.error(f"Failed to predict workload: {e}")
            return {"error": str(e)}
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is valid."""
        if cache_key not in self._cache:
            return False
        
        timestamp = self._cache_timestamps.get(cache_key)
        if not timestamp:
            return False
        
        age = (datetime.now() - timestamp).total_seconds()
        return age < self._cache_ttl
    
    def _calculate_satisfaction_trends(self, tickets: List[Ticket]) -> Dict[str, str]:
        """Calculate satisfaction trends over time."""
        # Group tickets by month and calculate average satisfaction
        monthly_satisfaction = defaultdict(list)
        
        for ticket in tickets:
            if ticket.customer_satisfaction and ticket.created_at:
                month_key = ticket.created_at.strftime("%Y-%m")
                monthly_satisfaction[month_key].append(ticket.customer_satisfaction)
        
        # Calculate trend
        if len(monthly_satisfaction) < 2:
            return {"overall": "insufficient_data"}
        
        monthly_averages = []
        for month in sorted(monthly_satisfaction.keys()):
            avg = statistics.mean(monthly_satisfaction[month])
            monthly_averages.append(avg)
        
        # Simple trend calculation
        if len(monthly_averages) >= 3:
            recent_avg = statistics.mean(monthly_averages[-2:])
            earlier_avg = statistics.mean(monthly_averages[:-2])
            
            if recent_avg > earlier_avg + 0.2:
                trend = "improving"
            elif recent_avg < earlier_avg - 0.2:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {"overall": trend}
    
    def _calculate_category_trends(self, tickets: List[Ticket]) -> Dict[str, str]:
        """Calculate trends for each category."""
        # Group tickets by category and month
        category_monthly = defaultdict(lambda: defaultdict(int))
        
        for ticket in tickets:
            if ticket.created_at:
                month_key = ticket.created_at.strftime("%Y-%m")
                category_monthly[ticket.category][month_key] += 1
        
        trends = {}
        for category, monthly_data in category_monthly.items():
            if len(monthly_data) < 2:
                trends[category] = "stable"
                continue
            
            # Simple trend based on last two months vs earlier months
            sorted_months = sorted(monthly_data.keys())
            if len(sorted_months) >= 3:
                recent_count = sum(monthly_data[m] for m in sorted_months[-2:])
                earlier_count = sum(monthly_data[m] for m in sorted_months[:-2])
                
                if recent_count > earlier_count * 1.2:
                    trends[category] = "increasing"
                elif recent_count < earlier_count * 0.8:
                    trends[category] = "decreasing"
                else:
                    trends[category] = "stable"
            else:
                trends[category] = "stable"
        
        return trends
    
    def _group_tickets_by_period(
        self,
        tickets: List[Ticket],
        period: TrendPeriod,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Group tickets by time period."""
        data_points = []
        
        if period == TrendPeriod.DAILY:
            delta = timedelta(days=1)
        elif period == TrendPeriod.WEEKLY:
            delta = timedelta(weeks=1)
        elif period == TrendPeriod.MONTHLY:
            delta = timedelta(days=30)
        else:
            delta = timedelta(days=90)
        
        current_date = start_date
        while current_date < end_date:
            period_end = min(current_date + delta, end_date)
            
            # Count tickets in this period
            period_tickets = [
                t for t in tickets
                if t.created_at and current_date <= t.created_at < period_end
            ]
            
            data_points.append({
                "period_start": current_date.isoformat(),
                "period_end": period_end.isoformat(),
                "value": len(period_tickets),
                "tickets": period_tickets
            })
            
            current_date = period_end
        
        return data_points
    
    def _prepare_features_for_prediction(self, tickets: List[Ticket]) -> Optional[List[Dict[str, Any]]]:
        """Prepare features for ML prediction."""
        try:
            # Group tickets by day
            daily_data = defaultdict(lambda: {
                "count": 0,
                "high_priority": 0,
                "categories": defaultdict(int),
                "day_of_week": 0,
                "month": 0
            })
            
            for ticket in tickets:
                if ticket.created_at:
                    date_key = ticket.created_at.date()
                    daily_data[date_key]["count"] += 1
                    daily_data[date_key]["day_of_week"] = ticket.created_at.weekday()
                    daily_data[date_key]["month"] = ticket.created_at.month
                    
                    if ticket.priority >= 4:
                        daily_data[date_key]["high_priority"] += 1
                    
                    daily_data[date_key]["categories"][ticket.category] += 1
            
            # Convert to feature vectors
            features = []
            for date, data in daily_data.items():
                features.append({
                    "date": date,
                    "ticket_count": data["count"],
                    "high_priority_count": data["high_priority"],
                    "day_of_week": data["day_of_week"],
                    "month": data["month"],
                    "software_tickets": data["categories"].get("software", 0),
                    "hardware_tickets": data["categories"].get("hardware", 0),
                    "network_tickets": data["categories"].get("network", 0)
                })
            
            return sorted(features, key=lambda x: x["date"])
            
        except Exception as e:
            logger.error(f"Failed to prepare features: {e}")
            return None
    
    def _get_or_train_workload_model(self, features_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get existing model or train new one."""
        model_key = "workload_prediction"
        
        if model_key in self._models:
            model_info = self._models[model_key]
            # Check if model needs retraining (older than 7 days)
            if (datetime.now() - model_info["last_trained"]).days < 7:
                return model_info
        
        # Train new model
        try:
            # Prepare training data
            X = []
            y = []
            
            for i, features in enumerate(features_data[:-1]):  # Exclude last day for prediction
                X.append([
                    features["day_of_week"],
                    features["month"],
                    features_data[max(0, i-1)]["ticket_count"],  # Previous day count
                    features_data[max(0, i-6):i+1],  # Last week average
                ])
                y.append(features_data[i+1]["ticket_count"])  # Next day count
            
            if len(X) < 10:
                # Fallback to simple average
                avg_tickets = statistics.mean([f["ticket_count"] for f in features_data])
                return {
                    "type": "average",
                    "model": None,
                    "accuracy": 0.0,
                    "last_trained": datetime.now(),
                    "avg_tickets": avg_tickets
                }
            
            # Flatten X for sklearn
            X_processed = []
            for x in X:
                row = [x[0], x[1], x[2]]  # day_of_week, month, prev_day_count
                # Add week average
                week_data = x[3] if isinstance(x[3], list) else [x[3]]
                week_avg = statistics.mean([d.get("ticket_count", 0) for d in week_data]) if week_data else 0
                row.append(week_avg)
                X_processed.append(row)
            
            X_array = np.array(X_processed)
            y_array = np.array(y)
            
            # Train model
            model = RandomForestRegressor(n_estimators=50, random_state=42)
            model.fit(X_array, y_array)
            
            # Calculate accuracy (simple R-squared)
            predictions = model.predict(X_array)
            accuracy = model.score(X_array, y_array)
            
            model_info = {
                "type": "random_forest",
                "model": model,
                "accuracy": accuracy,
                "last_trained": datetime.now(),
                "features": ["day_of_week", "month", "prev_day_count", "week_avg"]
            }
            
            self._models[model_key] = model_info
            return model_info
            
        except Exception as e:
            logger.error(f"Failed to train model: {e}")
            # Fallback to average
            avg_tickets = statistics.mean([f["ticket_count"] for f in features_data])
            return {
                "type": "average",
                "model": None,
                "accuracy": 0.0,
                "last_trained": datetime.now(),
                "avg_tickets": avg_tickets
            }
    
    def _generate_workload_predictions(
        self,
        model_info: Dict[str, Any],
        forecast_days: int
    ) -> List[Dict[str, Any]]:
        """Generate workload predictions."""
        predictions = []
        
        try:
            if model_info["type"] == "average":
                # Simple average-based prediction
                avg_tickets = model_info.get("avg_tickets", 0)
                
                for i in range(forecast_days):
                    date = datetime.now(timezone.utc) + timedelta(days=i+1)
                    predictions.append({
                        "date": date.date().isoformat(),
                        "predicted_tickets": round(avg_tickets),
                        "confidence_lower": max(0, round(avg_tickets * 0.8)),
                        "confidence_upper": round(avg_tickets * 1.2)
                    })
            
            else:
                # ML model prediction
                model = model_info["model"]
                
                for i in range(forecast_days):
                    date = datetime.now(timezone.utc) + timedelta(days=i+1)
                    
                    # Prepare features for prediction
                    features = [
                        date.weekday(),  # day_of_week
                        date.month,      # month
                        predictions[-1]["predicted_tickets"] if predictions else 0,  # prev_day_count
                        0  # week_avg (placeholder)
                    ]
                    
                    prediction = model.predict([features])[0]
                    
                    predictions.append({
                        "date": date.date().isoformat(),
                        "predicted_tickets": max(0, round(prediction)),
                        "confidence_lower": max(0, round(prediction * 0.7)),
                        "confidence_upper": round(prediction * 1.3)
                    })
            
            return predictions
            
        except Exception as e:
            logger.error(f"Failed to generate predictions: {e}")
            return []