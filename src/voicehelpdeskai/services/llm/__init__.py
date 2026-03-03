"""Large Language Model (LLM) services module.

This module provides advanced LLM capabilities with:
- Multiple backend support (Ollama, llama.cpp, vLLM, Transformers)
- Optimized Mistral 7B service for Italian helpdesk
- Advanced prompt management with A/B testing
- Conversation management with state tracking
- Memory management for GPU optimization
- Strategic response caching
"""

from .llm_service import (
    LLMService,
    ModelConfig,
    GenerationParams,
    LLMResponse,
    StreamingChunk,
    LLMBackend,
    QuantizationType,
    BackendFactory,
    MemoryManager,
    TokenCounter
)

from .mistral_service import (
    MistralService,
    TicketOperation,
    KnowledgeBaseEntry
)

from .prompt_manager import (
    PromptManager,
    PromptTemplate,
    PromptVariable,
    FewShotExample,
    PromptType,
    TaskType,
    ABTestConfig,
    ABTestResult
)

from .conversation_manager import (
    ConversationManager,
    ConversationContext,
    ConversationMessage,
    ConversationSummary,
    ConversationState,
    MessageType,
    SentimentPolarity,
    IntentType,
    Entity
)

from .llm_manager import (
    LLMManager,
    get_llm_manager
)

__all__ = [
    # Core LLM services
    'LLMService',
    'MistralService',
    'PromptManager',
    'ConversationManager',
    'LLMManager',
    
    # LLM service components
    'ModelConfig',
    'GenerationParams',
    'LLMResponse',
    'StreamingChunk',
    'BackendFactory',
    'MemoryManager',
    'TokenCounter',
    
    # Enums
    'LLMBackend',
    'QuantizationType',
    'PromptType',
    'TaskType',
    'ConversationState',
    'MessageType',
    'SentimentPolarity',
    'IntentType',
    
    # Data models
    'TicketOperation',
    'KnowledgeBaseEntry',
    'PromptTemplate',
    'PromptVariable',
    'FewShotExample',
    'ABTestConfig',
    'ABTestResult',
    'ConversationContext',
    'ConversationMessage',
    'ConversationSummary',
    'Entity',
    
    # Factory functions
    'create_mistral_service',
    'create_llm_stack',
    'get_llm_manager',
]

# Version info
__version__ = "1.0.0"
__author__ = "VoiceHelpDeskAI Team"


def create_mistral_service(
    model_size: str = "mistral-7b",
    quantization: str = "int8",
    enable_rag: bool = True,
    enable_function_calling: bool = True,
    optimize_for_8gb: bool = True,
    backend: str = "transformers"
) -> MistralService:
    """Factory function to create optimized Mistral service.
    
    Args:
        model_size: Mistral model variant
        quantization: Quantization type (none, int4, int8, fp16)
        enable_rag: Enable RAG integration
        enable_function_calling: Enable function calling
        optimize_for_8gb: Optimize for 8GB GPU memory
        backend: Backend to use
        
    Returns:
        Configured MistralService instance
    """
    # Map quantization string to enum
    quant_mapping = {
        "none": QuantizationType.NONE,
        "int4": QuantizationType.INT4,
        "int8": QuantizationType.INT8,
        "fp16": QuantizationType.FP16,
        "bf16": QuantizationType.BF16
    }
    
    # Map backend string to enum
    backend_mapping = {
        "transformers": LLMBackend.TRANSFORMERS,
        "ollama": LLMBackend.OLLAMA,
        "llama_cpp": LLMBackend.LLAMA_CPP,
        "vllm": LLMBackend.VLLM,
        "openai": LLMBackend.OPENAI
    }
    
    # Create model config
    config = BackendFactory.get_optimal_config_for_model(
        model_name=model_size,
        backend=backend_mapping.get(backend, LLMBackend.TRANSFORMERS),
        optimize_for_8gb=optimize_for_8gb
    )
    
    # Override quantization if specified
    config.quantization = quant_mapping.get(quantization, QuantizationType.INT8)
    
    # Create service
    service = MistralService(
        config=config,
        enable_rag=enable_rag,
        enable_function_calling=enable_function_calling,
        conversation_memory_size=20
    )
    
    return service


def create_llm_stack(
    model_config: ModelConfig,
    enable_prompt_management: bool = True,
    enable_conversation_management: bool = True,
    enable_ab_testing: bool = True,
    max_context_length: int = 8000
) -> tuple[LLMService, PromptManager, ConversationManager]:
    """Factory function to create complete LLM stack.
    
    Args:
        model_config: Model configuration
        enable_prompt_management: Enable prompt management
        enable_conversation_management: Enable conversation management  
        enable_ab_testing: Enable A/B testing for prompts
        max_context_length: Maximum context length
        
    Returns:
        Tuple of (LLMService, PromptManager, ConversationManager)
    """
    # Create LLM service
    if model_config.name.startswith("mistral"):
        llm_service = MistralService(config=model_config)
    else:
        llm_service = BackendFactory.create_service(model_config)
    
    # Create prompt manager
    prompt_manager = None
    if enable_prompt_management:
        prompt_manager = PromptManager(
            enable_ab_testing=enable_ab_testing,
            enable_performance_tracking=True,
            auto_optimization=True
        )
    
    # Create conversation manager
    conversation_manager = None
    if enable_conversation_management and prompt_manager:
        conversation_manager = ConversationManager(
            llm_service=llm_service,
            prompt_manager=prompt_manager,
            max_context_length=max_context_length,
            auto_summarize=True,
            sentiment_tracking=True,
            entity_tracking=True
        )
    
    return llm_service, prompt_manager, conversation_manager


# Convenience imports for common patterns
from .llm_service import LLMResponse as LLMOutput
from .mistral_service import TicketOperation as TicketOp
from .conversation_manager import ConversationMessage as ChatMessage