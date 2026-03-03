"""
Comprehensive alerting system for VoiceHelpDeskAI.

Provides configurable alert rules, thresholds, and notification channels
for monitoring system health, performance, and business metrics.
"""

import asyncio
import time
import smtplib
import json
from typing import Dict, List, Optional, Any, Callable, Union, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from contextlib import contextmanager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading

import httpx
from loguru import logger

from ..config import config_manager
from .logging_system import logging_system, LogLevel, EventType
from .health_check import HealthCheckSystem, HealthStatus
from .metrics_collector import MetricsCollector


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status states."""
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertCondition(Enum):
    """Alert condition operators."""
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    EQUAL = "eq"
    NOT_EQUAL = "ne"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"


@dataclass
class AlertThreshold:
    """Alert threshold configuration."""
    value: Union[int, float, str]
    condition: AlertCondition
    duration: int = 60  # seconds
    
    def check(self, current_value: Union[int, float, str]) -> bool:
        """Check if current value meets threshold condition."""
        try:
            if self.condition == AlertCondition.GREATER_THAN:
                return float(current_value) > float(self.value)
            elif self.condition == AlertCondition.LESS_THAN:
                return float(current_value) < float(self.value)
            elif self.condition == AlertCondition.GREATER_EQUAL:
                return float(current_value) >= float(self.value)
            elif self.condition == AlertCondition.LESS_EQUAL:
                return float(current_value) <= float(self.value)
            elif self.condition == AlertCondition.EQUAL:
                return current_value == self.value
            elif self.condition == AlertCondition.NOT_EQUAL:
                return current_value != self.value
            elif self.condition == AlertCondition.CONTAINS:
                return str(self.value) in str(current_value)
            elif self.condition == AlertCondition.NOT_CONTAINS:
                return str(self.value) not in str(current_value)
        except (ValueError, TypeError):
            logger.error(f"Failed to compare values: {current_value} vs {self.value}")
            return False
        
        return False


@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    description: str
    metric_query: str
    threshold: AlertThreshold
    severity: AlertSeverity
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    notification_channels: List[str] = field(default_factory=list)
    suppress_duration: int = 300  # seconds
    escalation_rules: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class AlertInstance:
    """Active alert instance."""
    rule: AlertRule
    status: AlertStatus
    started_at: datetime
    last_seen: datetime
    resolved_at: Optional[datetime] = None
    current_value: Optional[Union[int, float, str]] = None
    fire_count: int = 0
    notification_sent: bool = False
    suppressed_until: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            'rule_name': self.rule.name,
            'status': self.status.value,
            'severity': self.rule.severity.value,
            'started_at': self.started_at.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'current_value': self.current_value,
            'fire_count': self.fire_count,
            'notification_sent': self.notification_sent,
            'labels': self.rule.labels,
            'annotations': self.rule.annotations
        }
        
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        
        if self.suppressed_until:
            data['suppressed_until'] = self.suppressed_until.isoformat()
        
        return data


class NotificationChannel:
    """Base class for notification channels."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
    
    async def send_notification(self, alert: AlertInstance, message: str) -> bool:
        """Send notification for alert. Override in subclasses."""
        raise NotImplementedError


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel."""
    
    async def send_notification(self, alert: AlertInstance, message: str) -> bool:
        """Send email notification."""
        try:
            smtp_server = self.config.get('smtp_server')
            smtp_port = self.config.get('smtp_port', 587)
            username = self.config.get('username')
            password = self.config.get('password')
            from_email = self.config.get('from_email')
            to_emails = self.config.get('to_emails', [])
            
            if not all([smtp_server, username, password, from_email, to_emails]):
                logger.error("Email configuration incomplete")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = f"[{alert.rule.severity.value.upper()}] {alert.rule.name}"
            
            body = f"""
Alert: {alert.rule.name}
Severity: {alert.rule.severity.value}
Status: {alert.status.value}
Current Value: {alert.current_value}
Started: {alert.started_at}

Description: {alert.rule.description}

