"""Task result storage system for persistent task results and graceful shutdown."""

import asyncio
import json
import pickle
import time
import signal
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as redis
from celery.result import AsyncResult

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class ResultStatus(Enum):
    """Task result status."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"
    TIMEOUT = "TIMEOUT"


class StorageBackend(Enum):
    """Storage backend types."""
    REDIS = "redis"
    DATABASE = "database"
    FILE = "file"
    MEMORY = "memory"


@dataclass
class TaskResult:
    """Task result data structure."""
    task_id: str
    task_name: str
    status: ResultStatus
    result: Any
    error: Optional[str]
    traceback: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    execution_time: Optional[float]  # seconds
    worker_id: Optional[str]
    queue_name: Optional[str]
    args: List[Any]
    kwargs: Dict[str, Any]
    metadata: Dict[str, Any]
    retry_count: int
    expires_at: Optional[datetime]
    created_at: datetime


class TaskResultStorage:
    """Persistent storage for task results with multiple backends."""
    
    def __init__(self, backend: StorageBackend = StorageBackend.REDIS):
        self.backend = backend
        self.redis_client = None
        self.db_connection = None
        self.file_storage_path = None
        self.memory_storage = {}
        
        # Configuration
        self.default_ttl = 86400 * 7  # 7 days
        self.max_result_size = 1024 * 1024  # 1MB
        self.compression_enabled = True
        self.encryption_enabled = False
        
        # Statistics
        self.stats = {
            'total_stored': 0,
            'total_retrieved': 0,
            'total_expired': 0,
            'total_errors': 0,
            'storage_size_bytes': 0
        }
    
    async def initialize(self):
        """Initialize the storage backend."""
        try:
            if self.backend == StorageBackend.REDIS:
                await self._initialize_redis()
            elif self.backend == StorageBackend.DATABASE:
                await self._initialize_database()
            elif self.backend == StorageBackend.FILE:
                await self._initialize_file_storage()
            # Memory storage doesn't need initialization
            
            logger.info(f"TaskResultStorage initialized with {self.backend.value} backend")
            
        except Exception as e:
            logger.error(f"Failed to initialize TaskResultStorage: {e}")
            raise
    
    async def _initialize_redis(self):
        """Initialize Redis backend."""
        redis_url = settings.redis_url or 'redis://localhost:6379/2'  # Use different DB
        self.redis_client = redis.from_url(redis_url, decode_responses=False)  # Binary mode for pickle
        await self.redis_client.ping()
    
    async def _initialize_database(self):
        """Initialize database backend."""
        # TODO: Implement database storage
        pass
    
    async def _initialize_file_storage(self):
        """Initialize file storage backend."""
        import os
        self.file_storage_path = settings.task_results_dir or 'task_results'
        os.makedirs(self.file_storage_path, exist_ok=True)
    
    async def store_result(self, task_result: TaskResult, ttl: Optional[int] = None) -> bool:
        """Store a task result."""
        try:
            ttl = ttl or self.default_ttl
            
            # Validate result size
            serialized_size = len(str(task_result.result)) if task_result.result else 0
            if serialized_size > self.max_result_size:
                logger.warning(f"Task result too large: {serialized_size} bytes")
                # Store only metadata for large results
                task_result.result = f"<Large result truncated: {serialized_size} bytes>"
            
            if self.backend == StorageBackend.REDIS:
                success = await self._store_redis(task_result, ttl)
            elif self.backend == StorageBackend.DATABASE:
                success = await self._store_database(task_result, ttl)
            elif self.backend == StorageBackend.FILE:
                success = await self._store_file(task_result, ttl)
            else:  # MEMORY
                success = await self._store_memory(task_result, ttl)
            
            if success:
                self.stats['total_stored'] += 1
                logger.debug(f"Stored task result: {task_result.task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to store task result: {e}")
            self.stats['total_errors'] += 1
            return False
    
    async def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Retrieve a task result."""
        try:
            if self.backend == StorageBackend.REDIS:
                result = await self._get_redis(task_id)
            elif self.backend == StorageBackend.DATABASE:
                result = await self._get_database(task_id)
            elif self.backend == StorageBackend.FILE:
                result = await self._get_file(task_id)
            else:  # MEMORY
                result = await self._get_memory(task_id)
            
            if result:
                self.stats['total_retrieved'] += 1
                logger.debug(f"Retrieved task result: {task_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get task result: {e}")
            self.stats['total_errors'] += 1
            return None
    
    async def delete_result(self, task_id: str) -> bool:
        """Delete a task result."""
        try:
            if self.backend == StorageBackend.REDIS:
                success = await self._delete_redis(task_id)
            elif self.backend == StorageBackend.DATABASE:
                success = await self._delete_database(task_id)
            elif self.backend == StorageBackend.FILE:
                success = await self._delete_file(task_id)
            else:  # MEMORY
                success = await self._delete_memory(task_id)
            
            if success:
                logger.debug(f"Deleted task result: {task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete task result: {e}")
            return False
    
    async def cleanup_expired(self) -> int:
        """Clean up expired task results."""
        try:
            current_time = datetime.now(timezone.utc)
            deleted_count = 0
            
            if self.backend == StorageBackend.REDIS:
                # Redis handles TTL automatically, but we can check for manual cleanup
                pattern = "task_result:*"
                keys = await self.redis_client.keys(pattern)
                for key in keys:
                    ttl = await self.redis_client.ttl(key)
                    if ttl == -2:  # Key doesn't exist (expired)
                        deleted_count += 1
            
            elif self.backend == StorageBackend.MEMORY:
                expired_ids = []
                for task_id, (result, expiry) in self.memory_storage.items():
                    if expiry and current_time > expiry:
                        expired_ids.append(task_id)
                
                for task_id in expired_ids:
                    del self.memory_storage[task_id]
                    deleted_count += 1
            
            elif self.backend == StorageBackend.FILE:
                import os
                import glob
                
                pattern = os.path.join(self.file_storage_path, "*.json")
                for file_path in glob.glob(pattern):
                    try:
                        stat = os.stat(file_path)
                        # Check if file is older than default TTL
                        if current_time.timestamp() - stat.st_mtime > self.default_ttl:
                            os.remove(file_path)
                            deleted_count += 1
                    except Exception:
                        continue
            
            if deleted_count > 0:
                self.stats['total_expired'] += deleted_count
                logger.info(f"Cleaned up {deleted_count} expired task results")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired results: {e}")
            return 0
    
    async def get_results_by_status(self, status: ResultStatus, limit: int = 100) -> List[TaskResult]:
        """Get task results by status."""
        try:
            results = []
            
            if self.backend == StorageBackend.REDIS:
                pattern = "task_result:*"
                keys = await self.redis_client.keys(pattern)
                
                for key in keys[:limit]:  # Limit to avoid performance issues
                    try:
                        data = await self.redis_client.get(key)
                        if data:
                            task_result = self._deserialize_result(data)
                            if task_result and task_result.status == status:
                                results.append(task_result)
                                
                                if len(results) >= limit:
                                    break
                    except Exception:
                        continue
            
            elif self.backend == StorageBackend.MEMORY:
                for task_id, (task_result, _) in list(self.memory_storage.items())[:limit]:
                    if task_result.status == status:
                        results.append(task_result)
                        
                        if len(results) >= limit:
                            break
            
            # TODO: Implement for database and file backends
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get results by status: {e}")
            return []
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            stats = self.stats.copy()
            
            if self.backend == StorageBackend.REDIS:
                info = await self.redis_client.info('memory')
                stats['backend_memory_usage'] = info.get('used_memory', 0)
                
                # Count stored results
                pattern = "task_result:*"
                keys = await self.redis_client.keys(pattern)
                stats['stored_count'] = len(keys)
            
            elif self.backend == StorageBackend.MEMORY:
                stats['stored_count'] = len(self.memory_storage)
                stats['backend_memory_usage'] = sum(
                    len(str(result)) for result, _ in self.memory_storage.values()
                )
            
            elif self.backend == StorageBackend.FILE:
                import os
                import glob
                
                pattern = os.path.join(self.file_storage_path, "*.json")
                files = glob.glob(pattern)
                stats['stored_count'] = len(files)
                stats['backend_memory_usage'] = sum(
                    os.path.getsize(f) for f in files
                )
            
            stats['backend'] = self.backend.value
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return self.stats.copy()
    
    # Backend-specific implementations
    
    async def _store_redis(self, task_result: TaskResult, ttl: int) -> bool:
        """Store result in Redis."""
        try:
            key = f"task_result:{task_result.task_id}"
            data = self._serialize_result(task_result)
            
            await self.redis_client.setex(key, ttl, data)
            return True
            
        except Exception as e:
            logger.error(f"Redis store error: {e}")
            return False
    
    async def _get_redis(self, task_id: str) -> Optional[TaskResult]:
        """Get result from Redis."""
        try:
            key = f"task_result:{task_id}"
            data = await self.redis_client.get(key)
            
            if data:
                return self._deserialize_result(data)
            return None
            
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def _delete_redis(self, task_id: str) -> bool:
        """Delete result from Redis."""
        try:
            key = f"task_result:{task_id}"
            result = await self.redis_client.delete(key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def _store_memory(self, task_result: TaskResult, ttl: int) -> bool:
        """Store result in memory."""
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
            self.memory_storage[task_result.task_id] = (task_result, expires_at)
            return True
            
        except Exception as e:
            logger.error(f"Memory store error: {e}")
            return False
    
    async def _get_memory(self, task_id: str) -> Optional[TaskResult]:
        """Get result from memory."""
        try:
            if task_id in self.memory_storage:
                task_result, expires_at = self.memory_storage[task_id]
                
                # Check expiration
                if expires_at and datetime.now(timezone.utc) > expires_at:
                    del self.memory_storage[task_id]
                    return None
                
                return task_result
            return None
            
        except Exception as e:
            logger.error(f"Memory get error: {e}")
            return None
    
    async def _delete_memory(self, task_id: str) -> bool:
        """Delete result from memory."""
        try:
            if task_id in self.memory_storage:
                del self.memory_storage[task_id]
                return True
            return False
            
        except Exception as e:
            logger.error(f"Memory delete error: {e}")
            return False
    
    async def _store_file(self, task_result: TaskResult, ttl: int) -> bool:
        """Store result in file."""
        try:
            import os
            
            filename = f"{task_result.task_id}.json"
            file_path = os.path.join(self.file_storage_path, filename)
            
            # Convert to serializable format
            data = asdict(task_result)
            data['created_at'] = task_result.created_at.isoformat()
            data['started_at'] = task_result.started_at.isoformat() if task_result.started_at else None
            data['completed_at'] = task_result.completed_at.isoformat() if task_result.completed_at else None
            data['expires_at'] = task_result.expires_at.isoformat() if task_result.expires_at else None
            data['status'] = task_result.status.value
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"File store error: {e}")
            return False
    
    async def _get_file(self, task_id: str) -> Optional[TaskResult]:
        """Get result from file."""
        try:
            import os
            
            filename = f"{task_id}.json"
            file_path = os.path.join(self.file_storage_path, filename)
            
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Convert back to TaskResult
            return TaskResult(
                task_id=data['task_id'],
                task_name=data['task_name'],
                status=ResultStatus(data['status']),
                result=data['result'],
                error=data['error'],
                traceback=data['traceback'],
                started_at=datetime.fromisoformat(data['started_at']) if data['started_at'] else None,
                completed_at=datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None,
                execution_time=data['execution_time'],
                worker_id=data['worker_id'],
                queue_name=data['queue_name'],
                args=data['args'],
                kwargs=data['kwargs'],
                metadata=data['metadata'],
                retry_count=data['retry_count'],
                expires_at=datetime.fromisoformat(data['expires_at']) if data['expires_at'] else None,
                created_at=datetime.fromisoformat(data['created_at'])
            )
            
        except Exception as e:
            logger.error(f"File get error: {e}")
            return None
    
    async def _delete_file(self, task_id: str) -> bool:
        """Delete result from file."""
        try:
            import os
            
            filename = f"{task_id}.json"
            file_path = os.path.join(self.file_storage_path, filename)
            
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
            
        except Exception as e:
            logger.error(f"File delete error: {e}")
            return False
    
    async def _store_database(self, task_result: TaskResult, ttl: int) -> bool:
        """Store result in database."""
        # TODO: Implement database storage
        return False
    
    async def _get_database(self, task_id: str) -> Optional[TaskResult]:
        """Get result from database."""
        # TODO: Implement database retrieval
        return None
    
    async def _delete_database(self, task_id: str) -> bool:
        """Delete result from database."""
        # TODO: Implement database deletion
        return False
    
    def _serialize_result(self, task_result: TaskResult) -> bytes:
        """Serialize task result for storage."""
        try:
            if self.compression_enabled:
                import gzip
                data = pickle.dumps(task_result)
                return gzip.compress(data)
            else:
                return pickle.dumps(task_result)
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            raise
    
    def _deserialize_result(self, data: bytes) -> Optional[TaskResult]:
        """Deserialize task result from storage."""
        try:
            if self.compression_enabled:
                import gzip
                data = gzip.decompress(data)
            
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            return None


