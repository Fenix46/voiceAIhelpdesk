"""Advanced ticket builder for incremental construction and validation of IT support tickets."""

import asyncio
import time
import uuid
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from enum import Enum
import threading
import json
from pathlib import Path

from loguru import logger

from voicehelpdeskai.services.nlu import NLUManager, NLUResponse, IntentType, ITCategory, UrgencyLevel, ExtractedEntity
from voicehelpdeskai.config.manager import get_config_manager


class TicketStatus(Enum):
    """Ticket status levels."""
    DRAFT = "draft"
    INCOMPLETE = "incomplete"
    PENDING_VALIDATION = "pending_validation"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketPriority(Enum):
    """Ticket priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


class FieldType(Enum):
    """Types of ticket fields."""
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    DATETIME = "datetime"
    CATEGORY = "category"
    PRIORITY = "priority"
    ASSET_ID = "asset_id"
    IP_ADDRESS = "ip_address"
    SOFTWARE_VERSION = "software_version"
    ERROR_CODE = "error_code"
    FILE_ATTACHMENT = "file_attachment"


class ValidationSeverity(Enum):
    """Validation issue severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class FieldDefinition:
    """Definition of a ticket field."""
    name: str
    field_type: FieldType
    required: bool = False
    validation_pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    allowed_values: Optional[List[str]] = None
    depends_on: Optional[List[str]] = None
    auto_extract: bool = False
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationIssue:
    """Validation issue for ticket field."""
    field_name: str
    severity: ValidationSeverity
    message: str
    suggestion: Optional[str] = None
    auto_fix_available: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketValidationResult:
    """Result of ticket validation."""
    is_valid: bool
    completeness_score: float  # 0.0 to 1.0
    issues: List[ValidationIssue] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    invalid_fields: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    auto_fixes_applied: int = 0
    validation_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketInfo:
    """Complete ticket information."""
    # Core identification
    ticket_id: str
    title: str = ""
    description: str = ""
    
    # User information
    user_id: str = ""
    user_name: str = ""
    user_email: str = ""
    user_phone: str = ""
    department: str = ""
    
    # Classification
    category: ITCategory = ITCategory.GENERAL
    subcategory: str = ""
    priority: TicketPriority = TicketPriority.NORMAL
    urgency: UrgencyLevel = UrgencyLevel.MEDIO
    impact: str = "medium"
    
    # Technical details
    affected_systems: List[str] = field(default_factory=list)
    asset_ids: List[str] = field(default_factory=list)
    software_versions: List[str] = field(default_factory=list)
    error_codes: List[str] = field(default_factory=list)
    ip_addresses: List[str] = field(default_factory=list)
    
    # Problem details
    problem_summary: str = ""
    problem_description: str = ""
    reproduction_steps: List[str] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)
    business_impact: str = ""
    
    # Resolution information
    resolution_category: str = ""
    resolution_description: str = ""
    resolution_steps: List[str] = field(default_factory=list)
    workaround: str = ""
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Status and tracking
    status: TicketStatus = TicketStatus.DRAFT
    assigned_to: str = ""
    assigned_group: str = ""
    escalation_level: int = 0
    
    # Additional data
    tags: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    related_tickets: List[str] = field(default_factory=list)
    knowledge_base_articles: List[str] = field(default_factory=list)
    
    # Metrics
    customer_satisfaction: Optional[int] = None
    resolution_time: Optional[timedelta] = None
    first_response_time: Optional[timedelta] = None
    
    # Context from conversation
    conversation_id: str = ""
    original_input: str = ""
    nlu_confidence: float = 0.0
    auto_generated: bool = True
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketBuildResult:
    """Result of ticket building process."""
    ticket_info: TicketInfo
    validation_result: TicketValidationResult
    build_time: float = 0.0
    auto_populated_fields: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    requires_human_review: bool = False
    next_questions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TicketBuilder:
    """Advanced ticket builder with incremental construction and validation."""
    
    def __init__(self,
                 nlu_manager: Optional[NLUManager] = None,
                 ticket_schema_file: Optional[str] = None,
                 enable_auto_completion: bool = True,
                 enable_deduplication: bool = True,
                 enable_priority_calculation: bool = True,
                 enable_category_assignment: bool = True,
                 validation_strictness: str = "medium"):
        """Initialize ticket builder.
        
        Args:
            nlu_manager: NLU manager for entity extraction
            ticket_schema_file: JSON file defining ticket schema
            enable_auto_completion: Enable automatic field completion
            enable_deduplication: Enable duplicate ticket detection
            enable_priority_calculation: Enable automatic priority calculation
            enable_category_assignment: Enable automatic category assignment
            validation_strictness: Validation strictness (low, medium, high)
        """
        self.config = get_config_manager().get_config()
        self.nlu_manager = nlu_manager
        self.ticket_schema_file = ticket_schema_file or "./config/ticket_schema.json"
        self.enable_auto_completion = enable_auto_completion
        self.enable_deduplication = enable_deduplication
        self.enable_priority_calculation = enable_priority_calculation
        self.enable_category_assignment = enable_category_assignment
        self.validation_strictness = validation_strictness
        
        # Field definitions and schema
        self.field_definitions: Dict[str, FieldDefinition] = {}
        self.required_fields: Set[str] = set()
        self.auto_extract_fields: Set[str] = set()
        
        # Knowledge base for auto-completion
        self.category_patterns: Dict[ITCategory, List[str]] = {}
        self.priority_keywords: Dict[TicketPriority, List[str]] = {}
        self.common_problems: Dict[str, List[str]] = {}
        self.resolution_templates: Dict[str, str] = {}
        
        # Deduplication and similarity
        self.recent_tickets: List[TicketInfo] = []
        self.similarity_threshold = 0.8
        
        # State tracking
        self.active_builds: Dict[str, TicketInfo] = {}
        self.build_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self.stats = {
            'total_builds': 0,
            'successful_builds': 0,
            'failed_builds': 0,
            'auto_completed_fields': 0,
            'validation_failures': 0,
            'duplicates_detected': 0,
            'average_build_time': 0.0,
            'total_build_time': 0.0,
            'category_accuracy': 0.0,
            'priority_accuracy': 0.0,
            'field_completion_rates': {},
            'validation_issue_counts': {severity: 0 for severity in ValidationSeverity},
            'errors': 0,
            'last_error': None
        }
        
        # State
        self.is_initialized = False
        self.initialization_lock = threading.Lock()
        
        logger.info("TicketBuilder initialized")
    
    async def initialize(self) -> None:
        """Initialize ticket builder and load schemas."""
        if self.is_initialized:
            logger.warning("TicketBuilder already initialized")
            return
        
        with self.initialization_lock:
            if self.is_initialized:
                return
            
            try:
                logger.info("Initializing TicketBuilder...")
                
                # Load ticket schema
                await self._load_ticket_schema()
                
                # Load knowledge base
                await self._load_knowledge_base()
                
                # Initialize classification patterns
                self._initialize_classification_patterns()
                
                self.is_initialized = True
                logger.success(f"TicketBuilder initialized with {len(self.field_definitions)} field definitions")
                
            except Exception as e:
                logger.error(f"TicketBuilder initialization failed: {e}")
                self.stats['errors'] += 1
                self.stats['last_error'] = str(e)
                raise
    
    async def build_ticket(self,
                          user_input: str,
                          nlu_result: Optional[NLUResponse],
                          conversation_id: str,
                          user_id: str,
                          metadata: Optional[Dict[str, Any]] = None) -> TicketBuildResult:
        """Build ticket from user input and NLU analysis.
        
        Args:
            user_input: Original user input
            nlu_result: NLU analysis result
            conversation_id: Conversation identifier
            user_id: User identifier
            metadata: Additional metadata
            
        Returns:
            Complete ticket build result
        """
        if not self.is_initialized:
            await self.initialize()
        
        start_time = time.time()
        self.stats['total_builds'] += 1
        
        try:
            # Create base ticket
            ticket = TicketInfo(
                ticket_id=str(uuid.uuid4()),
                user_id=user_id,
                conversation_id=conversation_id,
                original_input=user_input,
                nlu_confidence=nlu_result.confidence if nlu_result else 0.0,
                metadata=metadata or {}
            )
            
            # Track build session
            session_id = f"{conversation_id}_{int(time.time())}"
            self.build_sessions[session_id] = {
                'ticket_id': ticket.ticket_id,
                'start_time': start_time,
                'user_input': user_input,
                'nlu_result': nlu_result
            }
            
            auto_populated_fields = []
            
            # Step 1: Extract basic information
            if nlu_result:
                auto_populated_fields.extend(await self._extract_basic_info(ticket, nlu_result))
            
            # Step 2: Auto-complete from context
            if self.enable_auto_completion:
                auto_populated_fields.extend(await self._auto_complete_fields(ticket, user_input))
            
            # Step 3: Calculate priority
            if self.enable_priority_calculation:
                await self._calculate_priority(ticket, nlu_result)
                auto_populated_fields.append('priority')
            
            # Step 4: Assign category
            if self.enable_category_assignment and nlu_result:
                await self._assign_category(ticket, nlu_result)
                auto_populated_fields.append('category')
            
            # Step 5: Check for duplicates
            duplicate_tickets = []
            if self.enable_deduplication:
                duplicate_tickets = await self._check_duplicates(ticket)
            
            # Step 6: Validate ticket
            validation_result = await self._validate_ticket(ticket)
            
            # Step 7: Generate next questions if incomplete
            next_questions = []
            if not validation_result.is_valid:
                next_questions = await self._generate_completion_questions(ticket, validation_result)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(ticket, validation_result, nlu_result)
            
            # Determine if human review is needed
            requires_human_review = (
                confidence_score < 0.6 or
                ticket.priority in [TicketPriority.CRITICAL, TicketPriority.EMERGENCY] or
                len(duplicate_tickets) > 0 or
                any(issue.severity == ValidationSeverity.CRITICAL for issue in validation_result.issues)
            )
            
            # Update ticket status
            if validation_result.is_valid:
                ticket.status = TicketStatus.VALIDATED
            elif validation_result.completeness_score > 0.8:
                ticket.status = TicketStatus.PENDING_VALIDATION
            else:
                ticket.status = TicketStatus.INCOMPLETE
            
            # Store active build
            self.active_builds[conversation_id] = ticket
            
            # Build result
            build_time = time.time() - start_time
            result = TicketBuildResult(
                ticket_info=ticket,
                validation_result=validation_result,
                build_time=build_time,
                auto_populated_fields=auto_populated_fields,
                confidence_score=confidence_score,
                requires_human_review=requires_human_review,
                next_questions=next_questions,
                metadata={
                    'session_id': session_id,
                    'duplicate_tickets': [t.ticket_id for t in duplicate_tickets],
                    'processing_steps': len(auto_populated_fields)
                }
            )
            
            # Update statistics
            self._update_build_stats(result)
            self.stats['successful_builds'] += 1
            
            logger.debug(f"Built ticket {ticket.ticket_id} in {build_time:.3f}s: "
                        f"confidence={confidence_score:.3f}, fields={len(auto_populated_fields)}")
            
            return result
            
        except Exception as e:
            build_time = time.time() - start_time
            self.stats['failed_builds'] += 1
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            logger.error(f"Ticket building failed after {build_time:.3f}s: {e}")
            
            # Return minimal result with error
            return TicketBuildResult(
                ticket_info=TicketInfo(ticket_id=str(uuid.uuid4()), user_id=user_id),
                validation_result=TicketValidationResult(
                    is_valid=False,
                    completeness_score=0.0,
                    issues=[ValidationIssue(
                        field_name="general",
                        severity=ValidationSeverity.CRITICAL,
                        message=f"Ticket building failed: {str(e)}"
                    )]
                ),
                build_time=build_time,
                confidence_score=0.0,
                requires_human_review=True,
                metadata={'error': str(e)}
            )
    
    async def update_ticket(self,
                           conversation_id: str,
                           new_input: str,
                           nlu_result: Optional[NLUResponse] = None) -> TicketBuildResult:
        """Update existing ticket with new information.
        
        Args:
            conversation_id: Conversation identifier
            new_input: New user input
            nlu_result: Optional NLU result for new input
            
        Returns:
            Updated ticket build result
        """
        if conversation_id not in self.active_builds:
            raise ValueError(f"No active ticket build for conversation {conversation_id}")
        
        start_time = time.time()
        ticket = self.active_builds[conversation_id]
        
        try:
            # Update ticket with new information
            ticket.updated_at = datetime.now()
            ticket.original_input += " " + new_input
            
            auto_populated_fields = []
            
            # Extract additional information
            if nlu_result:
                auto_populated_fields.extend(await self._extract_basic_info(ticket, nlu_result))
            
            # Auto-complete additional fields
            if self.enable_auto_completion:
                auto_populated_fields.extend(await self._auto_complete_fields(ticket, new_input))
            
            # Re-validate ticket
            validation_result = await self._validate_ticket(ticket)
            
            # Generate next questions if still incomplete
            next_questions = []
            if not validation_result.is_valid:
                next_questions = await self._generate_completion_questions(ticket, validation_result)
            
            # Recalculate confidence
            confidence_score = self._calculate_confidence_score(ticket, validation_result, nlu_result)
            
            # Update status
            if validation_result.is_valid:
                ticket.status = TicketStatus.VALIDATED
            elif validation_result.completeness_score > 0.8:
                ticket.status = TicketStatus.PENDING_VALIDATION
            
            build_time = time.time() - start_time
            
            result = TicketBuildResult(
                ticket_info=ticket,
                validation_result=validation_result,
                build_time=build_time,
                auto_populated_fields=auto_populated_fields,
                confidence_score=confidence_score,
                requires_human_review=confidence_score < 0.6,
                next_questions=next_questions,
                metadata={'update_operation': True}
            )
            
            logger.debug(f"Updated ticket {ticket.ticket_id} in {build_time:.3f}s")
            return result
            
        except Exception as e:
            logger.error(f"Ticket update failed: {e}")
            raise
    
    async def _extract_basic_info(self, ticket: TicketInfo, nlu_result: NLUResponse) -> List[str]:
        """Extract basic information from NLU result."""
        populated_fields = []
        
        try:
            # Extract title and description
            if not ticket.title and nlu_result.intent:
                ticket.title = self._generate_title_from_intent(nlu_result)
                populated_fields.append('title')
            
            if not ticket.description:
                ticket.description = ticket.original_input[:500]
                populated_fields.append('description')
            
            # Extract entities
            if nlu_result.entities:
                for entity in nlu_result.entities:
                    field_name = self._map_entity_to_field(entity)
                    if field_name and self._update_ticket_field(ticket, field_name, entity.value):
                        populated_fields.append(field_name)
            
            # Extract problem analysis information
            if nlu_result.problem_analysis:
                analysis = nlu_result.problem_analysis
                
                if analysis.problem_category:
                    ticket.problem_summary = analysis.problem_category
                    populated_fields.append('problem_summary')
                
                if analysis.affected_systems:
                    ticket.affected_systems.extend(analysis.affected_systems)
                    populated_fields.append('affected_systems')
                
                if analysis.business_impact_description:
                    ticket.business_impact = analysis.business_impact_description
                    populated_fields.append('business_impact')
                
                if analysis.recommended_solutions:
                    ticket.resolution_steps = [sol.description for sol in analysis.recommended_solutions[:3]]
                    populated_fields.append('resolution_steps')
            
        except Exception as e:
            logger.error(f"Basic info extraction failed: {e}")
        
        return populated_fields
    
    async def _auto_complete_fields(self, ticket: TicketInfo, user_input: str) -> List[str]:
        """Auto-complete fields from context and patterns."""
        populated_fields = []
        
        try:
            # Extract technical information with regex patterns
            
            # Error codes
            error_codes = re.findall(r'\b(?:error|errore|codice)\s*[:\-]?\s*([A-Z0-9\-]+)\b', user_input, re.IGNORECASE)
            if error_codes and not ticket.error_codes:
                ticket.error_codes = error_codes[:5]  # Limit to 5
                populated_fields.append('error_codes')
            
            # IP addresses
            ip_addresses = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', user_input)
            if ip_addresses and not ticket.ip_addresses:
                ticket.ip_addresses = ip_addresses[:3]  # Limit to 3
                populated_fields.append('ip_addresses')
            
            # Asset IDs (pattern like IT001234, WS789012)
            asset_ids = re.findall(r'\b[A-Z]{2,4}[0-9]{3,8}\b', user_input)
            if asset_ids and not ticket.asset_ids:
                ticket.asset_ids = asset_ids[:3]
                populated_fields.append('asset_ids')
            
            # Software versions
            versions = re.findall(r'\b(?:version|versione|v\.?)\s*([0-9]+(?:\.[0-9]+)*)\b', user_input, re.IGNORECASE)
            if versions and not ticket.software_versions:
                ticket.software_versions = [v for v in versions[:3]]
                populated_fields.append('software_versions')
            
            # Email addresses
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', user_input)
            if emails and not ticket.user_email:
                ticket.user_email = emails[0]
                populated_fields.append('user_email')
            
            # Phone numbers (Italian format)
            phones = re.findall(r'\b(?:\+39\s?)?(?:[0-9\s\-\.]{10,})\b', user_input)
            if phones and not ticket.user_phone:
                ticket.user_phone = phones[0]
                populated_fields.append('user_phone')
            
            # Extract problem steps
            if not ticket.reproduction_steps:
                steps = self._extract_steps_from_text(user_input)
                if steps:
                    ticket.reproduction_steps = steps
                    populated_fields.append('reproduction_steps')
            
        except Exception as e:
            logger.error(f"Auto-completion failed: {e}")
        
        return populated_fields
    
    async def _calculate_priority(self, ticket: TicketInfo, nlu_result: Optional[NLUResponse]) -> None:
        """Calculate ticket priority based on various factors."""
        try:
            priority_score = 0
            
            # Base priority from NLU urgency
            if nlu_result and nlu_result.intent:
                urgency = nlu_result.intent.urgency
                if urgency == UrgencyLevel.CRITICO:
                    priority_score += 4
                elif urgency == UrgencyLevel.ALTO:
                    priority_score += 3
                elif urgency == UrgencyLevel.MEDIO:
                    priority_score += 2
                else:
                    priority_score += 1
            
            # Keyword-based priority adjustment
            input_lower = ticket.original_input.lower()
            
            # Critical keywords
            critical_keywords = ['non funziona', 'down', 'crashed', 'errore critico', 'sistema bloccato', 'urgente']
            if any(keyword in input_lower for keyword in critical_keywords):
                priority_score += 2
            
            # High priority keywords
            high_keywords = ['lento', 'problema', 'errore', 'non riesco', 'blocco']
            if any(keyword in input_lower for keyword in high_keywords):
                priority_score += 1
            
            # Business impact factors
            if ticket.business_impact:
                impact_lower = ticket.business_impact.lower()
                if any(word in impact_lower for word in ['critico', 'grave', 'blocco produzione']):
                    priority_score += 2
                elif any(word in impact_lower for word in ['importante', 'significativo']):
                    priority_score += 1
            
            # System criticality
            if ticket.affected_systems:
                critical_systems = ['server', 'database', 'rete', 'email', 'security']
                if any(system.lower() in critical_systems for system in ticket.affected_systems):
                    priority_score += 1
            
            # Map score to priority
            if priority_score >= 6:
                ticket.priority = TicketPriority.EMERGENCY
            elif priority_score >= 5:
                ticket.priority = TicketPriority.CRITICAL
            elif priority_score >= 3:
                ticket.priority = TicketPriority.HIGH
            elif priority_score >= 2:
                ticket.priority = TicketPriority.NORMAL
            else:
                ticket.priority = TicketPriority.LOW
            
        except Exception as e:
            logger.error(f"Priority calculation failed: {e}")
            ticket.priority = TicketPriority.NORMAL
    
    async def _assign_category(self, ticket: TicketInfo, nlu_result: NLUResponse) -> None:
        """Assign category based on NLU analysis."""
        try:
            if nlu_result.intent and nlu_result.intent.category:
                ticket.category = nlu_result.intent.category
            else:
                # Fallback to pattern matching
                input_lower = ticket.original_input.lower()
                
                # Software issues
                software_keywords = ['software', 'programma', 'applicazione', 'app', 'word', 'excel', 'outlook']
                hardware_keywords = ['hardware', 'computer', 'stampante', 'mouse', 'tastiera', 'monitor']
                network_keywords = ['rete', 'internet', 'wifi', 'connessione', 'vpn', 'ip']
                security_keywords = ['password', 'accesso', 'login', 'sicurezza', 'virus', 'malware']

                if any(keyword in input_lower for keyword in software_keywords):
                    ticket.category = ITCategory.SOFTWARE
                elif any(keyword in input_lower for keyword in hardware_keywords):
                    ticket.category = ITCategory.HARDWARE
                elif any(keyword in input_lower for keyword in network_keywords):
                    ticket.category = ITCategory.NETWORK
                elif any(keyword in input_lower for keyword in security_keywords):
                    ticket.category = ITCategory.SECURITY
                else:
                    ticket.category = ITCategory.GENERAL
            
        except Exception as e:
            logger.error(f"Category assignment failed: {e}")
            ticket.category = ITCategory.GENERAL
    
    async def _check_duplicates(self, ticket: TicketInfo) -> List[TicketInfo]:
        """Check for potential duplicate tickets."""
        duplicates = []
        
        try:
            # Simple similarity check with recent tickets
            for recent_ticket in self.recent_tickets[-50:]:  # Check last 50 tickets
                similarity = self._calculate_ticket_similarity(ticket, recent_ticket)
                if similarity > self.similarity_threshold:
                    duplicates.append(recent_ticket)
            
            if duplicates:
                self.stats['duplicates_detected'] += 1
                logger.warning(f"Found {len(duplicates)} potential duplicates for ticket {ticket.ticket_id}")
            
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
        
        return duplicates
    
    async def _validate_ticket(self, ticket: TicketInfo) -> TicketValidationResult:
        """Validate ticket completeness and correctness."""
        start_time = time.time()
        issues = []
        missing_fields = []
        invalid_fields = []
        
        try:
            # Check required fields
            required_field_names = {'title', 'description', 'user_id', 'category', 'priority'}
            
            for field_name in required_field_names:
                field_value = getattr(ticket, field_name, None)
                if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                    missing_fields.append(field_name)
                    issues.append(ValidationIssue(
                        field_name=field_name,
                        severity=ValidationSeverity.ERROR,
                        message=f"Campo obbligatorio mancante: {field_name}",
                        suggestion=f"Fornire un valore per {field_name}",
                        auto_fix_available=False
                    ))
            
            # Validate field formats
            validation_checks = [
                ('user_email', self._validate_email, "Formato email non valido"),
                ('user_phone', self._validate_phone, "Formato telefono non valido"),
                ('ip_addresses', self._validate_ip_addresses, "Formato IP non valido"),
                ('error_codes', self._validate_error_codes, "Formato codice errore non valido")
            ]
            
            for field_name, validator, error_msg in validation_checks:
                field_value = getattr(ticket, field_name, None)
                if field_value and not validator(field_value):
                    invalid_fields.append(field_name)
                    issues.append(ValidationIssue(
                        field_name=field_name,
                        severity=ValidationSeverity.WARNING,
                        message=error_msg,
                        suggestion=f"Verificare il formato di {field_name}",
                        auto_fix_available=field_name in ['user_phone']  # Some fields can be auto-fixed
                    ))
            
            # Business logic validation
            if ticket.priority == TicketPriority.EMERGENCY and not ticket.business_impact:
                issues.append(ValidationIssue(
                    field_name='business_impact',
                    severity=ValidationSeverity.WARNING,
                    message="Ticket di emergenza dovrebbe includere impatto business",
                    suggestion="Aggiungere descrizione impatto business"
                ))
            
            if ticket.category == ITCategory.SECURITY and ticket.priority == TicketPriority.LOW:
                issues.append(ValidationIssue(
                    field_name='priority',
                    severity=ValidationSeverity.WARNING,
                    message="Problemi di sicurezza dovrebbero avere priorità più alta",
                    suggestion="Considerare di aumentare la priorità"
                ))
            
            # Calculate completeness score
            total_important_fields = 12  # Key fields that contribute to completeness
            completed_fields = 0
            
            completeness_checks = [
                bool(ticket.title),
                bool(ticket.description),
                bool(ticket.user_id),
                bool(ticket.category != ITCategory.GENERAL),
                bool(ticket.problem_summary),
                bool(ticket.business_impact),
                bool(ticket.affected_systems),
                bool(ticket.reproduction_steps),
                bool(ticket.user_email),
                bool(ticket.priority != TicketPriority.NORMAL),
                bool(ticket.asset_ids or ticket.ip_addresses),
                bool(ticket.error_codes or ticket.error_messages)
            ]
            
            completed_fields = sum(completeness_checks)
            completeness_score = completed_fields / total_important_fields
            
            # Determine overall validity
            critical_issues = [issue for issue in issues if issue.severity == ValidationSeverity.CRITICAL]
            error_issues = [issue for issue in issues if issue.severity == ValidationSeverity.ERROR]
            is_valid = len(critical_issues) == 0 and len(error_issues) == 0
            
            validation_time = time.time() - start_time
            
            result = TicketValidationResult(
                is_valid=is_valid,
                completeness_score=completeness_score,
                issues=issues,
                missing_fields=missing_fields,
                invalid_fields=invalid_fields,
                validation_time=validation_time
            )
            
            # Update statistics
            for issue in issues:
                self.stats['validation_issue_counts'][issue.severity] += 1
            
            if not is_valid:
                self.stats['validation_failures'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Ticket validation failed: {e}")
            return TicketValidationResult(
                is_valid=False,
                completeness_score=0.0,
                issues=[ValidationIssue(
                    field_name="validation",
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Validation failed: {str(e)}"
                )],
                validation_time=time.time() - start_time
            )
    
    async def _generate_completion_questions(self, ticket: TicketInfo, 
                                           validation_result: TicketValidationResult) -> List[str]:
        """Generate questions to complete missing ticket information."""
        questions = []
        
        try:
            # Generate questions based on missing fields
            for field_name in validation_result.missing_fields:
                question = self._get_field_question(field_name, ticket)
                if question:
                    questions.append(question)
            
            # Add questions based on category
            if ticket.category == ITCategory.SOFTWARE and not ticket.software_versions:
                questions.append("Puoi dirmi la versione del software con cui hai problemi?")
            
            if ticket.category == ITCategory.HARDWARE and not ticket.asset_ids:
                questions.append("Hai l'ID del computer o dispositivo che ha problemi?")
            
            if ticket.category == ITCategory.NETWORK and not ticket.ip_addresses:
                questions.append("Puoi fornirmi l'indirizzo IP del dispositivo interessato?")
            
            # Prioritize questions by importance
            questions = questions[:3]  # Limit to 3 most important questions
            
        except Exception as e:
            logger.error(f"Question generation failed: {e}")
        
        return questions
    
    def _generate_title_from_intent(self, nlu_result: NLUResponse) -> str:
        """Generate ticket title from NLU intent."""
        intent = nlu_result.intent.intent
        category = nlu_result.intent.category
        
        title_templates = {
            IntentType.PROBLEM_REPORT: {
                ITCategory.SOFTWARE: "Problema con software",
                ITCategory.HARDWARE: "Malfunzionamento hardware",
                ITCategory.NETWORK: "Problema di rete",
                ITCategory.SECURITY: "Problema di sicurezza",
                ITCategory.GENERAL: "Richiesta di supporto"
            },
            IntentType.INFORMATION_REQUEST: {
                ITCategory.GENERAL: "Richiesta informazioni"
            },
            IntentType.ESCALATION: {
                ITCategory.GENERAL: "Richiesta escalation"
            }
        }
        
        template = title_templates.get(intent, {}).get(category, "Ticket di supporto")
        
        # Add entity information if available
        if nlu_result.entities:
            for entity in nlu_result.entities[:2]:  # Add first 2 entities
                if entity.type in ['software', 'hardware']:
                    template += f" - {entity.value}"
        
        return template
    
    def _map_entity_to_field(self, entity: ExtractedEntity) -> Optional[str]:
        """Map NLU entity to ticket field."""
        entity_field_mapping = {
            'software': 'affected_systems',
            'hardware': 'affected_systems',
            'error_code': 'error_codes',
            'ip_address': 'ip_addresses',
            'email': 'user_email',
            'phone': 'user_phone',
            'asset_id': 'asset_ids',
            'person': 'user_name'
        }
        
        return entity_field_mapping.get(entity.type)
    
    def _update_ticket_field(self, ticket: TicketInfo, field_name: str, value: str) -> bool:
        """Update ticket field with extracted value."""
        try:
            if field_name in ['affected_systems', 'error_codes', 'ip_addresses', 'asset_ids']:
                # List fields
                field_list = getattr(ticket, field_name, [])
                if value not in field_list:
                    field_list.append(value)
                    setattr(ticket, field_name, field_list)
                    return True
            else:
                # Single value fields
                current_value = getattr(ticket, field_name, None)
                if not current_value:
                    setattr(ticket, field_name, value)
                    return True
        except Exception as e:
            logger.error(f"Field update failed for {field_name}: {e}")
        
        return False
    
    def _extract_steps_from_text(self, text: str) -> List[str]:
        """Extract problem reproduction steps from text."""
        steps = []
        
        # Look for numbered steps
        step_patterns = [
            r'(\d+)\.\s*([^\.]+)',
            r'(\d+)\)\s*([^\.]+)',
            r'step\s*(\d+)[:\-]\s*([^\.]+)',
            r'passo\s*(\d+)[:\-]\s*([^\.]+)'
        ]
        
        for pattern in step_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                steps = [match[1].strip() for match in matches]
                break
        
        # If no numbered steps, look for action words
        if not steps:
            action_pattern = r'\b(ho\s+\w+|provo\s+a\s+\w+|clicco\s+\w+|apro\s+\w+|chiudo\s+\w+)[^\.]*'
            actions = re.findall(action_pattern, text, re.IGNORECASE)
            steps = [action.strip() for action in actions[:5]]  # Limit to 5
        
        return steps
    
    def _calculate_ticket_similarity(self, ticket1: TicketInfo, ticket2: TicketInfo) -> float:
        """Calculate similarity between two tickets."""
        try:
            # Simple similarity based on title and description
            from difflib import SequenceMatcher
            
            title_similarity = SequenceMatcher(None, ticket1.title.lower(), ticket2.title.lower()).ratio()
            desc_similarity = SequenceMatcher(None, ticket1.description.lower(), ticket2.description.lower()).ratio()
            
            # Category and system similarity
            category_match = 1.0 if ticket1.category == ticket2.category else 0.0
            system_overlap = len(set(ticket1.affected_systems) & set(ticket2.affected_systems)) / max(len(set(ticket1.affected_systems) | set(ticket2.affected_systems)), 1)
            
            # Weighted average
            similarity = (title_similarity * 0.4 + desc_similarity * 0.4 + category_match * 0.1 + system_overlap * 0.1)
            
            return similarity
            
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0
    
    def _calculate_confidence_score(self, ticket: TicketInfo, validation_result: TicketValidationResult, 
                                  nlu_result: Optional[NLUResponse]) -> float:
        """Calculate overall confidence score for ticket."""
        try:
            # Base score from validation completeness
            base_score = validation_result.completeness_score
            
            # Adjust for NLU confidence
            if nlu_result:
                nlu_confidence = nlu_result.confidence
                base_score = (base_score * 0.7) + (nlu_confidence * 0.3)
            
            # Penalize for validation issues
            critical_issues = sum(1 for issue in validation_result.issues if issue.severity == ValidationSeverity.CRITICAL)
            error_issues = sum(1 for issue in validation_result.issues if issue.severity == ValidationSeverity.ERROR)
            
            penalty = (critical_issues * 0.3) + (error_issues * 0.2)
            base_score = max(0.0, base_score - penalty)
            
            # Bonus for important fields
            bonus = 0.0
            if ticket.business_impact:
                bonus += 0.1
            if ticket.reproduction_steps:
                bonus += 0.1
            if ticket.error_codes:
                bonus += 0.05
            
            final_score = min(1.0, base_score + bonus)
            return final_score
            
        except Exception as e:
            logger.error(f"Confidence calculation failed: {e}")
            return 0.5
    
    def _get_field_question(self, field_name: str, ticket: TicketInfo) -> Optional[str]:
        """Get appropriate question for missing field."""
        field_questions = {
            'title': "Puoi darmi un titolo breve per descrivere il problema?",
            'description': "Puoi descrivere il problema in dettaglio?",
            'user_email': "Qual è il tuo indirizzo email?",
            'user_phone': "Qual è il tuo numero di telefono?",
            'business_impact': "Qual è l'impatto di questo problema sul tuo lavoro?",
            'reproduction_steps': "Puoi descrivermi i passaggi per riprodurre il problema?",
            'affected_systems': "Quali sistemi o software sono interessati dal problema?",
            'error_codes': "Hai visto messaggi di errore o codici specifici?",
            'asset_ids': "Puoi fornirmi l'ID del computer o dispositivo interessato?",
            'department': "In quale dipartimento lavori?"
        }
        
        return field_questions.get(field_name)
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        if isinstance(email, list):
            return all(self._validate_email(e) for e in email)
        email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    def _validate_phone(self, phone: str) -> bool:
        """Validate phone format."""
        if isinstance(phone, list):
            return all(self._validate_phone(p) for p in phone)
        # Simple validation for Italian phone numbers
        phone_clean = re.sub(r'[\s\-\.]', '', phone)
        return len(phone_clean) >= 10 and phone_clean.isdigit()
    
    def _validate_ip_addresses(self, ips: Union[str, List[str]]) -> bool:
        """Validate IP address format."""
        if isinstance(ips, str):
            ips = [ips]
        
        for ip in ips:
            try:
                parts = ip.split('.')
                if len(parts) != 4:
                    return False
                for part in parts:
                    if not (0 <= int(part) <= 255):
                        return False
            except (ValueError, AttributeError):
                return False
        return True
    
    def _validate_error_codes(self, codes: Union[str, List[str]]) -> bool:
        """Validate error code format."""
        if isinstance(codes, str):
            codes = [codes]
        
        # Simple validation - error codes should be alphanumeric
        for code in codes:
            if not re.match(r'^[A-Za-z0-9\-_]+$', code):
                return False
        return True
    
    async def _load_ticket_schema(self) -> None:
        """Load ticket schema from configuration."""
        try:
            # Define default schema if file doesn't exist
            default_fields = [
                FieldDefinition("title", FieldType.TEXT, required=True, max_length=200),
                FieldDefinition("description", FieldType.TEXT, required=True, max_length=2000),
                FieldDefinition("user_email", FieldType.EMAIL, required=False),
                FieldDefinition("user_phone", FieldType.PHONE, required=False),
                FieldDefinition("category", FieldType.CATEGORY, required=True),
                FieldDefinition("priority", FieldType.PRIORITY, required=True),
                FieldDefinition("business_impact", FieldType.TEXT, required=False, max_length=500),
                FieldDefinition("affected_systems", FieldType.TEXT, required=False),
                FieldDefinition("error_codes", FieldType.ERROR_CODE, required=False, auto_extract=True),
                FieldDefinition("ip_addresses", FieldType.IP_ADDRESS, required=False, auto_extract=True),
                FieldDefinition("asset_ids", FieldType.ASSET_ID, required=False, auto_extract=True)
            ]
            
            for field_def in default_fields:
                self.field_definitions[field_def.name] = field_def
                if field_def.required:
                    self.required_fields.add(field_def.name)
                if field_def.auto_extract:
                    self.auto_extract_fields.add(field_def.name)
            
            logger.debug(f"Loaded {len(self.field_definitions)} field definitions")
            
        except Exception as e:
            logger.error(f"Schema loading failed: {e}")
            raise
    
    async def _load_knowledge_base(self) -> None:
        """Load knowledge base for auto-completion."""
        try:
            # Load category patterns
            self.category_patterns = {
                ITCategory.SOFTWARE: [
                    'word', 'excel', 'outlook', 'powerpoint', 'teams', 'software', 'programma', 'applicazione'
                ],
                ITCategory.HARDWARE: [
                    'computer', 'stampante', 'mouse', 'tastiera', 'monitor', 'hardware', 'pc', 'laptop'
                ],
                ITCategory.NETWORK: [
                    'rete', 'internet', 'wifi', 'connessione', 'vpn', 'router', 'switch', 'ip'
                ],
                ITCategory.SECURITY: [
                    'password', 'accesso', 'login', 'sicurezza', 'virus', 'malware', 'firewall'
                ]
            }
            
            # Load priority keywords
            self.priority_keywords = {
                TicketPriority.EMERGENCY: ['emergenza', 'critico', 'bloccato', 'down', 'fermo'],
                TicketPriority.CRITICAL: ['urgente', 'importante', 'grave', 'serio'],
                TicketPriority.HIGH: ['priorità alta', 'veloce', 'presto'],
                TicketPriority.NORMAL: ['normale', 'standard'],
                TicketPriority.LOW: ['bassa priorità', 'quando possibile', 'non urgente']
            }
            
        except Exception as e:
            logger.error(f"Knowledge base loading failed: {e}")
    
    def _initialize_classification_patterns(self) -> None:
        """Initialize patterns for classification."""
        # This would typically load from configuration files
        # For now, using simple default patterns
        pass
    
    def _update_build_stats(self, result: TicketBuildResult) -> None:
        """Update build statistics."""
        self.stats['total_build_time'] += result.build_time
        self.stats['average_build_time'] = (
            self.stats['total_build_time'] / self.stats['total_builds']
        )
        
        self.stats['auto_completed_fields'] += len(result.auto_populated_fields)
        
        # Update field completion rates
        for field_name in result.auto_populated_fields:
            self.stats['field_completion_rates'][field_name] = (
                self.stats['field_completion_rates'].get(field_name, 0) + 1
            )
    
    def get_active_tickets(self) -> Dict[str, TicketInfo]:
        """Get all active ticket builds."""
        return self.active_builds.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        stats = self.stats.copy()
        
        # Add current state
        stats['active_builds'] = len(self.active_builds)
        stats['build_sessions'] = len(self.build_sessions)
        stats['recent_tickets_count'] = len(self.recent_tickets)
        
        # Calculate derived metrics
        if stats['total_builds'] > 0:
            stats['success_rate'] = (stats['successful_builds'] / stats['total_builds']) * 100
            stats['auto_completion_rate'] = (stats['auto_completed_fields'] / stats['total_builds'])
        
        stats['timestamp'] = datetime.now().isoformat()
        
        return stats
    
    async def cleanup_expired_builds(self, max_age_hours: int = 24) -> int:
        """Clean up expired build sessions."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        expired_conversations = []
        for conversation_id, ticket in self.active_builds.items():
            if ticket.created_at < cutoff_time:
                expired_conversations.append(conversation_id)
        
        for conversation_id in expired_conversations:
            del self.active_builds[conversation_id]
        
        # Clean up build sessions
        expired_sessions = []
        for session_id, session_data in self.build_sessions.items():
            session_time = datetime.fromtimestamp(session_data['start_time'])
            if session_time < cutoff_time:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.build_sessions[session_id]
        
        total_cleaned = len(expired_conversations) + len(expired_sessions)
        if total_cleaned > 0:
            logger.info(f"Cleaned up {total_cleaned} expired ticket builds")
        
        return total_cleaned
