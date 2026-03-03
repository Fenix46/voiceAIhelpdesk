"""Advanced prompt management system with templates, optimization, and A/B testing."""

import asyncio
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import re
import random

from loguru import logger

from voicehelpdeskai.config.manager import get_config_manager


class PromptType(Enum):
    """Types of prompts."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TEMPLATE = "template"


class TaskType(Enum):
    """Task types for prompts."""
    HELPDESK_GENERAL = "helpdesk_general"
    TICKET_CLASSIFICATION = "ticket_classification"
    SOLUTION_GENERATION = "solution_generation"
    ESCALATION_DECISION = "escalation_decision"
    KNOWLEDGE_SEARCH = "knowledge_search"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    INTENT_EXTRACTION = "intent_extraction"
    ENTITY_EXTRACTION = "entity_extraction"
    CONVERSATION_SUMMARY = "conversation_summary"
    TROUBLESHOOTING = "troubleshooting"


@dataclass
class PromptVariable:
    """Variable definition for prompt templates."""
    name: str
    description: str
    type: str = "string"  # string, int, float, bool, list, dict
    required: bool = True
    default_value: Any = None
    validation_pattern: Optional[str] = None
    examples: List[Any] = field(default_factory=list)


@dataclass
class FewShotExample:
    """Few-shot learning example."""
    input: str
    output: str
    explanation: Optional[str] = None
    category: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptTemplate:
    """Prompt template with variables and examples."""
    id: str
    name: str
    task_type: TaskType
    prompt_type: PromptType
    template: str
    variables: List[PromptVariable] = field(default_factory=list)
    few_shot_examples: List[FewShotExample] = field(default_factory=list)
    description: str = ""
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    model_optimizations: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    active: bool = True


@dataclass
class PromptVersion:
    """Version information for prompt templates."""
    template_id: str
    version: str
    template: str
    changes: str
    created_at: datetime = field(default_factory=datetime.now)
    performance_data: Dict[str, Any] = field(default_factory=dict)
    is_rollback: bool = False


@dataclass
class ABTestConfig:
    """A/B testing configuration."""
    test_id: str
    template_a: str  # Template ID
    template_b: str  # Template ID
    traffic_split: float = 0.5  # Percentage for template A
    success_metric: str = "user_satisfaction"
    min_samples: int = 100
    confidence_level: float = 0.95
    start_date: datetime = field(default_factory=datetime.now)
    end_date: Optional[datetime] = None
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ABTestResult:
    """A/B testing result."""
    test_id: str
    template_a_performance: Dict[str, float]
    template_b_performance: Dict[str, float]
    winner: Optional[str] = None
    confidence: float = 0.0
    samples_a: int = 0
    samples_b: int = 0
    statistical_significance: bool = False
    recommendation: str = ""
    created_at: datetime = field(default_factory=datetime.now)


class PromptManager:
    """Advanced prompt management system."""
    
    def __init__(self,
                 templates_dir: Optional[Path] = None,
                 enable_ab_testing: bool = True,
                 enable_performance_tracking: bool = True,
                 auto_optimization: bool = True):
        """Initialize prompt manager.
        
        Args:
            templates_dir: Directory for storing prompt templates
            enable_ab_testing: Enable A/B testing functionality
            enable_performance_tracking: Enable performance metrics tracking
            auto_optimization: Enable automatic prompt optimization
        """
        self.config = get_config_manager().get_config()
        self.templates_dir = templates_dir or Path("./prompts")
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        self.enable_ab_testing = enable_ab_testing
        self.enable_performance_tracking = enable_performance_tracking
        self.auto_optimization = auto_optimization
        
        # Storage
        self.templates: Dict[str, PromptTemplate] = {}
        self.versions: Dict[str, List[PromptVersion]] = {}
        self.ab_tests: Dict[str, ABTestConfig] = {}
        self.ab_results: Dict[str, ABTestResult] = {}
        
        # Performance tracking
        self.usage_stats: Dict[str, Dict[str, Any]] = {}
        self.optimization_history: List[Dict[str, Any]] = []
        
        # Italian helpdesk specific templates
        self._initialize_default_templates()
        
        logger.info("PromptManager initialized with Italian helpdesk templates")
    
    def _initialize_default_templates(self):
        """Initialize default Italian helpdesk templates."""
        
        # General helpdesk assistant template
        helpdesk_template = PromptTemplate(
            id="helpdesk_general_v1",
            name="Assistente Help Desk Generale",
            task_type=TaskType.HELPDESK_GENERAL,
            prompt_type=PromptType.SYSTEM,
            template="""Sei un assistente AI specializzato nell'help desk IT per aziende italiane.