class GracefulShutdownManager:
    """Manager for graceful worker shutdown."""
    
    def __init__(self, task_storage: TaskResultStorage):
        self.task_storage = task_storage
        self.is_shutting_down = False
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.shutdown_timeout = 60  # seconds
        self.shutdown_callbacks: List[Callable] = []
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        asyncio.create_task(self.shutdown())
    
    def register_task(self, task_id: str, task: asyncio.Task):
        """Register an active task."""
        self.active_tasks[task_id] = task
    
    def unregister_task(self, task_id: str):
        """Unregister a completed task."""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
    
    def add_shutdown_callback(self, callback: Callable):
        """Add a callback to be called during shutdown."""
        self.shutdown_callbacks.append(callback)
    
    async def shutdown(self):
        """Perform graceful shutdown."""
        try:
            if self.is_shutting_down:
                return
            
            self.is_shutting_down = True
            logger.info("Starting graceful shutdown...")
            
            # Stop accepting new tasks
            for callback in self.shutdown_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback()
                    else:
                        callback()
                except Exception as e:
                    logger.error(f"Shutdown callback error: {e}")
            
            # Wait for active tasks to complete
            if self.active_tasks:
                logger.info(f"Waiting for {len(self.active_tasks)} active tasks to complete...")
                
                # Wait with timeout
                try:
                    await asyncio.wait_for(
                        self._wait_for_active_tasks(),
                        timeout=self.shutdown_timeout
                    )
                    logger.info("All active tasks completed successfully")
                except asyncio.TimeoutError:
                    logger.warning(f"Shutdown timeout reached, cancelling remaining tasks")
                    await self._cancel_remaining_tasks()
            
            # Save any pending results
            await self._save_pending_results()
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
    
    async def _wait_for_active_tasks(self):
        """Wait for all active tasks to complete."""
        while self.active_tasks:
            completed_tasks = []
            
            for task_id, task in self.active_tasks.items():
                if task.done():
                    completed_tasks.append(task_id)
                    
                    # Store result if task completed successfully
                    try:
                        if not task.cancelled() and task.exception() is None:
                            result = task.result()
                            # Store successful result
                            # TODO: Create TaskResult from task completion
                    except Exception as e:
                        logger.error(f"Error handling completed task {task_id}: {e}")
            
            # Remove completed tasks
            for task_id in completed_tasks:
                del self.active_tasks[task_id]
            
            if self.active_tasks:
                await asyncio.sleep(1)
    
    async def _cancel_remaining_tasks(self):
        """Cancel remaining active tasks."""
        for task_id, task in self.active_tasks.items():
            if not task.done():
                logger.warning(f"Cancelling task {task_id}")
                task.cancel()
                
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error cancelling task {task_id}: {e}")
        
        self.active_tasks.clear()
    
    async def _save_pending_results(self):
        """Save any pending task results."""
        # TODO: Implement saving of pending results
        pass


