"""Advanced transcription caching with fuzzy matching and compression."""

import asyncio
import hashlib
import gzip
import json
import pickle
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import threading

import numpy as np
from loguru import logger

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    try:
        import redis
        REDIS_AVAILABLE = True
    except ImportError:
        REDIS_AVAILABLE = False
        logger.warning("Redis not available - using in-memory cache only")

try:
    from scipy.spatial.distance import cosine
    from sklearn.feature_extraction.text import TfidfVectorizer
    FUZZY_MATCHING_AVAILABLE = True
except ImportError:
    FUZZY_MATCHING_AVAILABLE = False
    logger.warning("Scipy/sklearn not available - fuzzy matching disabled")

from voicehelpdeskai.services.stt.whisper_service import TranscriptionResult
from voicehelpdeskai.services.stt.transcription_processor import ProcessedTranscription
from voicehelpdeskai.config.manager import get_config_manager


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    transcription_result: TranscriptionResult
    processed_result: Optional[ProcessedTranscription]
    audio_hash: str
    audio_features: Optional[Dict[str, float]]
    created_at: datetime
    accessed_at: datetime
    access_count: int
    language: str
    model_version: str
    processing_version: str
    compression_ratio: float = 1.0
    file_size: int = 0


@dataclass
class AudioFeatures:
    """Audio features for similarity comparison."""
    duration: float
    sample_rate: int
    rms_energy: float
    zero_crossing_rate: float
    spectral_centroid: float
    mfcc_features: List[float]
    audio_hash: str


