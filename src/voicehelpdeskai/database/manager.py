"""Advanced database manager with connection pooling, transaction management, and reliability features."""

import asyncio
import time
import threading
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Type, Callable, AsyncContextManager
from dataclasses import dataclass
from enum import Enum
import logging
import json
from pathlib import Path

from sqlalchemy import create_engine, event, text, inspect, MetaData
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.exc import (
    SQLAlchemyError, DisconnectionError, OperationalError, 
    IntegrityError, DataError, TimeoutError
)
from sqlalchemy.sql import func
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from loguru import logger

from .models import Base, SystemLog, SystemLogSeverity
from voicehelpdeskai.config.manager import get_config_manager


class DatabaseState(Enum):
    """Database connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class TransactionIsolationLevel(Enum):
    """Transaction isolation levels."""
    READ_UNCOMMITTED = "READ_UNCOMMITTED"
    READ_COMMITTED = "READ_COMMITTED"
    REPEATABLE_READ = "REPEATABLE_READ"
    SERIALIZABLE = "SERIALIZABLE"


@dataclass
class ConnectionConfig:
    """Database connection configuration."""
    url: str
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    echo: bool = False
    echo_pool: bool = False
    connect_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class BackupConfig:
    """Database backup configuration."""
    enabled: bool = True
    backup_dir: str = "./backups/database"
    retention_days: int = 30
    schedule_hour: int = 2  # 2 AM
    compress: bool = True
    verify_backup: bool = True
    remote_storage: Optional[Dict[str, str]] = None


@dataclass
class PerformanceMetrics:
    """Database performance metrics."""
    total_connections: int = 0
    active_connections: int = 0
    pool_size: int = 0
    checked_out_connections: int = 0
    overflow_connections: int = 0
    invalid_connections: int = 0
    
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    average_query_time: float = 0.0
    slowest_query_time: float = 0.0
    
    deadlocks_detected: int = 0
    deadlocks_resolved: int = 0
    connection_timeouts: int = 0
    transaction_rollbacks: int = 0
    
    last_backup: Optional[datetime] = None
    backup_size_mb: float = 0.0


class DatabaseManager:
    """Advanced database manager with comprehensive features."""
    
    def __init__(self,
                 connection_config: Optional[ConnectionConfig] = None,
                 backup_config: Optional[BackupConfig] = None,
                 enable_metrics: bool = True,
                 enable_audit_logging: bool = True,
                 enable_query_logging: bool = False,
                 enable_automatic_backup: bool = True):
        """Initialize database manager.
        
        Args:
            connection_config: Database connection configuration
            backup_config: Backup configuration
            enable_metrics: Enable performance metrics collection
            enable_audit_logging: Enable audit logging
            enable_query_logging: Enable query logging for debugging
            enable_automatic_backup: Enable automatic backup scheduling
        """
        self.config = get_config_manager().get_config()
        
        # Configuration
        self.connection_config = connection_config or self._create_default_connection_config()
        self.backup_config = backup_config or BackupConfig()
        self.enable_metrics = enable_metrics
        self.enable_audit_logging = enable_audit_logging
        self.enable_query_logging = enable_query_logging
        self.enable_automatic_backup = enable_automatic_backup
        
        # Core components
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None
        self.scoped_session_factory: Optional[scoped_session] = None
        
        # State management
        self.state = DatabaseState.DISCONNECTED
        self.last_connection_attempt: Optional[datetime] = None
        self.connection_lock = threading.Lock()
        
        # Metrics and monitoring
        self.metrics = PerformanceMetrics()
        self.query_history: List[Dict[str, Any]] = []
        self.slow_queries: List[Dict[str, Any]] = []
        self.slow_query_threshold = 1.0  # seconds
        
        # Background tasks
        self.backup_task: Optional[asyncio.Task] = None
        self.metrics_task: Optional[asyncio.Task] = None
        self.maintenance_task: Optional[asyncio.Task] = None
        
        # Migration and schema management
        self.alembic_config: Optional[Config] = None
        self.migrations_dir = "./alembic"
        
        # Error handling and resilience
        self.max_retry_attempts = 3
        self.retry_delay = 1.0
        self.circuit_breaker_threshold = 10
        self.circuit_breaker_timeout = 60
        self.failed_attempts = 0
        self.circuit_breaker_open_until: Optional[datetime] = None
        
        logger.info("DatabaseManager initialized")
    
    async def initialize(self) -> None:
        """Initialize database manager and establish connections."""
        try:
            logger.info("Initializing DatabaseManager...")
            
            # Create engine
            await self._create_engine()
            
            # Create session factories
            self._create_session_factories()
            
            # Setup event listeners
            self._setup_event_listeners()
            
            # Initialize Alembic
            await self._initialize_alembic()
            
            # Test connection
            await self._test_connection()
            
            # Start background tasks
            if self.enable_metrics:
                await self._start_metrics_collection()
            
            if self.enable_automatic_backup:
                await self._start_automatic_backup()
            
            await self._start_maintenance_tasks()
            
            self.state = DatabaseState.CONNECTED
            logger.success("DatabaseManager initialization complete")
            
        except Exception as e:
            self.state = DatabaseState.ERROR
            logger.error(f"DatabaseManager initialization failed: {e}")
            raise
    
    async def _create_engine(self) -> None:
        """Create database engine with connection pooling."""
        try:
            # Determine pool class based on database type
            if "sqlite" in self.connection_config.url:
                # SQLite doesn't support connection pooling
                pool_class = NullPool
                connect_args = {"check_same_thread": False}
            else:
                pool_class = QueuePool
                connect_args = {}
            
            self.engine = create_engine(
                self.connection_config.url,
                poolclass=pool_class,
                pool_size=self.connection_config.pool_size,
                max_overflow=self.connection_config.max_overflow,
                pool_timeout=self.connection_config.pool_timeout,
                pool_recycle=self.connection_config.pool_recycle,
                pool_pre_ping=self.connection_config.pool_pre_ping,
                echo=self.connection_config.echo,
                echo_pool=self.connection_config.echo_pool,
                connect_args=connect_args,
                # Additional reliability settings
                execution_options={
                    "isolation_level": "READ_COMMITTED",
                    "autocommit": False
                }
            )
            
            # Configure engine events
            self._configure_engine_events()
            
            logger.info(f"Database engine created: {self.connection_config.url}")
            
        except Exception as e:
            logger.error(f"Failed to create database engine: {e}")
            raise
    
    def _create_session_factories(self) -> None:
        """Create session factory and scoped session."""
        self.session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
        self.scoped_session_factory = scoped_session(self.session_factory)
        
        logger.debug("Session factories created")
    
    def _configure_engine_events(self) -> None:
        """Configure engine event listeners for monitoring and reliability."""
        
        @event.listens_for(self.engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            """Handle connection establishment."""
            self.metrics.total_connections += 1
            if self.enable_audit_logging:
                self._log_database_event("connection_established", {"connection_id": id(dbapi_conn)})
        
        @event.listens_for(self.engine, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            """Handle connection checkout from pool."""
            self.metrics.checked_out_connections += 1
        
        @event.listens_for(self.engine, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            """Handle connection checkin to pool."""
            self.metrics.checked_out_connections -= 1
        
        @event.listens_for(self.engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Log query execution start."""
            context._query_start_time = time.time()
            
            if self.enable_query_logging:
                logger.debug(f"Executing query: {statement[:200]}...")
        
        @event.listens_for(self.engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Log query execution completion and collect metrics."""
            total_time = time.time() - context._query_start_time
            
            self.metrics.total_queries += 1
            self.metrics.successful_queries += 1
            
            # Update average query time
            self.metrics.average_query_time = (
                (self.metrics.average_query_time * (self.metrics.successful_queries - 1) + total_time) 
                / self.metrics.successful_queries
            )
            
            # Track slowest query
            if total_time > self.metrics.slowest_query_time:
                self.metrics.slowest_query_time = total_time
            
            # Log slow queries
            if total_time > self.slow_query_threshold:
                slow_query_info = {
                    "statement": statement[:500],
                    "execution_time": total_time,
                    "timestamp": datetime.now(),
                    "parameters": str(parameters)[:200] if parameters else None
                }
                self.slow_queries.append(slow_query_info)
                
                # Keep only last 100 slow queries
                if len(self.slow_queries) > 100:
                    self.slow_queries.pop(0)
                
                logger.warning(f"Slow query detected: {total_time:.3f}s - {statement[:100]}...")
            
            # Add to query history
            if len(self.query_history) < 1000:  # Keep last 1000 queries
                self.query_history.append({
                    "statement": statement[:200],
                    "execution_time": total_time,
                    "timestamp": datetime.now()
                })
        
        @event.listens_for(self.engine, "handle_error")
        def handle_error(exception_context):
            """Handle database errors and update metrics."""
            self.metrics.failed_queries += 1
            self.failed_attempts += 1
            
            # Check if we should open circuit breaker
            if self.failed_attempts >= self.circuit_breaker_threshold:
                self.circuit_breaker_open_until = datetime.now() + timedelta(seconds=self.circuit_breaker_timeout)
                logger.error(f"Circuit breaker opened due to {self.failed_attempts} failed attempts")
            
            if self.enable_audit_logging:
                self._log_database_event("query_error", {
                    "error": str(exception_context.original_exception),
                    "statement": str(exception_context.statement)[:200] if exception_context.statement else None
                })
    
    def _setup_event_listeners(self) -> None:
        """Setup additional event listeners for audit logging."""
        
        # Listen for model changes for audit logging
        if self.enable_audit_logging:
            
            @event.listens_for(Session, "after_insert")
            def after_insert(mapper, connection, target):
                """Log record insertions."""
                self._log_audit_event("insert", mapper.class_.__name__, target)
            
            @event.listens_for(Session, "after_update")
            def after_update(mapper, connection, target):
                """Log record updates."""
                self._log_audit_event("update", mapper.class_.__name__, target)
            
            @event.listens_for(Session, "after_delete")
            def after_delete(mapper, connection, target):
                """Log record deletions."""
                self._log_audit_event("delete", mapper.class_.__name__, target)
    
    @contextmanager
    def get_session(self, 
                   isolation_level: Optional[TransactionIsolationLevel] = None,
                   autocommit: bool = False) -> Session:
        """Get database session with automatic cleanup.
        
        Args:
            isolation_level: Transaction isolation level
            autocommit: Enable autocommit mode
            
        Yields:
            Database session
        """
        if self.state != DatabaseState.CONNECTED:
            raise RuntimeError("Database not connected")
        
        if self._is_circuit_breaker_open():
            raise RuntimeError("Database circuit breaker is open")
        
        session = self.session_factory()
        
        try:
            # Set isolation level if specified
            if isolation_level:
                session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level.value}"))
            
            # Set autocommit if specified
            if autocommit:
                session.autocommit = True
            
            yield session
            
            # Reset failed attempts on successful operation
            self.failed_attempts = 0
            
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {e}")
            raise
        finally:
            session.close()
    
    @contextmanager
    def get_transaction(self, 
                       isolation_level: Optional[TransactionIsolationLevel] = None,
                       retry_on_deadlock: bool = True) -> Session:
        """Get database session with transaction management.
        
        Args:
            isolation_level: Transaction isolation level
            retry_on_deadlock: Retry transaction on deadlock
            
        Yields:
            Database session with active transaction
        """
        max_attempts = self.max_retry_attempts if retry_on_deadlock else 1
        
        for attempt in range(max_attempts):
            try:
                with self.get_session(isolation_level=isolation_level) as session:
                    session.begin()
                    yield session
                    session.commit()
                    break
                    
            except (OperationalError, IntegrityError) as e:
                if attempt < max_attempts - 1 and self._is_deadlock_error(e):
                    # Deadlock detected, retry after delay
                    self.metrics.deadlocks_detected += 1
                    retry_delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Deadlock detected, retrying in {retry_delay}s (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(retry_delay)
                    continue
                else:
                    self.metrics.transaction_rollbacks += 1
                    logger.error(f"Transaction failed after {attempt + 1} attempts: {e}")
                    raise
            except Exception as e:
                self.metrics.transaction_rollbacks += 1
                logger.error(f"Transaction error: {e}")
                raise
        else:
            self.metrics.deadlocks_resolved += 1
    
    async def execute_query(self, 
                          query: str, 
                          parameters: Optional[Dict[str, Any]] = None,
                          fetch_results: bool = True) -> Optional[List[Dict[str, Any]]]:
        """Execute raw SQL query with error handling.
        
        Args:
            query: SQL query string
            parameters: Query parameters
            fetch_results: Whether to fetch and return results
            
        Returns:
            Query results if fetch_results=True
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(query), parameters or {})
                
                if fetch_results:
                    # Convert result to list of dictionaries
                    columns = result.keys()
                    return [dict(zip(columns, row)) for row in result.fetchall()]
                else:
                    session.commit()
                    return None
                    
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def _initialize_alembic(self) -> None:
        """Initialize Alembic for database migrations."""
        try:
            alembic_cfg_path = Path(self.migrations_dir) / "alembic.ini"
            
            if alembic_cfg_path.exists():
                self.alembic_config = Config(str(alembic_cfg_path))
                self.alembic_config.set_main_option("sqlalchemy.url", self.connection_config.url)
                
                logger.info("Alembic configuration loaded")
            else:
                logger.warning(f"Alembic configuration not found at {alembic_cfg_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize Alembic: {e}")
    
    async def run_migrations(self, target_revision: str = "head") -> None:
        """Run database migrations.
        
        Args:
            target_revision: Target migration revision
        """
        try:
            if not self.alembic_config:
                raise RuntimeError("Alembic not initialized")
            
            logger.info(f"Running migrations to {target_revision}")
            command.upgrade(self.alembic_config, target_revision)
            logger.success("Migrations completed successfully")
            
            if self.enable_audit_logging:
                self._log_database_event("migration_completed", {"target_revision": target_revision})
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            if self.enable_audit_logging:
                self._log_database_event("migration_failed", {"error": str(e), "target_revision": target_revision})
            raise
    
    async def create_backup(self, 
                          backup_name: Optional[str] = None,
                          compress: Optional[bool] = None) -> str:
        """Create database backup.
        
        Args:
            backup_name: Custom backup name
            compress: Whether to compress backup
            
        Returns:
            Path to backup file
        """
        try:
            if not backup_name:
                backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            compress = compress if compress is not None else self.backup_config.compress
            backup_dir = Path(self.backup_config.backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            backup_path = backup_dir / f"{backup_name}.sql"
            if compress:
                backup_path = backup_path.with_suffix(".sql.gz")
            
            # Database-specific backup logic
            if "sqlite" in self.connection_config.url:
                await self._backup_sqlite(backup_path)
            elif "postgresql" in self.connection_config.url:
                await self._backup_postgresql(backup_path, compress)
            else:
                # Generic backup using SQL dump
                await self._backup_generic(backup_path)
            
            # Update metrics
            self.metrics.last_backup = datetime.now()
            self.metrics.backup_size_mb = backup_path.stat().st_size / (1024 * 1024)
            
            logger.info(f"Backup created: {backup_path} ({self.metrics.backup_size_mb:.2f} MB)")
            
            if self.enable_audit_logging:
                self._log_database_event("backup_created", {
                    "backup_path": str(backup_path),
                    "size_mb": self.metrics.backup_size_mb,
                    "compressed": compress
                })
            
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            if self.enable_audit_logging:
                self._log_database_event("backup_failed", {"error": str(e)})
            raise
    
    async def _backup_sqlite(self, backup_path: Path) -> None:
        """Create SQLite backup."""
        import shutil
        
        # Extract database path from URL
        db_path = self.connection_config.url.replace("sqlite:///", "")
        
        if backup_path.suffix == ".gz":
            # Compressed backup
            import gzip
            with open(db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            # Uncompressed backup
            shutil.copy2(db_path, backup_path)
    
    async def _backup_postgresql(self, backup_path: Path, compress: bool) -> None:
        """Create PostgreSQL backup using pg_dump."""
        import subprocess
        from urllib.parse import urlparse
        
        parsed_url = urlparse(self.connection_config.url)
        
        cmd = [
            "pg_dump",
            "-h", parsed_url.hostname or "localhost",
            "-p", str(parsed_url.port or 5432),
            "-U", parsed_url.username,
            "-d", parsed_url.path.lstrip('/'),
            "--no-password",
            "--clean",
            "--if-exists"
        ]
        
        if compress:
            cmd.extend(["-Z", "9"])  # Maximum compression
        
        cmd.extend(["-f", str(backup_path)])
        
        # Set password via environment variable
        env = {"PGPASSWORD": parsed_url.password} if parsed_url.password else {}
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {stderr.decode()}")
    
    async def _backup_generic(self, backup_path: Path) -> None:
        """Create generic SQL dump backup."""
        with self.get_session() as session:
            # Get all table names
            inspector = inspect(self.engine)
            table_names = inspector.get_table_names()
            
            with open(backup_path, 'w') as f:
                for table_name in table_names:
                    # Write table structure and data
                    result = session.execute(text(f"SELECT * FROM {table_name}"))
                    columns = result.keys()
                    
                    f.write(f"-- Table: {table_name}\n")
                    
                    for row in result.fetchall():
                        values = [f"'{v}'" if isinstance(v, str) else str(v) for v in row]
                        f.write(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(values)});\n")
                    
                    f.write("\n")
    
    async def cleanup_old_backups(self) -> int:
        """Clean up old backup files based on retention policy.
        
        Returns:
            Number of backups deleted
        """
        try:
            backup_dir = Path(self.backup_config.backup_dir)
            if not backup_dir.exists():
                return 0
            
            cutoff_date = datetime.now() - timedelta(days=self.backup_config.retention_days)
            deleted_count = 0
            
            for backup_file in backup_dir.glob("backup_*.sql*"):
                if backup_file.stat().st_mtime < cutoff_date.timestamp():
                    backup_file.unlink()
                    deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old backups")
                
                if self.enable_audit_logging:
                    self._log_database_event("backup_cleanup", {"deleted_count": deleted_count})
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
            return 0
    
    async def _test_connection(self) -> None:
        """Test database connection."""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                logger.info("Database connection test successful")
                
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise
    
    async def _start_metrics_collection(self) -> None:
        """Start background metrics collection."""
        async def metrics_collector():
            while True:
                try:
                    await self._collect_metrics()
                    await asyncio.sleep(60)  # Collect metrics every minute
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Metrics collection error: {e}")
                    await asyncio.sleep(60)
        
        self.metrics_task = asyncio.create_task(metrics_collector())
        logger.info("Started metrics collection")
    
    async def _collect_metrics(self) -> None:
        """Collect database performance metrics."""
        try:
            if hasattr(self.engine.pool, 'size'):
                self.metrics.pool_size = self.engine.pool.size()
                self.metrics.checked_out_connections = self.engine.pool.checkedout()
                self.metrics.overflow_connections = self.engine.pool.overflow()
                self.metrics.invalid_connections = self.engine.pool.invalidated()
            
            # Update active connections
            with self.get_session() as session:
                if "postgresql" in self.connection_config.url:
                    result = session.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"))
                    self.metrics.active_connections = result.scalar()
                elif "mysql" in self.connection_config.url:
                    result = session.execute(text("SHOW STATUS LIKE 'Threads_connected'"))
                    self.metrics.active_connections = int(result.fetchone()[1])
            
        except Exception as e:
            logger.debug(f"Metrics collection error: {e}")
    
    async def _start_automatic_backup(self) -> None:
        """Start automatic backup scheduling."""
        async def backup_scheduler():
            while True:
                try:
                    # Calculate time until next backup
                    now = datetime.now()
                    next_backup = now.replace(
                        hour=self.backup_config.schedule_hour, 
                        minute=0, 
                        second=0, 
                        microsecond=0
                    )
                    
                    if next_backup <= now:
                        next_backup += timedelta(days=1)
                    
                    # Wait until backup time
                    sleep_seconds = (next_backup - now).total_seconds()
                    await asyncio.sleep(sleep_seconds)
                    
                    # Create backup
                    await self.create_backup()
                    
                    # Cleanup old backups
                    await self.cleanup_old_backups()
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Automatic backup error: {e}")
                    await asyncio.sleep(3600)  # Wait 1 hour before retry
        
        self.backup_task = asyncio.create_task(backup_scheduler())
        logger.info(f"Scheduled automatic backups at {self.backup_config.schedule_hour}:00")
    
    async def _start_maintenance_tasks(self) -> None:
        """Start database maintenance tasks."""
        async def maintenance_worker():
            while True:
                try:
                    # Run maintenance every 6 hours
                    await asyncio.sleep(6 * 3600)
                    
                    # Analyze query performance
                    await self._analyze_performance()
                    
                    # Update table statistics
                    await self._update_table_statistics()
                    
                    # Cleanup old logs
                    await self._cleanup_old_logs()
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Maintenance task error: {e}")
        
        self.maintenance_task = asyncio.create_task(maintenance_worker())
        logger.info("Started database maintenance tasks")
    
    async def _analyze_performance(self) -> None:
        """Analyze database performance and log insights."""
        try:
            insights = []
            
            # Check for slow queries
            if len(self.slow_queries) > 10:
                insights.append(f"Found {len(self.slow_queries)} slow queries")
            
            # Check connection pool utilization
            if hasattr(self.engine.pool, 'size'):
                utilization = (self.metrics.checked_out_connections / self.metrics.pool_size) * 100
                if utilization > 80:
                    insights.append(f"High connection pool utilization: {utilization:.1f}%")
            
            # Check error rates
            if self.metrics.total_queries > 0:
                error_rate = (self.metrics.failed_queries / self.metrics.total_queries) * 100
                if error_rate > 5:
                    insights.append(f"High error rate: {error_rate:.1f}%")
            
            if insights and self.enable_audit_logging:
                self._log_database_event("performance_analysis", {"insights": insights})
                
        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
    
    async def _update_table_statistics(self) -> None:
        """Update table statistics for query optimization."""
        try:
            with self.get_session() as session:
                if "postgresql" in self.connection_config.url:
                    session.execute(text("ANALYZE"))
                elif "mysql" in self.connection_config.url:
                    session.execute(text("ANALYZE TABLE"))
                
                session.commit()
                logger.debug("Updated table statistics")
                
        except Exception as e:
            logger.debug(f"Statistics update failed: {e}")
    
    async def _cleanup_old_logs(self) -> None:
        """Clean up old system logs to prevent database bloat."""
        try:
            with self.get_session() as session:
                # Delete logs older than 30 days
                cutoff_date = datetime.now() - timedelta(days=30)
                
                deleted = session.execute(
                    text("DELETE FROM system_logs WHERE timestamp < :cutoff"),
                    {"cutoff": cutoff_date}
                ).rowcount
                
                session.commit()
                
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old log entries")
                
        except Exception as e:
            logger.error(f"Log cleanup failed: {e}")
    
    def _create_default_connection_config(self) -> ConnectionConfig:
        """Create default connection configuration."""
        database_url = getattr(self.config, 'database_url', 'sqlite:///./voicehelpdesk.db')
        
        return ConnectionConfig(
            url=database_url,
            pool_size=20,
            max_overflow=30,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=getattr(self.config, 'database_echo', False),
            connect_timeout=30,
            retry_attempts=3,
            retry_delay=1.0
        )
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self.circuit_breaker_open_until:
            if datetime.now() < self.circuit_breaker_open_until:
                return True
            else:
                # Circuit breaker timeout expired, reset
                self.circuit_breaker_open_until = None
                self.failed_attempts = 0
                logger.info("Circuit breaker closed - resuming database operations")
        
        return False
    
    def _is_deadlock_error(self, error: Exception) -> bool:
        """Check if error is a deadlock."""
        error_str = str(error).lower()
        deadlock_keywords = [
            "deadlock", "lock wait timeout", "lock timeout",
            "serialization failure", "concurrent update"
        ]
        return any(keyword in error_str for keyword in deadlock_keywords)
    
    def _log_database_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log database event."""
        try:
            with self.get_session() as session:
                log_entry = SystemLog(
                    event_type=f"database_{event_type}",
                    severity=SystemLogSeverity.INFO.value,
                    source="DatabaseManager",
                    message=f"Database event: {event_type}",
                    details=details
                )
                session.add(log_entry)
                session.commit()
                
        except Exception as e:
            # Don't let audit logging failures break the main operation
            logger.debug(f"Audit logging failed: {e}")
    
    def _log_audit_event(self, operation: str, table_name: str, target: Any) -> None:
        """Log audit event for model changes."""
        try:
            # Extract relevant information from the target object
            target_id = getattr(target, 'id', None)
            
            details = {
                "operation": operation,
                "table": table_name,
                "record_id": target_id,
            }
            
            # Add user information if available
            if hasattr(target, 'updated_by'):
                details["user_id"] = target.updated_by
            
            self._log_database_event("audit_log", details)
            
        except Exception as e:
            logger.debug(f"Audit event logging failed: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive database metrics."""
        metrics_dict = {
            # Connection metrics
            "total_connections": self.metrics.total_connections,
            "active_connections": self.metrics.active_connections,
            "pool_size": self.metrics.pool_size,
            "checked_out_connections": self.metrics.checked_out_connections,
            "overflow_connections": self.metrics.overflow_connections,
            "invalid_connections": self.metrics.invalid_connections,
            
            # Query metrics
            "total_queries": self.metrics.total_queries,
            "successful_queries": self.metrics.successful_queries,
            "failed_queries": self.metrics.failed_queries,
            "average_query_time": self.metrics.average_query_time,
            "slowest_query_time": self.metrics.slowest_query_time,
            "slow_queries_count": len(self.slow_queries),
            
            # Reliability metrics
            "deadlocks_detected": self.metrics.deadlocks_detected,
            "deadlocks_resolved": self.metrics.deadlocks_resolved,
            "connection_timeouts": self.metrics.connection_timeouts,
            "transaction_rollbacks": self.metrics.transaction_rollbacks,
            "failed_attempts": self.failed_attempts,
            "circuit_breaker_open": self._is_circuit_breaker_open(),
            
            # Backup metrics
            "last_backup": self.metrics.last_backup.isoformat() if self.metrics.last_backup else None,
            "backup_size_mb": self.metrics.backup_size_mb,
            
            # System state
            "database_state": self.state.value,
            "last_connection_attempt": self.last_connection_attempt.isoformat() if self.last_connection_attempt else None,
            "configuration": {
                "pool_size": self.connection_config.pool_size,
                "max_overflow": self.connection_config.max_overflow,
                "pool_timeout": self.connection_config.pool_timeout,
                "pool_recycle": self.connection_config.pool_recycle,
            }
        }
        
        # Add derived metrics
        if self.metrics.total_queries > 0:
            metrics_dict["success_rate"] = (self.metrics.successful_queries / self.metrics.total_queries) * 100
            metrics_dict["error_rate"] = (self.metrics.failed_queries / self.metrics.total_queries) * 100
        
        if self.metrics.pool_size > 0:
            metrics_dict["pool_utilization"] = (self.metrics.checked_out_connections / self.metrics.pool_size) * 100
        
        return metrics_dict
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "metrics": {},
            "issues": []
        }
        
        try:
            # Check database connectivity
            start_time = time.time()
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            connection_time = time.time() - start_time
            
            health["checks"]["connectivity"] = {
                "status": "healthy",
                "response_time_ms": connection_time * 1000
            }
            
            # Check connection pool
            if hasattr(self.engine.pool, 'size'):
                pool_utilization = (self.metrics.checked_out_connections / self.metrics.pool_size) * 100
                
                health["checks"]["connection_pool"] = {
                    "status": "healthy" if pool_utilization < 80 else "warning" if pool_utilization < 95 else "critical",
                    "utilization_percentage": pool_utilization,
                    "checked_out": self.metrics.checked_out_connections,
                    "pool_size": self.metrics.pool_size
                }
                
                if pool_utilization >= 95:
                    health["issues"].append("Connection pool nearly exhausted")
                    health["status"] = "critical"
                elif pool_utilization >= 80:
                    health["issues"].append("High connection pool utilization")
                    if health["status"] == "healthy":
                        health["status"] = "warning"
            
            # Check error rates
            if self.metrics.total_queries > 0:
                error_rate = (self.metrics.failed_queries / self.metrics.total_queries) * 100
                
                health["checks"]["error_rate"] = {
                    "status": "healthy" if error_rate < 1 else "warning" if error_rate < 5 else "critical",
                    "error_percentage": error_rate,
                    "failed_queries": self.metrics.failed_queries,
                    "total_queries": self.metrics.total_queries
                }
                
                if error_rate >= 5:
                    health["issues"].append(f"High database error rate: {error_rate:.1f}%")
                    health["status"] = "critical"
                elif error_rate >= 1:
                    health["issues"].append(f"Elevated database error rate: {error_rate:.1f}%")
                    if health["status"] == "healthy":
                        health["status"] = "warning"
            
            # Check circuit breaker
            if self._is_circuit_breaker_open():
                health["checks"]["circuit_breaker"] = {"status": "critical"}
                health["issues"].append("Database circuit breaker is open")
                health["status"] = "critical"
            else:
                health["checks"]["circuit_breaker"] = {"status": "healthy"}
            
            # Check backup status
            if self.backup_config.enabled and self.metrics.last_backup:
                hours_since_backup = (datetime.now() - self.metrics.last_backup).total_seconds() / 3600
                
                health["checks"]["backup"] = {
                    "status": "healthy" if hours_since_backup < 25 else "warning" if hours_since_backup < 49 else "critical",
                    "hours_since_last_backup": hours_since_backup,
                    "last_backup": self.metrics.last_backup.isoformat()
                }
                
                if hours_since_backup >= 49:
                    health["issues"].append("Database backup is overdue")
                    health["status"] = "critical"
                elif hours_since_backup >= 25:
                    health["issues"].append("Database backup is getting old")
                    if health["status"] == "healthy":
                        health["status"] = "warning"
            
            # Add performance metrics
            health["metrics"] = {
                "average_query_time_ms": self.metrics.average_query_time * 1000,
                "slowest_query_time_ms": self.metrics.slowest_query_time * 1000,
                "slow_queries_count": len(self.slow_queries),
                "connection_response_time_ms": connection_time * 1000
            }
            
        except Exception as e:
            health["status"] = "critical"
            health["issues"].append(f"Health check failed: {str(e)}")
            health["checks"]["connectivity"] = {"status": "critical", "error": str(e)}
        
        return health
    
    async def shutdown(self) -> None:
        """Shutdown database manager and cleanup resources."""
        try:
            logger.info("Shutting down DatabaseManager...")
            
            # Cancel background tasks
            if self.backup_task:
                self.backup_task.cancel()
                try:
                    await self.backup_task
                except asyncio.CancelledError:
                    pass
            
            if self.metrics_task:
                self.metrics_task.cancel()
                try:
                    await self.metrics_task
                except asyncio.CancelledError:
                    pass
            
            if self.maintenance_task:
                self.maintenance_task.cancel()
                try:
                    await self.maintenance_task
                except asyncio.CancelledError:
                    pass
            
            # Close all sessions
            if self.scoped_session_factory:
                self.scoped_session_factory.remove()
            
            # Dispose engine
            if self.engine:
                self.engine.dispose()
            
            self.state = DatabaseState.DISCONNECTED
            logger.success("DatabaseManager shutdown complete")
            
        except Exception as e:
            logger.error(f"DatabaseManager shutdown failed: {e}")


# Global database manager instance
_database_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
    return _database_manager