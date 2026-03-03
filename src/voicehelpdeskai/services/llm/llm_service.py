"""Base LLM service with support for multiple backends and optimizations."""

import asyncio
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator, Any, Union, Tuple
import json
import psutil
import gc

import numpy as np
from loguru import logger

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available - some features disabled")

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available - using approximation for token counting")

from voicehelpdeskai.config.manager import get_config_manager


class LLMBackend(Enum):
    """Supported LLM backends."""
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"
    VLLM = "vllm"
    TRANSFORMERS = "transformers"
    OPENAI = "openai"


class QuantizationType(Enum):
    """Quantization types supported."""
    NONE = "none"
    INT4 = "4bit"
    INT8 = "8bit"
    FP16 = "fp16"
    BF16 = "bf16"


@dataclass
class ModelConfig:
    """Model configuration settings."""
    name: str
    backend: LLMBackend
    model_path: Optional[str] = None
    quantization: QuantizationType = QuantizationType.NONE
    context_length: int = 4096
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repetition_penalty: float = 1.0
    gpu_layers: int = -1  # -1 for auto
    rope_freq_base: float = 10000.0
    rope_freq_scale: float = 1.0
    batch_size: int = 1
    threads: int = 0  # 0 for auto
    mmap: bool = True
    mlock: bool = False
    numa: bool = False


@dataclass
class GenerationParams:
    """Parameters for text generation."""
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repetition_penalty: Optional[float] = None
    stop_sequences: Optional[List[str]] = None
    stream: bool = False
    include_usage: bool = True