class TranscriptionCache:
    """Advanced caching system with fuzzy matching and compression."""
    
    def __init__(self,
                 redis_client: Optional[redis.Redis] = None,
                 cache_dir: Optional[Path] = None,
                 ttl_seconds: int = 86400,  # 24 hours
                 max_memory_entries: int = 1000,
                 enable_compression: bool = True,
                 compression_threshold: int = 1024,  # bytes
                 enable_fuzzy_matching: bool = True,
                 fuzzy_threshold: float = 0.85,
                 max_fuzzy_candidates: int = 10,
                 enable_audio_features: bool = True):
        """Initialize transcription cache.
        
        Args:
            redis_client: Optional Redis client for persistent caching
            cache_dir: Directory for file-based cache persistence
            ttl_seconds: Time-to-live for cache entries
            max_memory_entries: Maximum entries in memory cache
            enable_compression: Enable data compression
            compression_threshold: Minimum size for compression
            enable_fuzzy_matching: Enable fuzzy audio matching
            fuzzy_threshold: Similarity threshold for fuzzy matching
            max_fuzzy_candidates: Maximum candidates to check for fuzzy matching
            enable_audio_features: Enable audio feature extraction
        """
        self.redis_client = redis_client
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.ttl_seconds = ttl_seconds
        self.max_memory_entries = max_memory_entries
        self.enable_compression = enable_compression
        self.compression_threshold = compression_threshold
        self.enable_fuzzy_matching = enable_fuzzy_matching and FUZZY_MATCHING_AVAILABLE
        self.fuzzy_threshold = fuzzy_threshold
        self.max_fuzzy_candidates = max_fuzzy_candidates
        self.enable_audio_features = enable_audio_features
        
        # In-memory cache
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.access_times: Dict[str, datetime] = {}
        self.cache_lock = threading.RLock()
        
        # Feature extraction for fuzzy matching
        self.feature_cache: Dict[str, AudioFeatures] = {}
        self.tfidf_vectorizer = None
        if self.enable_fuzzy_matching:
            self.tfidf_vectorizer = TfidfVectorizer(max_features=100)
        
        # Statistics
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'fuzzy_matches': 0,
            'compression_saves': 0,
            'total_requests': 0,
            'average_lookup_time': 0.0,
            'memory_usage_mb': 0.0,
            'disk_usage_mb': 0.0,
        }
        
        # Setup cache directory
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / "transcriptions").mkdir(exist_ok=True)
            (self.cache_dir / "features").mkdir(exist_ok=True)
        
        # Configuration
        self.config = get_config_manager().get_config()
        
        logger.info(f"TranscriptionCache initialized: "
                   f"redis={'enabled' if redis_client else 'disabled'}, "
                   f"compression={enable_compression}, "
                   f"fuzzy_matching={self.enable_fuzzy_matching}")
    
    def _generate_audio_hash(self, audio_data: np.ndarray, 
                           sample_rate: int = 16000) -> str:
        """Generate hash for audio data."""
        # Normalize audio for consistent hashing
        normalized_audio = audio_data / (np.max(np.abs(audio_data)) + 1e-8)
        
        # Create hash from normalized audio and parameters
        hash_data = f"{normalized_audio.tobytes()}{sample_rate}".encode()
        return hashlib.sha256(hash_data).hexdigest()
    
    def _extract_audio_features(self, audio_data: np.ndarray, 
                              sample_rate: int = 16000) -> AudioFeatures:
        """Extract audio features for similarity comparison."""
        try:
            duration = len(audio_data) / sample_rate
            
            # Basic features
            rms_energy = np.sqrt(np.mean(audio_data ** 2))
            zero_crossings = np.where(np.diff(np.sign(audio_data)))[0]
            zero_crossing_rate = len(zero_crossings) / len(audio_data)
            
            # Spectral centroid (simple approximation)
            fft = np.abs(np.fft.rfft(audio_data))
            freqs = np.fft.rfftfreq(len(audio_data), 1/sample_rate)
            spectral_centroid = np.sum(freqs * fft) / (np.sum(fft) + 1e-8)
            
            # Simple MFCC approximation (first few coefficients)
            mfcc_features = []
            if len(fft) > 10:
                # Log magnitude spectrum
                log_spectrum = np.log(fft[:10] + 1e-8)
                mfcc_features = log_spectrum.tolist()
            
            audio_hash = self._generate_audio_hash(audio_data, sample_rate)
            
            return AudioFeatures(
                duration=duration,
                sample_rate=sample_rate,
                rms_energy=rms_energy,
                zero_crossing_rate=zero_crossing_rate,
                spectral_centroid=spectral_centroid,
                mfcc_features=mfcc_features,
                audio_hash=audio_hash
            )
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return AudioFeatures(
                duration=len(audio_data) / sample_rate,
                sample_rate=sample_rate,
                rms_energy=0.0,
                zero_crossing_rate=0.0,
                spectral_centroid=0.0,
                mfcc_features=[],
                audio_hash=self._generate_audio_hash(audio_data, sample_rate)
            )
    
    def _calculate_audio_similarity(self, features1: AudioFeatures, 
                                  features2: AudioFeatures) -> float:
        """Calculate similarity between two audio features."""
        if not FUZZY_MATCHING_AVAILABLE:
            return 0.0
        
        try:
            # Duration similarity
            duration_diff = abs(features1.duration - features2.duration)
            duration_sim = max(0, 1 - duration_diff / max(features1.duration, features2.duration))
            
            # Energy similarity
            energy_diff = abs(features1.rms_energy - features2.rms_energy)
            energy_sim = max(0, 1 - energy_diff / max(features1.rms_energy, features2.rms_energy, 0.01))
            
            # MFCC similarity
            mfcc_sim = 0.0
            if features1.mfcc_features and features2.mfcc_features:
                min_len = min(len(features1.mfcc_features), len(features2.mfcc_features))
                if min_len > 0:
                    mfcc1 = np.array(features1.mfcc_features[:min_len])
                    mfcc2 = np.array(features2.mfcc_features[:min_len])
                    # Use cosine similarity
                    mfcc_sim = 1 - cosine(mfcc1, mfcc2) if np.any(mfcc1) and np.any(mfcc2) else 0.0
                    mfcc_sim = max(0, mfcc_sim)
            
            # Weighted combination
            similarity = (duration_sim * 0.3 + energy_sim * 0.3 + mfcc_sim * 0.4)
            return similarity
            
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0
    
    def _compress_data(self, data: bytes) -> Tuple[bytes, float]:
        """Compress data if beneficial."""
        if not self.enable_compression or len(data) < self.compression_threshold:
            return data, 1.0
        
        try:
            compressed = gzip.compress(data)
            compression_ratio = len(data) / len(compressed)
            
            # Only use compression if it saves significant space
            if compression_ratio > 1.2:
                self.stats['compression_saves'] += 1
                return compressed, compression_ratio
            else:
                return data, 1.0
                
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return data, 1.0
    
    def _decompress_data(self, data: bytes, is_compressed: bool) -> bytes:
        """Decompress data if needed."""
        if not is_compressed:
            return data
        
        try:
            return gzip.decompress(data)
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            return data
    
    def _serialize_entry(self, entry: CacheEntry) -> bytes:
        """Serialize cache entry."""
        try:
            # Convert to dict and handle datetime serialization
            entry_dict = asdict(entry)
            entry_dict['created_at'] = entry_dict['created_at'].isoformat()
            entry_dict['accessed_at'] = entry_dict['accessed_at'].isoformat()
            
            # Use pickle for complex objects
            return pickle.dumps(entry_dict)
            
        except Exception as e:
            logger.error(f"Serialization failed: {e}")
            return b""
    
    def _deserialize_entry(self, data: bytes) -> Optional[CacheEntry]:
        """Deserialize cache entry."""
        try:
            entry_dict = pickle.loads(data)
            
            # Handle datetime deserialization
            entry_dict['created_at'] = datetime.fromisoformat(entry_dict['created_at'])
            entry_dict['accessed_at'] = datetime.fromisoformat(entry_dict['accessed_at'])
            
            return CacheEntry(**entry_dict)
            
        except Exception as e:
            logger.error(f"Deserialization failed: {e}")
            return None
    
    async def get(self, audio_data: np.ndarray, 
                 sample_rate: int = 16000,
                 language: Optional[str] = None) -> Optional[Tuple[TranscriptionResult, Optional[ProcessedTranscription]]]:
        """Get transcription from cache.
        
        Args:
            audio_data: Audio data to look up
            sample_rate: Audio sample rate
            language: Target language for filtering
            
        Returns:
            Tuple of (TranscriptionResult, ProcessedTranscription) or None
        """
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        try:
            # Generate audio hash
            audio_hash = self._generate_audio_hash(audio_data, sample_rate)
            
            # Try exact match first
            cache_key = f"transcription:{audio_hash}"
            if language:
                cache_key += f":{language}"
            
            entry = await self._get_cache_entry(cache_key)
            
            if entry:
                # Check TTL
                if datetime.now() - entry.created_at < timedelta(seconds=self.ttl_seconds):
                    # Update access information
                    entry.accessed_at = datetime.now()
                    entry.access_count += 1
                    await self._store_cache_entry(cache_key, entry)
                    
                    self.stats['cache_hits'] += 1
                    lookup_time = time.time() - start_time
                    self.stats['average_lookup_time'] = (
                        (self.stats['average_lookup_time'] * (self.stats['total_requests'] - 1) + lookup_time) /
                        self.stats['total_requests']
                    )
                    
                    logger.debug(f"Cache hit for audio hash: {audio_hash[:8]}")
                    return entry.transcription_result, entry.processed_result
            
            # Try fuzzy matching if enabled
            if self.enable_fuzzy_matching:
                fuzzy_result = await self._fuzzy_match(audio_data, sample_rate, language)
                if fuzzy_result:
                    self.stats['fuzzy_matches'] += 1
                    lookup_time = time.time() - start_time
                    self.stats['average_lookup_time'] = (
                        (self.stats['average_lookup_time'] * (self.stats['total_requests'] - 1) + lookup_time) /
                        self.stats['total_requests']
                    )
                    
                    logger.debug(f"Fuzzy match found for audio hash: {audio_hash[:8]}")
                    return fuzzy_result
            
            # Cache miss
            self.stats['cache_misses'] += 1
            lookup_time = time.time() - start_time
            self.stats['average_lookup_time'] = (
                (self.stats['average_lookup_time'] * (self.stats['total_requests'] - 1) + lookup_time) /
                self.stats['total_requests']
            )
            
            logger.debug(f"Cache miss for audio hash: {audio_hash[:8]}")
            return None
            
        except Exception as e:
            logger.error(f"Cache lookup failed: {e}")
            return None
    
    async def put(self, 
                 audio_data: np.ndarray,
                 transcription_result: TranscriptionResult,
                 processed_result: Optional[ProcessedTranscription] = None,
                 sample_rate: int = 16000,
                 model_version: str = "unknown",
                 processing_version: str = "unknown") -> None:
        """Store transcription in cache.
        
        Args:
            audio_data: Original audio data
            transcription_result: Transcription result to cache
            processed_result: Optional processed transcription
            sample_rate: Audio sample rate
            model_version: Model version for cache invalidation
            processing_version: Processing version for cache invalidation
        """
        try:
            # Generate audio hash and features
            audio_hash = self._generate_audio_hash(audio_data, sample_rate)
            
            audio_features = None
            if self.enable_audio_features:
                features = self._extract_audio_features(audio_data, sample_rate)
                audio_features = asdict(features)
                
                # Store features separately for fuzzy matching
                with self.cache_lock:
                    self.feature_cache[audio_hash] = features
            
            # Create cache entry
            entry = CacheEntry(
                transcription_result=transcription_result,
                processed_result=processed_result,
                audio_hash=audio_hash,
                audio_features=audio_features,
                created_at=datetime.now(),
                accessed_at=datetime.now(),
                access_count=1,
                language=transcription_result.language,
                model_version=model_version,
                processing_version=processing_version,
                file_size=len(audio_data.tobytes())
            )
            
            # Store entry
            cache_key = f"transcription:{audio_hash}"
            if transcription_result.language:
                cache_key += f":{transcription_result.language}"
            
            await self._store_cache_entry(cache_key, entry)
            
            logger.debug(f"Cached transcription for audio hash: {audio_hash[:8]}")
            
        except Exception as e:
            logger.error(f"Failed to cache transcription: {e}")
    
    async def _get_cache_entry(self, cache_key: str) -> Optional[CacheEntry]:
        """Get cache entry from storage."""
        # Try memory cache first
        with self.cache_lock:
            if cache_key in self.memory_cache:
                return self.memory_cache[cache_key]
        
        # Try Redis if available
        if REDIS_AVAILABLE and self.redis_client:
            try:
                data = await self.redis_client.get(cache_key)
                if data:
                    # Check if compressed
                    is_compressed = cache_key.endswith(':compressed')
                    decompressed_data = self._decompress_data(data, is_compressed)
                    entry = self._deserialize_entry(decompressed_data)
                    
                    if entry:
                        # Store in memory cache
                        with self.cache_lock:
                            self._add_to_memory_cache(cache_key, entry)
                        return entry
            except Exception as e:
                logger.error(f"Redis cache retrieval failed: {e}")
        
        # Try file cache if available
        if self.cache_dir:
            try:
                cache_file = self.cache_dir / "transcriptions" / f"{cache_key}.pkl"
                if cache_file.exists():
                    with open(cache_file, 'rb') as f:
                        data = f.read()
                    
                    is_compressed = cache_file.suffix == '.gz'
                    decompressed_data = self._decompress_data(data, is_compressed)
                    entry = self._deserialize_entry(decompressed_data)
                    
                    if entry:
                        # Store in memory cache
                        with self.cache_lock:
                            self._add_to_memory_cache(cache_key, entry)
                        return entry
            except Exception as e:
                logger.error(f"File cache retrieval failed: {e}")
        
        return None
    
    async def _store_cache_entry(self, cache_key: str, entry: CacheEntry) -> None:
        """Store cache entry in all available storage."""
        try:
            # Serialize entry
            serialized_data = self._serialize_entry(entry)
            if not serialized_data:
                return
            
            # Compress if beneficial
            compressed_data, compression_ratio = self._compress_data(serialized_data)
            entry.compression_ratio = compression_ratio
            is_compressed = compression_ratio > 1.2
            
            # Store in memory cache
            with self.cache_lock:
                self._add_to_memory_cache(cache_key, entry)
            
            # Store in Redis if available
            if REDIS_AVAILABLE and self.redis_client:
                try:
                    storage_key = cache_key + (':compressed' if is_compressed else '')
                    await self.redis_client.setex(
                        storage_key, 
                        self.ttl_seconds, 
                        compressed_data
                    )
                except Exception as e:
                    logger.error(f"Redis cache storage failed: {e}")
            
            # Store in file cache if available
            if self.cache_dir:
                try:
                    cache_file = self.cache_dir / "transcriptions" / f"{cache_key}.pkl"
                    if is_compressed:
                        cache_file = cache_file.with_suffix('.pkl.gz')
                    
                    with open(cache_file, 'wb') as f:
                        f.write(compressed_data)
                except Exception as e:
                    logger.error(f"File cache storage failed: {e}")
                    
        except Exception as e:
            logger.error(f"Cache entry storage failed: {e}")
    
    def _add_to_memory_cache(self, cache_key: str, entry: CacheEntry) -> None:
        """Add entry to memory cache with LRU eviction."""
        # Check if we need to evict entries
        if len(self.memory_cache) >= self.max_memory_entries:
            self._evict_lru_entries(self.max_memory_entries // 4)  # Evict 25%
        
        self.memory_cache[cache_key] = entry
        self.access_times[cache_key] = datetime.now()
        
        # Update memory usage stats
        self._update_memory_stats()
    
    def _evict_lru_entries(self, count: int) -> None:
        """Evict least recently used entries."""
        if not self.access_times:
            return
        
        # Sort by access time
        sorted_keys = sorted(self.access_times.keys(), 
                           key=lambda k: self.access_times[k])
        
        # Remove oldest entries
        for key in sorted_keys[:count]:
            self.memory_cache.pop(key, None)
            self.access_times.pop(key, None)
    
    def _update_memory_stats(self) -> None:
        """Update memory usage statistics."""
        try:
            total_size = 0
            for entry in self.memory_cache.values():
                # Rough size estimation
                total_size += entry.file_size
                if entry.processed_result:
                    total_size += len(entry.processed_result.text.encode('utf-8'))
            
            self.stats['memory_usage_mb'] = total_size / (1024 * 1024)
        except Exception:
            pass
    
    async def _fuzzy_match(self, 
                         audio_data: np.ndarray, 
                         sample_rate: int,
                         language: Optional[str]) -> Optional[Tuple[TranscriptionResult, Optional[ProcessedTranscription]]]:
        """Find similar audio in cache using fuzzy matching."""
        if not self.enable_fuzzy_matching or not FUZZY_MATCHING_AVAILABLE:
            return None
        
        try:
            # Extract features for query audio
            query_features = self._extract_audio_features(audio_data, sample_rate)
            
            # Find similar audio in cache
            candidates = []
            
            with self.cache_lock:
                for cached_hash, cached_features in list(self.feature_cache.items()):
                    similarity = self._calculate_audio_similarity(query_features, cached_features)
                    if similarity >= self.fuzzy_threshold:
                        candidates.append((cached_hash, similarity))
            
            if not candidates:
                return None
            
            # Sort by similarity and take best matches
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_candidates = candidates[:self.max_fuzzy_candidates]
            
            # Try to retrieve the best matching transcription
            for cached_hash, similarity in best_candidates:
                cache_key = f"transcription:{cached_hash}"
                if language:
                    cache_key += f":{language}"
                
                entry = await self._get_cache_entry(cache_key)
                if entry and datetime.now() - entry.created_at < timedelta(seconds=self.ttl_seconds):
                    logger.debug(f"Fuzzy match found with similarity: {similarity:.3f}")
                    return entry.transcription_result, entry.processed_result
            
            return None
            
        except Exception as e:
            logger.error(f"Fuzzy matching failed: {e}")
            return None
    
    async def invalidate_by_model_version(self, model_version: str) -> int:
        """Invalidate cache entries by model version.
        
        Args:
            model_version: Model version to invalidate
            
        Returns:
            Number of entries invalidated
        """
        count = 0
        
        try:
            # Invalidate from memory cache
            with self.cache_lock:
                keys_to_remove = [
                    key for key, entry in self.memory_cache.items()
                    if entry.model_version == model_version
                ]
                
                for key in keys_to_remove:
                    self.memory_cache.pop(key, None)
                    self.access_times.pop(key, None)
                    count += 1
            
            # TODO: Implement Redis and file cache invalidation
            # This would require iterating through all keys, which can be expensive
            
            logger.info(f"Invalidated {count} cache entries for model version: {model_version}")
            return count
            
        except Exception as e:
            logger.error(f"Cache invalidation failed: {e}")
            return 0
    
    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries.
        
        Returns:
            Number of entries cleaned up
        """
        count = 0
        cutoff_time = datetime.now() - timedelta(seconds=self.ttl_seconds)
        
        try:
            # Clean memory cache
            with self.cache_lock:
                keys_to_remove = [
                    key for key, entry in self.memory_cache.items()
                    if entry.created_at < cutoff_time
                ]
                
                for key in keys_to_remove:
                    self.memory_cache.pop(key, None)
                    self.access_times.pop(key, None)
                    count += 1
            
            # Clean file cache
            if self.cache_dir:
                cache_files = list((self.cache_dir / "transcriptions").glob("*.pkl*"))
                for cache_file in cache_files:
                    if cache_file.stat().st_mtime < cutoff_time.timestamp():
                        try:
                            cache_file.unlink()
                            count += 1
                        except Exception as e:
                            logger.error(f"Failed to remove expired cache file: {e}")
            
            if count > 0:
                logger.info(f"Cleaned up {count} expired cache entries")
            
            return count
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = self.stats.copy()
        
        # Add calculated metrics
        total_requests = stats['total_requests']
        if total_requests > 0:
            stats['hit_rate'] = stats['cache_hits'] / total_requests * 100
            stats['miss_rate'] = stats['cache_misses'] / total_requests * 100
            stats['fuzzy_match_rate'] = stats['fuzzy_matches'] / total_requests * 100
        
        # Add current state
        with self.cache_lock:
            stats['memory_cache_size'] = len(self.memory_cache)
            stats['feature_cache_size'] = len(self.feature_cache)
        
        stats['redis_enabled'] = REDIS_AVAILABLE and self.redis_client is not None
        stats['file_cache_enabled'] = self.cache_dir is not None
        stats['fuzzy_matching_enabled'] = self.enable_fuzzy_matching
        stats['compression_enabled'] = self.enable_compression
        
        return stats
    
    async def clear_cache(self) -> None:
        """Clear all cache data."""
        try:
            # Clear memory cache
            with self.cache_lock:
                self.memory_cache.clear()
                self.access_times.clear()
                self.feature_cache.clear()
            
            # Clear Redis cache
            if REDIS_AVAILABLE and self.redis_client:
                try:
                    keys = await self.redis_client.keys("transcription:*")
                    if keys:
                        await self.redis_client.delete(*keys)
                except Exception as e:
                    logger.error(f"Redis cache clear failed: {e}")
            
            # Clear file cache
            if self.cache_dir:
                try:
                    cache_files = list((self.cache_dir / "transcriptions").glob("*.pkl*"))
                    for cache_file in cache_files:
                        cache_file.unlink()
                except Exception as e:
                    logger.error(f"File cache clear failed: {e}")
            
            # Reset stats
            self.stats = {k: 0.0 for k in self.stats.keys()}
            
            logger.info("Cache cleared successfully")
            
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
    
    async def close(self) -> None:
        """Close cache and cleanup resources."""
        try:
            if REDIS_AVAILABLE and self.redis_client:
                await self.redis_client.close()
            
            with self.cache_lock:
                self.memory_cache.clear()
                self.access_times.clear()
                self.feature_cache.clear()
            
            logger.info("TranscriptionCache closed")
            
        except Exception as e:
            logger.error(f"Cache close failed: {e}")