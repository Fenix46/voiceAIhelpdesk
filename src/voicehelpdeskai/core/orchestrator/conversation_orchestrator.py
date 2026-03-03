"""Advanced conversation orchestrator for managing the complete voice help desk pipeline."""

import asyncio
import time
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, AsyncGenerator, Tuple
from enum import Enum
import threading
from contextlib import asynccontextmanager

import numpy as np
from loguru import logger

from voicehelpdeskai.services.stt import STTManager, ProcessedTranscription
from voicehelpdeskai.services.nlu import NLUManager, NLUResponse
from voicehelpdeskai.services.llm import LLMService, ConversationManager, GenerationParams
from voicehelpdeskai.services.tts import TTSManager, SynthesisRequest, SynthesisResponse
from voicehelpdeskai.config.manager import get_config_manager

from .response_generator import ResponseGenerator, GenerationStrategy
from .ticket_builder import TicketBuilder, TicketInfo
from .quality_controller import QualityController, QualityCheck


class PipelineStage(Enum):
    """Pipeline processing stages."""
    AUDIO_INPUT = "audio_input"
    SPEECH_TO_TEXT = "speech_to_text"
    NLU_PROCESSING = "nlu_processing"
    RESPONSE_GENERATION = "response_generation"
    QUALITY_CHECK = "quality_check"
    TICKET_BUILDING = "ticket_building"
    TEXT_TO_SPEECH = "text_to_speech"
    AUDIO_OUTPUT = "audio_output"
    COMPLETED = "completed"
    FAILED = "failed"


class ConversationState(Enum):
    """Overall conversation states."""
    INITIALIZING = "initializing"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    WAITING_USER = "waiting_user"
    BUILDING_TICKET = "building_ticket"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    ERROR = "error"
    TIMEOUT = "timeout"


class FailoverStrategy(Enum):
    """Failover strategies for error handling."""
    RETRY = "retry"
    FALLBACK_SERVICE = "fallback_service"
    DEGRADED_MODE = "degraded_mode"
    HUMAN_ESCALATION = "human_escalation"
    GRACEFUL_FAIL = "graceful_fail"