CARATTERISTICHE DEL TUO COMPORTAMENTO:
- Rispondi sempre in italiano professionale ma cordiale
- Mantieni un tono paziente e comprensivo
- Fornisci soluzioni pratiche e step-by-step
- Richiedi chiarimenti quando necessario
- Suggerisci escalation per problemi complessi

INFORMAZIONI CONTESTUALI:
{context}

COMPETENZE PRINCIPALI:
- Risoluzione problemi hardware e software
- Configurazione reti e connettività
- Gestione account utente e permessi
- Supporto applicazioni aziendali
- Sicurezza informatica base

ISTRUZIONI SPECIFICHE:
{specific_instructions}

Ricorda: se non sei sicuro della soluzione, è meglio escalare il problema piuttosto che fornire informazioni incorrette.""",
            variables=[
                PromptVariable(
                    name="context",
                    description="Contesto della conversazione o informazioni aggiuntive",
                    required=False,
                    default_value=""
                ),
                PromptVariable(
                    name="specific_instructions",
                    description="Istruzioni specifiche per questo caso",
                    required=False,
                    default_value=""
                )
            ],
            tags=["helpdesk", "general", "italian"],
            model_optimizations={
                "max_tokens": 1024,
                "temperature": 0.7,
                "top_p": 0.9
            }
        )
        
        # Ticket classification template
        classification_template = PromptTemplate(
            id="ticket_classification_v1",
            name="Classificazione Ticket",
            task_type=TaskType.TICKET_CLASSIFICATION,
            prompt_type=PromptType.USER,
            template="""Analizza la seguente richiesta di supporto e fornisci:

RICHIESTA UTENTE:
{user_request}

CLASSIFICAZIONE RICHIESTA:
1. CATEGORIA: [HARDWARE|SOFTWARE|NETWORK|EMAIL|ACCOUNT|TELEFONIA|SECURITY|OTHER]
2. PRIORITÀ: [BASSA|MEDIA|ALTA|CRITICA]
3. URGENZA: [BASSA|MEDIA|ALTA|CRITICA]
4. COMPLESSITÀ: [SEMPLICE|MEDIA|COMPLESSA]
5. TEMPO STIMATO: [minuti]
6. SKILLS RICHIESTE: [lista competenze necessarie]

GIUSTIFICAZIONE:
Spiega brevemente la classificazione scelta.

PROSSIMI PASSI SUGGERITI:
- Lista delle azioni immediate da intraprendere""",
            variables=[
                PromptVariable(
                    name="user_request",
                    description="Testo della richiesta dell'utente",
                    required=True,
                    examples=["Il computer non si accende", "Non riesco ad accedere alla email"]
                )
            ],
            few_shot_examples=[
                FewShotExample(
                    input="Il mio computer si spegne da solo",
                    output="""CATEGORIA: HARDWARE
PRIORITÀ: MEDIA
URGENZA: MEDIA
COMPLESSITÀ: MEDIA
TEMPO STIMATO: 30 minuti
SKILLS RICHIESTE: [diagnostica hardware, troubleshooting]

GIUSTIFICAZIONE: Problema hardware che potrebbe indicare surriscaldamento, alimentatore difettoso o problemi di memoria.

PROSSIMI PASSI SUGGERITI:
- Verificare temperatura sistema
- Controllare log eventi Windows
- Test memoria RAM
- Verifica alimentatore""",
                    category="hardware"
                )
            ],
            tags=["classification", "ticket", "triage"]
        )
        
        # Solution generation template
        solution_template = PromptTemplate(
            id="solution_generation_v1",
            name="Generazione Soluzioni",
            task_type=TaskType.SOLUTION_GENERATION,
            prompt_type=PromptType.USER,
            template="""Fornisci una soluzione dettagliata per il seguente problema IT:

PROBLEMA:
{problem_description}

CATEGORIA: {category}
PRIORITÀ: {priority}

INFORMAZIONI AGGIUNTIVE:
- Sistema operativo: {os}
- Software coinvolto: {software}
- Dettagli hardware: {hardware}
- Contesto utente: {user_context}

