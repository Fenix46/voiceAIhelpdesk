"""Natural Language Understanding (NLU) services module.

This module provides comprehensive NLU capabilities for IT helpdesk with:
- Multi-label intent classification for IT problems  
- Entity extraction with fuzzy matching and validation
- Problem analysis and categorization with solution matching
- Dialogue state tracking with policy-based flow management
- Italian language optimization for helpdesk scenarios
"""

from .intent_classifier import (
    IntentClassifier,
    IntentPrediction,
    IntentType,
    ITCategory,
    UrgencyLevel,
    TrainingExample
)

from .entity_extractor import (
    EntityExtractor,
    ExtractedEntity,
    EntityType,
    ValidationRule
)

from .problem_analyzer import (
    ProblemAnalyzer,
    ProblemAnalysis,
    ProblemSignature,
    ProblemSeverity,
    ProblemComplexity,
    ResolutionStatus,
    SolutionTemplate
)

from .dialogue_state_tracker import (
    DialogueStateTracker,
    DialogueContext,
    DialogueTurn,
    DialogueState,
    DialogueAction,
    ContextSlot,
    SlotValue,
    DialoguePolicy
)

from .nlu_manager import (
    NLUManager,
    NLUResponse,
    get_nlu_manager
)

__all__ = [
    # Intent Classification
    'IntentClassifier',
    'IntentPrediction',
    'IntentType',
    'ITCategory', 
    'UrgencyLevel',
    'TrainingExample',
    
    # Entity Extraction
    'EntityExtractor',
    'ExtractedEntity',
    'EntityType',
    'ValidationRule',
    
    # Problem Analysis
    'ProblemAnalyzer',
    'ProblemAnalysis',
    'ProblemSignature',
    'ProblemSeverity',
    'ProblemComplexity',
    'ResolutionStatus',
    'SolutionTemplate',
    
    # Dialogue State Tracking
    'DialogueStateTracker',
    'DialogueContext',
    'DialogueTurn',
    'DialogueState',
    'DialogueAction',
    'ContextSlot',
    'SlotValue',
    'DialoguePolicy',
    
    # NLU Manager
    'NLUManager',
    'NLUResponse',
    'get_nlu_manager',
    
    # Factory functions
    'create_nlu_stack',
    'create_intent_classifier',
    'create_entity_extractor',
    'create_problem_analyzer',
    'create_dialogue_tracker',
]

# Version info
__version__ = "1.0.0"
__author__ = "VoiceHelpDeskAI Team"


def create_nlu_stack(
    enable_intent_classification: bool = True,
    enable_entity_extraction: bool = True,
    enable_problem_analysis: bool = True,
    enable_dialogue_tracking: bool = True,
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    fuzzy_threshold: float = 0.8,
    confidence_threshold: float = 0.7
) -> tuple[IntentClassifier, EntityExtractor, ProblemAnalyzer, DialogueStateTracker]:
    """Factory function to create complete NLU stack.
    
    Args:
        enable_intent_classification: Enable intent classification
        enable_entity_extraction: Enable entity extraction
        enable_problem_analysis: Enable problem analysis
        enable_dialogue_tracking: Enable dialogue state tracking
        model_name: Sentence transformer model name
        fuzzy_threshold: Threshold for fuzzy matching
        confidence_threshold: Minimum confidence threshold
        
    Returns:
        Tuple of (IntentClassifier, EntityExtractor, ProblemAnalyzer, DialogueStateTracker)
    """
    intent_classifier = None
    entity_extractor = None
    problem_analyzer = None
    dialogue_tracker = None
    
    if enable_intent_classification:
        intent_classifier = IntentClassifier(
            model_name=model_name,
            confidence_threshold=confidence_threshold,
            enable_llm_fallback=True
        )
    
    if enable_entity_extraction:
        entity_extractor = EntityExtractor(
            model_name=model_name,
            fuzzy_threshold=fuzzy_threshold,
            enable_fuzzy_matching=True,
            enable_validation=True
        )
    
    if enable_problem_analysis:
        problem_analyzer = ProblemAnalyzer(
            model_name=model_name,
            similarity_threshold=confidence_threshold,
            enable_clustering=True,
            enable_solution_matching=True
        )
    
    if enable_dialogue_tracking:
        dialogue_tracker = DialogueStateTracker(
            enable_proactive_suggestions=True,
            enable_context_inference=True
        )
    
    return intent_classifier, entity_extractor, problem_analyzer, dialogue_tracker


