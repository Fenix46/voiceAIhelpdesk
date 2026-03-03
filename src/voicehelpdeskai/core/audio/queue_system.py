"""Thread-safe audio queue system with priority and memory management."""

import heapq
import threading
import time
import weakref
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional, Any, Dict, List, Callable, Generic, TypeVar
from concurrent.futures import ThreadPoolExecutor
import uuid

import numpy as np
from loguru import logger

from voicehelpdeskai.config.manager import get_config_manager
from voicehelpdeskai.core.audio.exceptions import AudioQueueError

T = TypeVar('T')


class Priority(IntEnum):
    """Audio processing priority levels (lower number = higher priority)."""
    CRITICAL = 0    # Real-time audio processing
    HIGH = 1        # Interactive voice commands
    NORMAL = 2      # Regular audio processing
    LOW = 3         # Background processing
    BULK = 4        # Batch processing


class AudioChunkStatus(Enum):
    """Status of audio chunks in the queue."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class AudioChunkMetadata:
    """Metadata for audio chunks in the queue."""
    chunk_id: str
    created_at: float
    priority: Priority
    source: str
    processing_deadline: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    tags: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if chunk has expired."""
        if self.processing_deadline is None:
            return False
        return time.time() > self.processing_deadline
    
    def can_retry(self) -> bool:
        """Check if chunk can be retried."""
        return self.retry_count < self.max_retries


@dataclass
class QueuedAudioChunk(Generic[T]):
    """Audio chunk with metadata for queue processing."""
    data: T
    metadata: AudioChunkMetadata
    status: AudioChunkStatus = AudioChunkStatus.PENDING
    processing_start_time: Optional[float] = None
    processing_end_time: Optional[float] = None
    error_message: Optional[str] = None
    
    def __lt__(self, other: 'QueuedAudioChunk') -> bool:
        """Compare chunks for priority queue ordering."""
        # First by priority (lower number = higher priority)
        if self.metadata.priority != other.metadata.priority:
            return self.metadata.priority < other.metadata.priority
        
        # Then by creation time (older first for same priority)
        return self.metadata.created_at < other.metadata.created_at
    
    def get_processing_duration(self) -> Optional[float]:
        """Get processing duration if completed."""
        if self.processing_start_time and self.processing_end_time:
            return self.processing_end_time - self.processing_start_time
        return None
    
    def mark_processing_started(self):
        """Mark chunk as processing started."""
        self.status = AudioChunkStatus.PROCESSING
        self.processing_start_time = time.time()
    
    def mark_processing_completed(self):
        """Mark chunk as processing completed."""
        self.status = AudioChunkStatus.COMPLETED
        self.processing_end_time = time.time()
    
    def mark_processing_failed(self, error_message: str):
        """Mark chunk as processing failed."""
        self.status = AudioChunkStatus.FAILED
        self.processing_end_time = time.time()
        self.error_message = error_message


