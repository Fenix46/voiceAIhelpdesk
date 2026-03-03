"""Advanced response generator with template-based and LLM hybrid approaches."""

import asyncio
import time
import json
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
import threading
import hashlib
from pathlib import Path

from loguru import logger

from voicehelpdeskai.services.llm import LLMService, ConversationManager, GenerationParams
from voicehelpdeskai.services.nlu import NLUResponse, IntentType, ITCategory, UrgencyLevel
from voicehelpdeskai.config.manager import get_config_manager


class GenerationStrategy(Enum):
    """Response generation strategies."""
    TEMPLATE_BASED = "template_based"      # Fast template responses
    LLM_ENHANCED = "llm_enhanced"         # LLM with templates
    HYBRID = "hybrid"                     # Smart combination
    FULL_LLM = "full_llm"                # Full LLM generation
    CACHED = "cached"                     # Cached responses


class ResponseType(Enum):
    """Types of response content."""
    GREETING = "greeting"
    ACKNOWLEDGMENT = "acknowledgment"
    INFORMATION_REQUEST = "information_request"
    SOLUTION_STEPS = "solution_steps"
    ESCALATION = "escalation"
    CLOSURE = "closure"
    ERROR_HANDLING = "error_handling"
    CLARIFICATION = "clarification"
    CONFIRMATION = "confirmation"


class PersonalizationLevel(Enum):
    """Levels of response personalization."""
    NONE = "none"
    BASIC = "basic"          # Name, basic preferences
    CONTEXTUAL = "contextual"  # History, context
    ADVANCED = "advanced"    # Full personality adaptation


