"""Advanced Dialogue State Tracking for IT helpdesk with flow management and context understanding."""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from datetime import datetime, timedelta

from loguru import logger

from .intent_classifier import IntentClassifier, IntentPrediction, IntentType, ITCategory, UrgencyLevel
from .entity_extractor import EntityExtractor, ExtractedEntity, EntityType
from .problem_analyzer import ProblemAnalyzer, ProblemAnalysis, ProblemSeverity
from voicehelpdeskai.config.manager import get_config_manager


class DialogueState(Enum):
    """Dialogue states in IT helpdesk conversation."""
    INITIAL = "initial"                    # Start of conversation
    PROBLEM_IDENTIFICATION = "problem_identification"  # Understanding the problem
    INFORMATION_GATHERING = "information_gathering"    # Collecting details
    SOLUTION_PRESENTATION = "solution_presentation"    # Presenting solutions
    SOLUTION_EXECUTION = "solution_execution"          # Guiding through solution
    VERIFICATION = "verification"                       # Verifying resolution
    ESCALATION = "escalation"                          # Escalating issue
    CLOSURE = "closure"                                # Closing conversation
    FOLLOW_UP = "follow_up"                           # Post-resolution follow-up


class DialogueAction(Enum):
    """Actions that can be taken in dialogue."""
    ASK_FOR_DETAILS = "ask_for_details"
    REQUEST_SCREENSHOT = "request_screenshot"
    PROVIDE_SOLUTION = "provide_solution"
    ASK_FOR_CONFIRMATION = "ask_for_confirmation"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    SCHEDULE_FOLLOW_UP = "schedule_follow_up"
    CLOSE_TICKET = "close_ticket"
    REQUEST_FEEDBACK = "request_feedback"
    CLARIFY_PROBLEM = "clarify_problem"
    GATHER_SYSTEM_INFO = "gather_system_info"


class ContextSlot(Enum):
    """Context slots for tracking information."""
    USER_NAME = "user_name"
    USER_ID = "user_id"
    DEPARTMENT = "department"
    PROBLEM_CATEGORY = "problem_category"
    AFFECTED_SYSTEM = "affected_system"
    ERROR_MESSAGE = "error_message"
    URGENCY = "urgency"
    WHEN_OCCURRED = "when_occurred"
    STEPS_ATTEMPTED = "steps_attempted"
    SIMILAR_ISSUES = "similar_issues"
    CURRENT_SOLUTION = "current_solution"
    SATISFACTION_LEVEL = "satisfaction_level"


@dataclass
class SlotValue:
    """Value stored in a context slot."""
    value: Any
    confidence: float
    source: str  # 'user', 'extracted', 'inferred'
    timestamp: datetime = field(default_factory=datetime.now)
    confirmed: bool = False


@dataclass
class DialogueTurn:
    """Single turn in dialogue."""
    turn_id: str
    user_input: str
    intent: IntentPrediction
    entities: List[ExtractedEntity]
    state_before: DialogueState
    state_after: DialogueState
    action_taken: DialogueAction
    system_response: str
    context_updates: Dict[str, SlotValue] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0


@dataclass
class DialogueContext:
    """Complete dialogue context."""
    conversation_id: str
    user_id: str
    session_id: str
    current_state: DialogueState
    context_slots: Dict[ContextSlot, SlotValue] = field(default_factory=dict)
    dialogue_history: List[DialogueTurn] = field(default_factory=list)
    problem_analysis: Optional[ProblemAnalysis] = None
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DialoguePolicy:
    """Policy for dialogue state transitions."""
    from_state: DialogueState
    conditions: Dict[str, Any]  # Conditions to match
    to_state: DialogueState
    action: DialogueAction
    priority: int = 0  # Higher priority policies are checked first
    requirements: List[ContextSlot] = field(default_factory=list)  # Required context slots


