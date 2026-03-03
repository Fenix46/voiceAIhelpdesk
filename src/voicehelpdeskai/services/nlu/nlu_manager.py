"""NLU Manager for coordinating all Natural Language Understanding components."""

import asyncio
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

from loguru import logger

from .intent_classifier import IntentClassifier, IntentPrediction, IntentType, ITCategory, UrgencyLevel
from .entity_extractor import EntityExtractor, ExtractedEntity, EntityType
from .problem_analyzer import ProblemAnalyzer, ProblemAnalysis, ProblemSeverity, SolutionTemplate
from .dialogue_state_tracker import DialogueStateTracker, DialogueContext, DialogueState, DialogueAction
from voicehelpdeskai.config.manager import get_config_manager


@dataclass
class NLUResponse:
    """Complete NLU analysis response."""
    # Core results
    intent: IntentPrediction
    entities: List[ExtractedEntity]
    problem_analysis: Optional[ProblemAnalysis] = None
    dialogue_response: Optional[Tuple[str, DialogueAction]] = None
    
    # Processing metadata
    processing_time: float = 0.0
    confidence: float = 0.0
    requires_human_review: bool = False
    
    # Context information
    conversation_id: Optional[str] = None
    dialogue_state: Optional[DialogueState] = None
    
    # Additional metadata
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class NLUManager:
    """Centralized manager for all NLU services and coordination."""
    
    def __init__(self,
                 model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                 enable_intent_classification: bool = True,
                 enable_entity_extraction: bool = True,
                 enable_problem_analysis: bool = True,
                 enable_dialogue_tracking: bool = True,
                 confidence_threshold: float = 0.7,
                 fuzzy_threshold: float = 0.8):
        """Initialize NLU Manager.
        
        Args:
            model_name: Sentence transformer model name
            enable_intent_classification: Enable intent classification
            enable_entity_extraction: Enable entity extraction
            enable_problem_analysis: Enable problem analysis
            enable_dialogue_tracking: Enable dialogue state tracking
            confidence_threshold: Minimum confidence threshold
            fuzzy_threshold: Fuzzy matching threshold
        """
        self.config = get_config_manager().get_config()
        self.model_name = model_name
        self.enable_intent_classification = enable_intent_classification
        self.enable_entity_extraction = enable_entity_extraction
        self.enable_problem_analysis = enable_problem_analysis
        self.enable_dialogue_tracking = enable_dialogue_tracking
        self.confidence_threshold = confidence_threshold
        self.fuzzy_threshold = fuzzy_threshold
        
        # Core services
        self.intent_classifier: Optional[IntentClassifier] = None
        self.entity_extractor: Optional[EntityExtractor] = None
        self.problem_analyzer: Optional[ProblemAnalyzer] = None
        self.dialogue_tracker: Optional[DialogueStateTracker] = None
        
        # Service state
        self.is_initialized = False
        self.initialization_lock = threading.Lock()
        
        # Performance tracking
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0,
            'intent_classifications': 0,
            'entity_extractions': 0,
            'problem_analyses': 0,
            'dialogue_interactions': 0,
            'high_confidence_results': 0,
            'human_review_flagged': 0,
            'last_error': None,
            'errors': 0,
        }
        
        logger.info(f"NLU Manager initialized with model: {model_name}")
    
    async def initialize(self) -> None:
        """Initialize all NLU services."""
        if self.is_initialized:
            logger.warning("NLU Manager already initialized")
            return
        
        with self.initialization_lock:
            if self.is_initialized:
                return
            
            try:
                logger.info("Initializing NLU services...")
                
                # Initialize intent classifier
                if self.enable_intent_classification:
                    self.intent_classifier = IntentClassifier(
                        model_name=self.model_name,
                        confidence_threshold=self.confidence_threshold,
                        enable_llm_fallback=True
                    )
                    await self.intent_classifier.initialize()
                    logger.success("Intent classifier initialized")
                
                # Initialize entity extractor
                if self.enable_entity_extraction:
                    self.entity_extractor = EntityExtractor(
                        model_name=self.model_name,
                        fuzzy_threshold=self.fuzzy_threshold,
                        enable_fuzzy_matching=True,
                        enable_validation=True
                    )
                    await self.entity_extractor.initialize()
                    logger.success("Entity extractor initialized")
                
                # Initialize problem analyzer
                if self.enable_problem_analysis:
                    self.problem_analyzer = ProblemAnalyzer(
                        model_name=self.model_name,
                        similarity_threshold=self.confidence_threshold,
                        enable_clustering=True,
                        enable_solution_matching=True
                    )
                    await self.problem_analyzer.initialize()
                    logger.success("Problem analyzer initialized")
                
                # Initialize dialogue tracker
                if self.enable_dialogue_tracking:
                    self.dialogue_tracker = DialogueStateTracker(
                        enable_proactive_suggestions=True,
                        enable_context_inference=True
                    )
                    await self.dialogue_tracker.initialize()
                    logger.success("Dialogue state tracker initialized")
                
                self.is_initialized = True
                logger.success("NLU Manager initialization complete")
                
            except Exception as e:
                logger.error(f"NLU Manager initialization failed: {e}")
                self.stats['errors'] += 1
                self.stats['last_error'] = str(e)
                raise
    
    async def process_text(self,
                          text: str,
                          conversation_id: Optional[str] = None,
                          user_id: Optional[str] = None,
                          session_id: Optional[str] = None) -> NLUResponse:
        """Process text through complete NLU pipeline.
        
        Args:
            text: Input text to process
            conversation_id: Optional conversation ID for dialogue tracking
            user_id: Optional user ID
            session_id: Optional session ID
            
        Returns:
            Complete NLU analysis response
        """
        if not self.is_initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Step 1: Intent classification
            intent = None
            if self.intent_classifier:
                intent = await self.intent_classifier.classify_intent(text)
                self.stats['intent_classifications'] += 1
            else:
                # Fallback intent if classifier disabled
                intent = IntentPrediction(
                    intent=IntentType.PROBLEM_REPORT,
                    confidence=0.1,
                    category=ITCategory.GENERAL,
                    urgency=UrgencyLevel.MEDIO
                )
            
            # Step 2: Entity extraction
            entities = []
            if self.entity_extractor:
                entities = await self.entity_extractor.extract_entities(text)
                self.stats['entity_extractions'] += 1
            
            # Step 3: Problem analysis (if problem-related intent)
            problem_analysis = None
            if (self.problem_analyzer and 
                intent.intent in [IntentType.PROBLEM_REPORT, IntentType.ESCALATION]):
                problem_analysis = await self.problem_analyzer.analyze_problem(text)
                self.stats['problem_analyses'] += 1
            
            # Step 4: Dialogue processing
            dialogue_response = None
            dialogue_state = None
            if self.dialogue_tracker and conversation_id:
                # Check if conversation exists
                context = await self.dialogue_tracker.get_dialogue_context(conversation_id)
                if not context and user_id and session_id:
                    # Start new conversation
                    conversation_id = await self.dialogue_tracker.start_dialogue(
                        user_id=user_id,
                        session_id=session_id,
                        initial_message=text
                    )
                    context = await self.dialogue_tracker.get_dialogue_context(conversation_id)
                
                if context:
                    dialogue_response = await self.dialogue_tracker.process_user_input(
                        conversation_id=conversation_id,
                        user_input=text
                    )
                    dialogue_state = context.current_state
                    self.stats['dialogue_interactions'] += 1
            
            # Calculate overall confidence
            confidence_scores = [intent.confidence]
            if entities:
                confidence_scores.extend([e.confidence for e in entities])
            if problem_analysis:
                confidence_scores.append(problem_analysis.analysis_confidence)
            
            overall_confidence = sum(confidence_scores) / len(confidence_scores)
            
            # Determine if human review is needed
            requires_review = (
                overall_confidence < 0.5 or
                (problem_analysis and problem_analysis.escalation_recommended) or
                (intent.urgency == UrgencyLevel.CRITICO and overall_confidence < 0.8)
            )
            
            # Create response
            processing_time = time.time() - start_time
            
            response = NLUResponse(
                intent=intent,
                entities=entities,
                problem_analysis=problem_analysis,
                dialogue_response=dialogue_response,
                processing_time=processing_time,
                confidence=overall_confidence,
                requires_human_review=requires_review,
                conversation_id=conversation_id,
                dialogue_state=dialogue_state,
                metadata={
                    'services_used': {
                        'intent_classifier': self.intent_classifier is not None,
                        'entity_extractor': self.entity_extractor is not None,
                        'problem_analyzer': self.problem_analyzer is not None,
                        'dialogue_tracker': self.dialogue_tracker is not None,
                    },
                    'entity_count': len(entities),
                    'problem_severity': problem_analysis.severity.value if problem_analysis else None,
                    'dialogue_action': dialogue_response[1].value if dialogue_response else None,
                }
            )
            
            # Update statistics
            self._update_stats(response, processing_time)
            
            logger.debug(f"Processed text in {processing_time:.3f}s: "
                        f"confidence={overall_confidence:.3f}, entities={len(entities)}")
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Text processing failed after {processing_time:.3f}s: {e}")
            self.stats['failed_requests'] += 1
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            
            # Return minimal response with error
            return NLUResponse(
                intent=IntentPrediction(
                    intent=IntentType.PROBLEM_REPORT,
                    confidence=0.1,
                    category=ITCategory.GENERAL,
                    urgency=UrgencyLevel.MEDIO,
                    explanation=f"Processing failed: {str(e)}"
                ),
                entities=[],
                processing_time=processing_time,
                confidence=0.1,
                requires_human_review=True,
                metadata={'error': str(e)}
            )
    
    async def start_conversation(self,
                               user_id: str,
                               session_id: str,
                               initial_message: Optional[str] = None) -> str:
        """Start new conversation.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            initial_message: Optional initial message
            
        Returns:
            Conversation ID
        """
        if not self.dialogue_tracker:
            raise RuntimeError("Dialogue tracking not enabled")
        
        if not self.is_initialized:
            await self.initialize()
        
        return await self.dialogue_tracker.start_dialogue(
            user_id=user_id,
            session_id=session_id,
            initial_message=initial_message
        )
    
    async def get_conversation_context(self, conversation_id: str) -> Optional[DialogueContext]:
        """Get conversation context.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            DialogueContext or None
        """
        if not self.dialogue_tracker:
            return None
        
        return await self.dialogue_tracker.get_dialogue_context(conversation_id)
    
    async def close_conversation(self, conversation_id: str, reason: str = "completed") -> None:
        """Close conversation.
        
        Args:
            conversation_id: Conversation ID
            reason: Reason for closing
        """
        if self.dialogue_tracker:
            await self.dialogue_tracker.close_dialogue(conversation_id, reason)
    
    async def add_solution_feedback(self,
                                  solution_id: str,
                                  success: bool,
                                  feedback_score: float) -> None:
        """Add feedback for solution.
        
        Args:
            solution_id: Solution template ID
            success: Whether solution was successful
            feedback_score: Feedback score (0.0-5.0)
        """
        if self.problem_analyzer:
            self.problem_analyzer.update_solution_feedback(
                solution_id, success, feedback_score
            )
    
    async def add_training_example(self,
                                 text: str,
                                 intent: IntentType,
                                 category: ITCategory,
                                 urgency: UrgencyLevel) -> None:
        """Add training example for intent classifier.
        
        Args:
            text: Training text
            intent: Correct intent
            category: Correct category
            urgency: Correct urgency
        """
        if self.intent_classifier:
            from .intent_classifier import TrainingExample
            example = TrainingExample(
                text=text,
                intent=intent,
                category=category,
                urgency=urgency
            )
            self.intent_classifier.add_training_example(example)
    
    async def batch_process(self, texts: List[str]) -> List[NLUResponse]:
        """Process multiple texts in batch.
        
        Args:
            texts: List of texts to process
            
        Returns:
            List of NLU responses
        """
        results = []
        
        for text in texts:
            response = await self.process_text(text)
            results.append(response)
        
        return results
    
    async def get_similar_problems(self,
                                 text: str,
                                 max_results: int = 5) -> List[Tuple[str, float]]:
        """Get similar problems from history.
        
        Args:
            text: Problem description
            max_results: Maximum number of results
            
        Returns:
            List of (problem_id, similarity_score) tuples
        """
        if not self.problem_analyzer:
            return []
        
        # Perform problem analysis to get similar problems
        analysis = await self.problem_analyzer.analyze_problem(text)
        return analysis.similar_problems[:max_results]
    
    async def get_solution_templates(self,
                                   category: Optional[ITCategory] = None) -> List[SolutionTemplate]:
        """Get solution templates, optionally filtered by category.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of solution templates
        """
        if not self.problem_analyzer:
            return []
        
        templates = list(self.problem_analyzer.solution_templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        return templates
    
    def _update_stats(self, response: NLUResponse, processing_time: float) -> None:
        """Update processing statistics."""
        self.stats['total_requests'] += 1
        self.stats['successful_requests'] += 1
        self.stats['total_processing_time'] += processing_time
        self.stats['average_processing_time'] = (
            self.stats['total_processing_time'] / self.stats['total_requests']
        )
        
        if response.confidence >= self.confidence_threshold:
            self.stats['high_confidence_results'] += 1
        
        if response.requires_human_review:
            self.stats['human_review_flagged'] += 1
    
    async def cleanup_resources(self) -> Dict[str, int]:
        """Clean up old resources and data."""
        cleanup_stats = {'total_cleaned': 0}
        
        try:
            # Cleanup expired dialogues
            if self.dialogue_tracker:
                cleaned = await self.dialogue_tracker.cleanup_expired_dialogues()
                cleanup_stats['expired_dialogues'] = cleaned
                cleanup_stats['total_cleaned'] += cleaned
            
            logger.info(f"Cleaned up {cleanup_stats['total_cleaned']} NLU resources")
            
        except Exception as e:
            logger.error(f"NLU resource cleanup failed: {e}")
            cleanup_stats['error'] = str(e)
        
        return cleanup_stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all NLU services."""
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
            
            # Check individual services
            services_status = {}
            
            if self.enable_intent_classification:
                if self.intent_classifier:
                    services_status['intent_classifier'] = 'healthy'
                else:
                    services_status['intent_classifier'] = 'unhealthy'
                    health['errors'].append('Intent classifier not initialized')
                    health['overall_status'] = 'degraded'
            else:
                services_status['intent_classifier'] = 'disabled'
            
            if self.enable_entity_extraction:
                if self.entity_extractor:
                    services_status['entity_extractor'] = 'healthy'
                else:
                    services_status['entity_extractor'] = 'unhealthy'
                    health['errors'].append('Entity extractor not initialized')
                    health['overall_status'] = 'degraded'
            else:
                services_status['entity_extractor'] = 'disabled'
            
            if self.enable_problem_analysis:
                if self.problem_analyzer:
                    services_status['problem_analyzer'] = 'healthy'
                else:
                    services_status['problem_analyzer'] = 'unhealthy'
                    health['errors'].append('Problem analyzer not initialized')
                    health['overall_status'] = 'degraded'
            else:
                services_status['problem_analyzer'] = 'disabled'
            
            if self.enable_dialogue_tracking:
                if self.dialogue_tracker:
                    services_status['dialogue_tracker'] = 'healthy'
                else:
                    services_status['dialogue_tracker'] = 'unhealthy'
                    health['errors'].append('Dialogue tracker not initialized')
                    health['overall_status'] = 'degraded'
            else:
                services_status['dialogue_tracker'] = 'disabled'
            
            health['services'].update(services_status)
            
            # Add error statistics
            if self.stats['errors'] > 0:
                health['recent_errors'] = self.stats['errors']
                health['last_error'] = self.stats['last_error']
                if self.stats['failed_requests'] / max(self.stats['total_requests'], 1) > 0.1:
                    health['overall_status'] = 'degraded'
            
        except Exception as e:
            health['overall_status'] = 'unhealthy'
            health['errors'].append(f'Health check failed: {str(e)}')
        
        return health
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all services."""
        stats = self.stats.copy()
        
        # Add service-specific statistics
        if self.intent_classifier:
            stats['intent_classifier'] = self.intent_classifier.get_stats()
        
        if self.entity_extractor:
            stats['entity_extractor'] = self.entity_extractor.get_stats()
        
        if self.problem_analyzer:
            stats['problem_analyzer'] = self.problem_analyzer.get_analytics()
        
        if self.dialogue_tracker:
            stats['dialogue_tracker'] = self.dialogue_tracker.get_analytics()
        
        # Add configuration info
        stats['configuration'] = {
            'model_name': self.model_name,
            'confidence_threshold': self.confidence_threshold,
            'fuzzy_threshold': self.fuzzy_threshold,
            'services_enabled': {
                'intent_classification': self.enable_intent_classification,
                'entity_extraction': self.enable_entity_extraction,
                'problem_analysis': self.enable_problem_analysis,
                'dialogue_tracking': self.enable_dialogue_tracking,
            }
        }
        
        # Add derived metrics
        if stats['total_requests'] > 0:
            stats['success_rate'] = (stats['successful_requests'] / stats['total_requests']) * 100
            stats['high_confidence_rate'] = (stats['high_confidence_results'] / stats['total_requests']) * 100
            stats['human_review_rate'] = (stats['human_review_flagged'] / stats['total_requests']) * 100
        
        return stats


# Global NLU manager instance
_nlu_manager: Optional[NLUManager] = None


def get_nlu_manager() -> NLUManager:
    """Get global NLU manager instance."""
    global _nlu_manager
    if _nlu_manager is None:
        _nlu_manager = NLUManager()
    return _nlu_manager