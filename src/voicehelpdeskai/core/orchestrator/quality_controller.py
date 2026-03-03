"""Advanced quality controller for response validation, fact checking, and quality assurance."""

import asyncio
import time
import uuid
import re
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from enum import Enum
import threading
from pathlib import Path

from loguru import logger

from voicehelpdeskai.services.llm import LLMService, GenerationParams
from voicehelpdeskai.services.nlu import NLUResponse, IntentType, ITCategory
from voicehelpdeskai.config.manager import get_config_manager


class QualityDimension(Enum):
    """Quality assessment dimensions."""
    ACCURACY = "accuracy"              # Factual correctness
    RELEVANCE = "relevance"           # Relevance to user query
    COMPLETENESS = "completeness"     # Information completeness
    COHERENCE = "coherence"           # Logical consistency
    CLARITY = "clarity"               # Clear communication
    SAFETY = "safety"                 # Safety and appropriateness
    HELPFULNESS = "helpfulness"       # Practical utility
    TONE = "tone"                     # Appropriate tone
    TECHNICAL_ACCURACY = "technical_accuracy"  # Technical correctness


class CheckType(Enum):
    """Types of quality checks."""
    AUTOMATED = "automated"           # Automated rule-based checks
    LLM_BASED = "llm_based"          # LLM-powered evaluation
    KNOWLEDGE_BASE = "knowledge_base" # KB fact verification
    PATTERN_BASED = "pattern_based"   # Pattern matching
    HEURISTIC = "heuristic"          # Heuristic evaluation
    SENTIMENT = "sentiment"          # Sentiment analysis
    SAFETY = "safety"                # Safety and appropriateness