class DialogueStateTracker:
    """Advanced dialogue state tracker with policy-based transitions."""
    
    def __init__(self,
                 context_timeout: int = 3600,  # 1 hour
                 max_turns_per_state: int = 5,
                 enable_proactive_suggestions: bool = True,
                 enable_context_inference: bool = True):
        """Initialize dialogue state tracker.
        
        Args:
            context_timeout: Context timeout in seconds
            max_turns_per_state: Maximum turns allowed in same state
            enable_proactive_suggestions: Enable proactive suggestions
            enable_context_inference: Enable context inference from dialogue
        """
        self.config = get_config_manager().get_config()
        self.context_timeout = context_timeout
        self.max_turns_per_state = max_turns_per_state
        self.enable_proactive_suggestions = enable_proactive_suggestions
        self.enable_context_inference = enable_context_inference
        
        # Dependencies
        self.intent_classifier = None
        self.entity_extractor = None
        self.problem_analyzer = None
        
        # Active dialogues
        self.active_dialogues: Dict[str, DialogueContext] = {}
        
        # Dialogue policies
        self.dialogue_policies: List[DialoguePolicy] = []
        self._initialize_dialogue_policies()
        
        # Response templates
        self.response_templates = self._initialize_response_templates()
        
        # Context inference patterns
        self.inference_patterns = self._initialize_inference_patterns()
        
        # Performance tracking
        self.stats = {
            'total_conversations': 0,
            'completed_conversations': 0,
            'escalated_conversations': 0,
            'average_turns_per_conversation': 0.0,
            'average_resolution_time': 0.0,
            'state_transitions': {},
            'context_inference_success': 0,
            'policy_matches': 0,
        }
        
        logger.info("DialogueStateTracker initialized")
    
    async def initialize(self) -> None:
        """Initialize dependencies."""
        try:
            # Initialize intent classifier
            self.intent_classifier = IntentClassifier()
            await self.intent_classifier.initialize()
            
            # Initialize entity extractor
            self.entity_extractor = EntityExtractor()
            await self.entity_extractor.initialize()
            
            # Initialize problem analyzer
            self.problem_analyzer = ProblemAnalyzer()
            await self.problem_analyzer.initialize()
            
            logger.success("DialogueStateTracker dependencies initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize DialogueStateTracker: {e}")
            raise
    
    async def start_dialogue(self,
                           user_id: str,
                           session_id: str,
                           initial_message: Optional[str] = None) -> str:
        """Start new dialogue session.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            initial_message: Optional initial message from user
            
        Returns:
            Conversation ID
        """
        conversation_id = str(uuid.uuid4())
        
        # Create new dialogue context
        context = DialogueContext(
            conversation_id=conversation_id,
            user_id=user_id,
            session_id=session_id,
            current_state=DialogueState.INITIAL
        )
        
        self.active_dialogues[conversation_id] = context
        self.stats['total_conversations'] += 1
        
        logger.info(f"Started dialogue {conversation_id} for user {user_id}")
        
        # Process initial message if provided
        if initial_message:
            await self.process_user_input(conversation_id, initial_message)
        
        return conversation_id
    
    async def process_user_input(self,
                               conversation_id: str,
                               user_input: str) -> Tuple[str, DialogueAction]:
        """Process user input and update dialogue state.
        
        Args:
            conversation_id: Conversation identifier
            user_input: User's input text
            
        Returns:
            Tuple of (system_response, action_taken)
        """
        if conversation_id not in self.active_dialogues:
            raise ValueError(f"Dialogue {conversation_id} not found")
        
        context = self.active_dialogues[conversation_id]
        context.last_activity = datetime.now()
        
        try:
            # Create turn ID
            turn_id = str(uuid.uuid4())
            
            # Classify intent and extract entities
            intent = await self.intent_classifier.classify_intent(user_input)
            entities = await self.entity_extractor.extract_entities(user_input)
            
            # Store state before processing
            state_before = context.current_state
            
            # Update context with extracted information
            await self._update_context_from_input(context, intent, entities, user_input)
            
            # Determine next state and action
            new_state, action = await self._determine_next_state_and_action(context, intent, entities)
            
            # Update dialogue state
            context.current_state = new_state
            
            # Generate system response
            system_response = await self._generate_system_response(context, action, intent, entities)
            
            # Create dialogue turn
            turn = DialogueTurn(
                turn_id=turn_id,
                user_input=user_input,
                intent=intent,
                entities=entities,
                state_before=state_before,
                state_after=new_state,
                action_taken=action,
                system_response=system_response,
                confidence=intent.confidence
            )
            
            context.dialogue_history.append(turn)
            
            # Update statistics
            self._update_transition_stats(state_before, new_state)
            
            logger.debug(f"Processed input for {conversation_id}: {state_before.value} -> {new_state.value}")
            
            return system_response, action
            
        except Exception as e:
            logger.error(f"Failed to process user input: {e}")
            return "Mi dispiace, ho avuto un problema nel processare la tua richiesta. Puoi riprovare?", DialogueAction.CLARIFY_PROBLEM
    
    async def _update_context_from_input(self,
                                       context: DialogueContext,
                                       intent: IntentPrediction,
                                       entities: List[ExtractedEntity],
                                       user_input: str) -> None:
        """Update dialogue context with information from user input."""
        
        # Map entities to context slots
        entity_slot_mapping = {
            EntityType.USER_ID: ContextSlot.USER_NAME,
            EntityType.EMAIL: ContextSlot.USER_ID,
            EntityType.DEPARTMENT: ContextSlot.DEPARTMENT,
            EntityType.SOFTWARE_NAME: ContextSlot.AFFECTED_SYSTEM,
            EntityType.HARDWARE_MODEL: ContextSlot.AFFECTED_SYSTEM,
            EntityType.ERROR_MESSAGE: ContextSlot.ERROR_MESSAGE,
        }
        
        # Update slots from entities
        for entity in entities:
            if entity.entity_type in entity_slot_mapping:
                slot = entity_slot_mapping[entity.entity_type]
                slot_value = SlotValue(
                    value=entity.text,
                    confidence=entity.confidence,
                    source='extracted'
                )
                context.context_slots[slot] = slot_value
        
        # Update problem category from intent
        if intent.category != ITCategory.GENERAL:
            context.context_slots[ContextSlot.PROBLEM_CATEGORY] = SlotValue(
                value=intent.category.value,
                confidence=intent.confidence,
                source='extracted'
            )
        
        # Update urgency
        if intent.urgency != UrgencyLevel.MEDIO:  # Only update if not default
            context.context_slots[ContextSlot.URGENCY] = SlotValue(
                value=intent.urgency.value,
                confidence=intent.confidence,
                source='extracted'
            )
        
        # Infer context from dialogue patterns
        if self.enable_context_inference:
            await self._infer_context_from_patterns(context, user_input, intent)
    
    async def _infer_context_from_patterns(self,
                                         context: DialogueContext,
                                         user_input: str,
                                         intent: IntentPrediction) -> None:
        """Infer context information using patterns."""
        
        import re
        text_lower = user_input.lower()
        
        # Time-related patterns
        time_patterns = {
            'stamattina': 'this morning',
            'ieri': 'yesterday',
            'oggi': 'today',
            'questa settimana': 'this week',
            'da quando': 'since when'
        }
        
        for pattern, time_ref in time_patterns.items():
            if pattern in text_lower:
                context.context_slots[ContextSlot.WHEN_OCCURRED] = SlotValue(
                    value=time_ref,
                    confidence=0.7,
                    source='inferred'
                )
                break
        
        # Attempted solutions patterns
        solution_patterns = [
            r'ho già provato (?:a |con )?(.*?)(?:\.|,|$)',
            r'ho fatto (?:già )?(.*)(?:\.|,|$)',
            r'ho tentato (?:di |con )?(.*?)(?:\.|,|$)'
        ]
        
        for pattern in solution_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                attempts = [match.strip() for match in matches if match.strip()]
                if attempts:
                    context.context_slots[ContextSlot.STEPS_ATTEMPTED] = SlotValue(
                        value=attempts,
                        confidence=0.6,
                        source='inferred'
                    )
                    self.stats['context_inference_success'] += 1
                break
    
    async def _determine_next_state_and_action(self,
                                             context: DialogueContext,
                                             intent: IntentPrediction,
                                             entities: List[ExtractedEntity]) -> Tuple[DialogueState, DialogueAction]:
        """Determine next dialogue state and action using policies."""
        
        current_state = context.current_state
        
        # Check dialogue policies in priority order
        policies = sorted(self.dialogue_policies, key=lambda p: p.priority, reverse=True)
        
        for policy in policies:
            if policy.from_state != current_state:
                continue
            
            # Check if policy conditions are met
            if await self._check_policy_conditions(context, policy, intent, entities):
                self.stats['policy_matches'] += 1
                return policy.to_state, policy.action
        
        # Default transitions if no policy matches
        default_transitions = {
            DialogueState.INITIAL: (DialogueState.PROBLEM_IDENTIFICATION, DialogueAction.ASK_FOR_DETAILS),
            DialogueState.PROBLEM_IDENTIFICATION: (DialogueState.INFORMATION_GATHERING, DialogueAction.GATHER_SYSTEM_INFO),
            DialogueState.INFORMATION_GATHERING: (DialogueState.SOLUTION_PRESENTATION, DialogueAction.PROVIDE_SOLUTION),
            DialogueState.SOLUTION_PRESENTATION: (DialogueState.SOLUTION_EXECUTION, DialogueAction.ASK_FOR_CONFIRMATION),
            DialogueState.SOLUTION_EXECUTION: (DialogueState.VERIFICATION, DialogueAction.ASK_FOR_CONFIRMATION),
            DialogueState.VERIFICATION: (DialogueState.CLOSURE, DialogueAction.CLOSE_TICKET),
        }
        
        return default_transitions.get(current_state, (current_state, DialogueAction.CLARIFY_PROBLEM))
    
    async def _check_policy_conditions(self,
                                     context: DialogueContext,
                                     policy: DialoguePolicy,
                                     intent: IntentPrediction,
                                     entities: List[ExtractedEntity]) -> bool:
        """Check if policy conditions are satisfied."""
        
        conditions = policy.conditions
        
        # Check intent-based conditions
        if 'intent_type' in conditions:
            if intent.intent.value not in conditions['intent_type']:
                return False
        
        if 'intent_confidence' in conditions:
            if intent.confidence < conditions['intent_confidence']:
                return False
        
        if 'urgency_level' in conditions:
            if intent.urgency.value not in conditions['urgency_level']:
                return False
        
        # Check entity-based conditions
        if 'required_entities' in conditions:
            entity_types = [e.entity_type.value for e in entities]
            if not all(req_type in entity_types for req_type in conditions['required_entities']):
                return False
        
        # Check context slot conditions
        if 'required_slots' in conditions:
            for slot_name in conditions['required_slots']:
                slot = ContextSlot(slot_name)
                if slot not in context.context_slots:
                    return False
        
        # Check turn count in current state
        if 'max_turns_in_state' in conditions:
            turns_in_state = sum(1 for turn in context.dialogue_history 
                               if turn.state_after == context.current_state)
            if turns_in_state >= conditions['max_turns_in_state']:
                return True  # Force transition
        
        # Check if problem analysis is available
        if 'requires_problem_analysis' in conditions:
            if conditions['requires_problem_analysis'] and not context.problem_analysis:
                return False
        
        return True
    
    async def _generate_system_response(self,
                                      context: DialogueContext,
                                      action: DialogueAction,
                                      intent: IntentPrediction,
                                      entities: List[ExtractedEntity]) -> str:
        """Generate system response based on action and context."""
        
        # Get response template for action
        templates = self.response_templates.get(action, ["Mi dispiace, non ho una risposta pronta per questa situazione."])
        
        # Select appropriate template based on context
        template = templates[0]  # Simplified selection
        
        # Fill template with context information
        response = template
        
        # Replace placeholders with context values
        replacements = {
            '{user_name}': self._get_slot_value(context, ContextSlot.USER_NAME, "utente"),
            '{problem_category}': self._get_slot_value(context, ContextSlot.PROBLEM_CATEGORY, "generale"),
            '{affected_system}': self._get_slot_value(context, ContextSlot.AFFECTED_SYSTEM, "sistema"),
            '{urgency}': self._get_slot_value(context, ContextSlot.URGENCY, "normale"),
        }
        
        for placeholder, value in replacements.items():
            response = response.replace(placeholder, str(value))
        
        # Add proactive suggestions if enabled
        if self.enable_proactive_suggestions and action in [DialogueAction.ASK_FOR_DETAILS, DialogueAction.PROVIDE_SOLUTION]:
            suggestion = await self._generate_proactive_suggestion(context, intent, entities)
            if suggestion:
                response += f" \\n\\n{suggestion}"
        
        return response
    
    def _get_slot_value(self, context: DialogueContext, slot: ContextSlot, default: str = "") -> str:
        """Get value from context slot with fallback."""
        if slot in context.context_slots:
            return str(context.context_slots[slot].value)
        return default
    
    async def _generate_proactive_suggestion(self,
                                           context: DialogueContext,
                                           intent: IntentPrediction,
                                           entities: List[ExtractedEntity]) -> Optional[str]:
        """Generate proactive suggestions based on context."""
        
        suggestions = []
        
        # Suggest based on problem category
        if intent.category == ITCategory.SOFTWARE:
            suggestions.append("💡 Suggerimento: Potresti provare a riavviare l'applicazione se non l'hai già fatto.")
        elif intent.category == ITCategory.HARDWARE:
            suggestions.append("💡 Suggerimento: Controlla che tutti i cavi siano collegati correttamente.")
        elif intent.category == ITCategory.NETWORK:
            suggestions.append("💡 Suggerimento: Prova a disconnetterti e riconnetterti alla rete.")
        
        # Suggest based on urgency
        if intent.urgency == UrgencyLevel.CRITICO:
            suggestions.append("⚠️ Vista l'urgenza, posso anche metterti in contatto direttamente con un tecnico specializzato.")
        
        # Suggest based on missing information
        if ContextSlot.ERROR_MESSAGE not in context.context_slots:
            suggestions.append("📋 Se hai un messaggio di errore specifico, condividilo con me per un supporto più preciso.")
        
        return suggestions[0] if suggestions else None
    
    def _initialize_dialogue_policies(self) -> None:
        """Initialize dialogue transition policies."""
        
        policies = [
            # High priority: Escalation policies
            DialoguePolicy(
                from_state=DialogueState.PROBLEM_IDENTIFICATION,
                conditions={'urgency_level': ['critico'], 'intent_confidence': 0.8},
                to_state=DialogueState.ESCALATION,
                action=DialogueAction.ESCALATE_TO_HUMAN,
                priority=10
            ),
            
            # Escalate if stuck in same state too long
            DialoguePolicy(
                from_state=DialogueState.INFORMATION_GATHERING,
                conditions={'max_turns_in_state': 3},
                to_state=DialogueState.ESCALATION,
                action=DialogueAction.ESCALATE_TO_HUMAN,
                priority=9
            ),
            
            # Solution presentation when enough info collected
            DialoguePolicy(
                from_state=DialogueState.INFORMATION_GATHERING,
                conditions={'required_slots': ['problem_category', 'affected_system']},
                to_state=DialogueState.SOLUTION_PRESENTATION,
                action=DialogueAction.PROVIDE_SOLUTION,
                priority=7
            ),
            
            # Move to verification after solution attempt
            DialoguePolicy(
                from_state=DialogueState.SOLUTION_EXECUTION,
                conditions={'intent_type': ['problem_report', 'follow_up']},
                to_state=DialogueState.VERIFICATION,
                action=DialogueAction.ASK_FOR_CONFIRMATION,
                priority=6
            ),
            
            # Close ticket on positive confirmation
            DialoguePolicy(
                from_state=DialogueState.VERIFICATION,
                conditions={'intent_type': ['closure'], 'intent_confidence': 0.7},
                to_state=DialogueState.CLOSURE,
                action=DialogueAction.CLOSE_TICKET,
                priority=8
            ),
            
            # Follow-up scheduling
            DialoguePolicy(
                from_state=DialogueState.CLOSURE,
                conditions={'intent_type': ['follow_up']},
                to_state=DialogueState.FOLLOW_UP,
                action=DialogueAction.SCHEDULE_FOLLOW_UP,
                priority=5
            ),
        ]
        
        self.dialogue_policies = policies
    
    def _initialize_response_templates(self) -> Dict[DialogueAction, List[str]]:
        """Initialize response templates for different actions."""
        
        return {
            DialogueAction.ASK_FOR_DETAILS: [
                "Ciao {user_name}! Vedo che hai un problema con {problem_category}. Puoi darmi più dettagli su cosa sta succedendo?",
                "Ciao! Sono qui per aiutarti. Puoi descrivermi il problema che stai riscontrando?",
                "Salve! Dimmi pure quale difficoltà stai incontrando, ti aiuto volentieri."
            ],
            
            DialogueAction.GATHER_SYSTEM_INFO: [
                "Per aiutarti meglio con {affected_system}, puoi dirmi:\\n- Che sistema operativo stai usando?\\n- Quando è iniziato il problema?\\n- Hai fatto delle modifiche recenti?",
                "Ho bisogno di qualche informazione in più:\\n- Su che dispositivo si presenta il problema?\\n- È la prima volta che succede?\\n- Hai provato a riavviare?",
                "Per identificare meglio il problema, mi serve sapere:\\n- Che versione del software stai usando?\\n- Il problema è costante o intermittente?"
            ],
            
            DialogueAction.PROVIDE_SOLUTION: [
                "Basandomi sui dettagli che mi hai dato, ti suggerisco questi passaggi per risolvere il problema con {affected_system}:",
                "Ho identificato una possibile soluzione per il tuo problema. Ecco cosa ti consiglio di fare:",
                "Perfetto! Ora che ho capito il problema, proviamo con questa soluzione:"
            ],
            
            DialogueAction.ASK_FOR_CONFIRMATION: [
                "Hai provato i passaggi che ti ho suggerito? Come è andata?",
                "I passaggi che ti ho indicato hanno risolto il problema?",
                "Dimmi pure se la soluzione ha funzionato o se hai bisogno di ulteriore assistenza."
            ],
            
            DialogueAction.ESCALATE_TO_HUMAN: [
                "Vedo che si tratta di un problema complesso o urgente. Ti metto in contatto con un tecnico specializzato che potrà assisterti meglio.",
                "Per questo tipo di problema è meglio che parli direttamente con un esperto. Ti trasferisco subito.",
                "Vista la complessità del caso, è meglio che ti segua un tecnico umano. Sto organizzando il trasferimento."
            ],
            
            DialogueAction.CLOSE_TICKET: [
                "Perfetto! Sono contento che siamo riusciti a risolvere il problema. Il ticket è ora chiuso.\\n\\nSe dovessi avere altri problemi, non esitare a contattarmi!",
                "Ottimo! Il problema è risolto. Ticket chiuso con successo.\\n\\nTi ringrazio per aver usato il nostro sistema di supporto!",
                "Fantastico! Problema risolto. Se in futuro dovessi avere altre difficoltà, sarò sempre qui ad aiutarti!"
            ],
            
            DialogueAction.REQUEST_FEEDBACK: [
                "Prima di chiudere, potresti darmi un feedback su come è andata? Questo mi aiuta a migliorare l'assistenza.",
                "Come valuti l'aiuto che ti ho dato oggi? Il tuo feedback è molto importante per noi.",
                "Ti andrebbe di condividere la tua esperienza? Mi aiuta a offrire un servizio sempre migliore."
            ],
            
            DialogueAction.CLARIFY_PROBLEM: [
                "Non sono sicuro di aver capito bene. Potresti spiegarmi meglio il problema?",
                "Mi scuso, ma non ho compreso bene la situazione. Puoi riformulare la richiesta?",
                "Potresti darmi qualche dettaglio in più? Non sono riuscito a capire completamente il problema."
            ],
            
            DialogueAction.SCHEDULE_FOLLOW_UP: [
                "Ti programmo un follow-up per verificare che tutto continui a funzionare correttamente. Ti va bene se ti ricontatto tra qualche giorno?",
                "Perfetto! Ti richiamerò tra un paio di giorni per assicurarmi che il problema non si ripresenti.",
                "Ti organizzo un controllo periodico. Ti manderò un messaggio tra qualche giorno per verificare che tutto vada bene."
            ]
        }
    
    def _initialize_inference_patterns(self) -> Dict[str, Any]:
        """Initialize patterns for context inference."""
        
        return {
            'time_references': {
                'stamattina': 'morning',
                'oggi': 'today',
                'ieri': 'yesterday',
                'questa settimana': 'this_week',
                'la settimana scorsa': 'last_week'
            },
            'frequency_indicators': {
                'sempre': 'always',
                'spesso': 'often',
                'qualche volta': 'sometimes',
                'raramente': 'rarely',
                'mai': 'never'
            },
            'severity_indicators': {
                'bloccante': 'blocking',
                'critico': 'critical',
                'urgente': 'urgent',
                'importante': 'important',
                'normale': 'normal'
            }
        }
    
    def _update_transition_stats(self, from_state: DialogueState, to_state: DialogueState) -> None:
        """Update state transition statistics."""
        transition = f"{from_state.value}_{to_state.value}"
        if transition not in self.stats['state_transitions']:
            self.stats['state_transitions'][transition] = 0
        self.stats['state_transitions'][transition] += 1
    
    async def get_dialogue_context(self, conversation_id: str) -> Optional[DialogueContext]:
        """Get current dialogue context."""
        return self.active_dialogues.get(conversation_id)
    
    async def close_dialogue(self, conversation_id: str, reason: str = "completed") -> None:
        """Close dialogue and update statistics."""
        if conversation_id in self.active_dialogues:
            context = self.active_dialogues[conversation_id]
            
            # Update statistics
            if reason == "completed":
                self.stats['completed_conversations'] += 1
            elif reason == "escalated":
                self.stats['escalated_conversations'] += 1
            
            # Calculate metrics
            total_turns = len(context.dialogue_history)
            duration = (datetime.now() - context.started_at).total_seconds() / 60  # minutes
            
            # Update running averages
            n = self.stats['completed_conversations']
            if n > 0:
                self.stats['average_turns_per_conversation'] = (
                    (self.stats['average_turns_per_conversation'] * (n - 1) + total_turns) / n
                )
                self.stats['average_resolution_time'] = (
                    (self.stats['average_resolution_time'] * (n - 1) + duration) / n
                )
            
            # Remove from active dialogues
            del self.active_dialogues[conversation_id]
            
            logger.info(f"Closed dialogue {conversation_id}: {total_turns} turns, {duration:.1f} min, reason: {reason}")
    
    async def cleanup_expired_dialogues(self) -> int:
        """Clean up expired dialogues."""
        current_time = datetime.now()
        expired_dialogues = []
        
        for conv_id, context in self.active_dialogues.items():
            if (current_time - context.last_activity).total_seconds() > self.context_timeout:
                expired_dialogues.append(conv_id)
        
        for conv_id in expired_dialogues:
            await self.close_dialogue(conv_id, "expired")
        
        return len(expired_dialogues)
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get comprehensive analytics."""
        analytics = self.stats.copy()
        
        analytics.update({
            'active_dialogues': len(self.active_dialogues),
            'dialogue_policies': len(self.dialogue_policies),
            'response_templates': len(self.response_templates),
            'features_enabled': {
                'proactive_suggestions': self.enable_proactive_suggestions,
                'context_inference': self.enable_context_inference,
            },
            'configuration': {
                'context_timeout': self.context_timeout,
                'max_turns_per_state': self.max_turns_per_state,
            }
        })
        
        return analytics