@dataclass
class LLMResponse:
    """Response from LLM with metadata."""
    text: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    response_time: float = 0.0
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamingChunk:
    """Streaming response chunk."""
    text: str
    is_complete: bool = False
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TokenCounter:
    """Token counting utilities."""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        """Initialize token counter.
        
        Args:
            model_name: Model name for tiktoken encoding
        """
        self.model_name = model_name
        self.encoder = None
        
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoder = tiktoken.encoding_for_model(model_name)
            except KeyError:
                try:
                    self.encoder = tiktoken.get_encoding("cl100k_base")
                except Exception as e:
                    logger.warning(f"Failed to load tiktoken encoder: {e}")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.encoder:
            return len(self.encoder.encode(text))
        else:
            # Rough approximation: 1 token ≈ 4 characters for most models
            return len(text) // 4
    
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to maximum tokens."""
        if self.encoder:
            tokens = self.encoder.encode(text)
            if len(tokens) <= max_tokens:
                return text
            truncated_tokens = tokens[:max_tokens]
            return self.encoder.decode(truncated_tokens)
        else:
            # Rough approximation
            max_chars = max_tokens * 4
            if len(text) <= max_chars:
                return text
            return text[:max_chars]


class MemoryManager:
    """Memory management for LLM operations."""
    
    @staticmethod
    def get_available_memory() -> Dict[str, float]:
        """Get available system and GPU memory in GB."""
        memory_info = {}
        
        # System memory
        system_memory = psutil.virtual_memory()
        memory_info['system_total'] = system_memory.total / (1024**3)
        memory_info['system_available'] = system_memory.available / (1024**3)
        memory_info['system_used'] = system_memory.used / (1024**3)
        
        # GPU memory
        if TORCH_AVAILABLE and torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                gpu_memory = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                gpu_used = torch.cuda.memory_allocated(i) / (1024**3)
                gpu_free = gpu_memory - gpu_used
                
                memory_info[f'gpu_{i}_total'] = gpu_memory
                memory_info[f'gpu_{i}_used'] = gpu_used
                memory_info[f'gpu_{i}_free'] = gpu_free
        
        return memory_info
    
    @staticmethod
    def optimize_for_8gb_gpu(config: ModelConfig) -> ModelConfig:
        """Optimize model config for 8GB GPU."""
        memory_info = MemoryManager.get_available_memory()
        
        # Check if we have a GPU with ~8GB
        gpu_memory = 0
        for key, value in memory_info.items():
            if key.startswith('gpu_') and key.endswith('_total'):
                gpu_memory = max(gpu_memory, value)
        
        if 6 < gpu_memory < 10:  # ~8GB GPU detected
            logger.info(f"Detected ~8GB GPU, optimizing model config")
            
            # Use quantization for memory efficiency
            if config.quantization == QuantizationType.NONE:
                config.quantization = QuantizationType.INT8
            
            # Limit context length to save memory
            if config.context_length > 8192:
                config.context_length = 8192
                logger.info(f"Reduced context length to {config.context_length}")
            
            # Optimize batch size
            config.batch_size = 1
            
            # Use memory mapping
            config.mmap = True
            config.mlock = False  # Don't lock memory on smaller GPUs
        
        return config
    
    @staticmethod
    def cleanup_memory():
        """Clean up memory."""
        gc.collect()
        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()


class LLMService(ABC):
    """Abstract base class for LLM services."""
    
    def __init__(self, 
                 config: ModelConfig,
                 enable_caching: bool = True,
                 cache_size: int = 100):
        """Initialize LLM service.
        
        Args:
            config: Model configuration
            enable_caching: Enable response caching
            cache_size: Maximum cache size
        """
        self.config = config
        self.enable_caching = enable_caching
        self.cache_size = cache_size
        
        # Service state
        self.is_loaded = False
        self.is_loading = False
        self.load_lock = threading.Lock()
        
        # Token management
        self.token_counter = TokenCounter()
        self.memory_manager = MemoryManager()
        
        # Response cache
        self.response_cache: Dict[str, LLMResponse] = {}
        self.cache_access_times: Dict[str, float] = {}
        
        # Performance tracking
        self.stats = {
            'total_requests': 0,
            'cached_requests': 0,
            'total_tokens_input': 0,
            'total_tokens_output': 0,
            'total_response_time': 0.0,
            'average_response_time': 0.0,
            'average_tokens_per_second': 0.0,
            'errors': 0,
            'last_error': None,
        }
        
        # Configuration manager
        self.app_config = get_config_manager().get_config()
        
        logger.info(f"LLM Service initialized: {config.name} ({config.backend.value})")
    
    @abstractmethod
    async def load_model(self) -> None:
        """Load the model."""
        pass
    
    @abstractmethod
    async def unload_model(self) -> None:
        """Unload the model to free memory."""
        pass
    
    @abstractmethod
    async def generate(self, 
                      prompt: str, 
                      params: Optional[GenerationParams] = None) -> LLMResponse:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    async def generate_stream(self, 
                            prompt: str, 
                            params: Optional[GenerationParams] = None) -> AsyncGenerator[StreamingChunk, None]:
        """Generate streaming text from prompt."""
        pass
    
    async def ensure_loaded(self) -> None:
        """Ensure model is loaded."""
        if self.is_loaded:
            return
        
        if self.is_loading:
            # Wait for loading to complete
            while self.is_loading:
                await asyncio.sleep(0.1)
            return
        
        with self.load_lock:
            if self.is_loaded:
                return
            
            self.is_loading = True
            try:
                await self.load_model()
                self.is_loaded = True
                logger.success(f"Model {self.config.name} loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model {self.config.name}: {e}")
                raise
            finally:
                self.is_loading = False
    
    def _generate_cache_key(self, prompt: str, params: Optional[GenerationParams]) -> str:
        """Generate cache key for prompt and parameters."""
        key_data = {
            'prompt': prompt,
            'model': self.config.name,
            'max_tokens': params.max_tokens if params else self.config.max_tokens,
            'temperature': params.temperature if params else self.config.temperature,
            'top_p': params.top_p if params else self.config.top_p,
            'top_k': params.top_k if params else self.config.top_k,
        }
        
        import hashlib
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[LLMResponse]:
        """Get response from cache."""
        if not self.enable_caching or cache_key not in self.response_cache:
            return None
        
        # Update access time
        self.cache_access_times[cache_key] = time.time()
        
        response = self.response_cache[cache_key]
        response.cached = True
        
        return response
    
    def _add_to_cache(self, cache_key: str, response: LLMResponse) -> None:
        """Add response to cache."""
        if not self.enable_caching:
            return
        
        # Remove oldest entries if cache is full
        while len(self.response_cache) >= self.cache_size:
            oldest_key = min(self.cache_access_times.keys(), 
                           key=lambda k: self.cache_access_times[k])
            self.response_cache.pop(oldest_key, None)
            self.cache_access_times.pop(oldest_key, None)
        
        self.response_cache[cache_key] = response
        self.cache_access_times[cache_key] = time.time()
    
    def _update_stats(self, response: LLMResponse, cached: bool = False) -> None:
        """Update performance statistics."""
        self.stats['total_requests'] += 1
        
        if cached:
            self.stats['cached_requests'] += 1
        else:
            # Update token and timing stats only for non-cached responses
            if 'prompt_tokens' in response.usage:
                self.stats['total_tokens_input'] += response.usage['prompt_tokens']
            if 'completion_tokens' in response.usage:
                self.stats['total_tokens_output'] += response.usage['completion_tokens']
            
            self.stats['total_response_time'] += response.response_time
            
            # Calculate averages
            non_cached_requests = self.stats['total_requests'] - self.stats['cached_requests']
            if non_cached_requests > 0:
                self.stats['average_response_time'] = (
                    self.stats['total_response_time'] / non_cached_requests
                )
                
                total_output_tokens = self.stats['total_tokens_output']
                if total_output_tokens > 0 and self.stats['total_response_time'] > 0:
                    self.stats['average_tokens_per_second'] = (
                        total_output_tokens / self.stats['total_response_time']
                    )
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return self.token_counter.count_tokens(text)
    
    def truncate_to_context(self, text: str, reserve_tokens: int = 0) -> str:
        """Truncate text to fit in context window."""
        max_tokens = self.config.context_length - reserve_tokens
        return self.token_counter.truncate_to_tokens(text, max_tokens)
    
    def validate_generation_params(self, params: Optional[GenerationParams]) -> GenerationParams:
        """Validate and fill in generation parameters."""
        if params is None:
            params = GenerationParams()
        
        # Fill in defaults from config
        if params.max_tokens is None:
            params.max_tokens = self.config.max_tokens
        if params.temperature is None:
            params.temperature = self.config.temperature
        if params.top_p is None:
            params.top_p = self.config.top_p
        if params.top_k is None:
            params.top_k = self.config.top_k
        if params.repetition_penalty is None:
            params.repetition_penalty = self.config.repetition_penalty
        
        # Validate ranges
        params.temperature = max(0.0, min(2.0, params.temperature))
        params.top_p = max(0.0, min(1.0, params.top_p))
        params.top_k = max(1, min(100, params.top_k))
        params.repetition_penalty = max(0.1, min(2.0, params.repetition_penalty))
        params.max_tokens = max(1, min(self.config.max_tokens, params.max_tokens))
        
        return params
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the service."""
        health = {
            'status': 'healthy',
            'model_loaded': self.is_loaded,
            'model_loading': self.is_loading,
            'backend': self.config.backend.value,
            'model_name': self.config.name,
            'memory_info': self.memory_manager.get_available_memory(),
        }
        
        # Check if model is responsive
        if self.is_loaded:
            try:
                test_response = await self.generate(
                    "Test", 
                    GenerationParams(max_tokens=1, temperature=0.0)
                )
                health['response_test'] = 'passed'
                health['last_response_time'] = test_response.response_time
            except Exception as e:
                health['status'] = 'degraded'
                health['response_test'] = 'failed'
                health['error'] = str(e)
        else:
            health['status'] = 'not_ready'
        
        return health
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = self.stats.copy()
        
        # Add calculated metrics
        if stats['total_requests'] > 0:
            stats['cache_hit_rate'] = (
                stats['cached_requests'] / stats['total_requests'] * 100
            )
        
        # Add memory info
        stats['memory_info'] = self.memory_manager.get_available_memory()
        stats['cache_size'] = len(self.response_cache)
        stats['max_cache_size'] = self.cache_size
        
        return stats
    
    def clear_cache(self) -> int:
        """Clear response cache.
        
        Returns:
            Number of entries cleared
        """
        count = len(self.response_cache)
        self.response_cache.clear()
        self.cache_access_times.clear()
        return count
    
    async def warmup(self) -> None:
        """Warm up the model with a test generation."""
        try:
            await self.ensure_loaded()
            await self.generate(
                "Hello", 
                GenerationParams(max_tokens=5, temperature=0.0)
            )
            logger.info(f"Model {self.config.name} warmed up successfully")
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        try:
            if self.is_loaded:
                await self.unload_model()
            
            self.clear_cache()
            self.memory_manager.cleanup_memory()
            
            logger.info(f"LLM Service {self.config.name} shut down")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# Backend-specific implementations will be in separate files
