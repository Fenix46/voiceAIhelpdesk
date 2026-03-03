"""Advanced Problem Analysis and Categorization for IT helpdesk with solution matching."""

import asyncio
import json
import time
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime, timedelta
import numpy as np

from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available - using fallback methods")

try:
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available - limited analysis functionality")

from .intent_classifier import IntentClassifier, IntentPrediction, ITCategory, UrgencyLevel
from .entity_extractor import EntityExtractor, ExtractedEntity, EntityType
from voicehelpdeskai.config.manager import get_config_manager


class ProblemSeverity(Enum):
    """Problem severity levels."""
    CRITICAL = "critical"  # System down, business-critical
    HIGH = "high"         # Major functionality affected
    MEDIUM = "medium"     # Partial functionality affected
    LOW = "low"          # Minor issues, cosmetic problems


class ProblemComplexity(Enum):
    """Problem complexity levels."""
    SIMPLE = "simple"         # Standard procedures, quick fixes
    MODERATE = "moderate"     # Some investigation required
    COMPLEX = "complex"       # Extensive troubleshooting needed
    EXPERT = "expert"         # Specialist knowledge required


class ResolutionStatus(Enum):
    """Resolution status for problems."""
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    PARTIAL = "partial"
    ESCALATED = "escalated"


@dataclass
class ProblemSignature:
    """Unique signature for problem identification."""
    category: ITCategory
    error_pattern: str
    affected_systems: List[str]
    symptoms: List[str]
    signature_hash: str = ""
    
    def __post_init__(self):
        """Generate signature hash after initialization."""
        content = f"{self.category.value}|{self.error_pattern}|{sorted(self.affected_systems)}|{sorted(self.symptoms)}"
        self.signature_hash = hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass
class SolutionTemplate:
    """Template for problem solutions."""
    id: str
    title: str
    description: str
    category: ITCategory
    keywords: List[str]
    steps: List[str]
    prerequisites: List[str] = field(default_factory=list)
    estimated_time: int = 30  # minutes
    complexity: ProblemComplexity = ProblemComplexity.SIMPLE
    success_rate: float = 0.0
    usage_count: int = 0
    last_used: Optional[datetime] = None
    feedback_score: float = 0.0
    tags: List[str] = field(default_factory=list)


