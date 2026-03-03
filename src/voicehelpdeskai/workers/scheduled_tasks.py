"""Scheduled task management for periodic operations."""

import asyncio
import json
import os
import shutil
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import schedule
from celery.beat import PersistentScheduler
from celery.schedules import crontab
import redis.asyncio as redis

from ..core.config import settings
from ..core.logging import get_logger
from ..database import DatabaseManager
from .celery_app import celery_app

logger = get_logger(__name__)


class ScheduleType(Enum):
    """Types of scheduled tasks."""
    INTERVAL = "interval"
    CRON = "cron"
    ONCE = "once"


@dataclass
class ScheduledTaskInfo:
    """Information about a scheduled task."""
    task_id: str
    name: str
    task_func: str
    schedule_type: ScheduleType
    schedule_config: Dict[str, Any]
    next_run: datetime
    last_run: Optional[datetime]
    run_count: int
    success_count: int
    failure_count: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ScheduledTaskManager:
    """Manages scheduled tasks for maintenance and automation."""
    
    def __init__(self):
        self.redis_client = None
        self.scheduler = None
        self.scheduled_tasks: Dict[str, ScheduledTaskInfo] = {}
        self.is_running = False
        self.task_registry = {}
        
        # Register built-in tasks
        self._register_builtin_tasks()
    
    async def initialize(self):
        """Initialize the scheduled task manager."""
        try:
            # Initialize Redis connection
            redis_url = settings.redis_url or 'redis://localhost:6379/0'
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            await self.redis_client.ping()
            
            # Load scheduled tasks from storage
            await self._load_scheduled_tasks()
            
            logger.info("ScheduledTaskManager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ScheduledTaskManager: {e}")
            raise
    
    def _register_builtin_tasks(self):
        """Register built-in scheduled tasks."""
        
        # Database cleanup tasks
        self.task_registry['database_cleanup'] = {
            'name': 'Database Cleanup',
            'func': self._database_cleanup_task,
            'description': 'Clean up old records and optimize database'
        }
        
        # Cache invalidation
        self.task_registry['cache_invalidation'] = {
            'name': 'Cache Invalidation',
            'func': self._cache_invalidation_task,
            'description': 'Invalidate expired cache entries'
        }
        
        # Model updates
        self.task_registry['model_updates'] = {
            'name': 'Model Updates',
            'func': self._model_updates_task,
            'description': 'Check and update AI models'
        }
        
        # Report generation
        self.task_registry['report_generation'] = {
            'name': 'Report Generation',
            'func': self._report_generation_task,
            'description': 'Generate periodic reports'
        }
        
        # Backup execution
        self.task_registry['backup_execution'] = {
            'name': 'Backup Execution',
            'func': self._backup_execution_task,
            'description': 'Execute database and file backups'
        }
        
        # Health monitoring
        self.task_registry['health_monitoring'] = {
            'name': 'Health Monitoring',
            'func': self._health_monitoring_task,
            'description': 'Monitor system health and send alerts'
        }
        
        # Session cleanup
        self.task_registry['session_cleanup'] = {
            'name': 'Session Cleanup',
            'func': self._session_cleanup_task,
            'description': 'Clean up expired user sessions'
        }
        
        # Log rotation
        self.task_registry['log_rotation'] = {
            'name': 'Log Rotation',
            'func': self._log_rotation_task,
            'description': 'Rotate and archive log files'
        }
        
        # Metrics aggregation
        self.task_registry['metrics_aggregation'] = {
            'name': 'Metrics Aggregation',
            'func': self._metrics_aggregation_task,
            'description': 'Aggregate and store metrics data'
        }
        
        # File cleanup
        self.task_registry['file_cleanup'] = {
            'name': 'File Cleanup',
            'func': self._file_cleanup_task,
            'description': 'Clean up temporary and old files'
        }
    
    async def start(self):
        """Start the scheduled task manager."""
        try:
            if self.is_running:
                logger.warning("ScheduledTaskManager is already running")
                return
            
            self.is_running = True
            
            # Set up default scheduled tasks if none exist
            await self._setup_default_schedules()
            
            # Start the scheduler loop
            asyncio.create_task(self._scheduler_loop())
            
            logger.info("ScheduledTaskManager started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start ScheduledTaskManager: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop the scheduled task manager."""
        try:
            self.is_running = False
            
            # Save current state
            await self._save_scheduled_tasks()
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info("ScheduledTaskManager stopped")
            
        except Exception as e:
            logger.error(f"Error stopping ScheduledTaskManager: {e}")
    
    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.is_running:
            try:
                current_time = datetime.now(timezone.utc)
                
                # Check each scheduled task
                for task_id, task_info in self.scheduled_tasks.items():
                    if (task_info.enabled and 
                        task_info.next_run <= current_time):
                        
                        # Execute the task
                        await self._execute_scheduled_task(task_info)
                
                # Sleep for 30 seconds between checks
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _execute_scheduled_task(self, task_info: ScheduledTaskInfo):
        """Execute a scheduled task."""
        try:
            logger.info(f"Executing scheduled task: {task_info.name}")
            
            # Get task function
            task_func = self.task_registry.get(task_info.task_func, {}).get('func')
            if not task_func:
                logger.error(f"Task function not found: {task_info.task_func}")
                return
            
            start_time = time.time()
            
            try:
                # Execute task function
                result = await task_func()
                
                # Update success stats
                task_info.success_count += 1
                task_info.last_run = datetime.now(timezone.utc)
                task_info.run_count += 1
                
                execution_time = time.time() - start_time
                
                logger.info(
                    f"Scheduled task '{task_info.name}' completed successfully in {execution_time:.2f}s"
                )
                
                # Store execution result
                await self._store_task_result(task_info.task_id, 'success', result, execution_time)
                
            except Exception as e:
                # Update failure stats
                task_info.failure_count += 1
                task_info.last_run = datetime.now(timezone.utc)
                task_info.run_count += 1
                
                execution_time = time.time() - start_time
                
                logger.error(f"Scheduled task '{task_info.name}' failed: {e}")
                
                # Store execution result
                await self._store_task_result(task_info.task_id, 'failure', str(e), execution_time)
            
            # Calculate next run time
            task_info.next_run = self._calculate_next_run(task_info)
            task_info.updated_at = datetime.now(timezone.utc)
            
            # Save updated task info
            await self._save_scheduled_tasks()
            
        except Exception as e:
            logger.error(f"Error executing scheduled task {task_info.name}: {e}")
    
    def _calculate_next_run(self, task_info: ScheduledTaskInfo) -> datetime:
        """Calculate next run time for a scheduled task."""
        try:
            current_time = datetime.now(timezone.utc)
            schedule_config = task_info.schedule_config
            
            if task_info.schedule_type == ScheduleType.INTERVAL:
                # Interval-based scheduling
                interval_seconds = schedule_config.get('seconds', 0)
                interval_minutes = schedule_config.get('minutes', 0)
                interval_hours = schedule_config.get('hours', 0)
                interval_days = schedule_config.get('days', 0)
                
                total_seconds = (
                    interval_seconds +
                    interval_minutes * 60 +
                    interval_hours * 3600 +
                    interval_days * 86400
                )
                
                return current_time + timedelta(seconds=total_seconds)
            
            elif task_info.schedule_type == ScheduleType.CRON:
                # Cron-based scheduling (simplified)
                hour = schedule_config.get('hour', 0)
                minute = schedule_config.get('minute', 0)
                day_of_week = schedule_config.get('day_of_week', None)
                day_of_month = schedule_config.get('day_of_month', None)
                
                # Calculate next run based on cron expression
                next_run = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If time has passed today, schedule for tomorrow
                if next_run <= current_time:
                    next_run += timedelta(days=1)
                
                return next_run
            
            elif task_info.schedule_type == ScheduleType.ONCE:
                # One-time execution
                run_at = schedule_config.get('run_at')
                if run_at:
                    return datetime.fromisoformat(run_at)
                else:
                    return current_time + timedelta(seconds=60)  # Default to 1 minute
            
            else:
                # Default fallback
                return current_time + timedelta(hours=1)
                
        except Exception as e:
            logger.error(f"Error calculating next run time: {e}")
            return datetime.now(timezone.utc) + timedelta(hours=1)
    
    async def _setup_default_schedules(self):
        """Set up default scheduled tasks if none exist."""
        try:
            if not self.scheduled_tasks:
                # Database cleanup - daily at 2 AM
                await self.schedule_task(
                    name="Daily Database Cleanup",
                    task_func="database_cleanup",
                    schedule_type=ScheduleType.CRON,
                    schedule_config={'hour': 2, 'minute': 0}
                )
                
                # Cache invalidation - every 15 minutes
                await self.schedule_task(
                    name="Cache Invalidation",
                    task_func="cache_invalidation",
                    schedule_type=ScheduleType.INTERVAL,
                    schedule_config={'minutes': 15}
                )
                
                # Health monitoring - every 5 minutes
                await self.schedule_task(
                    name="System Health Check",
                    task_func="health_monitoring",
                    schedule_type=ScheduleType.INTERVAL,
                    schedule_config={'minutes': 5}
                )
                
                # Session cleanup - every 30 minutes
                await self.schedule_task(
                    name="Session Cleanup",
                    task_func="session_cleanup",
                    schedule_type=ScheduleType.INTERVAL,
                    schedule_config={'minutes': 30}
                )
                
                # Backup - daily at 3 AM
                await self.schedule_task(
                    name="Daily Backup",
                    task_func="backup_execution",
                    schedule_type=ScheduleType.CRON,
                    schedule_config={'hour': 3, 'minute': 0}
                )
                
                # File cleanup - daily at 1 AM
                await self.schedule_task(
                    name="File Cleanup",
                    task_func="file_cleanup",
                    schedule_type=ScheduleType.CRON,
                    schedule_config={'hour': 1, 'minute': 0}
                )
                
                # Weekly report - Mondays at 9 AM
                await self.schedule_task(
                    name="Weekly Report",
                    task_func="report_generation",
                    schedule_type=ScheduleType.CRON,
                    schedule_config={'hour': 9, 'minute': 0, 'day_of_week': 1}
                )
                
                logger.info("Set up default scheduled tasks")
        
        except Exception as e:
            logger.error(f"Failed to setup default schedules: {e}")
    
    # Built-in task implementations
    
    async def _database_cleanup_task(self) -> Dict[str, Any]:
        """Clean up old database records."""
        try:
            db_manager = DatabaseManager()
            
            # Clean up old conversations (older than 90 days)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)
            
            results = {
                'conversations_cleaned': 0,
                'sessions_cleaned': 0,
                'temp_files_cleaned': 0
            }
            
            # Clean conversations
            conversation_repo = db_manager.get_conversation_repository()
            old_conversations = conversation_repo.find_older_than(cutoff_date)
            
            for conversation in old_conversations:
                # Archive or delete conversation data
                if conversation.status in ['completed', 'cancelled', 'expired']:
                    conversation_repo.delete(conversation.id)
                    results['conversations_cleaned'] += 1
            
            # Clean up expired sessions
            from ..core.auth.session_manager import SessionManager
            session_manager = SessionManager()
            cleaned_sessions = await session_manager.cleanup_expired_sessions()
            results['sessions_cleaned'] = cleaned_sessions
            
            # Optimize database
            db_manager.optimize_database()
            
            logger.info(f"Database cleanup completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Database cleanup failed: {e}")
            raise
    
    async def _cache_invalidation_task(self) -> Dict[str, Any]:
        """Invalidate expired cache entries."""
        try:
            if not self.redis_client:
                return {'status': 'skipped', 'reason': 'no_redis_client'}
            
            # Get all cache keys
            cache_pattern = "cache:*"
            keys = await self.redis_client.keys(cache_pattern)
            
            invalidated_count = 0
            for key in keys:
                try:
                    ttl = await self.redis_client.ttl(key)
                    if ttl == -1:  # No expiration set
                        # Set default expiration (1 hour)
                        await self.redis_client.expire(key, 3600)
                    elif ttl == -2:  # Key doesn't exist or expired
                        invalidated_count += 1
                except Exception as e:
                    logger.warning(f"Error processing cache key {key}: {e}")
            
            # Also clean up analytics cache
            analytics_pattern = "analytics:*"
            analytics_keys = await self.redis_client.keys(analytics_pattern)
            
            for key in analytics_keys:
                try:
                    # Analytics cache expires after 1 hour
                    ttl = await self.redis_client.ttl(key)
                    if ttl > 3600:  # Expire if older than 1 hour
                        await self.redis_client.expire(key, 0)
                        invalidated_count += 1
                except Exception:
                    pass
            
            result = {
                'total_keys_checked': len(keys) + len(analytics_keys),
                'invalidated_count': invalidated_count,
                'status': 'completed'
            }
            
            logger.info(f"Cache invalidation completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            raise
    
    async def _model_updates_task(self) -> Dict[str, Any]:
        """Check and update AI models."""
        try:
            results = {
                'models_checked': 0,
                'models_updated': 0,
                'status': 'completed'
            }
            
            # Check STT models
            try:
                from ..services.ai.speech_to_text import STTService
                stt_service = STTService()
                stt_update = await stt_service.check_for_updates()
                if stt_update:
                    results['models_updated'] += 1
                results['models_checked'] += 1
            except Exception as e:
                logger.warning(f"STT model update check failed: {e}")
            
            # Check TTS models
            try:
                from ..services.ai.text_to_speech import TTSService
                tts_service = TTSService()
                tts_update = await tts_service.check_for_updates()
                if tts_update:
                    results['models_updated'] += 1
                results['models_checked'] += 1
            except Exception as e:
                logger.warning(f"TTS model update check failed: {e}")
            
            # Check text analysis models
            try:
                from ..services.ai.text_analysis import TextAnalysisService
                text_service = TextAnalysisService()
                text_update = await text_service.check_for_updates()
                if text_update:
                    results['models_updated'] += 1
                results['models_checked'] += 1
            except Exception as e:
                logger.warning(f"Text analysis model update check failed: {e}")
            
            logger.info(f"Model update check completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Model update task failed: {e}")
            raise
    
    async def _report_generation_task(self) -> Dict[str, Any]:
        """Generate periodic reports."""
        try:
            from ..services.reporting import ReportGenerator
            report_generator = ReportGenerator()
            
            # Generate weekly summary report
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=7)
            
            reports_generated = []
            
            # Ticket summary report
            try:
                ticket_report = await report_generator.generate_ticket_summary_report(
                    start_date=start_date,
                    end_date=end_date
                )
                reports_generated.append('ticket_summary')
            except Exception as e:
                logger.warning(f"Ticket report generation failed: {e}")
            
            # Conversation analytics report
            try:
                conversation_report = await report_generator.generate_conversation_analytics_report(
                    start_date=start_date,
                    end_date=end_date
                )
                reports_generated.append('conversation_analytics')
            except Exception as e:
                logger.warning(f"Conversation report generation failed: {e}")
            
            # System performance report
            try:
                performance_report = await report_generator.generate_performance_report(
                    start_date=start_date,
                    end_date=end_date
                )
                reports_generated.append('system_performance')
            except Exception as e:
                logger.warning(f"Performance report generation failed: {e}")
            
            result = {
                'reports_generated': reports_generated,
                'report_count': len(reports_generated),
                'period': f"{start_date.date()} to {end_date.date()}",
                'status': 'completed'
            }
            
            logger.info(f"Report generation completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            raise
    
    async def _backup_execution_task(self) -> Dict[str, Any]:
        """Execute database and file backups."""
        try:
            results = {
                'database_backup': False,
                'file_backup': False,
                'backup_size_mb': 0,
                'status': 'completed'
            }
            
            # Database backup
            try:
                db_manager = DatabaseManager()
                backup_info = await db_manager.create_backup()
                results['database_backup'] = True
                results['backup_size_mb'] += backup_info.get('size_mb', 0)
            except Exception as e:
                logger.error(f"Database backup failed: {e}")
                results['database_backup'] = False
            
            # File backup (important directories)
            try:
                backup_dirs = [
                    settings.upload_dir,
                    settings.reports_dir,
                    settings.models_dir
                ]
                
                backup_root = os.path.join(settings.backup_dir, 'files')
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(backup_root, f"files_backup_{timestamp}")
                
                os.makedirs(backup_path, exist_ok=True)
                
                for dir_path in backup_dirs:
                    if os.path.exists(dir_path):
                        dir_name = os.path.basename(dir_path)
                        dest_path = os.path.join(backup_path, dir_name)
                        shutil.copytree(dir_path, dest_path, ignore_dangling_symlinks=True)
                
                # Compress backup
                shutil.make_archive(backup_path, 'gztar', backup_path)
                shutil.rmtree(backup_path)  # Remove uncompressed version
                
                # Get backup size
                backup_file = f"{backup_path}.tar.gz"
                if os.path.exists(backup_file):
                    backup_size = os.path.getsize(backup_file)
                    results['backup_size_mb'] += backup_size / (1024 * 1024)
                    results['file_backup'] = True
                
            except Exception as e:
                logger.error(f"File backup failed: {e}")
                results['file_backup'] = False
            
            logger.info(f"Backup execution completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Backup execution failed: {e}")
            raise
    
    async def _health_monitoring_task(self) -> Dict[str, Any]:
        """Monitor system health and send alerts."""
        try:
            from ..core.monitoring.health_checker import HealthChecker
            health_checker = HealthChecker()
            
            # Perform health checks
            health_status = await health_checker.comprehensive_health_check()
            
            # Check for alerts
            alerts = []
            if health_status.get('database', {}).get('status') != 'healthy':
                alerts.append({
                    'type': 'database_unhealthy',
                    'severity': 'critical',
                    'message': 'Database health check failed'
                })
            
            if health_status.get('redis', {}).get('status') != 'healthy':
                alerts.append({
                    'type': 'redis_unhealthy',
                    'severity': 'high',
                    'message': 'Redis health check failed'
                })
            
            # Check system resources
            import psutil
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent
            
            if cpu_usage > 90:
                alerts.append({
                    'type': 'high_cpu_usage',
                    'severity': 'high',
                    'message': f'CPU usage is {cpu_usage}%'
                })
            
            if memory_usage > 90:
                alerts.append({
                    'type': 'high_memory_usage',
                    'severity': 'high',
                    'message': f'Memory usage is {memory_usage}%'
                })
            
            if disk_usage > 85:
                alerts.append({
                    'type': 'high_disk_usage',
                    'severity': 'medium',
                    'message': f'Disk usage is {disk_usage}%'
                })
            
            # Send alerts if any
            if alerts:
                await self._send_health_alerts(alerts)
            
            result = {
                'health_status': health_status,
                'alerts_count': len(alerts),
                'alerts': alerts,
                'system_metrics': {
                    'cpu_usage': cpu_usage,
                    'memory_usage': memory_usage,
                    'disk_usage': disk_usage
                },
                'status': 'completed'
            }
            
            logger.info(f"Health monitoring completed with {len(alerts)} alerts")
            return result
            
        except Exception as e:
            logger.error(f"Health monitoring failed: {e}")
            raise
    
    async def _session_cleanup_task(self) -> Dict[str, Any]:
        """Clean up expired user sessions."""
        try:
            from ..core.auth.session_manager import SessionManager
            session_manager = SessionManager()
            
            # Clean up expired sessions
            cleaned_count = await session_manager.cleanup_expired_sessions()
            
            # Clean up abandoned sessions (no activity for 24 hours)
            abandoned_count = await session_manager.cleanup_abandoned_sessions(
                inactive_hours=24
            )
            
            result = {
                'expired_sessions_cleaned': cleaned_count,
                'abandoned_sessions_cleaned': abandoned_count,
                'total_cleaned': cleaned_count + abandoned_count,
                'status': 'completed'
            }
            
            logger.info(f"Session cleanup completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            raise
    
    async def _log_rotation_task(self) -> Dict[str, Any]:
        """Rotate and archive log files."""
        try:
            log_dir = settings.log_dir or 'logs'
            archived_count = 0
            archived_size_mb = 0
            
            if os.path.exists(log_dir):
                for root, dirs, files in os.walk(log_dir):
                    for file in files:
                        if file.endswith('.log'):
                            file_path = os.path.join(root, file)
                            file_stat = os.stat(file_path)
                            
                            # Rotate files larger than 100MB or older than 7 days
                            should_rotate = (
                                file_stat.st_size > 100 * 1024 * 1024 or
                                time.time() - file_stat.st_mtime > 7 * 24 * 3600
                            )
                            
                            if should_rotate:
                                # Archive the log file
                                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                                archive_name = f"{file}_{timestamp}.gz"
                                archive_path = os.path.join(root, archive_name)
                                
                                import gzip
                                with open(file_path, 'rb') as f_in:
                                    with gzip.open(archive_path, 'wb') as f_out:
                                        shutil.copyfileobj(f_in, f_out)
                                
                                # Clear original log file
                                with open(file_path, 'w') as f:
                                    f.write('')
                                
                                archived_count += 1
                                archived_size_mb += file_stat.st_size / (1024 * 1024)
            
            result = {
                'files_archived': archived_count,
                'archived_size_mb': round(archived_size_mb, 2),
                'status': 'completed'
            }
            
            logger.info(f"Log rotation completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Log rotation failed: {e}")
            raise
    
    async def _metrics_aggregation_task(self) -> Dict[str, Any]:
        """Aggregate and store metrics data."""
        try:
            from ..core.monitoring.metrics_collector import MetricsCollector
            metrics_collector = MetricsCollector()
            
            # Aggregate metrics for the past hour
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=1)
            
            aggregated_metrics = await metrics_collector.aggregate_metrics(
                start_time=start_time,
                end_time=end_time
            )
            
            # Store aggregated metrics
            if self.redis_client:
                metrics_key = f"metrics:hourly:{start_time.strftime('%Y%m%d_%H')}"
                await self.redis_client.setex(
                    metrics_key,
                    86400,  # 24 hours TTL
                    json.dumps(aggregated_metrics)
                )
            
            result = {
                'period': f"{start_time.isoformat()} to {end_time.isoformat()}",
                'metrics_aggregated': len(aggregated_metrics),
                'status': 'completed'
            }
            
            logger.info(f"Metrics aggregation completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Metrics aggregation failed: {e}")
            raise
    
    async def _file_cleanup_task(self) -> Dict[str, Any]:
        """Clean up temporary and old files."""
        try:
            cleanup_dirs = [
                settings.temp_dir,
                settings.upload_dir,
                settings.audio_temp_dir
            ]
            
            total_files = 0
            deleted_files = 0
            freed_space_mb = 0
            
            # Files older than 7 days
            cutoff_time = time.time() - (7 * 24 * 3600)
            
            for dir_path in cleanup_dirs:
                if not os.path.exists(dir_path):
                    continue
                
                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            file_stat = os.stat(file_path)
                            total_files += 1
                            
                            if file_stat.st_mtime < cutoff_time:
                                file_size_mb = file_stat.st_size / (1024 * 1024)
                                os.remove(file_path)
                                deleted_files += 1
                                freed_space_mb += file_size_mb
                        except Exception as e:
                            logger.warning(f"Failed to process file {file_path}: {e}")
            
            result = {
                'total_files_scanned': total_files,
                'files_deleted': deleted_files,
                'freed_space_mb': round(freed_space_mb, 2),
                'status': 'completed'
            }
            
            logger.info(f"File cleanup completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"File cleanup failed: {e}")
            raise
    
    async def _send_health_alerts(self, alerts: List[Dict[str, Any]]):
        """Send health monitoring alerts."""
        try:
            # Send alerts via email or webhook
            from ..workers.tasks import send_email_notification_task
            
            for alert in alerts:
                if alert['severity'] in ['critical', 'high']:
                    # Send immediate notification
                    send_email_notification_task.delay(
                        recipient=settings.admin_email,
                        subject=f"System Alert: {alert['type']}",
                        body=alert['message']
                    )
            
        except Exception as e:
            logger.error(f"Failed to send health alerts: {e}")
    
    # Task management methods
    
    async def schedule_task(self, name: str, task_func: str, 
                          schedule_type: ScheduleType, schedule_config: Dict[str, Any],
                          enabled: bool = True) -> str:
        """Schedule a new task."""
        try:
            task_id = f"scheduled_{int(time.time())}_{len(self.scheduled_tasks)}"
            
            task_info = ScheduledTaskInfo(
                task_id=task_id,
                name=name,
                task_func=task_func,
                schedule_type=schedule_type,
                schedule_config=schedule_config,
                next_run=self._calculate_next_run_for_new_task(schedule_type, schedule_config),
                last_run=None,
                run_count=0,
                success_count=0,
                failure_count=0,
                enabled=enabled,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            self.scheduled_tasks[task_id] = task_info
            await self._save_scheduled_tasks()
            
            logger.info(f"Scheduled new task: {name} ({task_id})")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to schedule task: {e}")
            raise
    
    def _calculate_next_run_for_new_task(self, schedule_type: ScheduleType, 
                                       schedule_config: Dict[str, Any]) -> datetime:
        """Calculate next run time for a new task."""
        # Create a temporary task info to use the existing calculation method
        temp_task_info = ScheduledTaskInfo(
            task_id="temp",
            name="temp",
            task_func="temp",
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            next_run=datetime.now(timezone.utc),
            last_run=None,
            run_count=0,
            success_count=0,
            failure_count=0,
            enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        return self._calculate_next_run(temp_task_info)
    
    async def remove_scheduled_task(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        try:
            if task_id in self.scheduled_tasks:
                del self.scheduled_tasks[task_id]
                await self._save_scheduled_tasks()
                logger.info(f"Removed scheduled task: {task_id}")
                return True
            else:
                logger.warning(f"Scheduled task not found: {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove scheduled task: {e}")
            return False
    
    async def enable_scheduled_task(self, task_id: str) -> bool:
        """Enable a scheduled task."""
        try:
            if task_id in self.scheduled_tasks:
                self.scheduled_tasks[task_id].enabled = True
                self.scheduled_tasks[task_id].updated_at = datetime.now(timezone.utc)
                await self._save_scheduled_tasks()
                logger.info(f"Enabled scheduled task: {task_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to enable scheduled task: {e}")
            return False
    
    async def disable_scheduled_task(self, task_id: str) -> bool:
        """Disable a scheduled task."""
        try:
            if task_id in self.scheduled_tasks:
                self.scheduled_tasks[task_id].enabled = False
                self.scheduled_tasks[task_id].updated_at = datetime.now(timezone.utc)
                await self._save_scheduled_tasks()
                logger.info(f"Disabled scheduled task: {task_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Failed to disable scheduled task: {e}")
            return False
    
    async def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks."""
        try:
            tasks = []
            for task_info in self.scheduled_tasks.values():
                tasks.append({
                    'task_id': task_info.task_id,
                    'name': task_info.name,
                    'task_func': task_info.task_func,
                    'schedule_type': task_info.schedule_type.value,
                    'schedule_config': task_info.schedule_config,
                    'next_run': task_info.next_run.isoformat(),
                    'last_run': task_info.last_run.isoformat() if task_info.last_run else None,
                    'run_count': task_info.run_count,
                    'success_count': task_info.success_count,
                    'failure_count': task_info.failure_count,
                    'success_rate': (task_info.success_count / max(1, task_info.run_count)) * 100,
                    'enabled': task_info.enabled,
                    'created_at': task_info.created_at.isoformat(),
                    'updated_at': task_info.updated_at.isoformat()
                })
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to get scheduled tasks: {e}")
            return []
    
    async def _load_scheduled_tasks(self):
        """Load scheduled tasks from storage."""
        try:
            if self.redis_client:
                data = await self.redis_client.get('scheduled_tasks:config')
                if data:
                    tasks_data = json.loads(data)
                    for task_data in tasks_data:
                        task_info = ScheduledTaskInfo(
                            task_id=task_data['task_id'],
                            name=task_data['name'],
                            task_func=task_data['task_func'],
                            schedule_type=ScheduleType(task_data['schedule_type']),
                            schedule_config=task_data['schedule_config'],
                            next_run=datetime.fromisoformat(task_data['next_run']),
                            last_run=datetime.fromisoformat(task_data['last_run']) if task_data['last_run'] else None,
                            run_count=task_data['run_count'],
                            success_count=task_data['success_count'],
                            failure_count=task_data['failure_count'],
                            enabled=task_data['enabled'],
                            created_at=datetime.fromisoformat(task_data['created_at']),
                            updated_at=datetime.fromisoformat(task_data['updated_at'])
                        )
                        self.scheduled_tasks[task_info.task_id] = task_info
                    
                    logger.info(f"Loaded {len(self.scheduled_tasks)} scheduled tasks from storage")
        
        except Exception as e:
            logger.error(f"Failed to load scheduled tasks: {e}")
    
    async def _save_scheduled_tasks(self):
        """Save scheduled tasks to storage."""
        try:
            if self.redis_client:
                tasks_data = []
                for task_info in self.scheduled_tasks.values():
                    tasks_data.append({
                        'task_id': task_info.task_id,
                        'name': task_info.name,
                        'task_func': task_info.task_func,
                        'schedule_type': task_info.schedule_type.value,
                        'schedule_config': task_info.schedule_config,
                        'next_run': task_info.next_run.isoformat(),
                        'last_run': task_info.last_run.isoformat() if task_info.last_run else None,
                        'run_count': task_info.run_count,
                        'success_count': task_info.success_count,
                        'failure_count': task_info.failure_count,
                        'enabled': task_info.enabled,
                        'created_at': task_info.created_at.isoformat(),
                        'updated_at': task_info.updated_at.isoformat()
                    })
                
                await self.redis_client.setex(
                    'scheduled_tasks:config',
                    86400 * 7,  # 7 days TTL
                    json.dumps(tasks_data)
                )
        
        except Exception as e:
            logger.error(f"Failed to save scheduled tasks: {e}")
    
    async def _store_task_result(self, task_id: str, status: str, result: Any, execution_time: float):
        """Store task execution result."""
        try:
            if self.redis_client:
                result_data = {
                    'task_id': task_id,
                    'status': status,
                    'result': result if isinstance(result, (dict, list, str, int, float)) else str(result),
                    'execution_time': execution_time,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                key = f"scheduled_task_result:{task_id}:{int(time.time())}"
                await self.redis_client.setex(key, 86400, json.dumps(result_data))  # 24 hour TTL
        
        except Exception as e:
            logger.error(f"Failed to store task result: {e}")