class BackendFactory:
    """Factory for creating LLM service instances."""
    
    @staticmethod
    def create_service(config: ModelConfig, **kwargs) -> LLMService:
        """Create LLM service instance based on backend."""
        if config.backend == LLMBackend.OLLAMA:
            from .ollama_service import OllamaService
            return OllamaService(config, **kwargs)
        elif config.backend == LLMBackend.LLAMA_CPP:
            from .llama_cpp_service import LlamaCppService
            return LlamaCppService(config, **kwargs)
        elif config.backend == LLMBackend.VLLM:
            from .vllm_service import VLLMService
            return VLLMService(config, **kwargs)
        elif config.backend == LLMBackend.TRANSFORMERS:
            from .transformers_service import TransformersService
            return TransformersService(config, **kwargs)
        elif config.backend == LLMBackend.OPENAI:
            from .openai_service import OpenAIService
            return OpenAIService(config, **kwargs)
        else:
            raise ValueError(f"Unsupported backend: {config.backend}")
    
    @staticmethod
    def get_optimal_config_for_model(model_name: str, 
                                   backend: LLMBackend,
                                   optimize_for_8gb: bool = True) -> ModelConfig:
        """Get optimal configuration for a specific model."""
        configs = {
            "mistral-7b": ModelConfig(
                name="mistral-7b-instruct-v0.1",
                backend=backend,
                context_length=8192,
                max_tokens=2048,
                temperature=0.7,
                quantization=QuantizationType.INT8 if optimize_for_8gb else QuantizationType.NONE,
                gpu_layers=-1
            ),
            "llama2-7b": ModelConfig(
                name="llama2-7b-chat",
                backend=backend,
                context_length=4096,
                max_tokens=1024,
                temperature=0.7,
                quantization=QuantizationType.INT4 if optimize_for_8gb else QuantizationType.NONE,
                gpu_layers=-1
            ),
        }
        
        config = configs.get(model_name.lower())
        if config is None:
            # Default config
            config = ModelConfig(
                name=model_name,
                backend=backend,
                quantization=QuantizationType.INT8 if optimize_for_8gb else QuantizationType.NONE
            )
        
        if optimize_for_8gb:
            config = MemoryManager.optimize_for_8gb_gpu(config)
        
        return config