@dataclass
class ProblemAnalysis:
    """Complete analysis of a problem report."""
    problem_id: str
    original_text: str
    intent: IntentPrediction
    entities: List[ExtractedEntity]
    signature: ProblemSignature
    severity: ProblemSeverity
    complexity: ProblemComplexity
    urgency: UrgencyLevel
    category: ITCategory
    
    # Analysis results
    root_cause_analysis: Dict[str, Any]
    similar_problems: List[Tuple[str, float]]  # (problem_id, similarity)
    suggested_solutions: List[Tuple[SolutionTemplate, float]]  # (solution, confidence)
    escalation_recommended: bool = False
    estimated_resolution_time: int = 60  # minutes
    
    # Metadata
    analysis_confidence: float = 0.0
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    requires_human_review: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProblemAnalyzer:
    """Advanced problem analyzer for IT helpdesk with pattern recognition and solution matching."""
    
    def __init__(self,
                 model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                 similarity_threshold: float = 0.75,
                 enable_clustering: bool = True,
                 enable_solution_matching: bool = True,
                 max_similar_problems: int = 5):
        """Initialize problem analyzer.
        
        Args:
            model_name: Sentence transformer model for similarity analysis
            similarity_threshold: Threshold for problem similarity
            enable_clustering: Enable problem clustering
            enable_solution_matching: Enable automatic solution matching
            max_similar_problems: Maximum number of similar problems to return
        """
        self.config = get_config_manager().get_config()
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.enable_clustering = enable_clustering
        self.enable_solution_matching = enable_solution_matching
        self.max_similar_problems = max_similar_problems
        
        # Models
        self.sentence_model = None
        self.tfidf_vectorizer = None
        
        # Dependencies
        self.intent_classifier = None
        self.entity_extractor = None
        
        # Knowledge bases
        self.problem_history: Dict[str, ProblemAnalysis] = {}
        self.solution_templates: Dict[str, SolutionTemplate] = {}
        self.problem_patterns: Dict[str, List[str]] = {}
        
        # Clustering
        self.problem_clusters: Dict[int, List[str]] = {}
        self.cluster_centroids: Dict[int, np.ndarray] = {}
        
        # Italian IT problem patterns
        self.severity_indicators = {
            ProblemSeverity.CRITICAL: [
                r'\b(?:critico|urgente|bloccante|emergenza|production down)\b',
                r'\b(?:tutti|everyone|intera azienda|sistema principale)\b',
                r'\b(?:non funziona niente|tutto fermo|completamente bloccato)\b'
            ],
            ProblemSeverity.HIGH: [
                r'\b(?:importante|priorità alta|grave|serio)\b',
                r'\b(?:non posso lavorare|lavoro bloccato|deadline)\b',
                r'\b(?:molti utenti|diversi colleghi|team intero)\b'
            ],
            ProblemSeverity.MEDIUM: [
                r'\b(?:problema|difficoltà|rallentamento|lento)\b',
                r'\b(?:alcuni utenti|qualche volta|intermittente)\b'
            ],
            ProblemSeverity.LOW: [
                r'\b(?:piccolo|minore|estetico|miglioramento)\b',
                r'\b(?:quando possibile|non urgente|suggestion)\b'
            ]
        }
        
        self.complexity_indicators = {
            ProblemComplexity.EXPERT: [
                r'\b(?:server|database|network infrastructure|active directory)\b',
                r'\b(?:corrupted|malware|security breach|data loss)\b'
            ],
            ProblemComplexity.COMPLEX: [
                r'\b(?:multiple systems|integration|configuration|custom software)\b',
                r'\b(?:intermittent|random|sometimes works)\b'
            ],
            ProblemComplexity.MODERATE: [
                r'\b(?:software update|driver|installation|setup)\b',
                r'\b(?:error message|crash|freeze)\b'
            ],
            ProblemComplexity.SIMPLE: [
                r'\b(?:password|login|printer|basic|tutorial)\b',
                r'\b(?:how to|come si|dove trovo)\b'
            ]
        }
        
        # Initialize solution templates
        self._initialize_solution_templates()
        
        # Performance tracking
        self.stats = {
            'total_analyses': 0,
            'problems_categorized': 0,
            'solutions_matched': 0,
            'similar_problems_found': 0,
            'escalations_recommended': 0,
            'clustering_updates': 0,
            'analysis_time': 0.0,
            'average_confidence': 0.0,
        }
        
        logger.info("ProblemAnalyzer initialized")
    
    async def initialize(self) -> None:
        """Initialize models and dependencies."""
        try:
            # Load sentence transformer
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                logger.info(f"Loading sentence transformer: {self.model_name}")
                self.sentence_model = SentenceTransformer(self.model_name)
                logger.success("Sentence transformer loaded")
            
            # Initialize TF-IDF vectorizer
            if SKLEARN_AVAILABLE:
                self.tfidf_vectorizer = TfidfVectorizer(
                    max_features=1000,
                    stop_words='english',  # Add Italian stop words if available
                    ngram_range=(1, 2)
                )
            
            # Initialize intent classifier and entity extractor
            self.intent_classifier = IntentClassifier()
            await self.intent_classifier.initialize()
            
            self.entity_extractor = EntityExtractor()
            await self.entity_extractor.initialize()
            
            logger.success("ProblemAnalyzer initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize ProblemAnalyzer: {e}")
            raise
    
    async def analyze_problem(self, text: str, problem_id: Optional[str] = None) -> ProblemAnalysis:
        """Perform comprehensive problem analysis.
        
        Args:
            text: Problem description text
            problem_id: Optional problem identifier
            
        Returns:
            Complete problem analysis
        """
        start_time = time.time()
        
        if not problem_id:
            problem_id = hashlib.md5(f"{text}{datetime.now()}".encode()).hexdigest()[:12]
        
        try:
            # Step 1: Intent classification
            intent = await self.intent_classifier.classify_intent(text)
            
            # Step 2: Entity extraction
            entities = await self.entity_extractor.extract_entities(text)
            
            # Step 3: Generate problem signature
            signature = self._generate_problem_signature(text, intent, entities)
            
            # Step 4: Determine severity and complexity
            severity = self._analyze_severity(text, intent, entities)
            complexity = self._analyze_complexity(text, intent, entities)
            
            # Step 5: Root cause analysis
            root_cause = await self._perform_root_cause_analysis(text, intent, entities)
            
            # Step 6: Find similar problems
            similar_problems = await self._find_similar_problems(text, signature)
            
            # Step 7: Match solutions
            suggested_solutions = await self._match_solutions(intent, entities, signature)
            
            # Step 8: Determine escalation need
            escalation_needed = self._should_escalate(severity, complexity, intent, similar_problems)
            
            # Step 9: Estimate resolution time
            estimated_time = self._estimate_resolution_time(severity, complexity, suggested_solutions)
            
            # Step 10: Calculate overall confidence
            analysis_confidence = self._calculate_analysis_confidence(
                intent, entities, similar_problems, suggested_solutions
            )
            
            # Create analysis result
            analysis = ProblemAnalysis(
                problem_id=problem_id,
                original_text=text,
                intent=intent,
                entities=entities,
                signature=signature,
                severity=severity,
                complexity=complexity,
                urgency=intent.urgency,
                category=intent.category,
                root_cause_analysis=root_cause,
                similar_problems=similar_problems,
                suggested_solutions=suggested_solutions,
                escalation_recommended=escalation_needed,
                estimated_resolution_time=estimated_time,
                analysis_confidence=analysis_confidence,
                requires_human_review=analysis_confidence < 0.6
            )
            
            # Store analysis for future similarity matching
            self.problem_history[problem_id] = analysis
            
            # Update clustering if enabled
            if self.enable_clustering:
                await self._update_clustering(analysis)
            
            # Update statistics
            processing_time = time.time() - start_time
            self._update_stats(analysis, processing_time)
            
            logger.debug(f"Analyzed problem in {processing_time:.3f}s: "
                        f"severity={severity.value}, confidence={analysis_confidence:.3f}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Problem analysis failed: {e}")
            # Return minimal analysis with error
            return ProblemAnalysis(
                problem_id=problem_id,
                original_text=text,
                intent=IntentPrediction(intent=intent.intent, confidence=0.1, category=intent.category, urgency=intent.urgency),
                entities=[],
                signature=ProblemSignature(ITCategory.GENERAL, "", [], []),
                severity=ProblemSeverity.MEDIUM,
                complexity=ProblemComplexity.MODERATE,
                urgency=UrgencyLevel.MEDIO,
                category=ITCategory.GENERAL,
                root_cause_analysis={'error': str(e)},
                similar_problems=[],
                suggested_solutions=[],
                analysis_confidence=0.1,
                requires_human_review=True
            )
    
    def _generate_problem_signature(self,
                                  text: str,
                                  intent: IntentPrediction,
                                  entities: List[ExtractedEntity]) -> ProblemSignature:
        """Generate unique problem signature for pattern matching."""
        
        # Extract error patterns
        error_patterns = []
        for entity in entities:
            if entity.entity_type in [EntityType.ERROR_CODE, EntityType.ERROR_MESSAGE]:
                error_patterns.append(entity.text.lower())
        
        # Extract affected systems
        affected_systems = []
        for entity in entities:
            if entity.entity_type in [EntityType.SOFTWARE_NAME, EntityType.HARDWARE_MODEL, EntityType.HOSTNAME]:
                affected_systems.append(entity.text.lower())
        
        # Extract symptoms (key phrases)
        import re
        symptom_patterns = [
            r'\bnon funziona\b', r'\bcrash\b', r'\bfreeze\b', r'\blento\b',
            r'\berrore\b', r'\bbloccato\b', r'\bnon risponde\b'
        ]
        symptoms = []
        for pattern in symptom_patterns:
            if re.search(pattern, text.lower()):
                symptoms.append(pattern.strip('\\b'))
        
        return ProblemSignature(
            category=intent.category,
            error_pattern='|'.join(error_patterns) if error_patterns else 'generic',
            affected_systems=affected_systems,
            symptoms=symptoms
        )
    
    def _analyze_severity(self,
                         text: str,
                         intent: IntentPrediction,
                         entities: List[ExtractedEntity]) -> ProblemSeverity:
        """Analyze problem severity based on text indicators."""
        
        import re
        text_lower = text.lower()
        
        # Check severity indicators
        for severity, patterns in self.severity_indicators.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return severity
        
        # Default based on urgency
        urgency_to_severity = {
            UrgencyLevel.CRITICO: ProblemSeverity.CRITICAL,
            UrgencyLevel.ALTO: ProblemSeverity.HIGH,
            UrgencyLevel.MEDIO: ProblemSeverity.MEDIUM,
            UrgencyLevel.BASSO: ProblemSeverity.LOW
        }
        
        return urgency_to_severity.get(intent.urgency, ProblemSeverity.MEDIUM)
    
    def _analyze_complexity(self,
                           text: str,
                           intent: IntentPrediction,
                           entities: List[ExtractedEntity]) -> ProblemComplexity:
        """Analyze problem complexity based on indicators."""
        
        import re
        text_lower = text.lower()
        
        # Check complexity indicators
        for complexity, patterns in self.complexity_indicators.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return complexity
        
        # Consider number of affected systems
        systems_count = len([e for e in entities 
                           if e.entity_type in [EntityType.SOFTWARE_NAME, 
                                              EntityType.HARDWARE_MODEL,
                                              EntityType.HOSTNAME]])
        
        if systems_count > 3:
            return ProblemComplexity.COMPLEX
        elif systems_count > 1:
            return ProblemComplexity.MODERATE
        
        return ProblemComplexity.SIMPLE
    
    async def _perform_root_cause_analysis(self,
                                          text: str,
                                          intent: IntentPrediction,
                                          entities: List[ExtractedEntity]) -> Dict[str, Any]:
        """Perform automated root cause analysis."""
        
        analysis = {
            'primary_category': intent.category.value,
            'potential_causes': [],
            'contributing_factors': [],
            'analysis_method': 'pattern_based',
            'confidence': 0.0
        }
        
        # Category-specific root cause patterns
        cause_patterns = {
            ITCategory.HARDWARE: [
                'hardware failure', 'power supply issue', 'overheating',
                'component malfunction', 'connection problem'
            ],
            ITCategory.SOFTWARE: [
                'software bug', 'configuration error', 'compatibility issue',
                'corrupted files', 'missing dependencies'
            ],
            ITCategory.NETWORK: [
                'connectivity issue', 'DNS problem', 'firewall blocking',
                'bandwidth limitation', 'routing problem'
            ],
            ITCategory.ACCOUNT: [
                'permission issue', 'authentication failure', 'account lockout',
                'password policy violation', 'group membership'
            ]
        }
        
        # Check for specific error indicators
        if intent.category in cause_patterns:
            for cause in cause_patterns[intent.category]:
                # Simple keyword matching (could be enhanced with ML)
                if any(word in text.lower() for word in cause.split()):
                    analysis['potential_causes'].append(cause)
        
        # Analyze entity-specific causes
        for entity in entities:
            if entity.entity_type == EntityType.ERROR_CODE:
                analysis['contributing_factors'].append(f"Error code: {entity.text}")
            elif entity.entity_type == EntityType.SOFTWARE_NAME:
                analysis['contributing_factors'].append(f"Software involved: {entity.text}")
        
        # Calculate confidence based on available information
        info_score = len(entities) * 0.1 + len(analysis['potential_causes']) * 0.2
        analysis['confidence'] = min(info_score, 1.0)
        
        return analysis
    
    async def _find_similar_problems(self,
                                   text: str,
                                   signature: ProblemSignature) -> List[Tuple[str, float]]:
        """Find similar problems from history."""
        if not self.sentence_model or not self.problem_history:
            return []
        
        try:
            # Get embedding for current problem
            current_embedding = self.sentence_model.encode([text])[0]
            
            similarities = []
            
            for problem_id, analysis in self.problem_history.items():
                # Check signature similarity first
                signature_match = (
                    signature.category == analysis.signature.category and
                    len(set(signature.symptoms) & set(analysis.signature.symptoms)) > 0
                )
                
                if signature_match:
                    # Calculate semantic similarity
                    hist_embedding = self.sentence_model.encode([analysis.original_text])[0]
                    similarity = cosine_similarity([current_embedding], [hist_embedding])[0][0]
                    
                    if similarity >= self.similarity_threshold:
                        similarities.append((problem_id, float(similarity)))
            
            # Sort by similarity and return top matches
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:self.max_similar_problems]
            
        except Exception as e:
            logger.error(f"Similar problem search failed: {e}")
            return []
    
    async def _match_solutions(self,
                              intent: IntentPrediction,
                              entities: List[ExtractedEntity],
                              signature: ProblemSignature) -> List[Tuple[SolutionTemplate, float]]:
        """Match appropriate solutions for the problem."""
        if not self.enable_solution_matching or not self.solution_templates:
            return []
        
        matches = []
        
        for template_id, template in self.solution_templates.items():
            confidence = 0.0
            
            # Category match
            if template.category == intent.category:
                confidence += 0.4
            
            # Keyword matching
            text_lower = intent.explanation.lower() if intent.explanation else ""
            keyword_matches = sum(1 for keyword in template.keywords 
                                if keyword.lower() in text_lower)
            if template.keywords:
                confidence += (keyword_matches / len(template.keywords)) * 0.3
            
            # Entity matching
            entity_texts = [e.text.lower() for e in entities]
            tag_matches = sum(1 for tag in template.tags 
                            if any(tag.lower() in entity_text for entity_text in entity_texts))
            if template.tags:
                confidence += (tag_matches / len(template.tags)) * 0.2
            
            # Historical success rate
            confidence += template.success_rate * 0.1
            
            if confidence > 0.3:  # Minimum threshold
                matches.append((template, confidence))
        
        # Sort by confidence
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:3]  # Return top 3 solutions
    
    def _should_escalate(self,
                        severity: ProblemSeverity,
                        complexity: ProblemComplexity,
                        intent: IntentPrediction,
                        similar_problems: List[Tuple[str, float]]) -> bool:
        """Determine if problem should be escalated."""
        
        # Always escalate critical issues
        if severity == ProblemSeverity.CRITICAL:
            return True
        
        # Escalate complex expert-level issues
        if complexity == ProblemComplexity.EXPERT:
            return True
        
        # Escalate if confidence is very low
        if intent.confidence < 0.3:
            return True
        
        # Escalate if no similar problems found (unknown issue)
        if not similar_problems and severity in [ProblemSeverity.HIGH, ProblemSeverity.CRITICAL]:
            return True
        
        return False
    
    def _estimate_resolution_time(self,
                                 severity: ProblemSeverity,
                                 complexity: ProblemComplexity,
                                 suggested_solutions: List[Tuple[SolutionTemplate, float]]) -> int:
        """Estimate resolution time in minutes."""
        
        # Base times by severity
        base_times = {
            ProblemSeverity.CRITICAL: 30,
            ProblemSeverity.HIGH: 60,
            ProblemSeverity.MEDIUM: 120,
            ProblemSeverity.LOW: 240
        }
        
        # Complexity multipliers
        complexity_multipliers = {
            ProblemComplexity.SIMPLE: 0.5,
            ProblemComplexity.MODERATE: 1.0,
            ProblemComplexity.COMPLEX: 2.0,
            ProblemComplexity.EXPERT: 4.0
        }
        
        base_time = base_times[severity]
        multiplier = complexity_multipliers[complexity]
        
        # Adjust based on available solutions
        if suggested_solutions:
            # Use the best solution's estimated time
            best_solution = suggested_solutions[0][0]
            estimated = best_solution.estimated_time * multiplier
        else:
            estimated = base_time * multiplier
        
        return max(int(estimated), 15)  # Minimum 15 minutes
    
    def _calculate_analysis_confidence(self,
                                     intent: IntentPrediction,
                                     entities: List[ExtractedEntity],
                                     similar_problems: List[Tuple[str, float]],
                                     suggested_solutions: List[Tuple[SolutionTemplate, float]]) -> float:
        """Calculate overall analysis confidence."""
        
        confidence_factors = []
        
        # Intent classification confidence
        confidence_factors.append(intent.confidence * 0.3)
        
        # Entity extraction confidence
        if entities:
            avg_entity_confidence = sum(e.confidence for e in entities) / len(entities)
            confidence_factors.append(avg_entity_confidence * 0.2)
        
        # Similar problems confidence
        if similar_problems:
            best_similarity = similar_problems[0][1]
            confidence_factors.append(best_similarity * 0.2)
        
        # Solution matching confidence
        if suggested_solutions:
            best_solution_confidence = suggested_solutions[0][1]
            confidence_factors.append(best_solution_confidence * 0.3)
        
        return sum(confidence_factors) if confidence_factors else 0.1
    
    async def _update_clustering(self, analysis: ProblemAnalysis) -> None:
        """Update problem clusters with new analysis."""
        if not SKLEARN_AVAILABLE or not self.sentence_model:
            return
        
        try:
            # Get all problem texts for clustering
            all_texts = [a.original_text for a in self.problem_history.values()]
            
            if len(all_texts) < 5:  # Need minimum problems for clustering
                return
            
            # Generate embeddings
            embeddings = self.sentence_model.encode(all_texts)
            
            # Perform clustering
            n_clusters = min(5, len(all_texts) // 2)  # Adaptive cluster count
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            cluster_labels = kmeans.fit_predict(embeddings)
            
            # Update cluster information
            self.problem_clusters.clear()
            self.cluster_centroids.clear()
            
            for i, (problem_id, _) in enumerate(self.problem_history.items()):
                cluster_id = cluster_labels[i]
                if cluster_id not in self.problem_clusters:
                    self.problem_clusters[cluster_id] = []
                self.problem_clusters[cluster_id].append(problem_id)
            
            # Store centroids
            for i in range(n_clusters):
                self.cluster_centroids[i] = kmeans.cluster_centers_[i]
            
            self.stats['clustering_updates'] += 1
            logger.debug(f"Updated clustering: {n_clusters} clusters, {len(all_texts)} problems")
            
        except Exception as e:
            logger.error(f"Clustering update failed: {e}")
    
    def _initialize_solution_templates(self) -> None:
        """Initialize common IT solution templates."""
        
        templates = [
            SolutionTemplate(
                id="password_reset_std",
                title="Standard Password Reset",
                description="Reset password through standard procedure",
                category=ITCategory.ACCOUNT,
                keywords=["password", "reset", "login", "access"],
                steps=[
                    "Verify user identity",
                    "Access Active Directory Users and Computers",
                    "Reset password with temporary password",
                    "Configure 'User must change password at next logon'",
                    "Inform user of temporary password securely"
                ],
                estimated_time=10,
                complexity=ProblemComplexity.SIMPLE,
                success_rate=0.95,
                tags=["password", "authentication", "account"]
            ),
            
            SolutionTemplate(
                id="software_reinstall",
                title="Software Reinstallation",
                description="Standard software reinstallation procedure",
                category=ITCategory.SOFTWARE,
                keywords=["install", "software", "program", "application"],
                steps=[
                    "Backup user data if necessary",
                    "Uninstall existing software completely",
                    "Clean registry entries if needed",
                    "Download latest software version",
                    "Install with appropriate permissions",
                    "Configure software settings",
                    "Test functionality"
                ],
                estimated_time=45,
                complexity=ProblemComplexity.MODERATE,
                success_rate=0.85,
                tags=["software", "installation", "application"]
            ),
            
            SolutionTemplate(
                id="network_connectivity_basic",
                title="Basic Network Connectivity Troubleshooting",
                description="Standard network troubleshooting steps",
                category=ITCategory.NETWORK,
                keywords=["network", "connection", "internet", "connectivity"],
                steps=[
                    "Check physical cable connections",
                    "Verify network adapter status",
                    "Run ipconfig /release and /renew",
                    "Flush DNS cache (ipconfig /flushdns)",
                    "Test connectivity with ping",
                    "Check firewall settings",
                    "Contact network administrator if issue persists"
                ],
                estimated_time=30,
                complexity=ProblemComplexity.MODERATE,
                success_rate=0.75,
                tags=["network", "connectivity", "troubleshooting"]
            ),
            
            SolutionTemplate(
                id="printer_troubleshooting",
                title="Printer Troubleshooting",
                description="Common printer issue resolution",
                category=ITCategory.PRINTER,
                keywords=["printer", "print", "printing", "stampante"],
                steps=[
                    "Check printer power and connections",
                    "Verify printer status and error messages",
                    "Check paper and toner/ink levels",
                    "Clear print queue",
                    "Restart print spooler service",
                    "Update or reinstall printer drivers",
                    "Test print functionality"
                ],
                estimated_time=25,
                complexity=ProblemComplexity.SIMPLE,
                success_rate=0.80,
                tags=["printer", "hardware", "drivers"]
            )
        ]
        
        for template in templates:
            self.solution_templates[template.id] = template
    
    def _update_stats(self, analysis: ProblemAnalysis, processing_time: float) -> None:
        """Update analysis statistics."""
        self.stats['total_analyses'] += 1
        self.stats['analysis_time'] += processing_time
        self.stats['problems_categorized'] += 1
        
        if analysis.suggested_solutions:
            self.stats['solutions_matched'] += 1
        
        if analysis.similar_problems:
            self.stats['similar_problems_found'] += 1
        
        if analysis.escalation_recommended:
            self.stats['escalations_recommended'] += 1
        
        # Update running average confidence
        total_confidence = (self.stats['average_confidence'] * (self.stats['total_analyses'] - 1) + 
                           analysis.analysis_confidence)
        self.stats['average_confidence'] = total_confidence / self.stats['total_analyses']
    
    def get_problem_clusters(self) -> Dict[int, List[str]]:
        """Get current problem clusters."""
        return self.problem_clusters.copy()
    
    def get_solution_template(self, template_id: str) -> Optional[SolutionTemplate]:
        """Get solution template by ID."""
        return self.solution_templates.get(template_id)
    
    def update_solution_feedback(self, template_id: str, success: bool, feedback_score: float) -> None:
        """Update solution template with feedback."""
        if template_id in self.solution_templates:
            template = self.solution_templates[template_id]
            template.usage_count += 1
            template.last_used = datetime.now()
            
            # Update success rate (exponential moving average)
            alpha = 0.1
            template.success_rate = (1 - alpha) * template.success_rate + alpha * (1.0 if success else 0.0)
            
            # Update feedback score
            template.feedback_score = (template.feedback_score + feedback_score) / 2
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get comprehensive analytics."""
        analytics = self.stats.copy()
        
        if analytics['total_analyses'] > 0:
            analytics['average_analysis_time'] = analytics['analysis_time'] / analytics['total_analyses']
            analytics['solution_match_rate'] = (analytics['solutions_matched'] / analytics['total_analyses']) * 100
            analytics['similar_problem_rate'] = (analytics['similar_problems_found'] / analytics['total_analyses']) * 100
            analytics['escalation_rate'] = (analytics['escalations_recommended'] / analytics['total_analyses']) * 100
        
        analytics.update({
            'models_loaded': {
                'sentence_transformer': self.sentence_model is not None,
                'tfidf_vectorizer': self.tfidf_vectorizer is not None,
            },
            'knowledge_base': {
                'problems_analyzed': len(self.problem_history),
                'solution_templates': len(self.solution_templates),
                'problem_clusters': len(self.problem_clusters),
            },
            'features_enabled': {
                'clustering': self.enable_clustering,
                'solution_matching': self.enable_solution_matching,
            }
        })
        
        return analytics