class CircularAudioBuffer(Generic[T]):
    """Memory-efficient circular buffer for audio data."""
    
    def __init__(self, max_size: int):
        """Initialize circular buffer.
        
        Args:
            max_size: Maximum number of items in buffer
        """
        self.max_size = max_size
        self.buffer: List[Optional[T]] = [None] * max_size
        self.head = 0
        self.tail = 0
        self.count = 0
        self.lock = threading.RLock()
        self.total_items_added = 0
        self.total_items_removed = 0
    
    def put(self, item: T, block: bool = True, timeout: Optional[float] = None) -> bool:
        """Add item to buffer.
        
        Args:
            item: Item to add
            block: Whether to block if buffer is full
            timeout: Timeout for blocking operation
            
        Returns:
            True if item was added successfully
        """
        with self.lock:
            if self.count >= self.max_size:
                if not block:
                    return False
                
                # For circular buffer, we overwrite oldest
                self.tail = (self.tail + 1) % self.max_size
                self.count -= 1
                self.total_items_removed += 1
            
            self.buffer[self.head] = item
            self.head = (self.head + 1) % self.max_size
            self.count += 1
            self.total_items_added += 1
            
            return True
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[T]:
        """Get item from buffer.
        
        Args:
            block: Whether to block if buffer is empty
            timeout: Timeout for blocking operation
            
        Returns:
            Item from buffer or None
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                if self.count > 0:
                    item = self.buffer[self.tail]
                    self.buffer[self.tail] = None  # Clear reference
                    self.tail = (self.tail + 1) % self.max_size
                    self.count -= 1
                    self.total_items_removed += 1
                    return item
            
            if not block:
                return None
            
            if timeout and (time.time() - start_time) > timeout:
                return None
            
            time.sleep(0.001)  # Small sleep to avoid busy waiting
    
    def size(self) -> int:
        """Get current buffer size."""
        with self.lock:
            return self.count
    
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        with self.lock:
            return self.count == 0
    
    def is_full(self) -> bool:
        """Check if buffer is full."""
        with self.lock:
            return self.count >= self.max_size
    
    def clear(self):
        """Clear all items from buffer."""
        with self.lock:
            for i in range(self.max_size):
                self.buffer[i] = None
            self.head = 0
            self.tail = 0
            self.count = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        with self.lock:
            return {
                "max_size": self.max_size,
                "current_size": self.count,
                "total_added": self.total_items_added,
                "total_removed": self.total_items_removed,
                "utilization": self.count / self.max_size,
                "head": self.head,
                "tail": self.tail,
            }


class AudioQueue(Generic[T]):
    """Thread-safe audio queue with automatic cleanup."""
    
    def __init__(self,
                 max_size: int = 1000,
                 cleanup_interval: float = 60.0,
                 max_age: float = 300.0,
                 enable_auto_cleanup: bool = True):
        """Initialize audio queue.
        
        Args:
            max_size: Maximum queue size
            cleanup_interval: Cleanup interval in seconds
            max_age: Maximum age for chunks in seconds
            enable_auto_cleanup: Enable automatic cleanup
        """
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        self.max_age = max_age
        self.enable_auto_cleanup = enable_auto_cleanup
        
        # Core queue storage
        self.queue: deque[QueuedAudioChunk[T]] = deque(maxlen=max_size)
        self.lock = threading.RLock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)
        
        # Tracking
        self.chunk_registry: Dict[str, QueuedAudioChunk[T]] = {}
        
        # Statistics
        self.total_enqueued = 0
        self.total_dequeued = 0
        self.total_expired = 0
        self.total_failed = 0
        
        # Cleanup thread
        self.cleanup_thread: Optional[threading.Thread] = None
        self.stop_cleanup = threading.Event()
        
        if self.enable_auto_cleanup:
            self._start_cleanup_thread()
        
        logger.info(f"AudioQueue initialized with max_size={max_size}")
    
    def put(self, 
            data: T,
            priority: Priority = Priority.NORMAL,
            source: str = "unknown",
            processing_deadline: Optional[float] = None,
            tags: Optional[Dict[str, Any]] = None,
            block: bool = True,
            timeout: Optional[float] = None) -> str:
        """Add audio chunk to queue.
        
        Args:
            data: Audio data
            priority: Processing priority
            source: Source identifier
            processing_deadline: Processing deadline timestamp
            tags: Additional metadata tags
            block: Whether to block if queue is full
            timeout: Timeout for blocking operation
            
        Returns:
            Chunk ID
        """
        # Create chunk metadata
        chunk_id = str(uuid.uuid4())
        metadata = AudioChunkMetadata(
            chunk_id=chunk_id,
            created_at=time.time(),
            priority=priority,
            source=source,
            processing_deadline=processing_deadline,
            tags=tags or {}
        )
        
        # Create queued chunk
        chunk = QueuedAudioChunk(data=data, metadata=metadata)
        
        # Add to queue
        start_time = time.time()
        
        with self.not_full:
            while len(self.queue) >= self.max_size:
                if not block:
                    raise AudioQueueError("Queue is full and block=False")
                
                if timeout and (time.time() - start_time) > timeout:
                    raise AudioQueueError("Timeout waiting for queue space")
                
                # Remove oldest low-priority items to make space
                self._remove_low_priority_items()
                
                if len(self.queue) >= self.max_size:
                    self.not_full.wait(timeout=0.1)
            
            # Add to queue and registry
            self.queue.append(chunk)
            self.chunk_registry[chunk_id] = chunk
            self.total_enqueued += 1
            
            self.not_empty.notify()
        
        return chunk_id
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[QueuedAudioChunk[T]]:
        """Get audio chunk from queue.
        
        Args:
            block: Whether to block if queue is empty
            timeout: Timeout for blocking operation
            
        Returns:
            Queued audio chunk or None
        """
        start_time = time.time()
        
        with self.not_empty:
            while len(self.queue) == 0:
                if not block:
                    return None
                
                if timeout and (time.time() - start_time) > timeout:
                    return None
                
                self.not_empty.wait(timeout=0.1)
            
            # Get from queue
            chunk = self.queue.popleft()
            chunk.mark_processing_started()
            self.total_dequeued += 1
            
            self.not_full.notify()
            
            return chunk
    
    def get_by_id(self, chunk_id: str) -> Optional[QueuedAudioChunk[T]]:
        """Get chunk by ID.
        
        Args:
            chunk_id: Chunk identifier
            
        Returns:
            Queued audio chunk or None
        """
        with self.lock:
            return self.chunk_registry.get(chunk_id)
    
    def mark_completed(self, chunk_id: str) -> bool:
        """Mark chunk as completed.
        
        Args:
            chunk_id: Chunk identifier
            
        Returns:
            True if marked successfully
        """
        with self.lock:
            chunk = self.chunk_registry.get(chunk_id)
            if chunk:
                chunk.mark_processing_completed()
                return True
            return False
    
    def mark_failed(self, chunk_id: str, error_message: str) -> bool:
        """Mark chunk as failed.
        
        Args:
            chunk_id: Chunk identifier
            error_message: Error description
            
        Returns:
            True if marked successfully
        """
        with self.lock:
            chunk = self.chunk_registry.get(chunk_id)
            if chunk:
                chunk.mark_processing_failed(error_message)
                self.total_failed += 1
                
                # Retry if possible
                if chunk.metadata.can_retry():
                    chunk.metadata.retry_count += 1
                    chunk.status = AudioChunkStatus.PENDING
                    # Re-add to queue for retry
                    self.queue.append(chunk)
                
                return True
            return False
    
    def size(self) -> int:
        """Get current queue size."""
        with self.lock:
            return len(self.queue)
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        with self.lock:
            return len(self.queue) == 0
    
    def is_full(self) -> bool:
        """Check if queue is full."""
        with self.lock:
            return len(self.queue) >= self.max_size
    
    def clear(self):
        """Clear all items from queue."""
        with self.lock:
            self.queue.clear()
            self.chunk_registry.clear()
    
    def _remove_low_priority_items(self, count: int = 1):
        """Remove low-priority items to make space."""
        removed = 0
        queue_list = list(self.queue)
        
        # Sort by priority (higher priority number = lower priority)
        queue_list.sort(key=lambda x: (-x.metadata.priority.value, x.metadata.created_at))
        
        for chunk in queue_list:
            if removed >= count:
                break
            
            if chunk.metadata.priority >= Priority.LOW:
                self.queue.remove(chunk)
                if chunk.metadata.chunk_id in self.chunk_registry:
                    del self.chunk_registry[chunk.metadata.chunk_id]
                removed += 1
    
    def cleanup_old_chunks(self) -> int:
        """Clean up old chunks and update statistics.
        
        Returns:
            Number of chunks cleaned up
        """
        current_time = time.time()
        removed_count = 0
        
        with self.lock:
            # Find expired chunks
            expired_chunks = []
            for chunk in list(self.queue):
                age = current_time - chunk.metadata.created_at
                
                if (age > self.max_age or 
                    chunk.metadata.is_expired() or
                    chunk.status in [AudioChunkStatus.COMPLETED, AudioChunkStatus.FAILED]):
                    
                    expired_chunks.append(chunk)
            
            # Remove expired chunks
            for chunk in expired_chunks:
                try:
                    self.queue.remove(chunk)
                    if chunk.metadata.chunk_id in self.chunk_registry:
                        del self.chunk_registry[chunk.metadata.chunk_id]
                    removed_count += 1
                    
                    if chunk.metadata.is_expired():
                        self.total_expired += 1
                        
                except ValueError:
                    # Chunk already removed
                    pass
        
        if removed_count > 0:
            logger.debug(f"Cleaned up {removed_count} audio chunks")
        
        return removed_count
    
    def _start_cleanup_thread(self):
        """Start automatic cleanup thread."""
        def cleanup_worker():
            while not self.stop_cleanup.is_set():
                try:
                    self.cleanup_old_chunks()
                    self.stop_cleanup.wait(timeout=self.cleanup_interval)
                except Exception as e:
                    logger.error(f"Error in audio queue cleanup: {e}")
        
        self.cleanup_thread = threading.Thread(
            target=cleanup_worker,
            name="AudioQueueCleanup",
            daemon=True
        )
        self.cleanup_thread.start()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics.
        
        Returns:
            Dictionary with queue statistics
        """
        with self.lock:
            current_size = len(self.queue)
            registry_size = len(self.chunk_registry)
            
            # Count by status
            status_counts = {status.value: 0 for status in AudioChunkStatus}
            priority_counts = {priority.name: 0 for priority in Priority}
            
            for chunk in self.chunk_registry.values():
                status_counts[chunk.status.value] += 1
                priority_counts[chunk.metadata.priority.name] += 1
            
            return {
                "current_size": current_size,
                "registry_size": registry_size,
                "max_size": self.max_size,
                "total_enqueued": self.total_enqueued,
                "total_dequeued": self.total_dequeued,
                "total_expired": self.total_expired,
                "total_failed": self.total_failed,
                "utilization": current_size / self.max_size,
                "status_counts": status_counts,
                "priority_counts": priority_counts,
            }
    
    def shutdown(self):
        """Shutdown the queue and cleanup resources."""
        if self.cleanup_thread:
            self.stop_cleanup.set()
            self.cleanup_thread.join(timeout=5.0)
        
        self.clear()
        logger.info("AudioQueue shutdown completed")
    
    def __del__(self):
        """Destructor."""
        try:
            self.shutdown()
        except:
            pass