def create_intent_classifier(
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    confidence_threshold: float = 0.7,
    enable_llm_fallback: bool = True,
    fallback_threshold: float = 0.5
) -> IntentClassifier:
    """Factory function to create intent classifier.
    
    Args:
        model_name: Sentence transformer model name
        confidence_threshold: Minimum confidence for predictions
        enable_llm_fallback: Enable LLM fallback for ambiguous cases
        fallback_threshold: Threshold for LLM fallback
        
    Returns:
        Configured IntentClassifier instance
    """
    return IntentClassifier(
        model_name=model_name,
        confidence_threshold=confidence_threshold,
        fallback_threshold=fallback_threshold,
        enable_llm_fallback=enable_llm_fallback,
        cache_embeddings=True
    )


def create_entity_extractor(
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    fuzzy_threshold: float = 0.8,
    enable_spacy: bool = True,
    enable_fuzzy_matching: bool = True,
    enable_validation: bool = True
) -> EntityExtractor:
    """Factory function to create entity extractor.
    
    Args:
        model_name: Sentence transformer model name
        fuzzy_threshold: Threshold for fuzzy string matching
        enable_spacy: Use spaCy for named entity recognition
        enable_fuzzy_matching: Enable fuzzy matching for typos
        enable_validation: Enable entity validation
        
    Returns:
        Configured EntityExtractor instance
    """
    return EntityExtractor(
        model_name=model_name,
        fuzzy_threshold=fuzzy_threshold,
        enable_spacy=enable_spacy,
        enable_fuzzy_matching=enable_fuzzy_matching,
        enable_validation=enable_validation
    )


def create_problem_analyzer(
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    similarity_threshold: float = 0.75,
    enable_clustering: bool = True,
    enable_solution_matching: bool = True,
    max_similar_problems: int = 5
) -> ProblemAnalyzer:
    """Factory function to create problem analyzer.
    
    Args:
        model_name: Sentence transformer model name
        similarity_threshold: Threshold for problem similarity
        enable_clustering: Enable problem clustering
        enable_solution_matching: Enable automatic solution matching
        max_similar_problems: Maximum number of similar problems to return
        
    Returns:
        Configured ProblemAnalyzer instance
    """
    return ProblemAnalyzer(
        model_name=model_name,
        similarity_threshold=similarity_threshold,
        enable_clustering=enable_clustering,
        enable_solution_matching=enable_solution_matching,
        max_similar_problems=max_similar_problems
    )


def create_dialogue_tracker(
    context_timeout: int = 3600,
    max_turns_per_state: int = 5,
    enable_proactive_suggestions: bool = True,
    enable_context_inference: bool = True
) -> DialogueStateTracker:
    """Factory function to create dialogue state tracker.
    
    Args:
        context_timeout: Context timeout in seconds
        max_turns_per_state: Maximum turns allowed in same state
        enable_proactive_suggestions: Enable proactive suggestions
        enable_context_inference: Enable context inference from dialogue
        
    Returns:
        Configured DialogueStateTracker instance
    """
    return DialogueStateTracker(
        context_timeout=context_timeout,
        max_turns_per_state=max_turns_per_state,
        enable_proactive_suggestions=enable_proactive_suggestions,
        enable_context_inference=enable_context_inference
    )


# Convenience aliases for common patterns
from .intent_classifier import IntentPrediction as IntentResult
from .entity_extractor import ExtractedEntity as EntityResult
from .problem_analyzer import ProblemAnalysis as AnalysisResult
from .dialogue_state_tracker import DialogueContext as ConversationContext