class TaskResultManager:
    """High-level manager for task results and graceful shutdown."""
    
    def __init__(self, storage_backend: StorageBackend = StorageBackend.REDIS):
        self.storage = TaskResultStorage(storage_backend)
        self.shutdown_manager = GracefulShutdownManager(self.storage)
        self.cleanup_task = None
        self.cleanup_interval = 3600  # 1 hour
    
    async def initialize(self):
        """Initialize the result manager."""
        await self.storage.initialize()
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("TaskResultManager initialized")
    
    async def shutdown(self):
        """Shutdown the result manager."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        await self.shutdown_manager.shutdown()
        logger.info("TaskResultManager shutdown completed")
    
    async def store_task_result(self, task_id: str, task_name: str, status: ResultStatus,
                              result: Any = None, error: str = None, **kwargs) -> bool:
        """Store a task result."""
        task_result = TaskResult(
            task_id=task_id,
            task_name=task_name,
            status=status,
            result=result,
            error=error,
            traceback=kwargs.get('traceback'),
            started_at=kwargs.get('started_at'),
            completed_at=kwargs.get('completed_at'),
            execution_time=kwargs.get('execution_time'),
            worker_id=kwargs.get('worker_id'),
            queue_name=kwargs.get('queue_name'),
            args=kwargs.get('args', []),
            kwargs=kwargs.get('task_kwargs', {}),
            metadata=kwargs.get('metadata', {}),
            retry_count=kwargs.get('retry_count', 0),
            expires_at=kwargs.get('expires_at'),
            created_at=datetime.now(timezone.utc)
        )
        
        return await self.storage.store_result(task_result, kwargs.get('ttl'))
    
    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get a task result."""
        return await self.storage.get_result(task_id)
    
    async def delete_task_result(self, task_id: str) -> bool:
        """Delete a task result."""
        return await self.storage.delete_result(task_id)
    
    async def get_results_by_status(self, status: ResultStatus, limit: int = 100) -> List[TaskResult]:
        """Get task results by status."""
        return await self.storage.get_results_by_status(status, limit)
    
    async def get_storage_statistics(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return await self.storage.get_storage_stats()
    
    def register_active_task(self, task_id: str, task: asyncio.Task):
        """Register an active task for graceful shutdown."""
        self.shutdown_manager.register_task(task_id, task)
    
    def unregister_active_task(self, task_id: str):
        """Unregister a completed task."""
        self.shutdown_manager.unregister_task(task_id)
    
    async def _cleanup_loop(self):
        """Periodic cleanup of expired results."""
        while True:
            try:
                await self.storage.cleanup_expired()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(60)


# Global task result manager
task_result_manager = TaskResultManager()