class QualitySeverity(Enum):
    """Severity levels for quality issues."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QualityCheck:
    """Individual quality check result."""
    check_id: str
    dimension: QualityDimension
    check_type: CheckType
    score: float  # 0.0 to 1.0
    passed: bool
    
    # Issue details
    severity: QualitySeverity = QualitySeverity.INFO
    message: str = ""
    suggestion: str = ""
    
    # Technical details
    confidence: float = 0.0
    processing_time: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityScore:
    """Overall quality score with breakdown."""
    overall_score: float  # 0.0 to 1.0
    dimension_scores: Dict[QualityDimension, float] = field(default_factory=dict)
    
    # Quality indicators
    is_acceptable: bool = False
    requires_review: bool = False
    confidence_level: str = "medium"  # low, medium, high
    
    # Aggregate statistics
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    
    # Issues summary
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    
    # Metadata
    assessment_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class QualityAssessmentRequest:
    """Request for quality assessment."""
    response_text: str
    original_input: str
    nlu_result: Optional[NLUResponse] = None
    conversation_context: Optional[Dict[str, Any]] = None
    
    # Assessment options
    dimensions_to_check: List[QualityDimension] = field(default_factory=lambda: list(QualityDimension))
    check_types_to_use: List[CheckType] = field(default_factory=lambda: list(CheckType))
    enable_fact_checking: bool = True
    enable_safety_checks: bool = True
    enable_technical_validation: bool = True
    
    # Quality thresholds
    minimum_overall_score: float = 0.6
    minimum_dimension_scores: Dict[QualityDimension, float] = field(default_factory=dict)
    
    # Context
    priority_level: str = "normal"  # low, normal, high, critical
    user_context: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityAssessmentResult:
    """Complete quality assessment result."""
    request_id: str
    overall_score: QualityScore
    checks: List[QualityCheck] = field(default_factory=list)
    
    # Recommendations
    improvement_suggestions: List[str] = field(default_factory=list)
    alternative_responses: List[str] = field(default_factory=list)
    requires_regeneration: bool = False
    
    # Fact checking results
    fact_check_results: List[Dict[str, Any]] = field(default_factory=list)
    verified_facts: List[str] = field(default_factory=list)
    disputed_facts: List[str] = field(default_factory=list)
    
    # Safety assessment
    safety_issues: List[str] = field(default_factory=list)
    content_warnings: List[str] = field(default_factory=list)
    
    # Performance metrics
    processing_time: float = 0.0
    checks_performed: int = 0
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class QualityController:
    """Advanced quality controller for comprehensive response assessment."""
    
    def __init__(self,
                 llm_service: Optional[LLMService] = None,
                 knowledge_base_path: Optional[str] = None,
                 enable_llm_evaluation: bool = True,
                 enable_fact_checking: bool = True,
                 enable_safety_monitoring: bool = True,
                 quality_threshold: float = 0.7,
                 cache_assessments: bool = True):
        """Initialize quality controller.
        
        Args:
            llm_service: LLM service for advanced evaluation
            knowledge_base_path: Path to knowledge base for fact checking
            enable_llm_evaluation: Enable LLM-based quality evaluation
            enable_fact_checking: Enable fact verification
            enable_safety_monitoring: Enable safety and appropriateness checks
            quality_threshold: Minimum quality threshold
            cache_assessments: Enable assessment caching
        """
        self.config = get_config_manager().get_config()
        self.llm_service = llm_service
        self.knowledge_base_path = knowledge_base_path or "./data/knowledge_base"
        self.enable_llm_evaluation = enable_llm_evaluation
        self.enable_fact_checking = enable_fact_checking
        self.enable_safety_monitoring = enable_safety_monitoring
        self.quality_threshold = quality_threshold
        self.cache_assessments = cache_assessments
        
        # Knowledge base for fact checking
        self.knowledge_base: Dict[str, Any] = {}
        self.fact_patterns: Dict[str, str] = {}
        self.technical_facts: Dict[str, List[str]] = {}
        
        # Quality assessment rules
        self.quality_rules: Dict[QualityDimension, List[Dict[str, Any]]] = {}
        self.safety_patterns: List[Dict[str, Any]] = []
        self.prohibited_content: Set[str] = set()
        
        # Assessment cache
        self.assessment_cache: Dict[str, Tuple[QualityAssessmentResult, datetime]] = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Performance tracking
        self.stats = {
            'total_assessments': 0,
            'passed_assessments': 0,
            'failed_assessments': 0,
            'average_processing_time': 0.0,
            'total_processing_time': 0.0,
            'dimension_performance': {dim: {'total': 0, 'passed': 0} for dim in QualityDimension},
            'check_type_usage': {check: 0 for check in CheckType},
            'severity_distribution': {sev: 0 for sev in QualitySeverity},
            'fact_check_stats': {'verified': 0, 'disputed': 0, 'unknown': 0},
            'safety_violations': 0,
            'cache_performance': {'hits': 0, 'misses': 0},
            'errors': 0,
            'last_error': None
        }
        
        # State
        self.is_initialized = False
        self.initialization_lock = threading.Lock()
        
        logger.info("QualityController initialized")
    
    async def initialize(self) -> None:
        """Initialize quality controller and load resources."""
        if self.is_initialized:
            logger.warning("QualityController already initialized")
            return
        
        with self.initialization_lock:
            if self.is_initialized:
                return
            
            try:
                logger.info("Initializing QualityController...")
                
                # Load knowledge base
                await self._load_knowledge_base()
                
                # Initialize quality rules
                self._initialize_quality_rules()
                
                # Load safety patterns
                self._initialize_safety_patterns()
                
                # Load technical validation rules
                self._initialize_technical_validation()
                
                self.is_initialized = True
                logger.success("QualityController initialization complete")
                
            except Exception as e:
                logger.error(f"QualityController initialization failed: {e}")
                self.stats['errors'] += 1
                self.stats['last_error'] = str(e)
                raise
    
    async def check_response_quality(self,
                                   response_text: str,
                                   original_input: str,
                                   nlu_result: Optional[NLUResponse] = None,
                                   conversation_context: Optional[Dict[str, Any]] = None) -> QualityAssessmentResult:
        """Perform comprehensive quality assessment of response.
        
        Args:
            response_text: Response text to assess
            original_input: Original user input
            nlu_result: NLU analysis result
            conversation_context: Conversation context
            
        Returns:
            Complete quality assessment result
        """
        if not self.is_initialized:
            await self.initialize()
        
        start_time = time.time()
        request_id = str(uuid.uuid4())
        self.stats['total_assessments'] += 1
        
        try:
            # Build assessment request
            request = QualityAssessmentRequest(
                response_text=response_text,
                original_input=original_input,
                nlu_result=nlu_result,
                conversation_context=conversation_context or {}
            )
            
            # Check cache
            if self.cache_assessments:
                cached_result = self._check_assessment_cache(request)
                if cached_result:
                    self.stats['cache_performance']['hits'] += 1
                    return cached_result
            
            self.stats['cache_performance']['misses'] += 1
            
            # Perform quality checks
            checks = []
            
            # Basic automated checks
            checks.extend(await self._perform_automated_checks(request))
            
            # Pattern-based checks
            checks.extend(await self._perform_pattern_checks(request))
            
            # Heuristic checks
            checks.extend(await self._perform_heuristic_checks(request))
            
            # LLM-based evaluation
            if self.enable_llm_evaluation and self.llm_service:
                checks.extend(await self._perform_llm_evaluation(request))
            
            # Fact checking
            fact_check_results = []
            if self.enable_fact_checking:
                fact_check_results = await self._perform_fact_checking(request)
                checks.extend(self._convert_fact_checks_to_quality_checks(fact_check_results))
            
            # Safety checks
            safety_issues = []
            if self.enable_safety_monitoring:
                safety_issues, safety_checks = await self._perform_safety_checks(request)
                checks.extend(safety_checks)
            
            # Calculate overall quality score
            overall_score = self._calculate_overall_score(checks, request)
            
            # Generate improvement suggestions
            suggestions = self._generate_improvement_suggestions(checks, request)
            
            # Determine if regeneration is needed
            requires_regeneration = (
                overall_score.overall_score < self.quality_threshold or
                overall_score.critical_issues > 0 or
                len(safety_issues) > 0
            )
            
            # Create assessment result
            processing_time = time.time() - start_time
            result = QualityAssessmentResult(
                request_id=request_id,
                overall_score=overall_score,
                checks=checks,
                improvement_suggestions=suggestions,
                requires_regeneration=requires_regeneration,
                fact_check_results=fact_check_results,
                verified_facts=[fact['claim'] for fact in fact_check_results if fact.get('verified', False)],
                disputed_facts=[fact['claim'] for fact in fact_check_results if not fact.get('verified', True)],
                safety_issues=safety_issues,
                processing_time=processing_time,
                checks_performed=len(checks),
                metadata={
                    'quality_threshold': self.quality_threshold,
                    'assessment_version': '1.0'
                }
            )
            
            # Update statistics
            self._update_assessment_stats(result)
            
            # Cache result
            if self.cache_assessments:
                self._cache_assessment_result(request, result)
            
            # Log assessment
            if overall_score.overall_score >= self.quality_threshold:
                self.stats['passed_assessments'] += 1
                logger.debug(f"Quality assessment passed: score={overall_score.overall_score:.3f}, "
                           f"checks={len(checks)}, time={processing_time:.3f}s")
            else:
                self.stats['failed_assessments'] += 1
                logger.warning(f"Quality assessment failed: score={overall_score.overall_score:.3f}, "
                             f"issues={overall_score.critical_issues + overall_score.high_issues}")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.stats['failed_assessments'] += 1
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            logger.error(f"Quality assessment failed after {processing_time:.3f}s: {e}")
            
            # Return minimal result with error
            return QualityAssessmentResult(
                request_id=request_id,
                overall_score=QualityScore(
                    overall_score=0.0,
                    is_acceptable=False,
                    requires_review=True,
                    critical_issues=1
                ),
                checks=[QualityCheck(
                    check_id="error_check",
                    dimension=QualityDimension.ACCURACY,
                    check_type=CheckType.AUTOMATED,
                    score=0.0,
                    passed=False,
                    severity=QualitySeverity.CRITICAL,
                    message=f"Assessment failed: {str(e)}"
                )],
                requires_regeneration=True,
                processing_time=processing_time,
                metadata={'error': str(e)}
            )
    
    async def _perform_automated_checks(self, request: QualityAssessmentRequest) -> List[QualityCheck]:
        """Perform automated rule-based quality checks."""
        checks = []
        
        try:
            response_text = request.response_text
            
            # Length and structure checks
            checks.append(self._check_response_length(response_text))
            checks.append(self._check_response_structure(response_text))
            checks.append(self._check_language_consistency(response_text))
            
            # Completeness checks
            checks.append(self._check_completeness(response_text, request.original_input))
            
            # Clarity checks
            checks.append(self._check_clarity(response_text))
            
            # Technical accuracy checks
            if request.nlu_result and request.nlu_result.intent.category in [ITCategory.SOFTWARE, ITCategory.HARDWARE, ITCategory.NETWORK]:
                checks.append(self._check_technical_accuracy(response_text, request.nlu_result))
            
            self.stats['check_type_usage'][CheckType.AUTOMATED] += len(checks)
            
        except Exception as e:
            logger.error(f"Automated checks failed: {e}")
        
        return checks
    
    async def _perform_pattern_checks(self, request: QualityAssessmentRequest) -> List[QualityCheck]:
        """Perform pattern-based quality checks."""
        checks = []
        
        try:
            response_text = request.response_text
            
            # Check for helpful patterns
            checks.append(self._check_helpful_patterns(response_text))
            
            # Check for inappropriate patterns
            checks.append(self._check_inappropriate_patterns(response_text))
            
            # Check for professional tone
            checks.append(self._check_professional_tone(response_text))
            
            # Check for action items
            checks.append(self._check_action_items(response_text, request.nlu_result))
            
            self.stats['check_type_usage'][CheckType.PATTERN_BASED] += len(checks)
            
        except Exception as e:
            logger.error(f"Pattern checks failed: {e}")
        
        return checks
    
    async def _perform_heuristic_checks(self, request: QualityAssessmentRequest) -> List[QualityCheck]:
        """Perform heuristic quality checks."""
        checks = []
        
        try:
            # Relevance heuristic
            checks.append(self._check_relevance_heuristic(request))
            
            # Coherence heuristic
            checks.append(self._check_coherence_heuristic(request.response_text))
            
            # Helpfulness heuristic
            checks.append(self._check_helpfulness_heuristic(request))
            
            self.stats['check_type_usage'][CheckType.HEURISTIC] += len(checks)
            
        except Exception as e:
            logger.error(f"Heuristic checks failed: {e}")
        
        return checks
    
    async def _perform_llm_evaluation(self, request: QualityAssessmentRequest) -> List[QualityCheck]:
        """Perform LLM-based quality evaluation."""
        checks = []
        
        try:
            if not self.llm_service:
                return checks
            
            # Overall quality evaluation
            overall_eval = await self._llm_evaluate_overall_quality(request)
            if overall_eval:
                checks.append(overall_eval)
            
            # Accuracy evaluation
            accuracy_eval = await self._llm_evaluate_accuracy(request)
            if accuracy_eval:
                checks.append(accuracy_eval)
            
            # Helpfulness evaluation
            helpfulness_eval = await self._llm_evaluate_helpfulness(request)
            if helpfulness_eval:
                checks.append(helpfulness_eval)
            
            self.stats['check_type_usage'][CheckType.LLM_BASED] += len(checks)
            
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
        
        return checks
    
    async def _perform_fact_checking(self, request: QualityAssessmentRequest) -> List[Dict[str, Any]]:
        """Perform fact checking against knowledge base."""
        fact_results = []
        
        try:
            response_text = request.response_text
            
            # Extract factual claims
            claims = self._extract_factual_claims(response_text)
            
            # Verify each claim
            for claim in claims:
                verification_result = await self._verify_fact(claim, request)
                fact_results.append(verification_result)
                
                # Update statistics
                if verification_result.get('verified'):
                    self.stats['fact_check_stats']['verified'] += 1
                elif verification_result.get('disputed'):
                    self.stats['fact_check_stats']['disputed'] += 1
                else:
                    self.stats['fact_check_stats']['unknown'] += 1
            
        except Exception as e:
            logger.error(f"Fact checking failed: {e}")
        
        return fact_results
    
    async def _perform_safety_checks(self, request: QualityAssessmentRequest) -> Tuple[List[str], List[QualityCheck]]:
        """Perform safety and appropriateness checks."""
        safety_issues = []
        safety_checks = []
        
        try:
            response_text = request.response_text.lower()
            
            # Check for prohibited content
            for prohibited_term in self.prohibited_content:
                if prohibited_term in response_text:
                    safety_issues.append(f"Contains prohibited content: {prohibited_term}")
                    self.stats['safety_violations'] += 1
            
            # Check safety patterns
            for pattern_rule in self.safety_patterns:
                if re.search(pattern_rule['pattern'], response_text, re.IGNORECASE):
                    safety_issues.append(pattern_rule['message'])
            
            # Create safety check result
            safety_check = QualityCheck(
                check_id="safety_overall",
                dimension=QualityDimension.SAFETY,
                check_type=CheckType.SAFETY,
                score=1.0 if len(safety_issues) == 0 else 0.0,
                passed=len(safety_issues) == 0,
                severity=QualitySeverity.CRITICAL if safety_issues else QualitySeverity.INFO,
                message="Safety check" + (f" - {len(safety_issues)} issues found" if safety_issues else " passed"),
                details={'issues': safety_issues}
            )
            safety_checks.append(safety_check)
            
            self.stats['check_type_usage'][CheckType.SAFETY] += 1
            
        except Exception as e:
            logger.error(f"Safety checks failed: {e}")
        
        return safety_issues, safety_checks
    
    def _check_response_length(self, response_text: str) -> QualityCheck:
        """Check if response length is appropriate."""
        length = len(response_text)
        
        # Optimal length range: 50-500 characters for most responses
        if 50 <= length <= 500:
            score = 1.0
            passed = True
            message = f"Good response length: {length} characters"
        elif length < 50:
            score = 0.3
            passed = False
            message = f"Response too short: {length} characters"
        elif length > 1000:
            score = 0.4
            passed = False
            message = f"Response too long: {length} characters"
        else:
            score = 0.7
            passed = True
            message = f"Acceptable response length: {length} characters"
        
        return QualityCheck(
            check_id="length_check",
            dimension=QualityDimension.CLARITY,
            check_type=CheckType.AUTOMATED,
            score=score,
            passed=passed,
            message=message,
            details={'length': length}
        )
    
    def _check_response_structure(self, response_text: str) -> QualityCheck:
        """Check response structure and formatting."""
        score = 1.0
        issues = []
        
        # Check for basic structure
        if not response_text.strip():
            score = 0.0
            issues.append("Empty response")
        
        # Check for proper capitalization
        if response_text and not response_text[0].isupper():
            score -= 0.2
            issues.append("Response doesn't start with capital letter")
        
        # Check for proper punctuation
        if response_text and response_text[-1] not in '.!?':
            score -= 0.1
            issues.append("Response doesn't end with proper punctuation")
        
        # Check for excessive repetition
        words = response_text.lower().split()
        if len(words) > 0:
            word_freq = {}
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1
            max_freq = max(word_freq.values())
            if max_freq > len(words) * 0.3:  # More than 30% repetition
                score -= 0.3
                issues.append("Excessive word repetition detected")
        
        score = max(0.0, score)
        
        return QualityCheck(
            check_id="structure_check",
            dimension=QualityDimension.COHERENCE,
            check_type=CheckType.AUTOMATED,
            score=score,
            passed=score >= 0.7,
            message=f"Structure check: {len(issues)} issues" if issues else "Good structure",
            details={'issues': issues}
        )
    
    def _check_language_consistency(self, response_text: str) -> QualityCheck:
        """Check language consistency (should be Italian)."""
        # Simple check for Italian language indicators
        italian_indicators = ['è', 'à', 'ì', 'ò', 'ù', 'che', 'con', 'per', 'una', 'del', 'della', 'gli', 'sono', 'hai', 'puoi']
        english_indicators = ['the', 'and', 'you', 'are', 'can', 'have', 'this', 'that', 'with', 'for']
        
        text_lower = response_text.lower()
        italian_count = sum(1 for indicator in italian_indicators if indicator in text_lower)
        english_count = sum(1 for indicator in english_indicators if indicator in text_lower)
        
        if italian_count > english_count:
            score = 1.0
            message = "Language consistency: Italian"
        elif english_count > italian_count:
            score = 0.3
            message = "Language consistency: Primarily English (expected Italian)"
        else:
            score = 0.7
            message = "Language consistency: Mixed or unclear"
        
        return QualityCheck(
            check_id="language_check",
            dimension=QualityDimension.CLARITY,
            check_type=CheckType.AUTOMATED,
            score=score,
            passed=score >= 0.7,
            message=message,
            details={'italian_indicators': italian_count, 'english_indicators': english_count}
        )
    
    def _check_completeness(self, response_text: str, original_input: str) -> QualityCheck:
        """Check if response addresses the original input."""
        # Simple completeness check based on keyword overlap
        response_words = set(response_text.lower().split())
        input_words = set(original_input.lower().split())
        
        # Remove common stop words
        stop_words = {'il', 'la', 'di', 'che', 'e', 'a', 'un', 'in', 'con', 'per', 'da', 'su', 'come', 'ho', 'hai', 'ha'}
        response_words -= stop_words
        input_words -= stop_words
        
        if len(input_words) > 0:
            overlap = len(response_words & input_words) / len(input_words)
            score = min(1.0, overlap * 2)  # Scale up overlap to get reasonable scores
        else:
            score = 0.5  # Default if no meaningful words in input
        
        return QualityCheck(
            check_id="completeness_check",
            dimension=QualityDimension.COMPLETENESS,
            check_type=CheckType.AUTOMATED,
            score=score,
            passed=score >= 0.5,
            message=f"Completeness: {score:.1%} keyword overlap",
            details={'overlap_ratio': overlap if 'overlap' in locals() else 0}
        )
    
    def _check_clarity(self, response_text: str) -> QualityCheck:
        """Check response clarity and readability."""
        score = 1.0
        issues = []
        
        # Check for overly complex sentences
        sentences = response_text.split('. ')
        avg_sentence_length = sum(len(sentence.split()) for sentence in sentences) / max(len(sentences), 1)
        
        if avg_sentence_length > 25:
            score -= 0.2
            issues.append("Sentences too long")
        
        # Check for jargon or overly technical terms
        technical_terms = ['API', 'TCP/IP', 'DNS', 'SSL', 'CPU', 'RAM', 'BIOS', 'DHCP']
        tech_count = sum(1 for term in technical_terms if term in response_text)
        
        if tech_count > 3:
            score -= 0.1
            issues.append("Too many technical terms")
        
        # Check for clear action words
        action_words = ['prova', 'verifica', 'clicca', 'apri', 'chiudi', 'riavvia', 'controlla']
        has_actions = any(word in response_text.lower() for word in action_words)
        
        if not has_actions and len(response_text) > 100:
            score -= 0.1
            issues.append("No clear action words")
        
        score = max(0.0, score)
        
        return QualityCheck(
            check_id="clarity_check",
            dimension=QualityDimension.CLARITY,
            check_type=CheckType.AUTOMATED,
            score=score,
            passed=score >= 0.7,
            message=f"Clarity: {len(issues)} issues" if issues else "Good clarity",
            details={'issues': issues, 'avg_sentence_length': avg_sentence_length}
        )
    
    def _check_technical_accuracy(self, response_text: str, nlu_result: NLUResponse) -> QualityCheck:
        """Check technical accuracy based on IT category."""
        score = 0.8  # Default moderate score
        issues = []
        
        category = nlu_result.intent.category
        text_lower = response_text.lower()
        
        # Category-specific technical validation
        if category == ITCategory.SOFTWARE:
            # Check for software-related accuracy
            if 'riavvia' in text_lower and 'software' in text_lower:
                score += 0.1  # Good basic advice
            if 'aggiorna' in text_lower:
                score += 0.1  # Update advice is usually good
        
        elif category == ITCategory.HARDWARE:
            # Check for hardware-related accuracy
            if 'controlla' in text_lower and ('cavi' in text_lower or 'connessioni' in text_lower):
                score += 0.1  # Good hardware troubleshooting
            if 'spegni' in text_lower and 'riaccendi' in text_lower:
                score += 0.1  # Power cycle advice
        
        elif category == ITCategory.NETWORK:
            # Check for network-related accuracy
            if 'connessione' in text_lower and ('verifica' in text_lower or 'controlla' in text_lower):
                score += 0.1  # Good network troubleshooting
            if 'router' in text_lower and 'riavvia' in text_lower:
                score += 0.1  # Router restart advice
        
        # Check for dangerous advice
        dangerous_patterns = [
            r'elimina.*file.*sistema',
            r'cancella.*cartella.*windows',
            r'modifica.*registry',
            r'formatta.*disco'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, text_lower):
                score -= 0.5
                issues.append(f"Potentially dangerous advice: {pattern}")
        
        score = max(0.0, min(1.0, score))
        
        return QualityCheck(
            check_id="technical_accuracy_check",
            dimension=QualityDimension.TECHNICAL_ACCURACY,
            check_type=CheckType.AUTOMATED,
            score=score,
            passed=score >= 0.6,
            message=f"Technical accuracy: {score:.1%}",
            details={'category': category.value, 'issues': issues}
        )
    
    def _check_helpful_patterns(self, response_text: str) -> QualityCheck:
        """Check for helpful patterns in response."""
        helpful_patterns = [
            r'ecco.*passi',
            r'prova.*seguire',
            r'puoi.*fare',
            r'ti.*aiuto',
            r'se.*problema.*persiste',
            r'controlla.*se',
            r'verifica.*che'
        ]
        
        text_lower = response_text.lower()
        helpful_count = sum(1 for pattern in helpful_patterns if re.search(pattern, text_lower))
        
        score = min(1.0, helpful_count * 0.3)  # Each helpful pattern adds 0.3
        
        return QualityCheck(
            check_id="helpful_patterns_check",
            dimension=QualityDimension.HELPFULNESS,
            check_type=CheckType.PATTERN_BASED,
            score=score,
            passed=score >= 0.5,
            message=f"Helpful patterns: {helpful_count} found",
            details={'helpful_patterns_count': helpful_count}
        )
    
    def _check_inappropriate_patterns(self, response_text: str) -> QualityCheck:
        """Check for inappropriate patterns."""
        inappropriate_patterns = [
            r'non.*so',
            r'non.*posso.*aiutare',
            r'impossibile',
            r'non.*funziona.*mai',
            r'non.*capisco',
            r'errore.*grave',
            r'problema.*serio'
        ]
        
        text_lower = response_text.lower()
        inappropriate_count = sum(1 for pattern in inappropriate_patterns if re.search(pattern, text_lower))
        
        score = max(0.0, 1.0 - (inappropriate_count * 0.3))
        
        return QualityCheck(
            check_id="inappropriate_patterns_check",
            dimension=QualityDimension.HELPFULNESS,
            check_type=CheckType.PATTERN_BASED,
            score=score,
            passed=score >= 0.7,
            message=f"Inappropriate patterns: {inappropriate_count} found",
            details={'inappropriate_patterns_count': inappropriate_count}
        )
    
    def _check_professional_tone(self, response_text: str) -> QualityCheck:
        """Check for professional tone."""
        professional_indicators = [
            'gentilmente', 'cortesemente', 'prego', 'grazie', 'buongiorno', 'buonasera',
            'la ringrazio', 'sono qui per aiutarti', 'posso assisterti'
        ]
        
        casual_indicators = [
            'ciao', 'hey', 'ok', 'boh', 'mah', 'tipo', 'insomma'
        ]
        
        text_lower = response_text.lower()
        professional_count = sum(1 for indicator in professional_indicators if indicator in text_lower)
        casual_count = sum(1 for indicator in casual_indicators if indicator in text_lower)
        
        if professional_count > casual_count:
            score = 1.0
            tone = "professional"
        elif casual_count > professional_count:
            score = 0.6
            tone = "casual"
        else:
            score = 0.8
            tone = "neutral"
        
        return QualityCheck(
            check_id="professional_tone_check",
            dimension=QualityDimension.TONE,
            check_type=CheckType.PATTERN_BASED,
            score=score,
            passed=score >= 0.7,
            message=f"Tone: {tone}",
            details={'professional_indicators': professional_count, 'casual_indicators': casual_count}
        )
    
    def _check_action_items(self, response_text: str, nlu_result: Optional[NLUResponse]) -> QualityCheck:
        """Check if response contains actionable items."""
        action_patterns = [
            r'prova.*a',
            r'verifica.*se',
            r'controlla.*che',
            r'clicca.*su',
            r'apri.*il',
            r'vai.*in',
            r'seleziona.*il',
            r'riavvia.*il'
        ]
        
        text_lower = response_text.lower()
        action_count = sum(1 for pattern in action_patterns if re.search(pattern, text_lower))
        
        # Expect more actions for problem reports
        expected_actions = 2 if (nlu_result and nlu_result.intent.intent == IntentType.PROBLEM_REPORT) else 1
        
        score = min(1.0, action_count / expected_actions)
        
        return QualityCheck(
            check_id="action_items_check",
            dimension=QualityDimension.HELPFULNESS,
            check_type=CheckType.PATTERN_BASED,
            score=score,
            passed=score >= 0.5,
            message=f"Action items: {action_count} found",
            details={'action_count': action_count, 'expected_actions': expected_actions}
        )
    
    def _check_relevance_heuristic(self, request: QualityAssessmentRequest) -> QualityCheck:
        """Heuristic check for response relevance."""
        # Simple relevance based on shared keywords and intent alignment
        response_lower = request.response_text.lower()
        input_lower = request.original_input.lower()
        
        # Extract keywords from input
        input_keywords = [word for word in input_lower.split() if len(word) > 3]
        
        # Count keyword matches
        keyword_matches = sum(1 for keyword in input_keywords if keyword in response_lower)
        relevance_ratio = keyword_matches / max(len(input_keywords), 1)
        
        # Intent alignment bonus
        intent_bonus = 0.0
        if request.nlu_result:
            intent = request.nlu_result.intent.intent
            if intent == IntentType.PROBLEM_REPORT and any(word in response_lower for word in ['problema', 'errore', 'risoluzione', 'soluzione']):
                intent_bonus = 0.2
            elif intent == IntentType.INFORMATION_REQUEST and any(word in response_lower for word in ['informazioni', 'dettagli', 'spiegazione']):
                intent_bonus = 0.2
        
        score = min(1.0, relevance_ratio + intent_bonus)
        
        return QualityCheck(
            check_id="relevance_heuristic",
            dimension=QualityDimension.RELEVANCE,
            check_type=CheckType.HEURISTIC,
            score=score,
            passed=score >= 0.6,
            message=f"Relevance: {score:.1%}",
            details={'keyword_matches': keyword_matches, 'total_keywords': len(input_keywords)}
        )
    
    def _check_coherence_heuristic(self, response_text: str) -> QualityCheck:
        """Heuristic check for response coherence."""
        # Simple coherence check based on sentence flow
        sentences = [s.strip() for s in response_text.split('.') if s.strip()]
        
        if len(sentences) <= 1:
            score = 0.8  # Single sentence is generally coherent
        else:
            # Check for logical connectors
            connectors = ['quindi', 'poi', 'inoltre', 'infine', 'prima', 'dopo', 'successivamente']
            connector_count = sum(1 for sentence in sentences for connector in connectors if connector in sentence.lower())
            
            # Check for topic consistency (simple word overlap between sentences)
            topic_consistency = 0
            for i in range(len(sentences) - 1):
                words1 = set(sentences[i].lower().split())
                words2 = set(sentences[i + 1].lower().split())
                overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                topic_consistency += overlap
            
            avg_consistency = topic_consistency / max(len(sentences) - 1, 1)
            score = min(1.0, (connector_count * 0.2) + (avg_consistency * 0.8))
        
        return QualityCheck(
            check_id="coherence_heuristic",
            dimension=QualityDimension.COHERENCE,
            check_type=CheckType.HEURISTIC,
            score=score,
            passed=score >= 0.6,
            message=f"Coherence: {score:.1%}",
            details={'sentence_count': len(sentences)}
        )
    
    def _check_helpfulness_heuristic(self, request: QualityAssessmentRequest) -> QualityCheck:
        """Heuristic check for response helpfulness."""
        response_lower = request.response_text.lower()
        
        # Check for solution-oriented language
        solution_words = ['soluzione', 'risoluzione', 'sistemare', 'correggere', 'aggiustare', 'risolvere']
        solution_count = sum(1 for word in solution_words if word in response_lower)
        
        # Check for next steps
        next_step_words = ['prossimo', 'successivo', 'poi', 'quindi', 'dopo']
        next_step_count = sum(1 for word in next_step_words if word in response_lower)
        
        # Check for contact/follow-up information
        contact_words = ['contatta', 'chiama', 'scrivi', 'ticket', 'supporto']
        contact_count = sum(1 for word in contact_words if word in response_lower)
        
        # Calculate helpfulness score
        total_helpful_elements = solution_count + next_step_count + contact_count
        score = min(1.0, total_helpful_elements * 0.25)
        
        return QualityCheck(
            check_id="helpfulness_heuristic",
            dimension=QualityDimension.HELPFULNESS,
            check_type=CheckType.HEURISTIC,
            score=score,
            passed=score >= 0.5,
            message=f"Helpfulness: {total_helpful_elements} helpful elements",
            details={
                'solution_words': solution_count,
                'next_steps': next_step_count,
                'contact_info': contact_count
            }
        )
    
    async def _llm_evaluate_overall_quality(self, request: QualityAssessmentRequest) -> Optional[QualityCheck]:
        """Use LLM to evaluate overall response quality."""
        try:
            prompt = f"""Valuta la qualità di questa risposta di supporto IT su una scala da 0 a 10.