STRUTTURA LA RISPOSTA COSÌ:

🔍 DIAGNOSI:
Analisi del problema e possibili cause

⚡ SOLUZIONE IMMEDIATA:
Passi da seguire subito (numerati)

✅ VERIFICA:
Come controllare che il problema sia risolto

🛡️ PREVENZIONE:
Come evitare il problema in futuro

📞 ESCALATION:
Quando e come escalare se la soluzione non funziona

⚠️ NOTE IMPORTANTI:
Avvertenze e precauzioni""",
            variables=[
                PromptVariable(
                    name="problem_description",
                    description="Descrizione dettagliata del problema",
                    required=True
                ),
                PromptVariable(
                    name="category",
                    description="Categoria del problema",
                    required=True,
                    examples=["HARDWARE", "SOFTWARE", "NETWORK"]
                ),
                PromptVariable(
                    name="priority",
                    description="Priorità del problema",
                    required=True,
                    examples=["BASSA", "MEDIA", "ALTA", "CRITICA"]
                ),
                PromptVariable(
                    name="os",
                    description="Sistema operativo",
                    required=False,
                    default_value="Non specificato"
                ),
                PromptVariable(
                    name="software",
                    description="Software coinvolto",
                    required=False,
                    default_value="Non specificato"
                ),
                PromptVariable(
                    name="hardware",
                    description="Hardware coinvolto",
                    required=False,
                    default_value="Non specificato"
                ),
                PromptVariable(
                    name="user_context",
                    description="Contesto dell'utente (ruolo, competenze)",
                    required=False,
                    default_value="Utente standard"
                )
            ],
            tags=["solution", "troubleshooting", "detailed"]
        )
        
        # Add templates to manager
        self.add_template(helpdesk_template)
        self.add_template(classification_template)
        self.add_template(solution_template)
        
        # Load existing templates from disk
        self._load_templates_from_disk()
    
    def add_template(self, template: PromptTemplate) -> str:
        """Add new prompt template.
        
        Args:
            template: PromptTemplate to add
            
        Returns:
            Template ID
        """
        if not template.id:
            template.id = str(uuid.uuid4())
        
        template.updated_at = datetime.now()
        self.templates[template.id] = template
        
        # Initialize version history
        if template.id not in self.versions:
            self.versions[template.id] = []
        
        # Save to disk
        self._save_template_to_disk(template)
        
        logger.info(f"Added prompt template: {template.name} ({template.id})")
        return template.id
    
    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get template by ID."""
        return self.templates.get(template_id)
    
    def get_templates_by_task(self, task_type: TaskType) -> List[PromptTemplate]:
        """Get all templates for a specific task type."""
        return [
            template for template in self.templates.values()
            if template.task_type == task_type and template.active
        ]
    
    def get_templates_by_tag(self, tag: str) -> List[PromptTemplate]:
        """Get templates by tag."""
        return [
            template for template in self.templates.values()
            if tag in template.tags and template.active
        ]
    
    def render_template(self, 
                       template_id: str, 
                       variables: Dict[str, Any],
                       include_examples: bool = False,
                       example_count: int = 3) -> str:
        """Render template with variables and optional examples.
        
        Args:
            template_id: ID of template to render
            variables: Variable values for template
            include_examples: Whether to include few-shot examples
            example_count: Number of examples to include
            
        Returns:
            Rendered prompt
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Validate and prepare variables
        prepared_vars = self._prepare_variables(template, variables)
        
        # Render base template
        rendered = template.template.format(**prepared_vars)
        
        # Add few-shot examples if requested
        if include_examples and template.few_shot_examples:
            examples_text = self._render_examples(
                template.few_shot_examples[:example_count]
            )
            rendered = f"{examples_text}\n\n{rendered}"
        
        # Track usage
        if self.enable_performance_tracking:
            self._track_template_usage(template_id)
        
        return rendered
    
    def _prepare_variables(self, 
                         template: PromptTemplate, 
                         variables: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare and validate variables for template rendering."""
        prepared = {}
        
        for var in template.variables:
            if var.name in variables:
                value = variables[var.name]
                
                # Type validation
                if var.type == "int" and not isinstance(value, int):
                    try:
                        value = int(value)
                    except ValueError:
                        raise ValueError(f"Variable {var.name} must be an integer")
                elif var.type == "float" and not isinstance(value, (int, float)):
                    try:
                        value = float(value)
                    except ValueError:
                        raise ValueError(f"Variable {var.name} must be a number")
                elif var.type == "bool" and not isinstance(value, bool):
                    value = bool(value)
                
                # Pattern validation
                if var.validation_pattern and isinstance(value, str):
                    if not re.match(var.validation_pattern, value):
                        raise ValueError(f"Variable {var.name} doesn't match required pattern")
                
                prepared[var.name] = value
                
            elif var.required:
                if var.default_value is not None:
                    prepared[var.name] = var.default_value
                else:
                    raise ValueError(f"Required variable missing: {var.name}")
            else:
                prepared[var.name] = var.default_value or ""
        
        return prepared
    
    def _render_examples(self, examples: List[FewShotExample]) -> str:
        """Render few-shot examples."""
        if not examples:
            return ""
        
        examples_text = "ESEMPI:\n\n"
        
        for i, example in enumerate(examples, 1):
            examples_text += f"Esempio {i}:\n"
            examples_text += f"Input: {example.input}\n"
            examples_text += f"Output: {example.output}\n"
            
            if example.explanation:
                examples_text += f"Spiegazione: {example.explanation}\n"
            
            examples_text += "\n"
        
        return examples_text
    
    def optimize_prompt_for_model(self, 
                                template_id: str, 
                                model_name: str,
                                performance_data: Optional[Dict[str, float]] = None) -> str:
        """Optimize prompt template for specific model.
        
        Args:
            template_id: Template to optimize
            model_name: Target model name
            performance_data: Optional performance metrics
            
        Returns:
            Optimized template ID
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Create optimized version
        optimized_template = PromptTemplate(
            id=f"{template_id}_opt_{model_name}",
            name=f"{template.name} (Ottimizzato per {model_name})",
            task_type=template.task_type,
            prompt_type=template.prompt_type,
            template=self._apply_model_optimizations(template.template, model_name),
            variables=template.variables.copy(),
            few_shot_examples=template.few_shot_examples.copy(),
            description=f"Versione ottimizzata per {model_name}",
            version=f"{template.version}_opt",
            tags=template.tags + [f"optimized_{model_name}"],
            model_optimizations=self._get_model_optimizations(model_name)
        )
        
        # Add performance data if provided
        if performance_data:
            optimized_template.performance_metrics = performance_data
        
        # Add optimized template
        self.add_template(optimized_template)
        
        # Log optimization
        self.optimization_history.append({
            'original_template': template_id,
            'optimized_template': optimized_template.id,
            'model': model_name,
            'timestamp': datetime.now(),
            'performance_data': performance_data
        })
        
        logger.info(f"Created optimized template for {model_name}: {optimized_template.id}")
        return optimized_template.id
    
    def _apply_model_optimizations(self, template: str, model_name: str) -> str:
        """Apply model-specific optimizations to template."""
        optimized = template
        
        if "mistral" in model_name.lower():
            # Mistral optimizations
            optimized = optimized.replace("Sei un assistente", "Sei un assistente AI specializzato")
            optimized = f"<s>[INST] {optimized} [/INST]"
            
        elif "llama" in model_name.lower():
            # Llama optimizations
            optimized = f"### Instruction:\n{optimized}\n\n### Response:"
            
        elif "gpt" in model_name.lower():
            # GPT optimizations - add structured thinking
            optimized = f"Think step by step.\n\n{optimized}"
        
        return optimized
    
    def _get_model_optimizations(self, model_name: str) -> Dict[str, Any]:
        """Get optimization parameters for specific model."""
        optimizations = {
            "mistral": {
                "max_tokens": 1024,
                "temperature": 0.7,
                "top_p": 0.9,
                "repetition_penalty": 1.1
            },
            "llama": {
                "max_tokens": 2048,
                "temperature": 0.8,
                "top_p": 0.95,
                "top_k": 40
            },
            "gpt": {
                "max_tokens": 1500,
                "temperature": 0.7,
                "top_p": 1.0
            }
        }
        
        for key, config in optimizations.items():
            if key in model_name.lower():
                return config
        
        # Default optimizations
        return {
            "max_tokens": 1024,
            "temperature": 0.7,
            "top_p": 0.9
        }
    
    def create_ab_test(self, 
                      template_a_id: str, 
                      template_b_id: str,
                      test_name: str,
                      traffic_split: float = 0.5,
                      success_metric: str = "user_satisfaction",
                      duration_days: int = 30) -> str:
        """Create A/B test between two templates.
        
        Args:
            template_a_id: First template ID
            template_b_id: Second template ID  
            test_name: Name for the test
            traffic_split: Traffic percentage for template A (0.0-1.0)
            success_metric: Metric to optimize for
            duration_days: Test duration in days
            
        Returns:
            Test ID
        """
        if not self.enable_ab_testing:
            raise RuntimeError("A/B testing not enabled")
        
        # Validate templates exist
        if not (self.get_template(template_a_id) and self.get_template(template_b_id)):
            raise ValueError("One or both templates not found")
        
        test_id = str(uuid.uuid4())
        end_date = datetime.now() + timedelta(days=duration_days)
        
        test_config = ABTestConfig(
            test_id=test_id,
            template_a=template_a_id,
            template_b=template_b_id,
            traffic_split=traffic_split,
            success_metric=success_metric,
            end_date=end_date,
            metadata={'test_name': test_name}
        )
        
        self.ab_tests[test_id] = test_config
        
        logger.info(f"Created A/B test: {test_name} ({test_id})")
        return test_id
    
    def get_template_for_ab_test(self, test_id: str, user_id: str) -> str:
        """Get template ID for user in A/B test.
        
        Args:
            test_id: A/B test ID
            user_id: User identifier for consistent assignment
            
        Returns:
            Template ID to use
        """
        test = self.ab_tests.get(test_id)
        if not test or not test.active:
            raise ValueError(f"A/B test not found or inactive: {test_id}")
        
        # Check if test has ended
        if test.end_date and datetime.now() > test.end_date:
            test.active = False
            raise ValueError(f"A/B test has ended: {test_id}")
        
        # Deterministic assignment based on user ID hash
        user_hash = hashlib.md5(f"{test_id}_{user_id}".encode()).hexdigest()
        hash_value = int(user_hash[:8], 16) / 0xffffffff  # Normalize to 0-1
        
        if hash_value < test.traffic_split:
            return test.template_a
        else:
            return test.template_b
    
    def record_ab_test_result(self, 
                            test_id: str, 
                            template_id: str, 
                            metric_value: float,
                            user_id: str,
                            metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record result for A/B test.
        
        Args:
            test_id: A/B test ID
            template_id: Template that was used
            metric_value: Success metric value
            user_id: User identifier
            metadata: Optional additional data
        """
        test = self.ab_tests.get(test_id)
        if not test:
            logger.warning(f"A/B test not found: {test_id}")
            return
        
        # Initialize results if needed
        if test_id not in self.ab_results:
            self.ab_results[test_id] = ABTestResult(
                test_id=test_id,
                template_a_performance={},
                template_b_performance={}
            )
        
        result = self.ab_results[test_id]
        
        # Record result
        if template_id == test.template_a:
            self._update_performance_metrics(result.template_a_performance, metric_value)
            result.samples_a += 1
        elif template_id == test.template_b:
            self._update_performance_metrics(result.template_b_performance, metric_value)
            result.samples_b += 1
        
        # Check if we have enough samples for analysis
        if (result.samples_a >= test.min_samples and 
            result.samples_b >= test.min_samples):
            self._analyze_ab_test_results(test_id)
    
    def _update_performance_metrics(self, metrics: Dict[str, float], value: float):
        """Update performance metrics with new value."""
        if 'sum' not in metrics:
            metrics['sum'] = 0
            metrics['count'] = 0
            metrics['min'] = float('inf')
            metrics['max'] = float('-inf')
        
        metrics['sum'] += value
        metrics['count'] += 1
        metrics['mean'] = metrics['sum'] / metrics['count']
        metrics['min'] = min(metrics['min'], value)
        metrics['max'] = max(metrics['max'], value)
    
    def _analyze_ab_test_results(self, test_id: str) -> None:
        """Analyze A/B test results for statistical significance."""
        test = self.ab_tests[test_id]
        result = self.ab_results[test_id]
        
        # Simple statistical analysis (can be enhanced with proper tests)
        mean_a = result.template_a_performance.get('mean', 0)
        mean_b = result.template_b_performance.get('mean', 0)
        
        improvement = ((mean_b - mean_a) / mean_a * 100) if mean_a > 0 else 0
        
        # Determine winner (simplified)
        if abs(improvement) > 5 and min(result.samples_a, result.samples_b) >= test.min_samples:
            result.statistical_significance = True
            result.winner = test.template_b if improvement > 0 else test.template_a
            result.confidence = 0.95  # Simplified
            
            if improvement > 0:
                result.recommendation = f"Template B performs {improvement:.1f}% better"
            else:
                result.recommendation = f"Template A performs {abs(improvement):.1f}% better"
        else:
            result.recommendation = "No significant difference found"
        
        logger.info(f"A/B test analysis updated for {test_id}: {result.recommendation}")
    
    def version_template(self, template_id: str, changes: str) -> str:
        """Create new version of template.
        
        Args:
            template_id: Template to version
            changes: Description of changes
            
        Returns:
            New version string
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Create version entry
        current_versions = self.versions.get(template_id, [])
        version_number = len(current_versions) + 1
        new_version = f"{template.version.split('.')[0]}.{version_number}.0"
        
        version_entry = PromptVersion(
            template_id=template_id,
            version=new_version,
            template=template.template,
            changes=changes
        )
        
        if template_id not in self.versions:
            self.versions[template_id] = []
        
        self.versions[template_id].append(version_entry)
        
        # Update template version
        template.version = new_version
        template.updated_at = datetime.now()
        
        logger.info(f"Created version {new_version} for template {template_id}")
        return new_version
    
    def rollback_template(self, template_id: str, target_version: str) -> bool:
        """Rollback template to previous version.
        
        Args:
            template_id: Template to rollback
            target_version: Version to rollback to
            
        Returns:
            True if successful
        """
        template = self.get_template(template_id)
        if not template:
            return False
        
        # Find target version
        versions = self.versions.get(template_id, [])
        target_version_data = None
        
        for version in versions:
            if version.version == target_version:
                target_version_data = version
                break
        
        if not target_version_data:
            logger.error(f"Version {target_version} not found for template {template_id}")
            return False
        
        # Create rollback version entry
        rollback_version = PromptVersion(
            template_id=template_id,
            version=f"{template.version}_rollback",
            template=template.template,
            changes=f"Rollback to version {target_version}",
            is_rollback=True
        )
        
        self.versions[template_id].append(rollback_version)
        
        # Restore template content
        template.template = target_version_data.template
        template.version = f"{target_version}_restored"
        template.updated_at = datetime.now()
        
        logger.info(f"Rolled back template {template_id} to version {target_version}")
        return True
    
    def _track_template_usage(self, template_id: str):
        """Track template usage for analytics."""
        if template_id not in self.usage_stats:
            self.usage_stats[template_id] = {
                'usage_count': 0,
                'first_used': datetime.now(),
                'last_used': datetime.now(),
                'daily_usage': {}
            }
        
        stats = self.usage_stats[template_id]
        stats['usage_count'] += 1
        stats['last_used'] = datetime.now()
        
        # Track daily usage
        today = datetime.now().date().isoformat()
        if today not in stats['daily_usage']:
            stats['daily_usage'][today] = 0
        stats['daily_usage'][today] += 1
    
    def _save_template_to_disk(self, template: PromptTemplate):
        """Save template to disk."""
        try:
            template_file = self.templates_dir / f"{template.id}.json"
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(template), f, indent=2, default=str, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save template to disk: {e}")
    
    def _load_templates_from_disk(self):
        """Load templates from disk."""
        try:
            for template_file in self.templates_dir.glob("*.json"):
                with open(template_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Convert back to objects
                template = PromptTemplate(**data)
                self.templates[template.id] = template
                
        except Exception as e:
            logger.error(f"Failed to load templates from disk: {e}")
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get prompt management analytics."""
        return {
            'total_templates': len(self.templates),
            'active_templates': sum(1 for t in self.templates.values() if t.active),
            'templates_by_task': {
                task.value: len(self.get_templates_by_task(task))
                for task in TaskType
            },
            'active_ab_tests': len([t for t in self.ab_tests.values() if t.active]),
            'completed_ab_tests': len([t for t in self.ab_tests.values() if not t.active]),
            'optimization_history_count': len(self.optimization_history),
            'most_used_templates': sorted(
                [(tid, stats['usage_count']) for tid, stats in self.usage_stats.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }