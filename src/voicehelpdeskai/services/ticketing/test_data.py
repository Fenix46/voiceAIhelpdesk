"""Test data generator for realistic ticket generation with various IT problems and patterns."""

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid

from faker import Faker

from ...database import DatabaseManager, get_ticket_repository, get_user_repository
from ...database.models import Ticket, TicketStatus, TicketPriority, TicketCategory, User

logger = logging.getLogger(__name__)


class TicketTemplate(Enum):
    """Common IT ticket templates."""
    SOFTWARE_CRASH = "software_crash"
    SLOW_PERFORMANCE = "slow_performance"
    LOGIN_ISSUES = "login_issues"
    EMAIL_PROBLEMS = "email_problems"
    PRINTER_ISSUES = "printer_issues"
    NETWORK_CONNECTIVITY = "network_connectivity"
    HARDWARE_FAILURE = "hardware_failure"
    SOFTWARE_INSTALLATION = "software_installation"
    PASSWORD_RESET = "password_reset"
    VPN_CONNECTION = "vpn_connection"
    SECURITY_INCIDENT = "security_incident"
    DATA_RECOVERY = "data_recovery"
    SYSTEM_UPGRADE = "system_upgrade"
    PERMISSION_REQUEST = "permission_request"
    VIRUS_MALWARE = "virus_malware"


@dataclass
class UserPersona:
    """User persona for realistic ticket generation."""
    name: str
    department: str
    role: str
    tech_level: str  # "basic", "intermediate", "advanced"
    communication_style: str  # "formal", "casual", "detailed", "brief"
    typical_issues: List[TicketTemplate]
    escalation_tendency: float  # 0.0 to 1.0
    satisfaction_bias: float  # -1.0 to 1.0 (affects satisfaction scores)


@dataclass
class TicketScenario:
    """Scenario for generating tickets."""
    template: TicketTemplate
    title_templates: List[str]
    description_templates: List[str]
    category: TicketCategory
    priority_weights: Dict[int, float]
    typical_resolution_time: Tuple[int, int]  # min, max minutes
    common_tags: List[str]
    affected_systems: List[str]
    resolution_templates: List[str]
    escalation_probability: float


class TestDataGenerator:
    """
    Comprehensive test data generator for realistic IT ticket scenarios.
    
    Features:
    - Realistic IT problems with varied descriptions
    - User personas with different behavior patterns
    - Temporal patterns (business hours, seasonal trends)
    - Historical data generation with proper aging
    - Edge cases and stress testing scenarios
    - Realistic resolution patterns and satisfaction scores
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None, locale: str = "it_IT"):
        """Initialize test data generator."""
        self.db_manager = db_manager or DatabaseManager()
        self.fake = Faker(locale)
        
        # Initialize personas and scenarios
        self.user_personas = self._create_user_personas()
        self.ticket_scenarios = self._create_ticket_scenarios()
        
        # Temporal patterns
        self.business_hours = (8, 18)
        self.business_days = [0, 1, 2, 3, 4]  # Monday to Friday
        
        logger.info("TestDataGenerator initialized")
    
    def _create_user_personas(self) -> List[UserPersona]:
        """Create diverse user personas."""
        return [
            UserPersona(
                name="Mario Rossi",
                department="Contabilità",
                role="Contabile",
                tech_level="basic",
                communication_style="formal",
                typical_issues=[
                    TicketTemplate.SOFTWARE_CRASH,
                    TicketTemplate.EMAIL_PROBLEMS,
                    TicketTemplate.PRINTER_ISSUES,
                    TicketTemplate.PASSWORD_RESET
                ],
                escalation_tendency=0.7,
                satisfaction_bias=-0.2
            ),
            UserPersona(
                name="Giulia Bianchi",
                department="Marketing",
                role="Marketing Manager",
                tech_level="intermediate",
                communication_style="detailed",
                typical_issues=[
                    TicketTemplate.SOFTWARE_INSTALLATION,
                    TicketTemplate.VPN_CONNECTION,
                    TicketTemplate.SLOW_PERFORMANCE,
                    TicketTemplate.PERMISSION_REQUEST
                ],
                escalation_tendency=0.3,
                satisfaction_bias=0.1
            ),
            UserPersona(
                name="Andrea Verdi",
                department="Vendite",
                role="Sales Representative",
                tech_level="basic",
                communication_style="brief",
                typical_issues=[
                    TicketTemplate.LOGIN_ISSUES,
                    TicketTemplate.NETWORK_CONNECTIVITY,
                    TicketTemplate.EMAIL_PROBLEMS,
                    TicketTemplate.VPN_CONNECTION
                ],
                escalation_tendency=0.8,
                satisfaction_bias=-0.1
            ),
            UserPersona(
                name="Francesca Neri",
                department="HR",
                role="HR Specialist",
                tech_level="intermediate",
                communication_style="formal",
                typical_issues=[
                    TicketTemplate.SOFTWARE_INSTALLATION,
                    TicketTemplate.PERMISSION_REQUEST,
                    TicketTemplate.SYSTEM_UPGRADE,
                    TicketTemplate.DATA_RECOVERY
                ],
                escalation_tendency=0.4,
                satisfaction_bias=0.3
            ),
            UserPersona(
                name="Luca Ferrari",
                department="Ingegneria",
                role="Software Engineer",
                tech_level="advanced",
                communication_style="detailed",
                typical_issues=[
                    TicketTemplate.SYSTEM_UPGRADE,
                    TicketTemplate.SOFTWARE_INSTALLATION,
                    TicketTemplate.NETWORK_CONNECTIVITY,
                    TicketTemplate.SECURITY_INCIDENT
                ],
                escalation_tendency=0.1,
                satisfaction_bias=0.2
            ),
            UserPersona(
                name="Elena Romano",
                department="Amministrazione",
                role="Admin Assistant",
                tech_level="basic",
                communication_style="casual",
                typical_issues=[
                    TicketTemplate.PRINTER_ISSUES,
                    TicketTemplate.EMAIL_PROBLEMS,
                    TicketTemplate.SOFTWARE_CRASH,
                    TicketTemplate.SLOW_PERFORMANCE
                ],
                escalation_tendency=0.6,
                satisfaction_bias=0.0
            ),
            UserPersona(
                name="Marco Conti",
                department="Finance",
                role="Financial Analyst",
                tech_level="intermediate",
                communication_style="formal",
                typical_issues=[
                    TicketTemplate.DATA_RECOVERY,
                    TicketTemplate.SOFTWARE_CRASH,
                    TicketTemplate.PERMISSION_REQUEST,
                    TicketTemplate.SECURITY_INCIDENT
                ],
                escalation_tendency=0.5,
                satisfaction_bias=-0.3
            ),
            UserPersona(
                name="Sara Colombo",
                department="Operations",
                role="Operations Manager",
                tech_level="advanced",
                communication_style="brief",
                typical_issues=[
                    TicketTemplate.SYSTEM_UPGRADE,
                    TicketTemplate.NETWORK_CONNECTIVITY,
                    TicketTemplate.HARDWARE_FAILURE,
                    TicketTemplate.VIRUS_MALWARE
                ],
                escalation_tendency=0.2,
                satisfaction_bias=0.4
            )
        ]
    
    def _create_ticket_scenarios(self) -> Dict[TicketTemplate, TicketScenario]:
        """Create realistic ticket scenarios."""
        return {
            TicketTemplate.SOFTWARE_CRASH: TicketScenario(
                template=TicketTemplate.SOFTWARE_CRASH,
                title_templates=[
                    "{software} si è bloccato improvvisamente",
                    "Errore critico in {software}",
                    "{software} non risponde e si chiude da solo",
                    "Crash frequenti di {software} durante il lavoro"
                ],
                description_templates=[
                    "Stavo lavorando su {software} quando improvvisamente si è chiuso senza salvare il mio lavoro. Questo succede {frequency}. Messaggio di errore: {error_msg}",
                    "Durante l'utilizzo di {software}, l'applicazione va in crash con il codice errore {error_code}. Ho perso {work_lost}. Urgente aiuto!",
                    "{software} continua a bloccarsi quando cerco di {action}. Ho già provato a riavviare il computer ma il problema persiste."
                ],
                category=TicketCategory.SOFTWARE,
                priority_weights={1: 0.1, 2: 0.2, 3: 0.4, 4: 0.2, 5: 0.1},
                typical_resolution_time=(30, 180),
                common_tags=["crash", "software", "urgente", "perdita-dati"],
                affected_systems=["Microsoft Office", "Adobe Creative Suite", "ERP", "CRM", "Browser"],
                resolution_templates=[
                    "Riavvio del servizio {service} e pulizia cache applicazione",
                    "Aggiornamento di {software} alla versione più recente",
                    "Ripristino file di configurazione corrotti",
                    "Reinstallazione completa di {software}"
                ],
                escalation_probability=0.3
            ),
            
            TicketTemplate.SLOW_PERFORMANCE: TicketScenario(
                template=TicketTemplate.SLOW_PERFORMANCE,
                title_templates=[
                    "Il computer è molto lento",
                    "Prestazioni degradate del sistema",
                    "Avvio lento e applicazioni che si bloccano",
                    "Rallentamenti estremi durante il lavoro"
                ],
                description_templates=[
                    "Il mio computer è diventato estremamente lento negli ultimi {timeframe}. L'avvio richiede {boot_time} minuti e le applicazioni impiegano molto tempo ad aprirsi.",
                    "Da quando ho installato {recent_software}, il sistema è rallentato significativamente. Le prestazioni sono {performance_level}.",
                    "Problemi di performance generalizzati: {symptoms}. Questo influisce sulla mia produttività."
                ],
                category=TicketCategory.HARDWARE,
                priority_weights={1: 0.05, 2: 0.4, 3: 0.4, 4: 0.1, 5: 0.05},
                typical_resolution_time=(45, 240),
                common_tags=["performance", "lentezza", "ottimizzazione", "hardware"],
                affected_systems=["Windows", "macOS", "Hardware", "Storage"],
                resolution_templates=[
                    "Pulizia disco e deframmentazione",
                    "Aggiornamento driver e sistema operativo",
                    "Scansione antivirus e rimozione malware",
                    "Upgrade RAM o sostituzione disco rigido"
                ],
                escalation_probability=0.2
            ),
            
            TicketTemplate.LOGIN_ISSUES: TicketScenario(
                template=TicketTemplate.LOGIN_ISSUES,
                title_templates=[
                    "Non riesco ad accedere al sistema",
                    "Problemi di login con Active Directory",
                    "Password non accettata",
                    "Accesso negato alle applicazioni aziendali"
                ],
                description_templates=[
                    "Da questa mattina non riesco più ad accedere a {system}. Inserisco le credenziali corrette ma ricevo il messaggio '{error_message}'.",
                    "Il mio account sembra essere bloccato. Non riesco ad accedere a {systems}. Ho bisogno di accesso urgente per {business_need}.",
                    "Password rifiutata per {system}. Ho provato più volte ma continua a dirmi che le credenziali sono errate."
                ],
                category=TicketCategory.ACCESS,
                priority_weights={1: 0.05, 2: 0.1, 3: 0.5, 4: 0.3, 5: 0.05},
                typical_resolution_time=(15, 60),
                common_tags=["login", "accesso", "password", "autenticazione"],
                affected_systems=["Active Directory", "VPN", "Email", "ERP", "SharePoint"],
                resolution_templates=[
                    "Reset password e sblocco account utente",
                    "Sincronizzazione credenziali Active Directory",
                    "Verifica permessi e gruppi di sicurezza",
                    "Riconfigurazione certificati di autenticazione"
                ],
                escalation_probability=0.1
            ),
            
            TicketTemplate.EMAIL_PROBLEMS: TicketScenario(
                template=TicketTemplate.EMAIL_PROBLEMS,
                title_templates=[
                    "Problemi con la ricezione email",
                    "Outlook non sincronizza le email",
                    "Non riesco ad inviare email",
                    "Errori di connessione server email"
                ],
                description_templates=[
                    "Da {timeframe} non ricevo più email. L'ultima email ricevuta risale a {last_email_time}. Outlook mostra {error_status}.",
                    "Quando provo ad inviare email ricevo l'errore '{error_message}'. Il problema è iniziato {when_started}.",
                    "La casella email non si sincronizza correttamente. Mancano email importanti e ho problemi con {specific_issues}."
                ],
                category=TicketCategory.SOFTWARE,
                priority_weights={1: 0.1, 2: 0.3, 3: 0.4, 4: 0.15, 5: 0.05},
                typical_resolution_time=(20, 90),
                common_tags=["email", "outlook", "sincronizzazione", "server"],
                affected_systems=["Microsoft Outlook", "Exchange Server", "SMTP", "IMAP"],
                resolution_templates=[
                    "Riconfigurazione profilo Outlook",
                    "Riparazione file PST corrotti",
                    "Aggiornamento impostazioni server email",
                    "Reset cache e ricostruzione indice email"
                ],
                escalation_probability=0.2
            ),
            
            TicketTemplate.PRINTER_ISSUES: TicketScenario(
                template=TicketTemplate.PRINTER_ISSUES,
                title_templates=[
                    "La stampante non funziona",
                    "Problemi di stampa su {printer_model}",
                    "Errore stampante: {error_code}",
                    "Impossibile stampare documenti"
                ],
                description_templates=[
                    "La stampante {printer_name} al {location} non stampa. Il led mostra {led_status} e compare il messaggio '{error_message}'.",
                    "Quando invio documenti alla stampante, questi rimangono in coda ma non vengono stampati. Ho provato {attempted_solutions}.",
                    "Problemi di qualità di stampa: {print_quality_issues}. La stampante necessita di {maintenance_needed}."
                ],
                category=TicketCategory.HARDWARE,
                priority_weights={1: 0.3, 2: 0.4, 3: 0.2, 4: 0.08, 5: 0.02},
                typical_resolution_time=(15, 45),
                common_tags=["stampante", "stampa", "hardware", "driver"],
                affected_systems=["Stampanti HP", "Stampanti Canon", "Server di stampa", "Driver"],
                resolution_templates=[
                    "Sostituzione cartucce e pulizia testine",
                    "Reinstallazione driver stampante",
                    "Reset coda di stampa e servizio spooler",
                    "Configurazione rete stampante"
                ],
                escalation_probability=0.1
            ),
            
            TicketTemplate.NETWORK_CONNECTIVITY: TicketScenario(
                template=TicketTemplate.NETWORK_CONNECTIVITY,
                title_templates=[
                    "Nessuna connessione internet",
                    "Problemi di rete intermittenti",
                    "Disconnessioni frequenti dal Wi-Fi",
                    "Impossibile accedere alle risorse di rete"
                ],
                description_templates=[
                    "Da {timeframe} non riesco più a connettermi a internet. Il computer mostra {connection_status} ma non riesco ad aprire nessun sito web.",
                    "La connessione di rete è instabile: {symptoms}. Questo compromette il mio lavoro su {affected_work}.",
                    "Impossibile accedere a {network_resources}. L'errore che compare è '{network_error}'."
                ],
                category=TicketCategory.NETWORK,
                priority_weights={1: 0.05, 2: 0.15, 3: 0.35, 4: 0.35, 5: 0.1},
                typical_resolution_time=(30, 120),
                common_tags=["rete", "connettività", "wifi", "internet"],
                affected_systems=["Router", "Switch", "Wi-Fi", "Cablaggio", "Firewall"],
                resolution_templates=[
                    "Reset configurazione di rete e rinnovo IP",
                    "Verifica cablaggio e sostituzione cavi",
                    "Aggiornamento driver scheda di rete",
                    "Riconfigurazione router e access point"
                ],
                escalation_probability=0.4
            ),
            
            TicketTemplate.HARDWARE_FAILURE: TicketScenario(
                template=TicketTemplate.HARDWARE_FAILURE,
                title_templates=[
                    "Guasto hardware: {component}",
                    "Il computer non si accende",
                    "Errori disco rigido",
                    "Problemi scheda video/audio"
                ],
                description_templates=[
                    "Il componente {hardware_component} sembra essere guasto. Sintomi: {failure_symptoms}. Il computer {computer_status}.",
                    "Errori hardware critici rilevati durante l'avvio: {error_codes}. Il sistema {system_behavior}.",
                    "Problemi con {failing_component}: {specific_issues}. Ho bisogno di {business_impact}."
                ],
                category=TicketCategory.HARDWARE,
                priority_weights={1: 0.02, 2: 0.08, 3: 0.2, 4: 0.4, 5: 0.3},
                typical_resolution_time=(60, 480),
                common_tags=["hardware", "guasto", "sostituzione", "riparazione"],
                affected_systems=["CPU", "RAM", "Hard Disk", "Scheda Madre", "Alimentatore"],
                resolution_templates=[
                    "Sostituzione componente hardware difettoso",
                    "Diagnosi approfondita e riparazione",
                    "Backup dati e migrazione su nuovo hardware",
                    "Reinstallazione sistema operativo post-riparazione"
                ],
                escalation_probability=0.5
            ),
            
            TicketTemplate.SECURITY_INCIDENT: TicketScenario(
                template=TicketTemplate.SECURITY_INCIDENT,
                title_templates=[
                    "Sospetta attività malevola",
                    "Possibile violazione sicurezza",
                    "Email di phishing ricevuta",
                    "Comportamento anomalo del sistema"
                ],
                description_templates=[
                    "Ho ricevuto un'email sospetta da {sender} con oggetto '{subject}'. Contiene {suspicious_content}. Non ho cliccato su nulla.",
                    "Il mio computer si comporta in modo strano: {anomalous_behavior}. Temo possa essere stato compromesso.",
                    "Possibile tentativo di accesso non autorizzato al mio account: {security_indicators}."
                ],
                category=TicketCategory.SECURITY,
                priority_weights={1: 0.01, 2: 0.04, 3: 0.15, 4: 0.3, 5: 0.5},
                typical_resolution_time=(45, 300),
                common_tags=["sicurezza", "malware", "phishing", "incidente"],
                affected_systems=["Firewall", "Antivirus", "EDR", "Email Security"],
                resolution_templates=[
                    "Scansione completa antimalware e quarantena",
                    "Analisi forense e isolamento sistema",
                    "Reset credenziali e rafforzamento sicurezza",
                    "Implementazione misure preventive aggiuntive"
                ],
                escalation_probability=0.8
            )
        }
    
    def generate_realistic_tickets(
        self,
        count: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_personas: Optional[List[UserPersona]] = None,
        include_resolution: bool = True,
        temporal_patterns: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Generate realistic tickets with various scenarios and patterns.
        
        Args:
            count: Number of tickets to generate
            start_date: Start date for ticket creation
            end_date: End date for ticket creation
            user_personas: Specific personas to use (default: all)
            include_resolution: Whether to include resolution data
            temporal_patterns: Whether to apply realistic temporal patterns
            
        Returns:
            List of generated ticket data
        """
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=90)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        
        personas = user_personas or self.user_personas
        tickets = []
        
        logger.info(f"Generating {count} realistic tickets from {start_date} to {end_date}")
        
        for i in range(count):
            # Select random persona
            persona = random.choice(personas)
            
            # Select ticket template based on persona's typical issues
            template = random.choice(persona.typical_issues)
            scenario = self.ticket_scenarios[template]
            
            # Generate creation time with temporal patterns
            if temporal_patterns:
                created_at = self._generate_realistic_timestamp(start_date, end_date)
            else:
                created_at = self.fake.date_time_between(start_date, end_date, tzinfo=timezone.utc)
            
            # Generate ticket data
            ticket_data = self._generate_ticket_from_scenario(
                scenario, persona, created_at, include_resolution
            )
            
            tickets.append(ticket_data)
            
            if (i + 1) % 100 == 0:
                logger.info(f"Generated {i + 1}/{count} tickets")
        
        logger.info(f"Successfully generated {len(tickets)} tickets")
        return tickets
    
    def generate_edge_cases(self) -> List[Dict[str, Any]]:
        """Generate edge case tickets for testing."""
        edge_cases = []
        
        # Extremely long descriptions
        edge_cases.append({
            "title": "Descrizione estremamente lunga per test limite",
            "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 50,
            "priority": 1,
            "category": "general",
            "user_id": str(uuid.uuid4()),
            "tags": ["test", "edge-case", "long-description"]
        })
        
        # Very short descriptions (minimum length)
        edge_cases.append({
            "title": "Test",
            "description": "Problema.",
            "priority": 5,
            "category": "software",
            "user_id": str(uuid.uuid4()),
            "tags": ["test", "edge-case", "short"]
        })
        
        # Special characters and unicode
        edge_cases.append({
            "title": "Errore con caratteri speciali: àèìòù €£$",
            "description": "Problema con caratteri speciali: àèìòù €£$ e emoji 🖥️💻🔧",
            "priority": 3,
            "category": "software",
            "user_id": str(uuid.uuid4()),
            "tags": ["test", "unicode", "special-chars"]
        })
        
        # Maximum priority with urgent timeline
        edge_cases.append({
            "title": "EMERGENZA: Sistema produzione completamente down",
            "description": "Tutti i sistemi di produzione sono offline. Perdita economica stimata €10.000/ora. Intervento immediato richiesto.",
            "priority": 5,
            "category": "hardware",
            "user_id": str(uuid.uuid4()),
            "business_impact": "Blocco totale produzione aziendale",
            "urgency_justification": "Perdita economica critica",
            "tags": ["emergenza", "produzione", "critico"]
        })
        
        # Ticket with many tags
        edge_cases.append({
            "title": "Test con molti tag",
            "description": "Ticket di test per verificare gestione tag multipli",
            "priority": 2,
            "category": "general",
            "user_id": str(uuid.uuid4()),
            "tags": [f"tag{i}" for i in range(20)]
        })
        
        # Ticket with complex affected systems
        edge_cases.append({
            "title": "Problemi multipli sistemi interconnessi",
            "description": "Cascata di errori che coinvolge molteplici sistemi aziendali interconnessi",
            "priority": 4,
            "category": "network",
            "user_id": str(uuid.uuid4()),
            "affected_systems": [
                "ERP SAP", "CRM Salesforce", "Email Exchange", "Active Directory",
                "Database SQL Server", "Backup Veeam", "Monitoring Nagios",
                "VPN Cisco", "Firewall SonicWall", "Switch HP"
            ],
            "tags": ["sistemi-multipli", "interconnessi", "cascata"]
        })
        
        return edge_cases
    
    def generate_stress_test_data(self, ticket_count: int = 1000) -> List[Dict[str, Any]]:
        """Generate large dataset for stress testing."""
        logger.info(f"Generating {ticket_count} tickets for stress testing")
        
        # Generate tickets with high concurrency scenario
        tickets = []
        
        # Peak load scenario (many tickets in short time)
        peak_start = datetime.now(timezone.utc) - timedelta(hours=2)
        peak_end = datetime.now(timezone.utc) - timedelta(hours=1)
        
        for i in range(ticket_count):
            # Most tickets in peak period
            if i < ticket_count * 0.7:
                created_at = self.fake.date_time_between(peak_start, peak_end, tzinfo=timezone.utc)
            else:
                created_at = self.fake.date_time_between(
                    datetime.now(timezone.utc) - timedelta(days=30),
                    datetime.now(timezone.utc),
                    tzinfo=timezone.utc
                )
            
            persona = random.choice(self.user_personas)
            template = random.choice(persona.typical_issues)
            scenario = self.ticket_scenarios[template]
            
            ticket = self._generate_ticket_from_scenario(scenario, persona, created_at, True)
            tickets.append(ticket)
        
        return tickets
    
    def create_sample_users(self, count: int = 50) -> List[Dict[str, Any]]:
        """Create sample users for testing."""
        departments = [
            "IT", "HR", "Finance", "Sales", "Marketing", 
            "Operations", "Engineering", "Support"
        ]
        
        roles = {
            "IT": ["System Admin", "Developer", "Support Technician", "IT Manager"],
            "HR": ["HR Specialist", "Recruiter", "HR Manager", "Payroll Specialist"],
            "Finance": ["Accountant", "Financial Analyst", "CFO", "Bookkeeper"],
            "Sales": ["Sales Rep", "Sales Manager", "Account Manager", "Sales Director"],
            "Marketing": ["Marketing Specialist", "Content Creator", "Marketing Manager"],
            "Operations": ["Operations Manager", "Process Analyst", "Operations Coordinator"],
            "Engineering": ["Software Engineer", "QA Engineer", "DevOps Engineer", "Architect"],
            "Support": ["Customer Support", "Technical Support", "Support Manager"]
        }
        
        users = []
        for i in range(count):
            department = random.choice(departments)
            role = random.choice(roles.get(department, ["Employee"]))
            
            user_data = {
                "username": self.fake.user_name(),
                "email": self.fake.email(),
                "full_name": self.fake.name(),
                "phone": self.fake.phone_number(),
                "department": department,
                "role": role,
                "location": self.fake.city(),
                "language": "it",
                "timezone": "Europe/Rome",
                "is_active": True,
                "is_admin": random.random() < 0.1  # 10% chance of being admin
            }
            users.append(user_data)
        
        return users
    
    def _generate_realistic_timestamp(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> datetime:
        """Generate timestamp following realistic patterns."""
        # Higher probability during business hours and weekdays
        
        # Random base time
        base_time = self.fake.date_time_between(start_date, end_date, tzinfo=timezone.utc)
        
        # Adjust for business patterns
        if random.random() < 0.7:  # 70% during business hours
            # Business hours (8 AM - 6 PM)
            hour = random.randint(self.business_hours[0], self.business_hours[1])
            minute = random.randint(0, 59)
            base_time = base_time.replace(hour=hour, minute=minute)
            
            # Prefer weekdays
            while base_time.weekday() not in self.business_days and random.random() < 0.8:
                base_time += timedelta(days=1)
        
        return base_time
    
    def _generate_ticket_from_scenario(
        self,
        scenario: TicketScenario,
        persona: UserPersona,
        created_at: datetime,
        include_resolution: bool
    ) -> Dict[str, Any]:
        """Generate ticket from scenario and persona."""
        # Select random templates
        title_template = random.choice(scenario.title_templates)
        description_template = random.choice(scenario.description_templates)
        
        # Generate context variables
        context = self._generate_context_variables(scenario, persona)
        
        # Fill templates
        try:
            title = title_template.format(**context)
            description = description_template.format(**context)
        except KeyError:
            # Fallback if template variables missing
            title = title_template
            description = description_template
        
        # Select priority based on weights
        priority = random.choices(
            list(scenario.priority_weights.keys()),
            weights=list(scenario.priority_weights.values())
        )[0]
        
        # Adjust priority based on persona
        if persona.escalation_tendency > 0.7 and random.random() < 0.3:
            priority = min(5, priority + 1)
        
        # Generate basic ticket data
        ticket_data = {
            "title": title,
            "description": description,
            "priority": priority,
            "category": scenario.category.value,
            "user_id": str(uuid.uuid4()),  # Would be real user ID in production
            "tags": random.choices(scenario.common_tags, k=random.randint(1, 4)),
            "created_at": created_at,
            "affected_systems": random.choices(scenario.affected_systems, k=random.randint(1, 3)),
            "business_impact": self._generate_business_impact(priority, scenario),
        }
        
        # Add resolution if requested and ticket is old enough
        if include_resolution:
            resolution_data = self._generate_resolution_data(
                scenario, persona, created_at, priority
            )
            ticket_data.update(resolution_data)
        
        return ticket_data
    
    def _generate_context_variables(
        self, 
        scenario: TicketScenario, 
        persona: UserPersona
    ) -> Dict[str, Any]:
        """Generate context variables for templates."""
        software_apps = [
            "Microsoft Word", "Excel", "PowerPoint", "Outlook",
            "Adobe Acrobat", "Chrome", "Firefox", "SAP", "Salesforce"
        ]
        
        error_messages = [
            "Applicazione non risponde",
            "Errore di memoria insufficiente",
            "Accesso negato",
            "File corrotto o danneggiato",
            "Connessione al server persa"
        ]
        
        frequencies = [
            "ogni giorno", "più volte al giorno", "occasionalmente",
            "da questa mattina", "da ieri", "dalla settimana scorsa"
        ]
        
        return {
            "software": random.choice(software_apps),
            "error_msg": random.choice(error_messages),
            "error_code": f"0x{random.randint(1000, 9999):04X}",
            "frequency": random.choice(frequencies),
            "timeframe": random.choice(["ieri", "questa mattina", "2 giorni", "una settimana"]),
            "work_lost": random.choice(["2 ore di lavoro", "un documento importante", "tutto il progetto"]),
            "action": random.choice(["aprire un file", "salvare", "stampare", "inviare email"]),
            "boot_time": random.randint(5, 15),
            "recent_software": random.choice(software_apps),
            "performance_level": random.choice(["pessime", "inaccettabili", "molto lente"]),
            "system": random.choice(["Windows", "Office 365", "VPN aziendale"]),
            "error_message": random.choice(error_messages),
            "business_need": random.choice([
                "una presentazione importante", 
                "completare il budget", 
                "rispondere ai clienti"
            ]),
            "printer_name": f"HP-{random.randint(1000, 9999)}",
            "printer_model": random.choice(["HP LaserJet", "Canon Pixma", "Epson WorkForce"]),
            "location": random.choice(["primo piano", "ufficio 205", "sala riunioni", "reception"]),
            "error_code": f"E{random.randint(100, 999)}",
            "led_status": random.choice(["rosso fisso", "giallo lampeggiante", "spento"]),
            "connection_status": random.choice([
                "connesso ma senza internet", 
                "disconnesso", 
                "connessione limitata"
            ]),
            "network_error": random.choice([
                "Timeout connessione",
                "Server non raggiungibile", 
                "DNS non risolve"
            ]),
            "hardware_component": random.choice(["disco rigido", "RAM", "scheda video"]),
            "failure_symptoms": random.choice([
                "rumori strani", "schermate blu", "riavvii casuali"
            ]),
            "sender": self.fake.email(),
            "subject": random.choice([
                "Aggiornamento urgente sicurezza",
                "Verifica account necessaria",
                "Problema con il pagamento"
            ]),
            "suspicious_content": random.choice([
                "link sospetti", "allegati strani", "richiesta password"
            ])
        }
    
    def _generate_business_impact(self, priority: int, scenario: TicketScenario) -> Optional[str]:
        """Generate business impact description based on priority."""
        if priority <= 2:
            return None
        
        impacts = {
            3: [
                "Ridotta produttività per l'utente",
                "Ritardi nelle attività quotidiane",
                "Difficoltà nella comunicazione con clienti"
            ],
            4: [
                "Blocco parziale delle operazioni",
                "Impatto su team di lavoro",
                "Ritardi in progetti critici"
            ],
            5: [
                "Blocco totale delle operazioni",
                "Perdita economica significativa",
                "Impatto su clienti esterni"
            ]
        }
        
        return random.choice(impacts.get(priority, impacts[3]))
    
    def _generate_resolution_data(
        self,
        scenario: TicketScenario,
        persona: UserPersona,
        created_at: datetime,
        priority: int
    ) -> Dict[str, Any]:
        """Generate resolution data for completed tickets."""
        now = datetime.now(timezone.utc)
        
        # Skip resolution for very recent tickets
        if (now - created_at).total_seconds() < 1800:  # Less than 30 minutes
            return {"status": TicketStatus.OPEN.value}
        
        # Determine if ticket should be resolved
        age_hours = (now - created_at).total_seconds() / 3600
        resolution_probability = min(0.95, age_hours / 24)  # Higher chance for older tickets
        
        if random.random() > resolution_probability:
            # Ticket still in progress
            statuses = [TicketStatus.IN_PROGRESS.value, TicketStatus.PENDING_USER.value]
            return {
                "status": random.choice(statuses),
                "assigned_to": str(uuid.uuid4())  # Would be real user ID
            }
        
        # Generate resolution
        resolution_time = random.randint(*scenario.typical_resolution_time)
        resolved_at = created_at + timedelta(minutes=resolution_time)
        
        # Adjust resolution time based on priority
        if priority >= 4:
            resolution_time = int(resolution_time * 0.7)  # Faster for high priority
        
        # Generate satisfaction based on persona bias and resolution time
        base_satisfaction = 4.0 + persona.satisfaction_bias
        
        # Adjust based on resolution speed
        expected_time = (scenario.typical_resolution_time[0] + scenario.typical_resolution_time[1]) / 2
        if resolution_time < expected_time * 0.8:
            base_satisfaction += 0.5  # Quick resolution
        elif resolution_time > expected_time * 1.5:
            base_satisfaction -= 0.8  # Slow resolution
        
        satisfaction = max(1, min(5, int(base_satisfaction + random.gauss(0, 0.3))))
        
        return {
            "status": random.choice([TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value]),
            "assigned_to": str(uuid.uuid4()),
            "actual_resolution_time": resolution_time,
            "resolved_at": resolved_at,
            "closed_at": resolved_at + timedelta(hours=random.randint(1, 24)),
            "solution": random.choice(scenario.resolution_templates),
            "customer_satisfaction": satisfaction
        }
    
    async def populate_database_with_test_data(
        self,
        ticket_count: int = 500,
        user_count: int = 50,
        days_back: int = 90
    ) -> Dict[str, int]:
        """Populate database with comprehensive test data."""
        try:
            logger.info(f"Populating database with test data: {user_count} users, {ticket_count} tickets")
            
            user_repo = get_user_repository()
            ticket_repo = get_ticket_repository()
            
            # Create sample users
            users_data = self.create_sample_users(user_count)
            created_users = 0
            
            for user_data in users_data:
                try:
                    user_repo.create(user_data)
                    created_users += 1
                except Exception as e:
                    logger.warning(f"Failed to create user: {e}")
            
            # Get created users for ticket assignment
            all_users = user_repo.get_all()
            if not all_users:
                raise ValueError("No users available for ticket creation")
            
            # Generate realistic tickets
            start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            tickets_data = self.generate_realistic_tickets(
                count=ticket_count,
                start_date=start_date,
                include_resolution=True,
                temporal_patterns=True
            )
            
            created_tickets = 0
            for ticket_data in tickets_data:
                try:
                    # Assign to real user
                    ticket_data["user_id"] = random.choice(all_users).id
                    ticket_repo.create(ticket_data)
                    created_tickets += 1
                except Exception as e:
                    logger.warning(f"Failed to create ticket: {e}")
            
            # Generate some edge cases
            edge_cases = self.generate_edge_cases()
            edge_cases_created = 0
            
            for edge_case in edge_cases:
                try:
                    edge_case["user_id"] = random.choice(all_users).id
                    ticket_repo.create(edge_case)
                    edge_cases_created += 1
                except Exception as e:
                    logger.warning(f"Failed to create edge case: {e}")
            
            result = {
                "users_created": created_users,
                "tickets_created": created_tickets,
                "edge_cases_created": edge_cases_created,
                "total_records": created_users + created_tickets + edge_cases_created
            }
            
            logger.info(f"Database populated successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to populate database: {e}")
            raise