Richiesta utente: {request.original_input}
Risposta: {request.response_text}

Criteri di valutazione:
- Accuratezza: La risposta è tecnicamente corretta?
- Rilevanza: La risposta risponde alla domanda dell'utente?
- Completezza: La risposta fornisce informazioni sufficienti?
- Chiarezza: La risposta è facile da capire?
- Utilità: La risposta aiuta l'utente a risolvere il problema?

Fornisci solo un numero da 0 a 10, seguito da una breve spiegazione (max 50 parole).
Formato: PUNTEGGIO: X/10 - Spiegazione breve"""

            response = await self.llm_service.generate(
                prompt,
                GenerationParams(max_tokens=100, temperature=0.1)
            )
            
            # Parse response
            text = response.text.strip()
            if 'PUNTEGGIO:' in text:
                score_part = text.split('PUNTEGGIO:')[1].split('-')[0].strip()
                score_match = re.search(r'(\d+(?:\.\d+)?)', score_part)
                if score_match:
                    score = float(score_match.group(1)) / 10.0  # Convert to 0-1 scale
                    explanation = text.split('-', 1)[1].strip() if '-' in text else ""
                    
                    return QualityCheck(
                        check_id="llm_overall_quality",
                        dimension=QualityDimension.ACCURACY,
                        check_type=CheckType.LLM_BASED,
                        score=score,
                        passed=score >= 0.7,
                        message=f"LLM evaluation: {score:.1%}",
                        confidence=0.8,
                        details={'explanation': explanation, 'raw_response': text}
                    )
            
        except Exception as e:
            logger.error(f"LLM overall evaluation failed: {e}")
        
        return None
    
    async def _llm_evaluate_accuracy(self, request: QualityAssessmentRequest) -> Optional[QualityCheck]:
        """Use LLM to evaluate response accuracy."""
        try:
            prompt = f"""Valuta l'accuratezza tecnica di questa risposta di supporto IT.