{message}
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel."""
    
    async def send_notification(self, alert: AlertInstance, message: str) -> bool:
        """Send Slack notification."""
        try:
            webhook_url = self.config.get('webhook_url')
            if not webhook_url:
                logger.error("Slack webhook URL not configured")
                return False
            
            # Determine color based on severity
            color_map = {
                AlertSeverity.LOW: "#36a64f",      # green
                AlertSeverity.MEDIUM: "#ff9900",   # orange
                AlertSeverity.HIGH: "#ff6600",     # red-orange
                AlertSeverity.CRITICAL: "#ff0000" # red
            }
            
            payload = {
                "attachments": [
                    {
                        "color": color_map.get(alert.rule.severity, "#cccccc"),
                        "title": f"{alert.rule.severity.value.upper()}: {alert.rule.name}",
                        "text": alert.rule.description,
                        "fields": [
                            {
                                "title": "Status",
                                "value": alert.status.value,
                                "short": True
                            },
                            {
                                "title": "Current Value",
                                "value": str(alert.current_value),
                                "short": True
                            },
                            {
                                "title": "Started",
                                "value": alert.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                                "short": True
                            },
                            {
                                "title": "Fire Count",
                                "value": str(alert.fire_count),
                                "short": True
                            }
                        ],
                        "footer": "VoiceHelpDeskAI Monitoring",
                        "ts": int(time.time())
                    }
                ]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False


class WebhookNotificationChannel(NotificationChannel):
    """Generic webhook notification channel."""
    
    async def send_notification(self, alert: AlertInstance, message: str) -> bool:
        """Send webhook notification."""
        try:
            url = self.config.get('url')
            method = self.config.get('method', 'POST').upper()
            headers = self.config.get('headers', {})
            
            if not url:
                logger.error("Webhook URL not configured")
                return False
            
            payload = {
                'alert': alert.to_dict(),
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
            
            async with httpx.AsyncClient() as client:
                if method == 'POST':
                    response = await client.post(url, json=payload, headers=headers)
                else:
                    response = await client.get(url, params=payload, headers=headers)
                
                return response.status_code < 400
                
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False


class AlertingSystem:
    """
    Comprehensive alerting system that monitors metrics,
    evaluates rules, and sends notifications.
    """
    
    def __init__(self, metrics_collector: MetricsCollector, 
                 health_check_system: HealthCheckSystem):
        self.metrics_collector = metrics_collector
        self.health_check_system = health_check_system
        
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, AlertInstance] = {}
        self.notification_channels: Dict[str, NotificationChannel] = {}
        
        self._evaluation_task: Optional[asyncio.Task] = None
        self._evaluation_interval = 30  # seconds
        self._locks = {'rules': threading.Lock(), 'alerts': threading.Lock()}
        
        # Alert history for analysis
        self._alert_history: List[AlertInstance] = []
        self._max_history_size = 1000
        
        # Initialize default rules and channels
        self._setup_default_rules()
        self._setup_notification_channels()
        
        logger.info("Alerting system initialized")
    
    def _setup_default_rules(self):
        """Setup default alert rules."""
        # High API latency
        self.add_rule(AlertRule(
            name="high_api_latency",
            description="API response time is above acceptable threshold",
            metric_query="voicehelpdesk_http_request_duration_seconds",
            threshold=AlertThreshold(value=2.0, condition=AlertCondition.GREATER_THAN, duration=120),
            severity=AlertSeverity.HIGH,
            labels={"category": "performance", "component": "api"},
            annotations={"runbook": "Check API performance, review slow queries"},
            notification_channels=["email", "slack"]
        ))
        
        # High error rate
        self.add_rule(AlertRule(
            name="high_error_rate",
            description="HTTP error rate is above acceptable threshold",
            metric_query="voicehelpdesk_http_requests_total{status=~'5..'}",
            threshold=AlertThreshold(value=0.05, condition=AlertCondition.GREATER_THAN, duration=300),
            severity=AlertSeverity.CRITICAL,
            labels={"category": "reliability", "component": "api"},
            annotations={"runbook": "Investigate error sources, check logs"},
            notification_channels=["email", "slack", "webhook"]
        ))
        
        # High memory usage
        self.add_rule(AlertRule(
            name="high_memory_usage",
            description="Memory usage is above critical threshold",
            metric_query="voicehelpdesk_memory_usage_bytes",
            threshold=AlertThreshold(value=0.9, condition=AlertCondition.GREATER_THAN, duration=180),
            severity=AlertSeverity.HIGH,
            labels={"category": "resources", "component": "system"},
            annotations={"runbook": "Check for memory leaks, restart services if needed"},
            notification_channels=["email", "slack"]
        ))
        
        # Model inference failures
        self.add_rule(AlertRule(
            name="model_inference_failures",
            description="AI model inference failure rate is too high",
            metric_query="voicehelpdesk_model_failures_total",
            threshold=AlertThreshold(value=10, condition=AlertCondition.GREATER_THAN, duration=300),
            severity=AlertSeverity.CRITICAL,
            labels={"category": "ai", "component": "models"},
            annotations={"runbook": "Check model health, verify GPU resources"},
            notification_channels=["email", "slack"]
        ))
        
        # Queue backlog
        self.add_rule(AlertRule(
            name="queue_backlog",
            description="Task queue backlog is too high",
            metric_query="voicehelpdesk_queue_depth",
            threshold=AlertThreshold(value=100, condition=AlertCondition.GREATER_THAN, duration=600),
            severity=AlertSeverity.MEDIUM,
            labels={"category": "performance", "component": "queues"},
            annotations={"runbook": "Scale workers, check task processing"},
            notification_channels=["email"]
        ))
        
        # Redis connection failures
        self.add_rule(AlertRule(
            name="redis_connection_failure",
            description="Redis connection is failing",
            metric_query="redis_health_check",
            threshold=AlertThreshold(value="unhealthy", condition=AlertCondition.EQUAL, duration=60),
            severity=AlertSeverity.CRITICAL,
            labels={"category": "infrastructure", "component": "redis"},
            annotations={"runbook": "Check Redis service, verify network connectivity"},
            notification_channels=["email", "slack", "webhook"]
        ))
        
        # Security incidents
        self.add_rule(AlertRule(
            name="security_incident",
            description="Security incident detected",
            metric_query="security_events",
            threshold=AlertThreshold(value="critical", condition=AlertCondition.CONTAINS, duration=0),
            severity=AlertSeverity.CRITICAL,
            labels={"category": "security", "component": "auth"},
            annotations={"runbook": "Investigate immediately, review audit logs"},
            notification_channels=["email", "slack", "webhook"]
        ))
        
        # Low user satisfaction
        self.add_rule(AlertRule(
            name="low_user_satisfaction",
            description="User satisfaction score is below acceptable level",
            metric_query="voicehelpdesk_user_satisfaction_score",
            threshold=AlertThreshold(value=3.0, condition=AlertCondition.LESS_THAN, duration=1800),
            severity=AlertSeverity.MEDIUM,
            labels={"category": "business", "component": "satisfaction"},
            annotations={"runbook": "Review recent conversations, check model performance"},
            notification_channels=["email"]
        ))
        
        logger.info(f"Initialized {len(self.rules)} default alert rules")
    
    def _setup_notification_channels(self):
        """Setup notification channels from configuration."""
        # Email channel
        email_config = {
            'smtp_server': config_manager.get('VOICEHELPDESK_SMTP_SERVER'),
            'smtp_port': config_manager.get('VOICEHELPDESK_SMTP_PORT', 587),
            'username': config_manager.get('VOICEHELPDESK_SMTP_USERNAME'),
            'password': config_manager.get('VOICEHELPDESK_SMTP_PASSWORD'),
            'from_email': config_manager.get('VOICEHELPDESK_ALERT_FROM_EMAIL'),
            'to_emails': config_manager.get('VOICEHELPDESK_ALERT_TO_EMAILS', '').split(',')
        }
        
        if email_config['smtp_server']:
            self.notification_channels['email'] = EmailNotificationChannel('email', email_config)
        
        # Slack channel
        slack_config = {
            'webhook_url': config_manager.get('VOICEHELPDESK_SLACK_WEBHOOK_URL')
        }
        
        if slack_config['webhook_url']:
            self.notification_channels['slack'] = SlackNotificationChannel('slack', slack_config)
        
        # Webhook channel
        webhook_config = {
            'url': config_manager.get('VOICEHELPDESK_ALERT_WEBHOOK_URL'),
            'method': config_manager.get('VOICEHELPDESK_ALERT_WEBHOOK_METHOD', 'POST'),
            'headers': json.loads(config_manager.get('VOICEHELPDESK_ALERT_WEBHOOK_HEADERS', '{}'))
        }
        
        if webhook_config['url']:
            self.notification_channels['webhook'] = WebhookNotificationChannel('webhook', webhook_config)
        
        logger.info(f"Initialized {len(self.notification_channels)} notification channels")
    
    # ==========================================================================
    # Rule Management
    # ==========================================================================
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        with self._locks['rules']:
            self.rules[rule.name] = rule
            logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove an alert rule."""
        with self._locks['rules']:
            if rule_name in self.rules:
                del self.rules[rule_name]
                # Resolve any active alerts for this rule
                if rule_name in self.active_alerts:
                    self._resolve_alert(rule_name)
                logger.info(f"Removed alert rule: {rule_name}")
    
    def update_rule(self, rule: AlertRule):
        """Update an existing alert rule."""
        with self._locks['rules']:
            if rule.name in self.rules:
                self.rules[rule.name] = rule
                logger.info(f"Updated alert rule: {rule.name}")
            else:
                self.add_rule(rule)
    
    def get_rules(self) -> List[AlertRule]:
        """Get all alert rules."""
        with self._locks['rules']:
            return list(self.rules.values())
    
    def enable_rule(self, rule_name: str):
        """Enable an alert rule."""
        with self._locks['rules']:
            if rule_name in self.rules:
                self.rules[rule_name].enabled = True
                logger.info(f"Enabled alert rule: {rule_name}")
    
    def disable_rule(self, rule_name: str):
        """Disable an alert rule."""
        with self._locks['rules']:
            if rule_name in self.rules:
                self.rules[rule_name].enabled = False
                # Resolve any active alerts for this rule
                if rule_name in self.active_alerts:
                    self._resolve_alert(rule_name)
                logger.info(f"Disabled alert rule: {rule_name}")
    
    # ==========================================================================
    # Alert Evaluation
    # ==========================================================================
    
    async def start_evaluation(self):
        """Start alert evaluation loop."""
        if self._evaluation_task and not self._evaluation_task.done():
            logger.warning("Alert evaluation already running")
            return
        
        self._evaluation_task = asyncio.create_task(self._evaluation_loop())
        logger.info(f"Started alert evaluation (interval: {self._evaluation_interval}s)")
    
    async def stop_evaluation(self):
        """Stop alert evaluation loop."""
        if self._evaluation_task:
            self._evaluation_task.cancel()
            try:
                await self._evaluation_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped alert evaluation")
    
    async def _evaluation_loop(self):
        """Main evaluation loop."""
        while True:
            try:
                await self._evaluate_all_rules()
                await asyncio.sleep(self._evaluation_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Alert evaluation failed: {e}")
                await asyncio.sleep(self._evaluation_interval)
    
    async def _evaluate_all_rules(self):
        """Evaluate all enabled alert rules."""
        with self._locks['rules']:
            enabled_rules = [rule for rule in self.rules.values() if rule.enabled]
        
        # Evaluate rules concurrently
        tasks = [self._evaluate_rule(rule) for rule in enabled_rules]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _evaluate_rule(self, rule: AlertRule):
        """Evaluate a single alert rule."""
        try:
            # Get current metric value
            current_value = await self._get_metric_value(rule.metric_query)
            
            # Check if threshold is met
            threshold_met = rule.threshold.check(current_value)
            
            now = datetime.now()
            
            if threshold_met:
                await self._handle_alert_triggered(rule, current_value, now)
            else:
                await self._handle_alert_resolved(rule, now)
                
        except Exception as e:
            logger.error(f"Failed to evaluate rule {rule.name}: {e}")
    
    async def _get_metric_value(self, metric_query: str) -> Union[int, float, str]:
        """Get current value for metric query."""
        # This is a simplified implementation
        # In a real system, you'd query your metrics backend
        
        if metric_query == "voicehelpdesk_http_request_duration_seconds":
            # Simulate API latency check
            return 1.5  # seconds
        elif metric_query == "voicehelpdesk_memory_usage_bytes":
            # Simulate memory usage check
            return 0.75  # 75%
        elif metric_query == "redis_health_check":
            # Check Redis health
            health_results = await self.health_check_system.run_all_checks()
            redis_check = next((c for c in health_results.checks if c.name == "redis"), None)
            return redis_check.status.value if redis_check else "unknown"
        else:
            # Default placeholder value
            return 0
    
    async def _handle_alert_triggered(self, rule: AlertRule, current_value: Any, timestamp: datetime):
        """Handle when an alert threshold is met."""
        with self._locks['alerts']:
            if rule.name in self.active_alerts:
                # Update existing alert
                alert = self.active_alerts[rule.name]
                alert.last_seen = timestamp
                alert.current_value = current_value
                alert.fire_count += 1
                
                # Check if we need to send notifications
                if not alert.notification_sent and alert.status == AlertStatus.FIRING:
                    await self._send_notifications(alert)
                    alert.notification_sent = True
            else:
                # Create new alert
                alert = AlertInstance(
                    rule=rule,
                    status=AlertStatus.PENDING,
                    started_at=timestamp,
                    last_seen=timestamp,
                    current_value=current_value,
                    fire_count=1
                )
                
                # Check if alert should fire immediately or after duration
                if rule.threshold.duration == 0:
                    alert.status = AlertStatus.FIRING
                    await self._send_notifications(alert)
                    alert.notification_sent = True
                
                self.active_alerts[rule.name] = alert
                
                # Log alert creation
                logging_system.log_event(
                    LogLevel.WARNING if rule.severity in [AlertSeverity.LOW, AlertSeverity.MEDIUM] else LogLevel.ERROR,
                    f"Alert triggered: {rule.name}",
                    EventType.SYSTEM,
                    alert_name=rule.name,
                    severity=rule.severity.value,
                    current_value=current_value
                )
    
    async def _handle_alert_resolved(self, rule: AlertRule, timestamp: datetime):
        """Handle when an alert condition is no longer met."""
        with self._locks['alerts']:
            if rule.name in self.active_alerts:
                alert = self.active_alerts[rule.name]
                
                if alert.status in [AlertStatus.PENDING, AlertStatus.FIRING]:
                    # Resolve the alert
                    alert.status = AlertStatus.RESOLVED
                    alert.resolved_at = timestamp
                    
                    # Send resolution notification
                    await self._send_resolution_notification(alert)
                    
                    # Move to history and remove from active
                    self._add_to_history(alert)
                    del self.active_alerts[rule.name]
                    
                    # Log alert resolution
                    logging_system.log_event(
                        LogLevel.INFO,
                        f"Alert resolved: {rule.name}",
                        EventType.SYSTEM,
                        alert_name=rule.name,
                        duration_seconds=(timestamp - alert.started_at).total_seconds()
                    )
    
    def _resolve_alert(self, rule_name: str):
        """Manually resolve an alert."""
        with self._locks['alerts']:
            if rule_name in self.active_alerts:
                alert = self.active_alerts[rule_name]
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()
                
                self._add_to_history(alert)
                del self.active_alerts[rule_name]
    
    # ==========================================================================
    # Notifications
    # ==========================================================================
    
    async def _send_notifications(self, alert: AlertInstance):
        """Send notifications for an alert."""
        message = self._format_alert_message(alert)
        
        tasks = []
        for channel_name in alert.rule.notification_channels:
            if channel_name in self.notification_channels:
                channel = self.notification_channels[channel_name]
                tasks.append(channel.send_notification(alert, message))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r is True)
            
            logging_system.log_event(
                LogLevel.INFO,
                f"Sent notifications for alert: {alert.rule.name}",
                EventType.SYSTEM,
                alert_name=alert.rule.name,
                notifications_sent=success_count,
                total_channels=len(tasks)
            )
    
    async def _send_resolution_notification(self, alert: AlertInstance):
        """Send resolution notification for an alert."""
        message = self._format_resolution_message(alert)
        
        tasks = []
        for channel_name in alert.rule.notification_channels:
            if channel_name in self.notification_channels:
                channel = self.notification_channels[channel_name]
                tasks.append(channel.send_notification(alert, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def _format_alert_message(self, alert: AlertInstance) -> str:
        """Format alert message for notifications."""
        duration = datetime.now() - alert.started_at
        
        return f"""
🚨 ALERT: {alert.rule.name}

Severity: {alert.rule.severity.value.upper()}
Current Value: {alert.current_value}
Threshold: {alert.rule.threshold.condition.value} {alert.rule.threshold.value}
Duration: {duration}
Fire Count: {alert.fire_count}

{alert.rule.description}

Runbook: {alert.rule.annotations.get('runbook', 'No runbook available')}
"""
    
    def _format_resolution_message(self, alert: AlertInstance) -> str:
        """Format resolution message for notifications."""
        duration = alert.resolved_at - alert.started_at
        
        return f"""
✅ RESOLVED: {alert.rule.name}

Alert has been resolved after {duration}
Final Value: {alert.current_value}
Total Fire Count: {alert.fire_count}
"""
    
    # ==========================================================================
    # Alert Management
    # ==========================================================================
    
    def get_active_alerts(self) -> List[AlertInstance]:
        """Get all active alerts."""
        with self._locks['alerts']:
            return list(self.active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[AlertInstance]:
        """Get alert history."""
        return self._alert_history[-limit:]
    
    def suppress_alert(self, rule_name: str, duration_minutes: int = 60):
        """Suppress an alert for a specified duration."""
        with self._locks['alerts']:
            if rule_name in self.active_alerts:
                alert = self.active_alerts[rule_name]
                alert.status = AlertStatus.SUPPRESSED
                alert.suppressed_until = datetime.now() + timedelta(minutes=duration_minutes)
                
                logger.info(f"Suppressed alert {rule_name} for {duration_minutes} minutes")
    
    def _add_to_history(self, alert: AlertInstance):
        """Add alert to history."""
        self._alert_history.append(alert)
        
        # Maintain history size limit
        if len(self._alert_history) > self._max_history_size:
            self._alert_history = self._alert_history[-self._max_history_size:]
    
    # ==========================================================================
    # Statistics and Analysis
    # ==========================================================================
    
    def get_alert_statistics(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get alert statistics for analysis."""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        recent_alerts = [
            alert for alert in self._alert_history
            if alert.started_at >= cutoff_time
        ]
        
        if not recent_alerts:
            return {
                'total_alerts': 0,
                'by_severity': {},
                'by_rule': {},
                'average_duration': 0,
                'resolution_rate': 0
            }
        
        # Count by severity
        by_severity = {}
        for alert in recent_alerts:
            severity = alert.rule.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        # Count by rule
        by_rule = {}
        for alert in recent_alerts:
            rule_name = alert.rule.name
            by_rule[rule_name] = by_rule.get(rule_name, 0) + 1
        
        # Calculate average duration
        resolved_alerts = [a for a in recent_alerts if a.resolved_at]
        if resolved_alerts:
            durations = [(a.resolved_at - a.started_at).total_seconds() for a in resolved_alerts]
            average_duration = sum(durations) / len(durations)
        else:
            average_duration = 0
        
        # Calculate resolution rate
        resolution_rate = len(resolved_alerts) / len(recent_alerts) if recent_alerts else 0
        
        return {
            'total_alerts': len(recent_alerts),
            'active_alerts': len(self.active_alerts),
            'by_severity': by_severity,
            'by_rule': by_rule,
            'average_duration_seconds': average_duration,
            'resolution_rate': resolution_rate,
            'time_window_hours': time_window_hours
        }


# Global alerting system instance
# Note: This will be initialized with proper dependencies in the main application
alerting_system: Optional[AlertingSystem] = None