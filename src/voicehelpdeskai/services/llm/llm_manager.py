"""LLM Service Manager for coordinating all LLM components and operations."""

import asyncio
import time
from typing import Dict, List, Optional, Any, AsyncGenerator, Union
from pathlib import Path
import threading
from datetime import datetime

from loguru import logger

from .llm_service import LLMService, ModelConfig, GenerationParams, LLMResponse, LLMBackend, QuantizationType
from .mistral_service import MistralService, KnowledgeBaseEntry
from .prompt_manager import PromptManager, TaskType
from .conversation_manager import ConversationManager, ConversationState, MessageType
from voicehelpdeskai.config.manager import get_config_manager


class LLMManager:
    """Centralized manager for all LLM services and coordination."""
    
    def __init__(self,
                 model_name: str = "gemma3-1B",
                 backend: str = "transformers",
                 quantization: str = "int8",
                 enable_conversation_management: bool = True,
                 enable_prompt_management: bool = True,
                 enable_rag: bool = True,
                 optimize_for_8gb: bool = True):
        """Initialize LLM Manager.
        
        Args:
            model_name: Name of the model to use
            backend: Backend for LLM inference
            quantization: Quantization type
            enable_conversation_management: Enable conversation tracking
            enable_prompt_management: Enable advanced prompt features
            enable_rag: Enable RAG capabilities
            optimize_for_8gb: Optimize for 8GB GPU memory
        """
        self.config = get_config_manager().get_config()
        self.model_name = model_name
        self.backend = backend
        self.quantization = quantization
        self.enable_conversation_management = enable_conversation_management
        self.enable_prompt_management = enable_prompt_management
        self.enable_rag = enable_rag
        self.optimize_for_8gb = optimize_for_8gb
        
        # Core services
        self.llm_service: Optional[LLMService] = None
        self.prompt_manager: Optional[PromptManager] = None
        self.conversation_manager: Optional[ConversationManager] = None
        
        # Service state
        self.is_initialized = False
        self.initialization_lock = threading.Lock()
        
        # Performance tracking
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_response_time': 0.0,
            'average_response_time': 0.0,
            'total_tokens_generated': 0,
            'average_tokens_per_second': 0.0,
            'conversations_managed': 0,
            'prompts_optimized': 0,
            'rag_queries': 0,
            'cache_hits': 0,
            'errors': 0,
            'last_error': None,
        }
        
        logger.info(f"LLM Manager initialized: model={model_name}, backend={backend}")
    
    async def initialize(self) -> None:
        """Initialize all LLM services."""
        if self.is_initialized:
            logger.warning("LLM Manager already initialized")
            return
        
        with self.initialization_lock:
            if self.is_initialized:
                return
            
            try:
                logger.info("Initializing LLM services...")
                
                # Create model configuration
                backend_enum = self._map_backend_string(self.backend)
                config = self._create_model_config(backend_enum)
                
                # Initialize LLM service
                if self.model_name.startswith("mistral"):
                    self.llm_service = MistralService(
                        config=config,
                        enable_rag=self.enable_rag,
                        enable_function_calling=True,
                        conversation_memory_size=20
                    )
                    logger.success("Mistral service initialized")
                else:
                    from .llm_service import BackendFactory
                    self.llm_service = BackendFactory.create_service(config)
                    logger.success("LLM service initialized")
                
                # Initialize prompt manager
                if self.enable_prompt_management:
                    prompts_dir = Path(self.config.ai_models.model_cache_dir) / "prompts"
                    self.prompt_manager = PromptManager(
                        templates_dir=prompts_dir,
                        enable_ab_testing=True,
                        enable_performance_tracking=True,
                        auto_optimization=True
                    )
                    logger.success("Prompt manager initialized")
                
                # Initialize conversation manager
                if self.enable_conversation_management and self.prompt_manager:
                    self.conversation_manager = ConversationManager(
                        llm_service=self.llm_service,
                        prompt_manager=self.prompt_manager,
                        max_context_length=8000,
                        auto_summarize=True,
                        sentiment_tracking=True,
                        entity_tracking=True
                    )
                    logger.success("Conversation manager initialized")
                
                # Load model and warm up
                await self._warmup_services()
                
                self.is_initialized = True
                logger.success("LLM Manager initialization complete")
                
            except Exception as e:
                logger.error(f"LLM Manager initialization failed: {e}")
                self.stats['errors'] += 1
                self.stats['last_error'] = str(e)
                raise
    
    def _map_backend_string(self, backend: str) -> LLMBackend:
        """Map backend string to enum."""
        mapping = {
            "transformers": LLMBackend.TRANSFORMERS,
            "ollama": LLMBackend.OLLAMA,
            "llama_cpp": LLMBackend.LLAMA_CPP,
            "vllm": LLMBackend.VLLM,
            "openai": LLMBackend.OPENAI
        }
        return mapping.get(backend.lower(), LLMBackend.TRANSFORMERS)
    
    def _map_quantization_string(self, quantization: str) -> QuantizationType:
        """Map quantization string to enum."""
        mapping = {
            "none": QuantizationType.NONE,
            "int4": QuantizationType.INT4,
            "int8": QuantizationType.INT8,
            "fp16": QuantizationType.FP16,
            "bf16": QuantizationType.BF16
        }
        return mapping.get(quantization.lower(), QuantizationType.INT8)
    
    def _create_model_config(self, backend: LLMBackend) -> ModelConfig:
        """Create model configuration."""
        from .llm_service import BackendFactory, MemoryManager
        
        config = BackendFactory.get_optimal_config_for_model(
            model_name=self.model_name,
            backend=backend,
            optimize_for_8gb=self.optimize_for_8gb
        )
        
        # Override quantization
        config.quantization = self._map_quantization_string(self.quantization)
        
        # Apply memory optimization if needed
        if self.optimize_for_8gb:
            config = MemoryManager.optimize_for_8gb_gpu(config)
        
        return config
    
    async def _warmup_services(self) -> None:
        """Warm up all services for better first-request performance."""
        try:
            if self.llm_service:
                await self.llm_service.warmup()
            
            logger.info("LLM services warmed up successfully")
            
        except Exception as e:
            logger.warning(f"Service warmup failed: {e}")
    
    async def generate_response(self,
                              prompt: str,
                              conversation_id: Optional[str] = None,
                              task_type: Optional[TaskType] = None,
                              template_id: Optional[str] = None,
                              template_variables: Optional[Dict[str, Any]] = None,
                              generation_params: Optional[GenerationParams] = None,
                              use_conversation_context: bool = True) -> LLMResponse:
        """Generate response with full LLM stack integration.
        
        Args:
            prompt: Input prompt or user message
            conversation_id: Optional conversation ID for context
            task_type: Type of task for prompt optimization
            template_id: Optional specific template ID to use
            template_variables: Variables for template rendering
            generation_params: Generation parameters
            use_conversation_context: Whether to use conversation context
            
        Returns:
            LLM response with metadata
        """
        if not self.is_initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Prepare the final prompt
            final_prompt = prompt
            
            # Use template if specified
            if template_id and self.prompt_manager:
                final_prompt = self.prompt_manager.render_template(
                    template_id=template_id,
                    variables=template_variables or {},
                    include_examples=True
                )
            elif task_type and self.prompt_manager:
                # Find best template for task
                templates = self.prompt_manager.get_templates_by_task(task_type)
                if templates:
                    template = templates[0]  # Use first/best template
                    variables = template_variables or {'user_request': prompt}
                    final_prompt = self.prompt_manager.render_template(
                        template_id=template.id,
                        variables=variables,
                        include_examples=True
                    )
            
            # Add conversation context if enabled
            if (use_conversation_context and 
                conversation_id and 
                self.conversation_manager):
                try:
                    context = await self.conversation_manager.get_conversation_context(
                        conversation_id, max_messages=10
                    )
                    final_prompt = f"{context}\n\nNUOVA RICHIESTA UTENTE: {prompt}"
                except ValueError:
                    # Conversation not found, use original prompt
                    pass
            
            # Generate response
            response = await self.llm_service.generate(
                prompt=final_prompt,
                params=generation_params
            )
            
            # Add to conversation if manager available
            if conversation_id and self.conversation_manager:
                try:
                    await self.conversation_manager.add_message(
                        conversation_id=conversation_id,
                        message_type=MessageType.USER,
                        content=prompt
                    )
                    await self.conversation_manager.add_message(
                        conversation_id=conversation_id,
                        message_type=MessageType.ASSISTANT,
                        content=response.text
                    )
                except ValueError:
                    # Conversation doesn't exist, skip
                    pass
            
            # Update statistics
            self.stats['total_requests'] += 1
            self.stats['successful_requests'] += 1
            
            processing_time = time.time() - start_time
            self.stats['total_response_time'] += processing_time
            self.stats['average_response_time'] = (
                self.stats['total_response_time'] / self.stats['successful_requests']
            )
            
            if 'completion_tokens' in response.usage:
                self.stats['total_tokens_generated'] += response.usage['completion_tokens']
                self.stats['average_tokens_per_second'] = (
                    self.stats['total_tokens_generated'] / self.stats['total_response_time']
                )
            
            if response.cached:
                self.stats['cache_hits'] += 1
            
            logger.debug(f"Generated response in {processing_time:.2f}s: "
                        f"'{response.text[:50]}{'...' if len(response.text) > 50 else ''}'")
            
            return response
            
        except Exception as e:
            self.stats['total_requests'] += 1
            self.stats['failed_requests'] += 1
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            processing_time = time.time() - start_time
            logger.error(f"Response generation failed after {processing_time:.2f}s: {e}")
            raise
    
    async def generate_streaming_response(self,
                                        prompt: str,
                                        conversation_id: Optional[str] = None,
                                        generation_params: Optional[GenerationParams] = None,
                                        use_conversation_context: bool = True) -> AsyncGenerator[str, None]:
        """Generate streaming response.
        
        Args:
            prompt: Input prompt
            conversation_id: Optional conversation ID
            generation_params: Generation parameters
            use_conversation_context: Whether to use conversation context
            
        Yields:
            Response chunks as strings
        """
        if not self.is_initialized:
            await self.initialize()
        
        try:
            # Prepare prompt with context
            final_prompt = prompt
            if (use_conversation_context and 
                conversation_id and 
                self.conversation_manager):
                try:
                    context = await self.conversation_manager.get_conversation_context(
                        conversation_id, max_messages=10
                    )
                    final_prompt = f"{context}\n\nNUOVA RICHIESTA UTENTE: {prompt}"
                except ValueError:
                    pass
            
            # Generate streaming response
            full_response = ""
            async for chunk in self.llm_service.generate_stream(
                prompt=final_prompt,
                params=generation_params
            ):
                if chunk.text:
                    full_response += chunk.text
                    yield chunk.text
                
                if chunk.is_complete:
                    break
            
            # Add to conversation
            if conversation_id and self.conversation_manager:
                try:
                    await self.conversation_manager.add_message(
                        conversation_id=conversation_id,
                        message_type=MessageType.USER,
                        content=prompt
                    )
                    await self.conversation_manager.add_message(
                        conversation_id=conversation_id,
                        message_type=MessageType.ASSISTANT,
                        content=full_response
                    )
                except ValueError:
                    pass
            
            self.stats['total_requests'] += 1
            self.stats['successful_requests'] += 1
            
        except Exception as e:
            self.stats['total_requests'] += 1
            self.stats['failed_requests'] += 1
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            logger.error(f"Streaming response generation failed: {e}")
            raise
    
    async def start_conversation(self,
                               user_id: str,
                               session_id: str,
                               initial_message: Optional[str] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start new conversation.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            initial_message: Optional initial message
            metadata: Optional metadata
            
        Returns:
            Conversation ID
        """
        if not self.conversation_manager:
            raise RuntimeError("Conversation management not enabled")
        
        conversation_id = await self.conversation_manager.start_conversation(
            user_id=user_id,
            session_id=session_id,
            initial_message=initial_message,
            metadata=metadata
        )
        
        self.stats['conversations_managed'] += 1
        return conversation_id
    
    async def add_knowledge_base_entry(self, entry: KnowledgeBaseEntry) -> None:
        """Add entry to knowledge base for RAG.
        
        Args:
            entry: Knowledge base entry
        """
        if isinstance(self.llm_service, MistralService):
            self.llm_service.add_knowledge_base_entry(entry)
            self.stats['rag_queries'] += 1
        else:
            logger.warning("Knowledge base only supported with MistralService")
    
    async def optimize_prompt_for_task(self,
                                     task_type: TaskType,
                                     performance_data: Optional[Dict[str, float]] = None) -> Optional[str]:
        """Optimize prompt for specific task.
        
        Args:
            task_type: Task type to optimize for
            performance_data: Optional performance metrics
            
        Returns:
            Optimized template ID
        """
        if not self.prompt_manager:
            return None
        
        templates = self.prompt_manager.get_templates_by_task(task_type)
        if not templates:
            return None
        
        # Optimize first template for current model
        optimized_id = self.prompt_manager.optimize_prompt_for_model(
            template_id=templates[0].id,
            model_name=self.model_name,
            performance_data=performance_data
        )
        
        self.stats['prompts_optimized'] += 1
        return optimized_id
    
    async def get_conversation_summary(self, conversation_id: str) -> Optional[str]:
        """Get conversation summary.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Summary ID or None
        """
        if not self.conversation_manager:
            return None
        
        return await self.conversation_manager.summarize_conversation(conversation_id)
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status."""
        status = {
            'initialized': self.is_initialized,
            'services': {
                'llm_service': self.llm_service is not None,
                'prompt_manager': self.prompt_manager is not None,
                'conversation_manager': self.conversation_manager is not None,
            },
            'configuration': {
                'model_name': self.model_name,
                'backend': self.backend,
                'quantization': self.quantization,
                'conversation_management': self.enable_conversation_management,
                'prompt_management': self.enable_prompt_management,
                'rag_enabled': self.enable_rag,
                'optimize_for_8gb': self.optimize_for_8gb,
            },
            'performance': self.stats.copy()
        }
        
        # Add service-specific stats
        if self.llm_service:
            llm_stats = self.llm_service.get_stats()
            status['llm_service_stats'] = llm_stats
            
            # Health check
            health = await self.llm_service.health_check()
            status['llm_service_health'] = health
        
        if self.prompt_manager:
            status['prompt_manager_stats'] = self.prompt_manager.get_analytics()
        
        if self.conversation_manager:
            status['conversation_manager_stats'] = self.conversation_manager.get_manager_stats()
        
        return status
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all services."""
        health = {
            'overall_status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {},
            'errors': []
        }
        
        try:
            # Check initialization
            if not self.is_initialized:
                health['services']['initialization'] = 'not_initialized'
                health['overall_status'] = 'unhealthy'
                health['errors'].append('Manager not initialized')
            else:
                health['services']['initialization'] = 'healthy'
            
            # Check LLM service
            if self.llm_service:
                llm_health = await self.llm_service.health_check()
                health['services']['llm_service'] = llm_health['status']
                if llm_health['status'] != 'healthy':
                    health['overall_status'] = 'degraded'
                    if 'error' in llm_health:
                        health['errors'].append(f"LLM service: {llm_health['error']}")
            else:
                health['services']['llm_service'] = 'disabled'
            
            # Check prompt manager
            if self.enable_prompt_management:
                if self.prompt_manager:
                    health['services']['prompt_manager'] = 'healthy'
                else:
                    health['services']['prompt_manager'] = 'unhealthy'
                    health['errors'].append('Prompt manager not initialized')
                    health['overall_status'] = 'degraded'
            else:
                health['services']['prompt_manager'] = 'disabled'
            
            # Check conversation manager
            if self.enable_conversation_management:
                if self.conversation_manager:
                    health['services']['conversation_manager'] = 'healthy'
                else:
                    health['services']['conversation_manager'] = 'unhealthy'
                    health['errors'].append('Conversation manager not initialized')
                    health['overall_status'] = 'degraded'
            else:
                health['services']['conversation_manager'] = 'disabled'
            
            # Add error stats
            if self.stats['errors'] > 0:
                health['recent_errors'] = self.stats['errors']
                health['last_error'] = self.stats['last_error']
                if self.stats['failed_requests'] / max(self.stats['total_requests'], 1) > 0.1:
                    health['overall_status'] = 'degraded'
            
        except Exception as e:
            health['overall_status'] = 'unhealthy'
            health['errors'].append(f'Health check failed: {str(e)}')
        
        return health
    
    async def cleanup_resources(self) -> Dict[str, int]:
        """Clean up old resources and data."""
        cleanup_stats = {'total_cleaned': 0}
        
        try:
            # Cleanup conversations
            if self.conversation_manager:
                cleaned = await self.conversation_manager.cleanup_old_conversations(24)
                cleanup_stats['old_conversations'] = cleaned
                cleanup_stats['total_cleaned'] += cleaned
            
            # Cleanup caches
            if self.llm_service:
                cleaned = self.llm_service.clear_cache()
                cleanup_stats['cache_entries'] = cleaned
                cleanup_stats['total_cleaned'] += cleaned
            
            logger.info(f"Cleaned up {cleanup_stats['total_cleaned']} resources")
            
        except Exception as e:
            logger.error(f"Resource cleanup failed: {e}")
            cleanup_stats['error'] = str(e)
        
        return cleanup_stats
    
    async def shutdown(self) -> None:
        """Shutdown all services and cleanup resources."""
        try:
            logger.info("Shutting down LLM Manager...")
            
            # Shutdown services
            if self.llm_service:
                await self.llm_service.shutdown()
            
            # Reset state
            self.is_initialized = False
            self.llm_service = None
            self.prompt_manager = None
            self.conversation_manager = None
            
            logger.success("LLM Manager shutdown complete")
            
        except Exception as e:
            logger.error(f"LLM Manager shutdown failed: {e}")


# Global LLM manager instance
_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get global LLM manager instance."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