Richiesta: {request.original_input}
Risposta: {request.response_text}

La risposta contiene informazioni tecnicamente corrette? Ci sono errori o consigli potenzialmente pericolosi?

Rispondi con:
ACCURATEZZA: [ALTA/MEDIA/BASSA]
MOTIVO: [spiegazione breve]"""

            response = await self.llm_service.generate(
                prompt,
                GenerationParams(max_tokens=150, temperature=0.1)
            )
            
            text = response.text.strip().upper()
            if 'ALTA' in text:
                score = 0.9
            elif 'MEDIA' in text:
                score = 0.7
            elif 'BASSA' in text:
                score = 0.3
            else:
                score = 0.5
            
            return QualityCheck(
                check_id="llm_accuracy",
                dimension=QualityDimension.ACCURACY,
                check_type=CheckType.LLM_BASED,
                score=score,
                passed=score >= 0.7,
                message=f"LLM accuracy evaluation: {score:.1%}",
                confidence=0.7,
                details={'raw_response': response.text}
            )
            
        except Exception as e:
            logger.error(f"LLM accuracy evaluation failed: {e}")
        
        return None
    
    async def _llm_evaluate_helpfulness(self, request: QualityAssessmentRequest) -> Optional[QualityCheck]:
        """Use LLM to evaluate response helpfulness."""
        try:
            prompt = f"""Valuta quanto sia utile questa risposta per l'utente.