class PriorityAudioQueue(Generic[T]):
    """Priority-based audio queue using heap."""
    
    def __init__(self,
                 max_size: int = 1000,
                 cleanup_interval: float = 60.0,
                 max_age: float = 300.0):
        """Initialize priority audio queue.
        
        Args:
            max_size: Maximum queue size
            cleanup_interval: Cleanup interval in seconds
            max_age: Maximum age for chunks in seconds
        """
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        self.max_age = max_age
        
        # Priority heap
        self.heap: List[QueuedAudioChunk[T]] = []
        self.lock = threading.RLock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)
        
        # Tracking
        self.chunk_registry: Dict[str, QueuedAudioChunk[T]] = {}
        
        # Statistics
        self.total_enqueued = 0
        self.total_dequeued = 0
        self.total_expired = 0
        
        logger.info(f"PriorityAudioQueue initialized with max_size={max_size}")
    
    def put(self,
            data: T,
            priority: Priority = Priority.NORMAL,
            source: str = "unknown",
            processing_deadline: Optional[float] = None,
            tags: Optional[Dict[str, Any]] = None,
            block: bool = True,
            timeout: Optional[float] = None) -> str:
        """Add audio chunk to priority queue.
        
        Args:
            data: Audio data
            priority: Processing priority
            source: Source identifier
            processing_deadline: Processing deadline timestamp
            tags: Additional metadata tags
            block: Whether to block if queue is full
            timeout: Timeout for blocking operation
            
        Returns:
            Chunk ID
        """
        # Create chunk
        chunk_id = str(uuid.uuid4())
        metadata = AudioChunkMetadata(
            chunk_id=chunk_id,
            created_at=time.time(),
            priority=priority,
            source=source,
            processing_deadline=processing_deadline,
            tags=tags or {}
        )
        
        chunk = QueuedAudioChunk(data=data, metadata=metadata)
        
        start_time = time.time()
        
        with self.not_full:
            while len(self.heap) >= self.max_size:
                if not block:
                    raise AudioQueueError("Priority queue is full and block=False")
                
                if timeout and (time.time() - start_time) > timeout:
                    raise AudioQueueError("Timeout waiting for priority queue space")
                
                self.not_full.wait(timeout=0.1)
            
            # Add to heap and registry
            heapq.heappush(self.heap, chunk)
            self.chunk_registry[chunk_id] = chunk
            self.total_enqueued += 1
            
            self.not_empty.notify()
        
        return chunk_id
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[QueuedAudioChunk[T]]:
        """Get highest priority audio chunk.
        
        Args:
            block: Whether to block if queue is empty
            timeout: Timeout for blocking operation
            
        Returns:
            Queued audio chunk or None
        """
        start_time = time.time()
        
        with self.not_empty:
            while len(self.heap) == 0:
                if not block:
                    return None
                
                if timeout and (time.time() - start_time) > timeout:
                    return None
                
                self.not_empty.wait(timeout=0.1)
            
            # Get highest priority chunk
            chunk = heapq.heappop(self.heap)
            chunk.mark_processing_started()
            self.total_dequeued += 1
            
            self.not_full.notify()
            
            return chunk
    
    def peek(self) -> Optional[QueuedAudioChunk[T]]:
        """Peek at highest priority chunk without removing it.
        
        Returns:
            Highest priority chunk or None
        """
        with self.lock:
            return self.heap[0] if self.heap else None
    
    def size(self) -> int:
        """Get current queue size."""
        with self.lock:
            return len(self.heap)
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        with self.lock:
            return len(self.heap) == 0
    
    def clear(self):
        """Clear all items from queue."""
        with self.lock:
            self.heap.clear()
            self.chunk_registry.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get priority queue statistics."""
        with self.lock:
            priority_counts = {priority.name: 0 for priority in Priority}
            
            for chunk in self.heap:
                priority_counts[chunk.metadata.priority.name] += 1
            
            return {
                "current_size": len(self.heap),
                "max_size": self.max_size,
                "total_enqueued": self.total_enqueued,
                "total_dequeued": self.total_dequeued,
                "total_expired": self.total_expired,
                "utilization": len(self.heap) / self.max_size,
                "priority_counts": priority_counts,
                "registry_size": len(self.chunk_registry),
            }


class AudioQueueManager:
    """Manager for multiple audio queues with load balancing."""
    
    def __init__(self, config_manager=None):
        """Initialize audio queue manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or get_config_manager()
        self.settings = self.config_manager.get_settings()
        
        # Queue collections
        self.queues: Dict[str, AudioQueue] = {}
        self.priority_queues: Dict[str, PriorityAudioQueue] = {}
        self.circular_buffers: Dict[str, CircularAudioBuffer] = {}
        
        # Thread pool for processing
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="AudioQueue")
        
        # Default queues
        self.create_queue("default", max_size=1000)
        self.create_priority_queue("priority", max_size=500)
        self.create_circular_buffer("circular", max_size=2000)
        
        logger.info("AudioQueueManager initialized")
    
    def create_queue(self, name: str, **kwargs) -> AudioQueue:
        """Create a new audio queue.
        
        Args:
            name: Queue name
            **kwargs: Queue configuration parameters
            
        Returns:
            Created audio queue
        """
        queue = AudioQueue(**kwargs)
        self.queues[name] = queue
        logger.info(f"Created audio queue: {name}")
        return queue
    
    def create_priority_queue(self, name: str, **kwargs) -> PriorityAudioQueue:
        """Create a new priority audio queue.
        
        Args:
            name: Queue name
            **kwargs: Queue configuration parameters
            
        Returns:
            Created priority audio queue
        """
        queue = PriorityAudioQueue(**kwargs)
        self.priority_queues[name] = queue
        logger.info(f"Created priority audio queue: {name}")
        return queue
    
    def create_circular_buffer(self, name: str, **kwargs) -> CircularAudioBuffer:
        """Create a new circular audio buffer.
        
        Args:
            name: Buffer name
            **kwargs: Buffer configuration parameters
            
        Returns:
            Created circular audio buffer
        """
        buffer = CircularAudioBuffer(**kwargs)
        self.circular_buffers[name] = buffer
        logger.info(f"Created circular audio buffer: {name}")
        return buffer
    
    def get_queue(self, name: str) -> Optional[AudioQueue]:
        """Get audio queue by name.
        
        Args:
            name: Queue name
            
        Returns:
            Audio queue or None
        """
        return self.queues.get(name)
    
    def get_priority_queue(self, name: str) -> Optional[PriorityAudioQueue]:
        """Get priority queue by name.
        
        Args:
            name: Queue name
            
        Returns:
            Priority queue or None
        """
        return self.priority_queues.get(name)
    
    def get_circular_buffer(self, name: str) -> Optional[CircularAudioBuffer]:
        """Get circular buffer by name.
        
        Args:
            name: Buffer name
            
        Returns:
            Circular buffer or None
        """
        return self.circular_buffers.get(name)
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """Get statistics for all queues.
        
        Returns:
            Combined statistics
        """
        stats = {
            "queues": {},
            "priority_queues": {},
            "circular_buffers": {},
            "total_queues": len(self.queues) + len(self.priority_queues) + len(self.circular_buffers),
        }
        
        for name, queue in self.queues.items():
            stats["queues"][name] = queue.get_statistics()
        
        for name, queue in self.priority_queues.items():
            stats["priority_queues"][name] = queue.get_statistics()
        
        for name, buffer in self.circular_buffers.items():
            stats["circular_buffers"][name] = buffer.get_stats()
        
        return stats
    
    def cleanup_all(self):
        """Clean up all queues."""
        total_cleaned = 0
        
        for queue in self.queues.values():
            total_cleaned += queue.cleanup_old_chunks()
        
        logger.info(f"Cleaned up {total_cleaned} chunks across all queues")
        return total_cleaned
    
    def shutdown(self):
        """Shutdown all queues and resources."""
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Shutdown all queues
        for queue in self.queues.values():
            queue.shutdown()
        
        # Clear collections
        self.queues.clear()
        self.priority_queues.clear()
        self.circular_buffers.clear()
        
        logger.info("AudioQueueManager shutdown completed")
    
    def __del__(self):
        """Destructor."""
        try:
            self.shutdown()
        except:
            pass