@dataclass
class PipelineMetrics:
    """Pipeline performance metrics."""
    total_processing_time: float = 0.0
    stage_times: Dict[PipelineStage, float] = field(default_factory=dict)
    stage_attempts: Dict[PipelineStage, int] = field(default_factory=dict)
    stage_failures: Dict[PipelineStage, int] = field(default_factory=dict)
    quality_scores: List[float] = field(default_factory=list)
    cache_hits: int = 0
    fallback_used: bool = False
    parallel_optimizations: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OrchestrationRequest:
    """Request for conversation orchestration."""
    # Audio input
    audio_data: Optional[np.ndarray] = None
    audio_stream: Optional[AsyncGenerator[np.ndarray, None]] = None
    sample_rate: int = 16000
    
    # Text input (alternative to audio)
    text_input: Optional[str] = None
    
    # Context
    conversation_id: Optional[str] = None
    user_id: str = ""
    session_id: str = ""
    
    # Processing options
    enable_streaming: bool = False
    enable_parallel_processing: bool = True
    enable_quality_checks: bool = True
    enable_ticket_building: bool = True
    timeout_seconds: float = 30.0
    
    # Response preferences
    response_language: str = "it"
    voice_id: Optional[str] = None
    response_format: str = "audio"  # "audio", "text", "both"
    
    # Metadata
    priority: str = "normal"  # "low", "normal", "high", "critical"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResponse:
    """Response from conversation orchestration."""
    # Processing results
    transcription: Optional[ProcessedTranscription] = None
    nlu_result: Optional[NLUResponse] = None
    response_text: str = ""
    audio_response: Optional[bytes] = None
    audio_stream: Optional[AsyncGenerator[bytes, None]] = None
    
    # Ticket information
    ticket_info: Optional[TicketInfo] = None
    ticket_status: str = "pending"
    
    # Pipeline status
    conversation_id: str = ""
    conversation_state: ConversationState = ConversationState.PROCESSING
    pipeline_stage: PipelineStage = PipelineStage.AUDIO_INPUT
    success: bool = False
    
    # Quality and confidence
    overall_confidence: float = 0.0
    quality_checks: List[QualityCheck] = field(default_factory=list)
    
    # Performance metrics
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)
    
    # Error handling
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fallback_applied: bool = False
    
    # Metadata
    processing_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationOrchestrator:
    """Advanced orchestrator for managing complete conversation pipeline."""
    
    def __init__(self,
                 stt_manager: Optional[STTManager] = None,
                 nlu_manager: Optional[NLUManager] = None,
                 llm_service: Optional[LLMService] = None,
                 conversation_manager: Optional[ConversationManager] = None,
                 tts_manager: Optional[TTSManager] = None,
                 response_generator: Optional[ResponseGenerator] = None,
                 ticket_builder: Optional[TicketBuilder] = None,
                 quality_controller: Optional[QualityController] = None,
                 max_concurrent_conversations: int = 50,
                 default_timeout: float = 30.0,
                 enable_metrics: bool = True,
                 enable_caching: bool = True):
        """Initialize conversation orchestrator.
        
        Args:
            stt_manager: Speech-to-text manager
            nlu_manager: Natural language understanding manager
            llm_service: Large language model service
            conversation_manager: Conversation state manager
            tts_manager: Text-to-speech manager
            response_generator: Response generation service
            ticket_builder: Ticket construction service
            quality_controller: Quality assurance service
            max_concurrent_conversations: Maximum concurrent conversations
            default_timeout: Default timeout for operations
            enable_metrics: Enable performance metrics
            enable_caching: Enable response caching
        """
        self.config = get_config_manager().get_config()
        
        # Core services (will be initialized lazily)
        self.stt_manager = stt_manager
        self.nlu_manager = nlu_manager
        self.llm_service = llm_service
        self.conversation_manager = conversation_manager
        self.tts_manager = tts_manager
        self.response_generator = response_generator
        self.ticket_builder = ticket_builder
        self.quality_controller = quality_controller
        
        # Configuration
        self.max_concurrent_conversations = max_concurrent_conversations
        self.default_timeout = default_timeout
        self.enable_metrics = enable_metrics
        self.enable_caching = enable_caching
        
        # State management
        self.active_conversations: Dict[str, OrchestrationResponse] = {}
        self.conversation_locks: Dict[str, asyncio.Lock] = {}
        self.initialization_lock = threading.Lock()
        self.is_initialized = False
        
        # Performance tracking
        self.global_metrics = {
            'total_conversations': 0,
            'successful_conversations': 0,
            'failed_conversations': 0,
            'average_processing_time': 0.0,
            'total_processing_time': 0.0,
            'pipeline_stage_stats': {stage: {'count': 0, 'time': 0.0, 'failures': 0} 
                                   for stage in PipelineStage},
            'conversation_state_counts': {state: 0 for state in ConversationState},
            'parallel_optimizations': 0,
            'cache_hits': 0,
            'fallbacks_used': 0,
            'quality_score_history': [],
            'last_error': None,
            'errors': 0
        }
        
        # Fallover strategies mapping
        self.fallback_strategies = {
            PipelineStage.SPEECH_TO_TEXT: FailoverStrategy.RETRY,
            PipelineStage.NLU_PROCESSING: FailoverStrategy.DEGRADED_MODE,
            PipelineStage.RESPONSE_GENERATION: FailoverStrategy.FALLBACK_SERVICE,
            PipelineStage.QUALITY_CHECK: FailoverStrategy.DEGRADED_MODE,
            PipelineStage.TICKET_BUILDING: FailoverStrategy.DEGRADED_MODE,
            PipelineStage.TEXT_TO_SPEECH: FailoverStrategy.RETRY,
        }
        
        logger.info("ConversationOrchestrator initialized")
    
    async def initialize(self) -> None:
        """Initialize all services and dependencies."""
        if self.is_initialized:
            logger.warning("ConversationOrchestrator already initialized")
            return
        
        with self.initialization_lock:
            if self.is_initialized:
                return
            
            try:
                logger.info("Initializing ConversationOrchestrator services...")
                
                # Initialize core services
                if not self.stt_manager:
                    from voicehelpdeskai.services.stt import get_stt_manager
                    self.stt_manager = get_stt_manager()
                await self.stt_manager.initialize()
                
                if not self.nlu_manager:
                    from voicehelpdeskai.services.nlu import get_nlu_manager
                    self.nlu_manager = get_nlu_manager()
                await self.nlu_manager.initialize()
                
                if not self.llm_service:
                    from voicehelpdeskai.services.llm import LLMService
                    self.llm_service = LLMService()
                
                if not self.conversation_manager:
                    from voicehelpdeskai.services.llm import ConversationManager, PromptManager
                    prompt_manager = PromptManager()
                    self.conversation_manager = ConversationManager(
                        llm_service=self.llm_service,
                        prompt_manager=prompt_manager
                    )
                
                if not self.tts_manager:
                    from voicehelpdeskai.services.tts import get_tts_manager
                    self.tts_manager = get_tts_manager()
                await self.tts_manager.initialize()
                
                # Initialize orchestrator services
                if not self.response_generator:
                    self.response_generator = ResponseGenerator(
                        llm_service=self.llm_service,
                        conversation_manager=self.conversation_manager
                    )
                await self.response_generator.initialize()
                
                if not self.ticket_builder:
                    self.ticket_builder = TicketBuilder(
                        nlu_manager=self.nlu_manager
                    )
                await self.ticket_builder.initialize()
                
                if not self.quality_controller:
                    self.quality_controller = QualityController(
                        llm_service=self.llm_service
                    )
                await self.quality_controller.initialize()
                
                self.is_initialized = True
                logger.success("ConversationOrchestrator initialization complete")
                
            except Exception as e:
                logger.error(f"ConversationOrchestrator initialization failed: {e}")
                self.global_metrics['errors'] += 1
                self.global_metrics['last_error'] = str(e)
                raise
    
    async def process_conversation(self, request: OrchestrationRequest) -> OrchestrationResponse:
        """Process complete conversation through the full pipeline.
        
        Args:
            request: Orchestration request with audio/text input
            
        Returns:
            Complete orchestration response
        """
        if not self.is_initialized:
            await self.initialize()
        
        start_time = time.time()
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Initialize response
        response = OrchestrationResponse(
            conversation_id=conversation_id,
            conversation_state=ConversationState.INITIALIZING,
            pipeline_stage=PipelineStage.AUDIO_INPUT,
            metrics=PipelineMetrics()
        )
        
        # Track conversation
        self.active_conversations[conversation_id] = response
        self.global_metrics['total_conversations'] += 1
        
        try:
            # Get or create conversation lock
            if conversation_id not in self.conversation_locks:
                self.conversation_locks[conversation_id] = asyncio.Lock()
            
            async with self.conversation_locks[conversation_id]:
                # Set timeout for the entire pipeline
                async with asyncio.timeout(request.timeout_seconds):
                    if request.enable_parallel_processing:
                        response = await self._process_pipeline_parallel(request, response)
                    else:
                        response = await self._process_pipeline_sequential(request, response)
            
            # Calculate final metrics
            response.processing_time = time.time() - start_time
            response.metrics.total_processing_time = response.processing_time
            response.success = response.pipeline_stage == PipelineStage.COMPLETED
            
            # Update global metrics
            self._update_global_metrics(response)
            
            if response.success:
                self.global_metrics['successful_conversations'] += 1
                logger.info(f"Conversation {conversation_id} completed successfully in {response.processing_time:.3f}s")
            else:
                self.global_metrics['failed_conversations'] += 1
                logger.warning(f"Conversation {conversation_id} failed at stage {response.pipeline_stage.value}")
            
            return response
            
        except asyncio.TimeoutError:
            response.conversation_state = ConversationState.TIMEOUT
            response.errors.append(f"Pipeline timeout after {request.timeout_seconds}s")
            response.processing_time = time.time() - start_time
            self.global_metrics['failed_conversations'] += 1
            logger.error(f"Conversation {conversation_id} timed out after {request.timeout_seconds}s")
            return response
            
        except Exception as e:
            response.conversation_state = ConversationState.ERROR
            response.pipeline_stage = PipelineStage.FAILED
            response.errors.append(str(e))
            response.processing_time = time.time() - start_time
            self.global_metrics['failed_conversations'] += 1
            self.global_metrics['errors'] += 1
            self.global_metrics['last_error'] = str(e)
            logger.error(f"Conversation {conversation_id} failed: {e}")
            return response
            
        finally:
            # Cleanup
            if conversation_id in self.active_conversations:
                del self.active_conversations[conversation_id]
    
    async def _process_pipeline_parallel(self, request: OrchestrationRequest, 
                                       response: OrchestrationResponse) -> OrchestrationResponse:
        """Process pipeline with parallel optimizations where possible."""
        try:
            # Stage 1: Audio/Text Input Processing
            response = await self._process_input_stage(request, response)
            if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                return response
            
            # Stage 2 & 3: STT and NLU Processing (can be optimized)
            if request.audio_data is not None or request.audio_stream is not None:
                # Parallel: STT processing
                stt_task = asyncio.create_task(self._process_stt_stage(request, response))
                
                # Wait for STT to complete
                response = await stt_task
                if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                    return response
                
                # Stage 3: NLU Processing
                response = await self._process_nlu_stage(request, response)
                if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                    return response
            else:
                # Direct text input - skip STT
                response.pipeline_stage = PipelineStage.NLU_PROCESSING
                response = await self._process_nlu_stage(request, response)
                if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                    return response
            
            # Stage 4, 5, 6: Parallel processing where possible
            tasks = []
            
            # Response generation (always needed)
            response_task = asyncio.create_task(
                self._process_response_generation_stage(request, response)
            )
            tasks.append(('response', response_task))
            
            # Quality check (if enabled)
            if request.enable_quality_checks:
                quality_task = asyncio.create_task(
                    self._prepare_quality_check(request, response)
                )
                tasks.append(('quality', quality_task))
            
            # Ticket building (if enabled)
            if request.enable_ticket_building:
                ticket_task = asyncio.create_task(
                    self._process_ticket_building_stage(request, response)
                )
                tasks.append(('ticket', ticket_task))
            
            # Wait for response generation first (it's required)
            response_result = await response_task
            if not response_result.success and response_result.pipeline_stage == PipelineStage.FAILED:
                # Cancel other tasks
                for name, task in tasks[1:]:
                    task.cancel()
                return response_result
            
            response = response_result
            
            # Process quality check if enabled
            if request.enable_quality_checks:
                response = await self._process_quality_check_stage(request, response)
                if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                    return response
            
            # Wait for ticket building to complete
            if request.enable_ticket_building:
                for name, task in tasks:
                    if name == 'ticket':
                        ticket_result = await task
                        response.ticket_info = ticket_result.ticket_info
                        response.ticket_status = ticket_result.ticket_status
                        break
            
            # Stage 7: TTS Processing
            if request.response_format in ["audio", "both"]:
                response = await self._process_tts_stage(request, response)
                if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                    return response
            
            # Final stage
            response.pipeline_stage = PipelineStage.COMPLETED
            response.conversation_state = ConversationState.RESOLVED
            response.success = True
            self.global_metrics['parallel_optimizations'] += 1
            
            return response
            
        except Exception as e:
            return await self._handle_pipeline_error(e, response)
    
    async def _process_pipeline_sequential(self, request: OrchestrationRequest,
                                         response: OrchestrationResponse) -> OrchestrationResponse:
        """Process pipeline sequentially stage by stage."""
        try:
            # Stage 1: Input Processing
            response = await self._process_input_stage(request, response)
            if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                return response
            
            # Stage 2: STT (if audio input)
            if request.audio_data is not None or request.audio_stream is not None:
                response = await self._process_stt_stage(request, response)
                if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                    return response
            else:
                response.pipeline_stage = PipelineStage.NLU_PROCESSING
            
            # Stage 3: NLU Processing
            response = await self._process_nlu_stage(request, response)
            if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                return response
            
            # Stage 4: Response Generation
            response = await self._process_response_generation_stage(request, response)
            if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                return response
            
            # Stage 5: Quality Check
            if request.enable_quality_checks:
                response = await self._process_quality_check_stage(request, response)
                if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                    return response
            
            # Stage 6: Ticket Building
            if request.enable_ticket_building:
                response = await self._process_ticket_building_stage(request, response)
                # Note: ticket building failure doesn't fail the entire pipeline
            
            # Stage 7: TTS
            if request.response_format in ["audio", "both"]:
                response = await self._process_tts_stage(request, response)
                if not response.success and response.pipeline_stage == PipelineStage.FAILED:
                    return response
            
            # Completion
            response.pipeline_stage = PipelineStage.COMPLETED
            response.conversation_state = ConversationState.RESOLVED
            response.success = True
            
            return response
            
        except Exception as e:
            return await self._handle_pipeline_error(e, response)
    
    async def _process_input_stage(self, request: OrchestrationRequest,
                                 response: OrchestrationResponse) -> OrchestrationResponse:
        """Process initial input validation and setup."""
        stage_start = time.time()
        response.conversation_state = ConversationState.LISTENING
        
        try:
            # Validate input
            if not request.audio_data and not request.audio_stream and not request.text_input:
                raise ValueError("No input provided (audio_data, audio_stream, or text_input required)")
            
            # Setup conversation context
            if not request.conversation_id:
                request.conversation_id = response.conversation_id
            
            response.pipeline_stage = PipelineStage.SPEECH_TO_TEXT if (
                request.audio_data is not None or request.audio_stream is not None
            ) else PipelineStage.NLU_PROCESSING
            
            stage_time = time.time() - stage_start
            response.metrics.stage_times[PipelineStage.AUDIO_INPUT] = stage_time
            response.metrics.stage_attempts[PipelineStage.AUDIO_INPUT] = 1
            
            return response
            
        except Exception as e:
            response.pipeline_stage = PipelineStage.FAILED
            response.conversation_state = ConversationState.ERROR
            response.errors.append(f"Input stage failed: {str(e)}")
            response.metrics.stage_failures[PipelineStage.AUDIO_INPUT] = 1
            return response
    
    async def _process_stt_stage(self, request: OrchestrationRequest,
                               response: OrchestrationResponse) -> OrchestrationResponse:
        """Process speech-to-text conversion."""
        stage_start = time.time()
        response.pipeline_stage = PipelineStage.SPEECH_TO_TEXT
        response.conversation_state = ConversationState.PROCESSING
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response.metrics.stage_attempts[PipelineStage.SPEECH_TO_TEXT] = attempt + 1
                
                if request.audio_stream:
                    # Streaming transcription
                    transcription_text = ""
                    async for chunk_transcription in self.stt_manager.transcribe_streaming(
                        request.audio_stream,
                        language=request.response_language,
                        sample_rate=request.sample_rate
                    ):
                        if chunk_transcription.is_final:
                            transcription_text += chunk_transcription.text + " "
                    
                    # Create processed transcription from streaming result
                    response.transcription = ProcessedTranscription(
                        text=transcription_text.strip(),
                        original_text=transcription_text.strip(),
                        confidence=0.8,  # Default for streaming
                        language=request.response_language,
                        processing_applied=[],
                        entities=[],
                        normalized_numbers=[],
                        corrected_words=[],
                        profanity_filtered=False,
                        processing_time=time.time() - stage_start
                    )
                else:
                    # Standard transcription
                    response.transcription = await self.stt_manager.transcribe(
                        request.audio_data,
                        language=request.response_language,
                        sample_rate=request.sample_rate
                    )
                
                # Validate transcription result
                if not response.transcription.text.strip():
                    if attempt < max_retries:
                        logger.warning(f"Empty transcription on attempt {attempt + 1}, retrying...")
                        continue
                    else:
                        raise ValueError("No speech detected in audio")
                
                stage_time = time.time() - stage_start
                response.metrics.stage_times[PipelineStage.SPEECH_TO_TEXT] = stage_time
                response.pipeline_stage = PipelineStage.NLU_PROCESSING
                
                logger.debug(f"STT completed: '{response.transcription.text[:100]}...'")
                return response
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"STT attempt {attempt + 1} failed: {e}, retrying...")
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    # Apply fallback strategy
                    return await self._apply_fallback_strategy(
                        PipelineStage.SPEECH_TO_TEXT, e, request, response
                    )
        
        return response
    
    async def _process_nlu_stage(self, request: OrchestrationRequest,
                               response: OrchestrationResponse) -> OrchestrationResponse:
        """Process natural language understanding."""
        stage_start = time.time()
        response.pipeline_stage = PipelineStage.NLU_PROCESSING
        
        try:
            # Get text to process
            text_to_process = ""
            if response.transcription:
                text_to_process = response.transcription.text
            elif request.text_input:
                text_to_process = request.text_input
            else:
                raise ValueError("No text available for NLU processing")
            
            # Process with NLU
            response.nlu_result = await self.nlu_manager.process_text(
                text=text_to_process,
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                session_id=request.session_id
            )
            
            stage_time = time.time() - stage_start
            response.metrics.stage_times[PipelineStage.NLU_PROCESSING] = stage_time
            response.metrics.stage_attempts[PipelineStage.NLU_PROCESSING] = 1
            response.pipeline_stage = PipelineStage.RESPONSE_GENERATION
            
            logger.debug(f"NLU completed: intent={response.nlu_result.intent.intent.value}, "
                        f"confidence={response.nlu_result.confidence:.3f}")
            return response
            
        except Exception as e:
            return await self._apply_fallback_strategy(
                PipelineStage.NLU_PROCESSING, e, request, response
            )
    
    async def _process_response_generation_stage(self, request: OrchestrationRequest,
                                               response: OrchestrationResponse) -> OrchestrationResponse:
        """Process response generation."""
        stage_start = time.time()
        response.pipeline_stage = PipelineStage.RESPONSE_GENERATION
        
        try:
            # Determine generation strategy
            strategy = GenerationStrategy.HYBRID
            if response.nlu_result and response.nlu_result.intent:
                if response.nlu_result.confidence > 0.8:
                    strategy = GenerationStrategy.TEMPLATE_BASED
                elif response.nlu_result.requires_human_review:
                    strategy = GenerationStrategy.LLM_ENHANCED
            
            # Generate response
            response.response_text = await self.response_generator.generate_response(
                text_input=response.transcription.text if response.transcription else request.text_input,
                nlu_result=response.nlu_result,
                conversation_id=request.conversation_id,
                strategy=strategy,
                user_context={
                    'user_id': request.user_id,
                    'session_id': request.session_id,
                    'language': request.response_language,
                    'priority': request.priority
                }
            )
            
            stage_time = time.time() - stage_start
            response.metrics.stage_times[PipelineStage.RESPONSE_GENERATION] = stage_time
            response.metrics.stage_attempts[PipelineStage.RESPONSE_GENERATION] = 1
            response.pipeline_stage = PipelineStage.QUALITY_CHECK
            
            logger.debug(f"Response generated: '{response.response_text[:100]}...'")
            return response
            
        except Exception as e:
            return await self._apply_fallback_strategy(
                PipelineStage.RESPONSE_GENERATION, e, request, response
            )
    
    async def _prepare_quality_check(self, request: OrchestrationRequest,
                                   response: OrchestrationResponse) -> OrchestrationResponse:
        """Prepare for quality check (can run in parallel)."""
        # This is a placeholder for parallel preparation
        return response
    
    async def _process_quality_check_stage(self, request: OrchestrationRequest,
                                         response: OrchestrationResponse) -> OrchestrationResponse:
        """Process quality assurance checks."""
        stage_start = time.time()
        response.pipeline_stage = PipelineStage.QUALITY_CHECK
        
        try:
            # Perform quality checks
            quality_result = await self.quality_controller.check_response_quality(
                response_text=response.response_text,
                original_input=response.transcription.text if response.transcription else request.text_input,
                nlu_result=response.nlu_result,
                conversation_context={
                    'conversation_id': request.conversation_id,
                    'user_id': request.user_id,
                    'priority': request.priority
                }
            )
            
            response.quality_checks = quality_result.checks
            response.overall_confidence = quality_result.overall_score
            
            # Check if response passes quality thresholds
            if quality_result.overall_score < 0.6:
                response.warnings.append(f"Low quality score: {quality_result.overall_score:.3f}")
                
                # Potentially regenerate response or flag for human review
                if quality_result.overall_score < 0.4:
                    response.nlu_result.requires_human_review = True
                    response.warnings.append("Response flagged for human review")
            
            stage_time = time.time() - stage_start
            response.metrics.stage_times[PipelineStage.QUALITY_CHECK] = stage_time
            response.metrics.stage_attempts[PipelineStage.QUALITY_CHECK] = 1
            response.pipeline_stage = PipelineStage.TICKET_BUILDING
            
            return response
            
        except Exception as e:
            return await self._apply_fallback_strategy(
                PipelineStage.QUALITY_CHECK, e, request, response
            )
    
    async def _process_ticket_building_stage(self, request: OrchestrationRequest,
                                           response: OrchestrationResponse) -> OrchestrationResponse:
        """Process ticket building and information extraction."""
        stage_start = time.time()
        response.pipeline_stage = PipelineStage.TICKET_BUILDING
        
        try:
            # Build ticket information
            ticket_result = await self.ticket_builder.build_ticket(
                user_input=response.transcription.text if response.transcription else request.text_input,
                nlu_result=response.nlu_result,
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                metadata=request.metadata
            )
            
            response.ticket_info = ticket_result.ticket_info
            response.ticket_status = "created" if ticket_result.validation_result.is_valid else "incomplete"
            
            if not ticket_result.validation_result.is_valid:
                response.warnings.extend([
                    f"Ticket validation issue: {issue}" 
                    for issue in ticket_result.validation_result.missing_fields
                ])
            
            stage_time = time.time() - stage_start
            response.metrics.stage_times[PipelineStage.TICKET_BUILDING] = stage_time
            response.metrics.stage_attempts[PipelineStage.TICKET_BUILDING] = 1
            response.pipeline_stage = PipelineStage.TEXT_TO_SPEECH
            
            logger.debug(f"Ticket built: {response.ticket_info.title[:50] if response.ticket_info else 'None'}...")
            return response
            
        except Exception as e:
            # Ticket building failure doesn't fail the entire pipeline
            logger.warning(f"Ticket building failed: {e}")
            response.warnings.append(f"Ticket building failed: {str(e)}")
            response.ticket_status = "failed"
            
            stage_time = time.time() - stage_start
            response.metrics.stage_times[PipelineStage.TICKET_BUILDING] = stage_time
            response.metrics.stage_failures[PipelineStage.TICKET_BUILDING] = 1
            response.pipeline_stage = PipelineStage.TEXT_TO_SPEECH
            
            return response
    
    async def _process_tts_stage(self, request: OrchestrationRequest,
                               response: OrchestrationResponse) -> OrchestrationResponse:
        """Process text-to-speech conversion."""
        stage_start = time.time()
        response.pipeline_stage = PipelineStage.TEXT_TO_SPEECH
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response.metrics.stage_attempts[PipelineStage.TEXT_TO_SPEECH] = attempt + 1
                
                # Create TTS request
                tts_request = SynthesisRequest(
                    text=response.response_text,
                    user_id=request.user_id,
                    voice_id=request.voice_id,
                    streaming=request.enable_streaming,
                    enable_personalization=True,
                    intent=response.nlu_result.intent if response.nlu_result else None,
                    conversation_context={
                        'conversation_id': request.conversation_id,
                        'priority': request.priority
                    }
                )
                
                # Synthesize speech
                tts_response = await self.tts_manager.synthesize_speech(tts_request)
                
                if tts_response.audio_data:
                    response.audio_response = tts_response.audio_data
                elif tts_response.audio_stream:
                    response.audio_stream = tts_response.audio_stream
                else:
                    if attempt < max_retries:
                        logger.warning(f"TTS attempt {attempt + 1} produced no audio, retrying...")
                        continue
                    else:
                        raise ValueError("TTS failed to produce audio")
                
                stage_time = time.time() - stage_start
                response.metrics.stage_times[PipelineStage.TEXT_TO_SPEECH] = stage_time
                response.pipeline_stage = PipelineStage.AUDIO_OUTPUT
                
                logger.debug(f"TTS completed: duration={tts_response.duration:.2f}s")
                return response
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"TTS attempt {attempt + 1} failed: {e}, retrying...")
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    return await self._apply_fallback_strategy(
                        PipelineStage.TEXT_TO_SPEECH, e, request, response
                    )
        
        return response
    
    async def _apply_fallback_strategy(self, stage: PipelineStage, error: Exception,
                                     request: OrchestrationRequest,
                                     response: OrchestrationResponse) -> OrchestrationResponse:
        """Apply fallback strategy for failed pipeline stage."""
        strategy = self.fallback_strategies.get(stage, FailoverStrategy.GRACEFUL_FAIL)
        response.fallback_applied = True
        self.global_metrics['fallbacks_used'] += 1
        
        logger.warning(f"Applying fallback strategy {strategy.value} for stage {stage.value}: {error}")
        
        if strategy == FailoverStrategy.RETRY:
            # Already handled in individual stage methods
            response.pipeline_stage = PipelineStage.FAILED
            response.conversation_state = ConversationState.ERROR
            response.errors.append(f"{stage.value} failed: {str(error)}")
            
        elif strategy == FailoverStrategy.DEGRADED_MODE:
            # Continue pipeline with reduced functionality
            if stage == PipelineStage.NLU_PROCESSING:
                # Create minimal NLU result
                from voicehelpdeskai.services.nlu import NLUResponse, IntentPrediction, IntentType, ITCategory, UrgencyLevel
                response.nlu_result = NLUResponse(
                    intent=IntentPrediction(
                        intent=IntentType.PROBLEM_REPORT,
                        confidence=0.1,
                        category=ITCategory.GENERAL,
                        urgency=UrgencyLevel.MEDIO
                    ),
                    entities=[],
                    confidence=0.1,
                    requires_human_review=True
                )
                response.pipeline_stage = PipelineStage.RESPONSE_GENERATION
                response.warnings.append("NLU running in degraded mode")
                
            elif stage == PipelineStage.QUALITY_CHECK:
                # Skip quality checks
                response.pipeline_stage = PipelineStage.TICKET_BUILDING
                response.warnings.append("Quality checks skipped")
                
            elif stage == PipelineStage.TICKET_BUILDING:
                # Continue without ticket
                response.pipeline_stage = PipelineStage.TEXT_TO_SPEECH
                response.warnings.append("Ticket building skipped")
                
        elif strategy == FailoverStrategy.FALLBACK_SERVICE:
            if stage == PipelineStage.RESPONSE_GENERATION:
                # Use template-based fallback response
                response.response_text = "Mi dispiace, sto avendo difficoltà tecniche. Un operatore umano ti contatterà presto per aiutarti."
                response.pipeline_stage = PipelineStage.QUALITY_CHECK
                response.warnings.append("Using fallback response template")
                
        elif strategy == FailoverStrategy.HUMAN_ESCALATION:
            response.conversation_state = ConversationState.ESCALATED
            response.response_text = "La tua richiesta è stata inoltrata a un operatore umano che ti contatterà al più presto."
            response.pipeline_stage = PipelineStage.TEXT_TO_SPEECH
            if response.nlu_result:
                response.nlu_result.requires_human_review = True
            
        else:  # GRACEFUL_FAIL
            response.pipeline_stage = PipelineStage.FAILED
            response.conversation_state = ConversationState.ERROR
            response.errors.append(f"{stage.value} failed: {str(error)}")
        
        # Update failure metrics
        response.metrics.stage_failures[stage] = response.metrics.stage_failures.get(stage, 0) + 1
        
        return response
    
    async def _handle_pipeline_error(self, error: Exception,
                                   response: OrchestrationResponse) -> OrchestrationResponse:
        """Handle unexpected pipeline errors."""
        response.pipeline_stage = PipelineStage.FAILED
        response.conversation_state = ConversationState.ERROR
        response.errors.append(f"Pipeline error: {str(error)}")
        response.fallback_applied = True
        
        logger.error(f"Pipeline error in conversation {response.conversation_id}: {error}")
        
        return response
    
    def _update_global_metrics(self, response: OrchestrationResponse) -> None:
        """Update global performance metrics."""
        if not self.enable_metrics:
            return
        
        self.global_metrics['total_processing_time'] += response.processing_time
        
        if self.global_metrics['total_conversations'] > 0:
            self.global_metrics['average_processing_time'] = (
                self.global_metrics['total_processing_time'] / 
                self.global_metrics['total_conversations']
            )
        
        # Update stage statistics
        for stage, stage_time in response.metrics.stage_times.items():
            self.global_metrics['pipeline_stage_stats'][stage]['count'] += 1
            self.global_metrics['pipeline_stage_stats'][stage]['time'] += stage_time
        
        for stage, failures in response.metrics.stage_failures.items():
            self.global_metrics['pipeline_stage_stats'][stage]['failures'] += failures
        
        # Update conversation state counts
        self.global_metrics['conversation_state_counts'][response.conversation_state] += 1
        
        # Track quality scores
        if response.overall_confidence > 0:
            self.global_metrics['quality_score_history'].append(response.overall_confidence)
            # Keep last 1000 scores
            if len(self.global_metrics['quality_score_history']) > 1000:
                self.global_metrics['quality_score_history'].pop(0)
        
        # Track optimizations
        if response.metrics.parallel_optimizations > 0:
            self.global_metrics['parallel_optimizations'] += response.metrics.parallel_optimizations
        
        if response.metrics.cache_hits > 0:
            self.global_metrics['cache_hits'] += response.metrics.cache_hits
    
    async def get_conversation_status(self, conversation_id: str) -> Optional[OrchestrationResponse]:
        """Get current status of active conversation."""
        return self.active_conversations.get(conversation_id)
    
    async def stop_conversation(self, conversation_id: str) -> bool:
        """Stop and cleanup active conversation."""
        if conversation_id in self.active_conversations:
            del self.active_conversations[conversation_id]
        
        if conversation_id in self.conversation_locks:
            del self.conversation_locks[conversation_id]
        
        logger.info(f"Stopped conversation {conversation_id}")
        return True
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        metrics = self.global_metrics.copy()
        
        # Add current state
        metrics['active_conversations'] = len(self.active_conversations)
        metrics['total_locks'] = len(self.conversation_locks)
        
        # Calculate derived metrics
        if metrics['total_conversations'] > 0:
            metrics['success_rate'] = (
                metrics['successful_conversations'] / metrics['total_conversations'] * 100
            )
            metrics['failure_rate'] = (
                metrics['failed_conversations'] / metrics['total_conversations'] * 100
            )
        
        # Calculate average quality score
        if metrics['quality_score_history']:
            metrics['average_quality_score'] = (
                sum(metrics['quality_score_history']) / len(metrics['quality_score_history'])
            )
        
        # Add timestamp
        metrics['timestamp'] = datetime.now().isoformat()
        
        return metrics
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health = {
            'overall_status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {},
            'metrics': {},
            'errors': []
        }
        
        try:
            # Check initialization
            if not self.is_initialized:
                health['overall_status'] = 'unhealthy'
                health['errors'].append('Orchestrator not initialized')
                return health
            
            # Check individual services
            services_health = {}
            
            if self.stt_manager:
                stt_health = await self.stt_manager.health_check()
                services_health['stt'] = stt_health['overall_status']
                if stt_health['overall_status'] != 'healthy':
                    health['errors'].extend(stt_health.get('errors', []))
            
            if self.nlu_manager:
                nlu_health = await self.nlu_manager.health_check()
                services_health['nlu'] = nlu_health['overall_status']
                if nlu_health['overall_status'] != 'healthy':
                    health['errors'].extend(nlu_health.get('errors', []))
            
            if self.tts_manager:
                tts_health = await self.tts_manager.health_check()
                services_health['tts'] = tts_health['overall_status']
                if tts_health['overall_status'] != 'healthy':
                    health['errors'].extend(tts_health.get('errors', []))
            
            health['services'] = services_health
            
            # Check metrics for anomalies
            metrics = self.get_metrics()
            health['metrics'] = {
                'active_conversations': metrics['active_conversations'],
                'success_rate': metrics.get('success_rate', 0),
                'average_processing_time': metrics['average_processing_time'],
                'total_errors': metrics['errors']
            }
            
            # Determine overall status
            degraded_services = [k for k, v in services_health.items() if v == 'degraded']
            unhealthy_services = [k for k, v in services_health.items() if v == 'unhealthy']
            
            if unhealthy_services:
                health['overall_status'] = 'unhealthy'
            elif degraded_services or metrics.get('success_rate', 100) < 80:
                health['overall_status'] = 'degraded'
            
        except Exception as e:
            health['overall_status'] = 'unhealthy'
            health['errors'].append(f'Health check failed: {str(e)}')
        
        return health
    
    async def cleanup_resources(self) -> Dict[str, int]:
        """Cleanup expired conversations and resources."""
        cleanup_stats = {'total_cleaned': 0}
        
        try:
            # Cleanup old conversations (>1 hour old)
            current_time = datetime.now()
            expired_conversations = []
            
            for conv_id, response in self.active_conversations.items():
                if (current_time - response.timestamp).total_seconds() > 3600:
                    expired_conversations.append(conv_id)
            
            for conv_id in expired_conversations:
                await self.stop_conversation(conv_id)
                cleanup_stats['total_cleaned'] += 1
            
            cleanup_stats['expired_conversations'] = len(expired_conversations)
            
            # Cleanup service resources
            if self.stt_manager:
                stt_cleanup = await self.stt_manager.cleanup_cache()
                cleanup_stats['stt_cache_cleaned'] = stt_cleanup.get('cleaned', 0)
                cleanup_stats['total_cleaned'] += cleanup_stats['stt_cache_cleaned']
            
            if self.nlu_manager:
                nlu_cleanup = await self.nlu_manager.cleanup_resources()
                cleanup_stats['nlu_resources_cleaned'] = nlu_cleanup.get('total_cleaned', 0)
                cleanup_stats['total_cleaned'] += cleanup_stats['nlu_resources_cleaned']
            
            if self.tts_manager:
                tts_cleanup = await self.tts_manager.clear_all_caches()
                cleanup_stats['tts_cache_cleaned'] = tts_cleanup.get('total_cleared', 0)
                cleanup_stats['total_cleaned'] += cleanup_stats['tts_cache_cleaned']
            
            if cleanup_stats['total_cleaned'] > 0:
                logger.info(f"Cleaned up {cleanup_stats['total_cleaned']} orchestrator resources")
            
        except Exception as e:
            logger.error(f"Resource cleanup failed: {e}")
            cleanup_stats['error'] = str(e)
        
        return cleanup_stats
    
    async def shutdown(self) -> None:
        """Shutdown orchestrator and all services."""
        try:
            logger.info("Shutting down ConversationOrchestrator...")
            
            # Stop all active conversations
            for conv_id in list(self.active_conversations.keys()):
                await self.stop_conversation(conv_id)
            
            # Shutdown services
            if self.stt_manager:
                await self.stt_manager.shutdown()
            
            if self.tts_manager:
                await self.tts_manager.shutdown()
            
            # Reset state
            self.is_initialized = False
            self.active_conversations.clear()
            self.conversation_locks.clear()
            
            logger.success("ConversationOrchestrator shutdown complete")
            
        except Exception as e:
            logger.error(f"ConversationOrchestrator shutdown failed: {e}")


# Global orchestrator instance
_conversation_orchestrator: Optional[ConversationOrchestrator] = None


def get_conversation_orchestrator() -> ConversationOrchestrator:
    """Get global conversation orchestrator instance."""
    global _conversation_orchestrator
    if _conversation_orchestrator is None:
        _conversation_orchestrator = ConversationOrchestrator()
    return _conversation_orchestrator