Richiesta: {request.original_input}
Risposta: {request.response_text}

La risposta fornisce passi concreti per risolvere il problema? È pratica e applicabile?

Rispondi con:
UTILITÀ: [ALTA/MEDIA/BASSA]
MOTIVO: [spiegazione breve]"""

            response = await self.llm_service.generate(
                prompt,
                GenerationParams(max_tokens=150, temperature=0.1)
            )
            
            text = response.text.strip().upper()
            if 'ALTA' in text:
                score = 0.9
            elif 'MEDIA' in text:
                score = 0.7
            elif 'BASSA' in text:
                score = 0.3
            else:
                score = 0.5
            
            return QualityCheck(
                check_id="llm_helpfulness",
                dimension=QualityDimension.HELPFULNESS,
                check_type=CheckType.LLM_BASED,
                score=score,
                passed=score >= 0.7,
                message=f"LLM helpfulness evaluation: {score:.1%}",
                confidence=0.7,
                details={'raw_response': response.text}
            )
            
        except Exception as e:
            logger.error(f"LLM helpfulness evaluation failed: {e}")
        
        return None
    
    def _extract_factual_claims(self, response_text: str) -> List[str]:
        """Extract factual claims from response text."""
        # Simple extraction of statements that appear to be factual
        claims = []
        
        # Look for statements with specific technical terms
        sentences = response_text.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            # Look for sentences containing specific facts
            if any(indicator in sentence.lower() for indicator in [
                'versione', 'richiede', 'supporta', 'compatibile', 'necessario', 'minimo'
            ]):
                claims.append(sentence)
        
        return claims[:5]  # Limit to 5 claims
    
    async def _verify_fact(self, claim: str, request: QualityAssessmentRequest) -> Dict[str, Any]:
        """Verify a factual claim against knowledge base."""
        # Simple fact verification (in a real system, this would check against a comprehensive KB)
        verification_result = {
            'claim': claim,
            'verified': None,  # True/False/None (unknown)
            'confidence': 0.5,
            'source': None,
            'details': {}
        }
        
        # Basic verification against known facts
        claim_lower = claim.lower()
        
        # Check for common IT facts
        if 'windows' in claim_lower and 'riavvia' in claim_lower:
            verification_result['verified'] = True
            verification_result['confidence'] = 0.9
            verification_result['source'] = 'common_knowledge'
        elif 'formatta' in claim_lower and 'disco' in claim_lower:
            verification_result['verified'] = False  # Dangerous advice
            verification_result['confidence'] = 0.9
            verification_result['source'] = 'safety_check'
        else:
            verification_result['verified'] = None  # Unknown
            verification_result['confidence'] = 0.1
        
        return verification_result
    
    def _convert_fact_checks_to_quality_checks(self, fact_results: List[Dict[str, Any]]) -> List[QualityCheck]:
        """Convert fact checking results to quality checks."""
        checks = []
        
        for fact_result in fact_results:
            if fact_result['verified'] is True:
                score = 1.0
                passed = True
                severity = QualitySeverity.INFO
                message = f"Verified fact: {fact_result['claim'][:50]}..."
            elif fact_result['verified'] is False:
                score = 0.0
                passed = False
                severity = QualitySeverity.HIGH
                message = f"Disputed fact: {fact_result['claim'][:50]}..."
            else:
                score = 0.5
                passed = True
                severity = QualitySeverity.LOW
                message = f"Unverified fact: {fact_result['claim'][:50]}..."
            
            check = QualityCheck(
                check_id=f"fact_check_{len(checks)}",
                dimension=QualityDimension.ACCURACY,
                check_type=CheckType.KNOWLEDGE_BASE,
                score=score,
                passed=passed,
                severity=severity,
                message=message,
                confidence=fact_result['confidence'],
                details=fact_result
            )
            checks.append(check)
        
        return checks
    
    def _calculate_overall_score(self, checks: List[QualityCheck], 
                               request: QualityAssessmentRequest) -> QualityScore:
        """Calculate overall quality score from individual checks."""
        if not checks:
            return QualityScore(overall_score=0.0, is_acceptable=False, requires_review=True)
        
        # Calculate dimension scores
        dimension_scores = {}
        dimension_counts = {}
        
        for check in checks:
            dimension = check.dimension
            if dimension not in dimension_scores:
                dimension_scores[dimension] = 0.0
                dimension_counts[dimension] = 0
            
            dimension_scores[dimension] += check.score
            dimension_counts[dimension] += 1
        
        # Average scores by dimension
        for dimension in dimension_scores:
            dimension_scores[dimension] /= dimension_counts[dimension]
        
        # Calculate weighted overall score
        dimension_weights = {
            QualityDimension.ACCURACY: 0.25,
            QualityDimension.RELEVANCE: 0.20,
            QualityDimension.HELPFULNESS: 0.20,
            QualityDimension.CLARITY: 0.15,
            QualityDimension.COMPLETENESS: 0.10,
            QualityDimension.SAFETY: 0.05,
            QualityDimension.COHERENCE: 0.03,
            QualityDimension.TONE: 0.02
        }
        
        overall_score = 0.0
        total_weight = 0.0
        
        for dimension, score in dimension_scores.items():
            weight = dimension_weights.get(dimension, 0.01)
            overall_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            overall_score /= total_weight
        
        # Count check results
        total_checks = len(checks)
        passed_checks = sum(1 for check in checks if check.passed)
        failed_checks = total_checks - passed_checks
        
        # Count issues by severity
        critical_issues = sum(1 for check in checks if check.severity == QualitySeverity.CRITICAL)
        high_issues = sum(1 for check in checks if check.severity == QualitySeverity.HIGH)
        medium_issues = sum(1 for check in checks if check.severity == QualitySeverity.MEDIUM)
        
        # Determine acceptability
        is_acceptable = (
            overall_score >= self.quality_threshold and
            critical_issues == 0 and
            high_issues <= 1
        )
        
        requires_review = (
            overall_score < 0.6 or
            critical_issues > 0 or
            high_issues > 2
        )
        
        # Determine confidence level
        if overall_score >= 0.8 and critical_issues == 0:
            confidence_level = "high"
        elif overall_score >= 0.6 and critical_issues == 0:
            confidence_level = "medium"
        else:
            confidence_level = "low"
        
        return QualityScore(
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            is_acceptable=is_acceptable,
            requires_review=requires_review,
            confidence_level=confidence_level,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            critical_issues=critical_issues,
            high_issues=high_issues,
            medium_issues=medium_issues
        )
    
    def _generate_improvement_suggestions(self, checks: List[QualityCheck], 
                                        request: QualityAssessmentRequest) -> List[str]:
        """Generate improvement suggestions based on failed checks."""
        suggestions = []
        
        # Collect suggestions from failed checks
        for check in checks:
            if not check.passed and check.suggestion:
                suggestions.append(check.suggestion)
        
        # Add general suggestions based on patterns
        failed_dimensions = set(check.dimension for check in checks if not check.passed)
        
        if QualityDimension.CLARITY in failed_dimensions:
            suggestions.append("Semplifica il linguaggio e usa frasi più brevi")
        
        if QualityDimension.COMPLETENESS in failed_dimensions:
            suggestions.append("Fornisci informazioni più complete per rispondere alla domanda")
        
        if QualityDimension.HELPFULNESS in failed_dimensions:
            suggestions.append("Includi passi specifici e actionable per aiutare l'utente")
        
        if QualityDimension.TECHNICAL_ACCURACY in failed_dimensions:
            suggestions.append("Verifica l'accuratezza tecnica delle informazioni fornite")
        
        # Remove duplicates and limit
        suggestions = list(set(suggestions))[:5]
        
        return suggestions
    
    def _check_assessment_cache(self, request: QualityAssessmentRequest) -> Optional[QualityAssessmentResult]:
        """Check if assessment is cached."""
        cache_key = self._create_assessment_cache_key(request)
        
        if cache_key in self.assessment_cache:
            cached_result, timestamp = self.assessment_cache[cache_key]
            
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                # Update timestamp and return
                cached_result.timestamp = datetime.now()
                return cached_result
            else:
                # Remove expired entry
                del self.assessment_cache[cache_key]
        
        return None
    
    def _cache_assessment_result(self, request: QualityAssessmentRequest, 
                               result: QualityAssessmentResult) -> None:
        """Cache assessment result."""
        cache_key = self._create_assessment_cache_key(request)
        self.assessment_cache[cache_key] = (result, datetime.now())
        
        # Cleanup old entries periodically
        if len(self.assessment_cache) > 1000:
            self._cleanup_assessment_cache()
    
    def _create_assessment_cache_key(self, request: QualityAssessmentRequest) -> str:
        """Create cache key for assessment request."""
        import hashlib
        
        key_data = f"{request.response_text}|{request.original_input}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _cleanup_assessment_cache(self) -> None:
        """Clean up expired cache entries."""
        current_time = datetime.now()
        expired_keys = []
        
        for key, (result, timestamp) in self.assessment_cache.items():
            if (current_time - timestamp).total_seconds() > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.assessment_cache[key]
    
    def _update_assessment_stats(self, result: QualityAssessmentResult) -> None:
        """Update assessment statistics."""
        self.stats['total_processing_time'] += result.processing_time
        self.stats['average_processing_time'] = (
            self.stats['total_processing_time'] / self.stats['total_assessments']
        )
        
        # Update dimension performance
        for check in result.checks:
            dimension_stats = self.stats['dimension_performance'][check.dimension]
            dimension_stats['total'] += 1
            if check.passed:
                dimension_stats['passed'] += 1
        
        # Update severity distribution
        for check in result.checks:
            self.stats['severity_distribution'][check.severity] += 1
    
    async def _load_knowledge_base(self) -> None:
        """Load knowledge base for fact checking."""
        try:
            # Load basic IT knowledge base
            self.knowledge_base = {
                'windows_versions': ['10', '11', '2019', '2022'],
                'office_versions': ['2016', '2019', '2021', '365'],
                'common_ports': {'HTTP': 80, 'HTTPS': 443, 'SSH': 22, 'FTP': 21},
                'safe_operations': ['riavvia', 'aggiorna', 'verifica', 'controlla'],
                'dangerous_operations': ['formatta', 'elimina sistema', 'cancella registro']
            }
            
            logger.debug("Knowledge base loaded")
            
        except Exception as e:
            logger.error(f"Knowledge base loading failed: {e}")
    
    def _initialize_quality_rules(self) -> None:
        """Initialize quality assessment rules."""
        # Define quality rules for each dimension
        self.quality_rules = {
            QualityDimension.ACCURACY: [
                {'type': 'technical_validation', 'weight': 0.8},
                {'type': 'fact_checking', 'weight': 0.2}
            ],
            QualityDimension.RELEVANCE: [
                {'type': 'keyword_matching', 'weight': 0.6},
                {'type': 'intent_alignment', 'weight': 0.4}
            ],
            QualityDimension.COMPLETENESS: [
                {'type': 'information_coverage', 'weight': 0.7},
                {'type': 'question_answering', 'weight': 0.3}
            ]
        }
    
    def _initialize_safety_patterns(self) -> None:
        """Initialize safety and appropriateness patterns."""
        self.safety_patterns = [
            {
                'pattern': r'elimina.*tutto',
                'message': 'Suggests deleting everything',
                'severity': 'critical'
            },
            {
                'pattern': r'formatta.*disco',
                'message': 'Suggests formatting disk',
                'severity': 'critical'
            },
            {
                'pattern': r'cancella.*sistema',
                'message': 'Suggests deleting system files',
                'severity': 'critical'
            }
        ]
        
        self.prohibited_content = {
            'password123', 'admin123', 'elimina tutto', 'formatta disco'
        }
    
    def _initialize_technical_validation(self) -> None:
        """Initialize technical validation rules."""
        self.technical_facts = {
            'windows': [
                'Windows 10 supporta USB 3.0',
                'Windows richiede almeno 4GB RAM',
                'Windows Update si trova in Impostazioni'
            ],
            'office': [
                'Office 365 richiede connessione internet',
                'Excel supporta fino a 1 milione di righe',
                'Outlook può configurare account IMAP'
            ]
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        stats = self.stats.copy()
        
        # Add current state
        stats['assessment_cache_size'] = len(self.assessment_cache)
        
        # Calculate derived metrics
        if stats['total_assessments'] > 0:
            stats['pass_rate'] = (stats['passed_assessments'] / stats['total_assessments']) * 100
            stats['cache_hit_rate'] = (stats['cache_performance']['hits'] / stats['total_assessments']) * 100
        
        # Add dimension performance percentages
        for dimension, performance in stats['dimension_performance'].items():
            if performance['total'] > 0:
                performance['pass_rate'] = (performance['passed'] / performance['total']) * 100
        
        stats['timestamp'] = datetime.now().isoformat()
        
        return stats
    
    async def clear_cache(self) -> int:
        """Clear assessment cache."""
        cache_size = len(self.assessment_cache)
        self.assessment_cache.clear()
        
        logger.info(f"Cleared {cache_size} cached assessments")
        return cache_size