@dataclass
class ResponseTemplate:
    """Template for generating responses."""
    id: str
    type: ResponseType
    intent_types: List[IntentType]
    categories: List[ITCategory]
    urgency_levels: List[UrgencyLevel]
    
    # Template content
    templates: Dict[str, str] = field(default_factory=dict)  # language -> template
    variables: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    # Personalization
    personalization_slots: List[str] = field(default_factory=list)
    tone_adaptations: Dict[str, str] = field(default_factory=dict)
    
    # Quality metrics
    success_rate: float = 0.0
    user_satisfaction: float = 0.0
    usage_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)
    
    # Metadata
    description: str = ""
    author: str = "system"
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserContext:
    """User context for personalization."""
    user_id: str
    session_id: str
    language: str = "it"
    
    # User preferences
    preferred_tone: str = "professional"  # professional, friendly, casual
    communication_style: str = "direct"   # direct, detailed, concise
    technical_level: str = "intermediate" # beginner, intermediate, advanced
    
    # Interaction history
    interaction_count: int = 0
    last_interaction: Optional[datetime] = None
    satisfaction_history: List[float] = field(default_factory=list)
    
    # Context from conversation
    current_problem_category: Optional[ITCategory] = None
    urgency_level: Optional[UrgencyLevel] = None
    escalation_history: int = 0
    
    # Personalization data
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationRequest:
    """Request for response generation."""
    text_input: str
    nlu_result: Optional[NLUResponse]
    conversation_id: str
    strategy: GenerationStrategy = GenerationStrategy.HYBRID
    user_context: Optional[UserContext] = None
    
    # Generation options
    enable_personalization: bool = True
    enable_caching: bool = True
    enable_multi_turn_planning: bool = True
    max_response_length: int = 500
    
    # Quality requirements
    min_confidence_threshold: float = 0.7
    require_confirmation: bool = False
    
    # Metadata
    priority: str = "normal"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResponse:
    """Response from generation process."""
    text: str
    strategy_used: GenerationStrategy
    template_id: Optional[str] = None
    confidence: float = 0.0
    
    # Personalization applied
    personalization_level: PersonalizationLevel = PersonalizationLevel.NONE
    personalization_applied: List[str] = field(default_factory=list)
    
    # Multi-turn planning
    follow_up_suggestions: List[str] = field(default_factory=list)
    expected_user_responses: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    
    # Generation metadata
    generation_time: float = 0.0
    tokens_used: int = 0
    cache_hit: bool = False
    fallback_used: bool = False
    
    # Quality indicators
    coherence_score: float = 0.0
    relevance_score: float = 0.0
    completeness_score: float = 0.0
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResponseGenerator:
    """Advanced response generator with multiple strategies."""
    
    def __init__(self,
                 llm_service: Optional[LLMService] = None,
                 conversation_manager: Optional[ConversationManager] = None,
                 templates_dir: Optional[str] = None,
                 enable_caching: bool = True,
                 enable_learning: bool = True,
                 cache_ttl: int = 3600):
        """Initialize response generator.
        
        Args:
            llm_service: LLM service for advanced generation
            conversation_manager: Conversation state manager
            templates_dir: Directory containing response templates
            enable_caching: Enable response caching
            enable_learning: Enable template learning/optimization
            cache_ttl: Cache time-to-live in seconds
        """
        self.config = get_config_manager().get_config()
        self.llm_service = llm_service
        self.conversation_manager = conversation_manager
        self.templates_dir = templates_dir or "./config/templates"
        self.enable_caching = enable_caching
        self.enable_learning = enable_learning
        self.cache_ttl = cache_ttl
        
        # Template storage
        self.templates: Dict[str, ResponseTemplate] = {}
        self.template_index: Dict[Tuple[IntentType, ITCategory], List[str]] = {}
        
        # User context storage
        self.user_contexts: Dict[str, UserContext] = {}
        
        # Caching
        self.response_cache: Dict[str, Tuple[GenerationResponse, datetime]] = {}
        self.cache_stats = {'hits': 0, 'misses': 0, 'total_requests': 0}
        
        # Performance tracking
        self.stats = {
            'total_generations': 0,
            'strategy_usage': {strategy: 0 for strategy in GenerationStrategy},
            'template_usage': {},
            'average_generation_time': 0.0,
            'total_generation_time': 0.0,
            'personalization_usage': {level: 0 for level in PersonalizationLevel},
            'user_satisfaction_scores': [],
            'cache_performance': {'hits': 0, 'misses': 0},
            'fallback_usage': 0,
            'errors': 0,
            'last_error': None
        }
        
        # State
        self.is_initialized = False
        self.initialization_lock = threading.Lock()
        
        logger.info("ResponseGenerator initialized")
    
    async def initialize(self) -> None:
        """Initialize response generator and load templates."""
        if self.is_initialized:
            logger.warning("ResponseGenerator already initialized")
            return
        
        with self.initialization_lock:
            if self.is_initialized:
                return
            
            try:
                logger.info("Initializing ResponseGenerator...")
                
                # Load default templates
                await self._load_default_templates()
                
                # Load custom templates if directory exists
                templates_path = Path(self.templates_dir)
                if templates_path.exists():
                    await self._load_templates_from_directory(templates_path)
                
                # Build template index
                self._build_template_index()
                
                self.is_initialized = True
                logger.success(f"ResponseGenerator initialized with {len(self.templates)} templates")
                
            except Exception as e:
                logger.error(f"ResponseGenerator initialization failed: {e}")
                self.stats['errors'] += 1
                self.stats['last_error'] = str(e)
                raise
    
    async def generate_response(self,
                              text_input: str,
                              nlu_result: Optional[NLUResponse],
                              conversation_id: str,
                              strategy: GenerationStrategy = GenerationStrategy.HYBRID,
                              user_context: Optional[Dict[str, Any]] = None) -> str:
        """Generate response using specified strategy.
        
        Args:
            text_input: User input text
            nlu_result: NLU analysis result
            conversation_id: Conversation identifier
            strategy: Generation strategy to use
            user_context: User context for personalization
            
        Returns:
            Generated response text
        """
        if not self.is_initialized:
            await self.initialize()
        
        start_time = time.time()
        self.stats['total_generations'] += 1
        self.stats['strategy_usage'][strategy] += 1
        
        try:
            # Build generation request
            request = GenerationRequest(
                text_input=text_input,
                nlu_result=nlu_result,
                conversation_id=conversation_id,
                strategy=strategy,
                user_context=self._build_user_context(user_context) if user_context else None
            )
            
            # Generate response
            response = await self._generate_response_internal(request)
            
            # Update statistics
            generation_time = time.time() - start_time
            self._update_generation_stats(response, generation_time)
            
            logger.debug(f"Generated response in {generation_time:.3f}s using {response.strategy_used.value}: "
                        f"'{response.text[:100]}...'")
            
            return response.text
            
        except Exception as e:
            generation_time = time.time() - start_time
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            logger.error(f"Response generation failed after {generation_time:.3f}s: {e}")
            
            # Return fallback response
            return self._get_fallback_response(nlu_result)
    
    async def _generate_response_internal(self, request: GenerationRequest) -> GenerationResponse:
        """Internal response generation logic."""
        
        # Check cache first
        if request.enable_caching:
            cached_response = self._check_cache(request)
            if cached_response:
                self.stats['cache_performance']['hits'] += 1
                return cached_response
        
        self.stats['cache_performance']['misses'] += 1
        
        # Choose generation strategy
        if request.strategy == GenerationStrategy.HYBRID:
            strategy = await self._choose_optimal_strategy(request)
        else:
            strategy = request.strategy
        
        # Generate response based on strategy
        if strategy == GenerationStrategy.TEMPLATE_BASED:
            response = await self._generate_template_response(request)
        elif strategy == GenerationStrategy.LLM_ENHANCED:
            response = await self._generate_llm_enhanced_response(request)
        elif strategy == GenerationStrategy.FULL_LLM:
            response = await self._generate_full_llm_response(request)
        else:  # HYBRID fallback
            response = await self._generate_hybrid_response(request)
        
        # Apply personalization
        if request.enable_personalization and request.user_context:
            response = await self._apply_personalization(response, request.user_context)
        
        # Multi-turn planning
        if request.enable_multi_turn_planning:
            response = await self._add_multi_turn_planning(response, request)
        
        # Cache response
        if request.enable_caching:
            self._cache_response(request, response)
        
        return response
    
    async def _choose_optimal_strategy(self, request: GenerationRequest) -> GenerationStrategy:
        """Choose optimal generation strategy based on context."""
        
        # Fast template-based for common scenarios
        if (request.nlu_result and 
            request.nlu_result.confidence > 0.8 and
            self._has_suitable_template(request.nlu_result)):
            return GenerationStrategy.TEMPLATE_BASED
        
        # LLM enhanced for medium confidence
        if (request.nlu_result and 
            0.5 <= request.nlu_result.confidence <= 0.8):
            return GenerationStrategy.LLM_ENHANCED
        
        # Full LLM for complex cases
        if (request.nlu_result and
            request.nlu_result.requires_human_review):
            return GenerationStrategy.FULL_LLM
        
        # Default to hybrid
        return GenerationStrategy.HYBRID
    
    async def _generate_template_response(self, request: GenerationRequest) -> GenerationResponse:
        """Generate response using templates."""
        start_time = time.time()
        
        try:
            # Find suitable template
            template = self._find_best_template(request.nlu_result)
            if not template:
                # Fallback to hybrid
                return await self._generate_hybrid_response(request)
            
            # Extract variables from NLU result and context
            variables = self._extract_template_variables(template, request)
            
            # Select appropriate template text
            language = request.user_context.language if request.user_context else "it"
            template_text = template.templates.get(language, 
                                                 template.templates.get("it", 
                                                                      list(template.templates.values())[0]))
            
            # Fill template
            response_text = self._fill_template(template_text, variables)
            
            # Create response
            response = GenerationResponse(
                text=response_text,
                strategy_used=GenerationStrategy.TEMPLATE_BASED,
                template_id=template.id,
                confidence=0.9,  # High confidence for template-based
                generation_time=time.time() - start_time,
                coherence_score=0.95,
                relevance_score=0.9,
                completeness_score=0.8
            )
            
            # Update template usage
            template.usage_count += 1
            self.stats['template_usage'][template.id] = (
                self.stats['template_usage'].get(template.id, 0) + 1
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Template-based generation failed: {e}")
            # Fallback to hybrid
            return await self._generate_hybrid_response(request)
    
    async def _generate_llm_enhanced_response(self, request: GenerationRequest) -> GenerationResponse:
        """Generate response using LLM with template guidance."""
        start_time = time.time()
        
        try:
            # Find template for guidance
            template = self._find_best_template(request.nlu_result)
            
            # Build enhanced prompt
            prompt = self._build_llm_enhanced_prompt(request, template)
            
            # Generate with LLM
            if self.llm_service:
                llm_response = await self.llm_service.generate(
                    prompt,
                    GenerationParams(
                        max_tokens=request.max_response_length,
                        temperature=0.3,
                        top_p=0.9
                    )
                )
                response_text = llm_response.text.strip()
                tokens_used = llm_response.tokens_used
                confidence = 0.8
            else:
                # Fallback to template
                return await self._generate_template_response(request)
            
            response = GenerationResponse(
                text=response_text,
                strategy_used=GenerationStrategy.LLM_ENHANCED,
                template_id=template.id if template else None,
                confidence=confidence,
                generation_time=time.time() - start_time,
                tokens_used=tokens_used,
                coherence_score=0.85,
                relevance_score=0.9,
                completeness_score=0.85
            )
            
            return response
            
        except Exception as e:
            logger.error(f"LLM-enhanced generation failed: {e}")
            # Fallback to template
            return await self._generate_template_response(request)
    
    async def _generate_full_llm_response(self, request: GenerationRequest) -> GenerationResponse:
        """Generate response using full LLM processing."""
        start_time = time.time()
        
        try:
            # Build comprehensive prompt
            prompt = self._build_full_llm_prompt(request)
            
            # Generate with LLM
            if self.llm_service:
                llm_response = await self.llm_service.generate(
                    prompt,
                    GenerationParams(
                        max_tokens=request.max_response_length,
                        temperature=0.4,
                        top_p=0.95
                    )
                )
                response_text = llm_response.text.strip()
                tokens_used = llm_response.tokens_used
                confidence = 0.75  # Moderate confidence for full LLM
            else:
                # Fallback to hybrid
                return await self._generate_hybrid_response(request)
            
            response = GenerationResponse(
                text=response_text,
                strategy_used=GenerationStrategy.FULL_LLM,
                confidence=confidence,
                generation_time=time.time() - start_time,
                tokens_used=tokens_used,
                coherence_score=0.8,
                relevance_score=0.85,
                completeness_score=0.9
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Full LLM generation failed: {e}")
            # Fallback to template
            return await self._generate_template_response(request)
    
    async def _generate_hybrid_response(self, request: GenerationRequest) -> GenerationResponse:
        """Generate response using hybrid approach."""
        start_time = time.time()
        
        try:
            # Try template first for speed
            template_response = await self._generate_template_response(request)
            
            # If template confidence is high, use it
            if template_response.confidence > 0.8:
                template_response.strategy_used = GenerationStrategy.HYBRID
                return template_response
            
            # Otherwise, enhance with LLM
            enhanced_response = await self._generate_llm_enhanced_response(request)
            enhanced_response.strategy_used = GenerationStrategy.HYBRID
            
            # Choose best response
            if enhanced_response.confidence > template_response.confidence:
                return enhanced_response
            else:
                return template_response
            
        except Exception as e:
            logger.error(f"Hybrid generation failed: {e}")
            # Final fallback
            return GenerationResponse(
                text=self._get_fallback_response(request.nlu_result),
                strategy_used=GenerationStrategy.HYBRID,
                confidence=0.3,
                generation_time=time.time() - start_time,
                fallback_used=True
            )
    
    async def _apply_personalization(self, response: GenerationResponse, 
                                   user_context: UserContext) -> GenerationResponse:
        """Apply personalization to response."""
        try:
            personalization_level = PersonalizationLevel.NONE
            applied_personalizations = []
            
            original_text = response.text
            
            # Basic personalization
            if user_context.name:
                response.text = response.text.replace("{name}", user_context.name)
                response.text = response.text.replace("{user}", user_context.name)
                applied_personalizations.append("name_substitution")
                personalization_level = PersonalizationLevel.BASIC
            
            # Tone adaptation
            if user_context.preferred_tone == "friendly":
                response.text = self._make_tone_friendlier(response.text)
                applied_personalizations.append("friendly_tone")
                personalization_level = PersonalizationLevel.CONTEXTUAL
            elif user_context.preferred_tone == "casual":
                response.text = self._make_tone_casual(response.text)
                applied_personalizations.append("casual_tone")
                personalization_level = PersonalizationLevel.CONTEXTUAL
            
            # Technical level adaptation
            if user_context.technical_level == "beginner":
                response.text = self._simplify_technical_language(response.text)
                applied_personalizations.append("simplified_technical")
                personalization_level = PersonalizationLevel.ADVANCED
            elif user_context.technical_level == "advanced":
                response.text = self._enhance_technical_detail(response.text)
                applied_personalizations.append("enhanced_technical")
                personalization_level = PersonalizationLevel.ADVANCED
            
            # Communication style adaptation
            if user_context.communication_style == "concise":
                response.text = self._make_more_concise(response.text)
                applied_personalizations.append("concise_style")
            elif user_context.communication_style == "detailed":
                response.text = self._add_more_detail(response.text)
                applied_personalizations.append("detailed_style")
            
            # Update personalization info
            response.personalization_level = personalization_level
            response.personalization_applied = applied_personalizations
            
            # Update user context
            user_context.interaction_count += 1
            user_context.last_interaction = datetime.now()
            self.user_contexts[user_context.user_id] = user_context
            
            # Track personalization usage
            self.stats['personalization_usage'][personalization_level] += 1
            
        except Exception as e:
            logger.error(f"Personalization failed: {e}")
            # Keep original response if personalization fails
        
        return response
    
    async def _add_multi_turn_planning(self, response: GenerationResponse,
                                     request: GenerationRequest) -> GenerationResponse:
        """Add multi-turn conversation planning."""
        try:
            if not request.nlu_result:
                return response
            
            intent = request.nlu_result.intent.intent
            
            # Add follow-up suggestions based on intent
            if intent == IntentType.PROBLEM_REPORT:
                response.follow_up_suggestions = [
                    "Vuoi che ti guidi attraverso i passaggi di risoluzione?",
                    "Hai bisogno di ulteriori informazioni su questo problema?",
                    "Devo creare un ticket per questo problema?"
                ]
                response.expected_user_responses = [
                    "sì", "no", "aiutami", "non capisco", "dimmi di più"
                ]
            
            elif intent == IntentType.INFORMATION_REQUEST:
                response.follow_up_suggestions = [
                    "Vuoi informazioni più dettagliate?",
                    "C'è qualcos'altro che vorresti sapere?",
                    "Ti serve aiuto con qualcosa di correlato?"
                ]
                response.expected_user_responses = [
                    "sì", "no", "dimmi altro", "basta così", "grazie"
                ]
            
            elif intent == IntentType.ESCALATION:
                response.requires_confirmation = True
                response.follow_up_suggestions = [
                    "Confermi che vuoi parlare con un operatore umano?",
                    "Vuoi che io provi prima ad aiutarti?",
                    "È urgente o puoi aspettare?"
                ]
                response.expected_user_responses = [
                    "sì", "conferma", "no", "prova tu", "è urgente"
                ]
            
        except Exception as e:
            logger.error(f"Multi-turn planning failed: {e}")
        
        return response
    
    def _check_cache(self, request: GenerationRequest) -> Optional[GenerationResponse]:
        """Check if response is cached."""
        if not self.enable_caching:
            return None
        
        # Create cache key
        cache_key = self._create_cache_key(request)
        
        # Check cache
        if cache_key in self.response_cache:
            cached_response, timestamp = self.response_cache[cache_key]
            
            # Check if cache is still valid
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                # Return copy with updated metadata
                cached_response.cache_hit = True
                cached_response.timestamp = datetime.now()
                return cached_response
            else:
                # Remove expired cache entry
                del self.response_cache[cache_key]
        
        return None
    
    def _cache_response(self, request: GenerationRequest, response: GenerationResponse) -> None:
        """Cache generated response."""
        if not self.enable_caching:
            return
        
        try:
            cache_key = self._create_cache_key(request)
            self.response_cache[cache_key] = (response, datetime.now())
            
            # Cleanup old cache entries periodically
            if len(self.response_cache) > 1000:
                self._cleanup_cache()
                
        except Exception as e:
            logger.error(f"Cache storage failed: {e}")
    
    def _create_cache_key(self, request: GenerationRequest) -> str:
        """Create cache key from request."""
        key_data = {
            'text': request.text_input,
            'intent': request.nlu_result.intent.intent.value if request.nlu_result else None,
            'category': request.nlu_result.intent.category.value if request.nlu_result else None,
            'strategy': request.strategy.value,
            'user_id': request.user_context.user_id if request.user_context else None,
            'language': request.user_context.language if request.user_context else "it"
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        current_time = datetime.now()
        expired_keys = []
        
        for key, (response, timestamp) in self.response_cache.items():
            if (current_time - timestamp).total_seconds() > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.response_cache[key]
        
        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _has_suitable_template(self, nlu_result: NLUResponse) -> bool:
        """Check if suitable template exists for NLU result."""
        if not nlu_result:
            return False
        
        intent = nlu_result.intent.intent
        category = nlu_result.intent.category
        
        return (intent, category) in self.template_index and len(self.template_index[(intent, category)]) > 0
    
    def _find_best_template(self, nlu_result: Optional[NLUResponse]) -> Optional[ResponseTemplate]:
        """Find best matching template for NLU result."""
        if not nlu_result:
            # Return a default template
            return self._get_default_template()
        
        intent = nlu_result.intent.intent
        category = nlu_result.intent.category
        urgency = nlu_result.intent.urgency
        
        # Look for exact match first
        template_ids = self.template_index.get((intent, category), [])
        
        for template_id in template_ids:
            template = self.templates[template_id]
            if urgency in template.urgency_levels:
                return template
        
        # Fallback to any template for the intent/category
        if template_ids:
            return self.templates[template_ids[0]]
        
        # Fallback to intent-only match
        for template in self.templates.values():
            if intent in template.intent_types:
                return template
        
        # Return default template
        return self._get_default_template()
    
    def _get_default_template(self) -> Optional[ResponseTemplate]:
        """Get default fallback template."""
        for template in self.templates.values():
            if template.type == ResponseType.ACKNOWLEDGMENT:
                return template
        return None
    
    def _extract_template_variables(self, template: ResponseTemplate, 
                                  request: GenerationRequest) -> Dict[str, str]:
        """Extract variables for template filling."""
        variables = {}
        
        # Default variables
        variables['user'] = (request.user_context.name if request.user_context and request.user_context.name 
                           else "utente")
        variables['time'] = datetime.now().strftime("%H:%M")
        variables['date'] = datetime.now().strftime("%d/%m/%Y")
        
        # Extract from NLU entities
        if request.nlu_result and request.nlu_result.entities:
            for entity in request.nlu_result.entities:
                variables[entity.type] = entity.value
        
        # Add conversation context
        variables['conversation_id'] = request.conversation_id
        
        # Add template-specific variables
        if 'problem_description' in template.variables and request.text_input:
            variables['problem_description'] = request.text_input[:100]
        
        return variables
    
    def _fill_template(self, template_text: str, variables: Dict[str, str]) -> str:
        """Fill template with variables."""
        result = template_text
        
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))
        
        return result
    
    def _build_llm_enhanced_prompt(self, request: GenerationRequest, 
                                 template: Optional[ResponseTemplate]) -> str:
        """Build prompt for LLM-enhanced generation."""
        prompt_parts = [
            "Sei un assistente IT esperto che aiuta gli utenti con problemi tecnici.",
            "Rispondi in italiano in modo professionale e utile.",
            ""
        ]
        
        # Add user input context
        prompt_parts.append(f"Richiesta utente: {request.text_input}")
        
        # Add NLU context
        if request.nlu_result:
            prompt_parts.append(f"Tipo di richiesta: {request.nlu_result.intent.intent.value}")
            prompt_parts.append(f"Categoria: {request.nlu_result.intent.category.value}")
            prompt_parts.append(f"Urgenza: {request.nlu_result.intent.urgency.value}")
        
        # Add template guidance
        if template:
            example_text = list(template.templates.values())[0] if template.templates else ""
            prompt_parts.append(f"Segui questo stile di risposta: {example_text}")
        
        # Add user context
        if request.user_context:
            prompt_parts.append(f"Livello tecnico utente: {request.user_context.technical_level}")
            prompt_parts.append(f"Stile di comunicazione: {request.user_context.communication_style}")
        
        prompt_parts.append("")
        prompt_parts.append("Genera una risposta utile e appropriata:")
        
        return "\n".join(prompt_parts)
    
    def _build_full_llm_prompt(self, request: GenerationRequest) -> str:
        """Build comprehensive prompt for full LLM generation."""
        prompt_parts = [
            "Sei un assistente virtuale IT avanzato di un help desk aziendale.",
            "Il tuo compito è fornire supporto tecnico completo e professionale in italiano.",
            "",
            "Linee guida:",
            "- Rispondi sempre in italiano",
            "- Mantieni un tono professionale ma amichevole",
            "- Fornisci soluzioni specifiche e actionable",
            "- Se non sei sicuro, chiedi chiarimenti",
            "- Offri di creare un ticket se necessario",
            "- Considera l'urgenza della richiesta",
            ""
        ]
        
        # Add conversation context
        if self.conversation_manager:
            # Get conversation history
            try:
                conversation_context = asyncio.create_task(
                    self.conversation_manager.get_conversation_context(request.conversation_id)
                )
                # Note: This is simplified - in real implementation we'd await this properly
                prompt_parts.append("Contesto conversazione: [Conversazione in corso]")
            except:
                pass
        
        # Add current request
        prompt_parts.append(f"Richiesta corrente: {request.text_input}")
        
        # Add NLU insights
        if request.nlu_result:
            prompt_parts.append(f"Analisi automatica:")
            prompt_parts.append(f"- Tipo: {request.nlu_result.intent.intent.value}")
            prompt_parts.append(f"- Categoria: {request.nlu_result.intent.category.value}")
            prompt_parts.append(f"- Urgenza: {request.nlu_result.intent.urgency.value}")
            prompt_parts.append(f"- Confidenza: {request.nlu_result.confidence:.2f}")
            
            if request.nlu_result.entities:
                entities_text = ", ".join([f"{e.type}: {e.value}" for e in request.nlu_result.entities])
                prompt_parts.append(f"- Entità rilevate: {entities_text}")
        
        # Add user context
        if request.user_context:
            prompt_parts.append(f"Profilo utente:")
            prompt_parts.append(f"- Livello tecnico: {request.user_context.technical_level}")
            prompt_parts.append(f"- Stile comunicazione: {request.user_context.communication_style}")
            if request.user_context.name:
                prompt_parts.append(f"- Nome: {request.user_context.name}")
        
        prompt_parts.append("")
        prompt_parts.append("Genera una risposta completa e utile:")
        
        return "\n".join(prompt_parts)
    
    def _get_fallback_response(self, nlu_result: Optional[NLUResponse]) -> str:
        """Get fallback response when all generation methods fail."""
        if nlu_result and nlu_result.intent.urgency == UrgencyLevel.CRITICO:
            return ("Mi dispiace, sto avendo difficoltà tecniche. "
                   "Data l'urgenza della tua richiesta, ti metterò in contatto "
                   "immediatamente con un operatore umano.")
        
        return ("Mi dispiace, sto avendo alcune difficoltà tecniche. "
               "Un operatore umano ti contatterà il prima possibile per aiutarti. "
               "Grazie per la pazienza.")
    
    def _build_user_context(self, context_data: Dict[str, Any]) -> UserContext:
        """Build user context from provided data."""
        user_id = context_data.get('user_id', 'unknown')
        
        # Check if we have existing context
        if user_id in self.user_contexts:
            user_context = self.user_contexts[user_id]
            # Update with new data
            for key, value in context_data.items():
                if hasattr(user_context, key):
                    setattr(user_context, key, value)
        else:
            # Create new context
            user_context = UserContext(
                user_id=user_id,
                session_id=context_data.get('session_id', ''),
                language=context_data.get('language', 'it'),
                **{k: v for k, v in context_data.items() 
                   if k in ['preferred_tone', 'communication_style', 'technical_level', 
                           'name', 'role', 'department']}
            )
            self.user_contexts[user_id] = user_context
        
        return user_context
    
    def _make_tone_friendlier(self, text: str) -> str:
        """Make text tone more friendly."""
        # Simple tone adjustments
        replacements = {
            "È necessario": "Ti consiglio di",
            "Devi": "Puoi provare a",
            "Errore": "Piccolo intoppo",
            "Problema": "Situazione",
            "Non funziona": "non sta funzionando come dovrebbe"
        }
        
        result = text
        for formal, friendly in replacements.items():
            result = result.replace(formal, friendly)
        
        # Add friendly elements
        if not any(greeting in text.lower() for greeting in ["ciao", "salve", "buongiorno"]):
            result = "Ciao! " + result
        
        return result
    
    def _make_tone_casual(self, text: str) -> str:
        """Make text tone more casual."""
        replacements = {
            "La prego": "Per favore",
            "Gentilmente": "",
            "Cordiali saluti": "Ciao!",
            "può": "puoi",
            "dovrebbe": "dovresti"
        }
        
        result = text
        for formal, casual in replacements.items():
            result = result.replace(formal, casual)
        
        return result
    
    def _simplify_technical_language(self, text: str) -> str:
        """Simplify technical language for beginners."""
        replacements = {
            "configurazione": "impostazioni",
            "implementare": "fare",
            "ottimizzare": "migliorare",
            "parametri": "valori",
            "interfaccia": "schermata"
        }
        
        result = text
        for technical, simple in replacements.items():
            result = result.replace(technical, simple)
        
        return result
    
    def _enhance_technical_detail(self, text: str) -> str:
        """Add more technical detail for advanced users."""
        # This would typically add more specific technical information
        # For now, just return the original text
        return text
    
    def _make_more_concise(self, text: str) -> str:
        """Make text more concise."""
        # Remove filler words and phrases
        text = text.replace("Ti posso dire che ", "")
        text = text.replace("Come puoi vedere, ", "")
        text = text.replace("In questo caso, ", "")
        
        # Split into sentences and keep essential ones
        sentences = text.split('. ')
        if len(sentences) > 2:
            # Keep first and last sentence for conciseness
            return sentences[0] + '. ' + sentences[-1]
        
        return text
    
    def _add_more_detail(self, text: str) -> str:
        """Add more detail to text."""
        # Add explanatory phrases
        detailed_text = text
        
        if "riavvia" in text.lower():
            detailed_text += " Questo permetterà di resettare tutti i processi e liberare la memoria."
        
        if "aggiorna" in text.lower():
            detailed_text += " L'aggiornamento risolverà bug noti e migliorerà le prestazioni."
        
        return detailed_text
    
    async def _load_default_templates(self) -> None:
        """Load default response templates."""
        # Default greeting template
        greeting_template = ResponseTemplate(
            id="greeting_general",
            type=ResponseType.GREETING,
            intent_types=[IntentType.GREETING],
            categories=[ITCategory.GENERAL],
            urgency_levels=[UrgencyLevel.BASSO, UrgencyLevel.MEDIO],
            templates={
                "it": "Ciao {user}! Sono l'assistente IT virtuale. Come posso aiutarti oggi?",
                "en": "Hello {user}! I'm the virtual IT assistant. How can I help you today?"
            },
            variables=["user"],
            description="General greeting template"
        )
        
        # Problem acknowledgment template
        problem_ack_template = ResponseTemplate(
            id="problem_acknowledgment",
            type=ResponseType.ACKNOWLEDGMENT,
            intent_types=[IntentType.PROBLEM_REPORT],
            categories=[ITCategory.GENERAL, ITCategory.SOFTWARE, ITCategory.HARDWARE],
            urgency_levels=[UrgencyLevel.BASSO, UrgencyLevel.MEDIO],
            templates={
                "it": "Ho capito il tuo problema con {problem_type}. Sto analizzando la situazione e ti fornirò una soluzione il prima possibile.",
                "en": "I understand your problem with {problem_type}. I'm analyzing the situation and will provide you with a solution as soon as possible."
            },
            variables=["problem_type", "user"],
            description="Problem acknowledgment template"
        )
        
        # Escalation template
        escalation_template = ResponseTemplate(
            id="escalation_critical",
            type=ResponseType.ESCALATION,
            intent_types=[IntentType.ESCALATION],
            categories=[ITCategory.GENERAL],
            urgency_levels=[UrgencyLevel.CRITICO, UrgencyLevel.ALTO],
            templates={
                "it": "Comprendo l'urgenza della tua richiesta. Sto inoltrando il tuo caso a un tecnico specializzato che ti contatterà entro {response_time} minuti.",
                "en": "I understand the urgency of your request. I'm forwarding your case to a specialized technician who will contact you within {response_time} minutes."
            },
            variables=["response_time", "user"],
            description="Critical escalation template"
        )
        
        # Information request template
        info_request_template = ResponseTemplate(
            id="information_request",
            type=ResponseType.INFORMATION_REQUEST,
            intent_types=[IntentType.INFORMATION_REQUEST],
            categories=[ITCategory.GENERAL],
            urgency_levels=[UrgencyLevel.BASSO, UrgencyLevel.MEDIO],
            templates={
                "it": "Per aiutarti meglio con {topic}, ho bisogno di qualche informazione aggiuntiva. Puoi dirmi {specific_question}?",
                "en": "To better help you with {topic}, I need some additional information. Can you tell me {specific_question}?"
            },
            variables=["topic", "specific_question"],
            description="Information request template"
        )
        
        # Solution steps template
        solution_template = ResponseTemplate(
            id="solution_steps",
            type=ResponseType.SOLUTION_STEPS,
            intent_types=[IntentType.PROBLEM_REPORT],
            categories=[ITCategory.SOFTWARE, ITCategory.HARDWARE],
            urgency_levels=[UrgencyLevel.BASSO, UrgencyLevel.MEDIO],
            templates={
                "it": "Ecco i passaggi per risolvere il problema:\n{steps}\n\nSe questi passaggi non risolvono il problema, fammi sapere e approfondiremo insieme.",
                "en": "Here are the steps to resolve the problem:\n{steps}\n\nIf these steps don't resolve the problem, let me know and we'll investigate further together."
            },
            variables=["steps"],
            description="Solution steps template"
        )
        
        # Add templates to storage
        templates = [
            greeting_template,
            problem_ack_template, 
            escalation_template,
            info_request_template,
            solution_template
        ]
        
        for template in templates:
            self.templates[template.id] = template
    
    async def _load_templates_from_directory(self, templates_dir: Path) -> None:
        """Load templates from directory."""
        try:
            for template_file in templates_dir.glob("*.json"):
                with open(template_file, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                
                template = ResponseTemplate(**template_data)
                self.templates[template.id] = template
                
                logger.debug(f"Loaded template: {template.id}")
                
        except Exception as e:
            logger.error(f"Failed to load templates from {templates_dir}: {e}")
    
    def _build_template_index(self) -> None:
        """Build index for fast template lookup."""
        self.template_index.clear()
        
        for template in self.templates.values():
            for intent_type in template.intent_types:
                for category in template.categories:
                    key = (intent_type, category)
                    if key not in self.template_index:
                        self.template_index[key] = []
                    self.template_index[key].append(template.id)
        
        logger.debug(f"Built template index with {len(self.template_index)} keys")
    
    def _update_generation_stats(self, response: GenerationResponse, generation_time: float) -> None:
        """Update generation statistics."""
        self.stats['total_generation_time'] += generation_time
        self.stats['average_generation_time'] = (
            self.stats['total_generation_time'] / self.stats['total_generations']
        )
        
        if response.cache_hit:
            self.stats['cache_performance']['hits'] += 1
        
        if response.fallback_used:
            self.stats['fallback_usage'] += 1
    
    async def record_user_feedback(self, conversation_id: str, user_id: str, 
                                 satisfaction_score: float, feedback_text: Optional[str] = None) -> None:
        """Record user feedback for learning."""
        try:
            # Update user context
            if user_id in self.user_contexts:
                self.user_contexts[user_id].satisfaction_history.append(satisfaction_score)
                # Keep last 10 scores
                if len(self.user_contexts[user_id].satisfaction_history) > 10:
                    self.user_contexts[user_id].satisfaction_history.pop(0)
            
            # Update global stats
            self.stats['user_satisfaction_scores'].append(satisfaction_score)
            if len(self.stats['user_satisfaction_scores']) > 1000:
                self.stats['user_satisfaction_scores'].pop(0)
            
            logger.debug(f"Recorded feedback for conversation {conversation_id}: {satisfaction_score}")
            
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        stats = self.stats.copy()
        
        # Add cache statistics
        stats['cache_stats'] = self.cache_stats.copy()
        stats['cache_size'] = len(self.response_cache)
        
        # Add template statistics
        stats['template_count'] = len(self.templates)
        stats['template_index_size'] = len(self.template_index)
        
        # Calculate derived metrics
        if stats['total_generations'] > 0:
            stats['cache_hit_rate'] = (
                stats['cache_performance']['hits'] / stats['total_generations'] * 100
            )
            stats['fallback_rate'] = (
                stats['fallback_usage'] / stats['total_generations'] * 100
            )
        
        # Calculate average satisfaction
        if stats['user_satisfaction_scores']:
            stats['average_satisfaction'] = (
                sum(stats['user_satisfaction_scores']) / len(stats['user_satisfaction_scores'])
            )
        
        stats['timestamp'] = datetime.now().isoformat()
        
        return stats
    
    async def clear_cache(self) -> int:
        """Clear response cache."""
        cache_size = len(self.response_cache)
        self.response_cache.clear()
        self.cache_stats = {'hits': 0, 'misses': 0, 'total_requests': 0}
        
        logger.info(f"Cleared {cache_size} cached responses")
        return cache_size