"""Advanced conversation management with state tracking, summarization, and analytics."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import re

from loguru import logger

from .llm_service import LLMService, GenerationParams
from .prompt_manager import PromptManager, TaskType


class ConversationState(Enum):
    """Conversation states."""
    INITIATED = "initiated"
    ACTIVE = "active" 
    WAITING_USER = "waiting_user"
    WAITING_SYSTEM = "waiting_system"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ABANDONED = "abandoned"


class MessageType(Enum):
    """Message types in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESULT = "function_result"
    SUMMARY = "summary"


class SentimentPolarity(Enum):
    """Sentiment polarity levels."""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class IntentType(Enum):
    """User intent types."""
    PROBLEM_REPORT = "problem_report"
    INFORMATION_REQUEST = "information_request"
    FOLLOW_UP = "follow_up"
    COMPLAINT = "complaint"
    PRAISE = "praise"
    ESCALATION_REQUEST = "escalation_request"
    CLOSURE_REQUEST = "closure_request"
    OTHER = "other"


@dataclass
class Entity:
    """Extracted entity from conversation."""
    type: str  # person, software, hardware, error_code, etc.
    value: str
    confidence: float
    start_pos: int = 0
    end_pos: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMessage:
    """Individual message in conversation."""
    id: str
    conversation_id: str
    message_type: MessageType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Analytics
    sentiment: Optional[SentimentPolarity] = None
    intent: Optional[IntentType] = None
    entities: List[Entity] = field(default_factory=list)
    confidence: float = 0.0
    processing_time: float = 0.0


@dataclass
class ConversationSummary:
    """Summary of conversation segment."""
    id: str
    conversation_id: str
    summary_text: str
    key_points: List[str] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)
    resolution_status: str = "unresolved"
    created_at: datetime = field(default_factory=datetime.now)
    messages_count: int = 0
    time_span: str = ""


@dataclass
class ConversationContext:
    """Conversation context and state."""
    conversation_id: str
    user_id: str
    session_id: str
    state: ConversationState = ConversationState.INITIATED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    # Conversation data
    messages: List[ConversationMessage] = field(default_factory=list)
    summaries: List[ConversationSummary] = field(default_factory=list)
    
    # Tracked entities and context
    persistent_entities: Dict[str, Entity] = field(default_factory=dict)
    current_topic: Optional[str] = None
    intent_history: List[IntentType] = field(default_factory=list)
    
    # Analytics and metrics
    total_messages: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    avg_response_time: float = 0.0
    satisfaction_score: Optional[float] = None
    escalation_count: int = 0
    
    # Sentiment tracking
    sentiment_history: List[Tuple[datetime, SentimentPolarity]] = field(default_factory=list)
    current_sentiment: SentimentPolarity = SentimentPolarity.NEUTRAL
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationManager:
    """Advanced conversation management system."""
    
    def __init__(self,
                 llm_service: LLMService,
                 prompt_manager: PromptManager,
                 max_context_length: int = 8000,
                 summarization_threshold: int = 20,  # messages
                 auto_summarize: bool = True,
                 sentiment_tracking: bool = True,
                 entity_tracking: bool = True,
                 conversation_timeout: int = 3600):  # seconds
        """Initialize conversation manager.
        
        Args:
            llm_service: LLM service for processing
            prompt_manager: Prompt manager for templates
            max_context_length: Maximum context length in tokens
            summarization_threshold: Message count to trigger summarization
            auto_summarize: Enable automatic summarization
            sentiment_tracking: Enable sentiment analysis
            entity_tracking: Enable entity extraction
            conversation_timeout: Conversation timeout in seconds
        """
        self.llm_service = llm_service
        self.prompt_manager = prompt_manager
        self.max_context_length = max_context_length
        self.summarization_threshold = summarization_threshold
        self.auto_summarize = auto_summarize
        self.sentiment_tracking = sentiment_tracking
        self.entity_tracking = entity_tracking
        self.conversation_timeout = conversation_timeout
        
        # Storage
        self.conversations: Dict[str, ConversationContext] = {}
        self.active_sessions: Dict[str, str] = {}  # session_id -> conversation_id
        
        # Entity patterns for extraction
        self.entity_patterns = {
            'software': [
                r'\b(?:microsoft|office|excel|word|powerpoint|outlook|windows|chrome|firefox|adobe|photoshop|acrobat)\b',
                r'\b(?:software|programma|applicazione)\s+[\w\s]+',
            ],
            'hardware': [
                r'\b(?:computer|laptop|desktop|stampante|printer|mouse|tastiera|keyboard|monitor|schermo)\b',
                r'\b(?:pc|server|workstation|tablet)\b',
            ],
            'error_code': [
                r'\b(?:errore|error)\s+(?:codice\s+)?[A-Z]?[\d\-]+\b',
                r'\b0x[a-fA-F0-9]{8}\b',
            ],
            'ip_address': [
                r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            ],
            'email': [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            ],
            'phone': [
                r'\b(?:\+39\s?)?(?:[\d\s\-\.]{10,})\b',
            ],
            'asset_id': [
                r'\b[A-Z]{2,4}[\d]{3,6}\b',  # IT001234
                r'\b(?:asset|bene|id)\s+[\w\-]+\b',
            ]
        }
        
        # Italian sentiment keywords
        self.sentiment_keywords = {
            SentimentPolarity.VERY_NEGATIVE: [
                'pessimo', 'orribile', 'terribile', 'odio', 'schifo', 'inutile', 'disastro'
            ],
            SentimentPolarity.NEGATIVE: [
                'cattivo', 'male', 'problema', 'errore', 'non funziona', 'rotto', 'difficile', 'frustrato'
            ],
            SentimentPolarity.NEUTRAL: [
                'ok', 'normale', 'standard', 'così così', 'neutro'
            ],
            SentimentPolarity.POSITIVE: [
                'bene', 'buono', 'funziona', 'ok', 'risolto', 'grazie', 'perfetto'
            ],
            SentimentPolarity.VERY_POSITIVE: [
                'ottimo', 'eccellente', 'fantastico', 'perfetto', 'eccezionale', 'meraviglioso'
            ]
        }
        
        # Intent detection patterns
        self.intent_patterns = {
            IntentType.PROBLEM_REPORT: [
                r'\b(?:problema|errore|non funziona|rotto|guasto|difetto)\b',
                r'\b(?:help|aiuto|supporto)\b'
            ],
            IntentType.INFORMATION_REQUEST: [
                r'\b(?:come|cosa|quando|dove|perché|chi|quale)\b',
                r'\b(?:informazioni|dettagli|spiegazione)\b'
            ],
            IntentType.FOLLOW_UP: [
                r'\b(?:aggiornamento|novità|stato|situazione)\b',
                r'\b(?:ancora|sempre|continua)\b'
            ],
            IntentType.COMPLAINT: [
                r'\b(?:lamento|protesta|insoddisfatto|arrabbiato)\b',
                r'\b(?:manager|responsabile|superiore)\b'
            ],
            IntentType.ESCALATION_REQUEST: [
                r'\b(?:escalation|livello superiore|manager|responsabile)\b',
                r'\b(?:parlare con|contattare)\b'
            ],
            IntentType.CLOSURE_REQUEST: [
                r'\b(?:chiudi|chiudere|risolto|completato|finito)\b',
                r'\b(?:grazie|ringrazio|apprezzo)\b'
            ]
        }
        
        logger.info("ConversationManager initialized")
    
    async def start_conversation(self, 
                                user_id: str, 
                                session_id: str,
                                initial_message: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start new conversation.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            initial_message: Optional initial message
            metadata: Optional metadata
            
        Returns:
            Conversation ID
        """
        conversation_id = str(uuid.uuid4())
        
        context = ConversationContext(
            conversation_id=conversation_id,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {}
        )
        
        self.conversations[conversation_id] = context
        self.active_sessions[session_id] = conversation_id
        
        # Add initial message if provided
        if initial_message:
            await self.add_message(
                conversation_id=conversation_id,
                message_type=MessageType.USER,
                content=initial_message
            )
        
        logger.info(f"Started conversation {conversation_id} for user {user_id}")
        return conversation_id
    
    async def add_message(self,
                         conversation_id: str,
                         message_type: MessageType,
                         content: str,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add message to conversation.
        
        Args:
            conversation_id: Conversation ID
            message_type: Type of message
            content: Message content
            metadata: Optional metadata
            
        Returns:
            Message ID
        """
        context = self.conversations.get(conversation_id)
        if not context:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Create message
        message_id = str(uuid.uuid4())
        message = ConversationMessage(
            id=message_id,
            conversation_id=conversation_id,
            message_type=message_type,
            content=content,
            metadata=metadata or {}
        )
        
        # Analyze message
        await self._analyze_message(message, context)
        
        # Add to conversation
        context.messages.append(message)
        context.total_messages += 1
        context.last_activity = datetime.now()
        
        if message_type == MessageType.USER:
            context.user_messages += 1
        elif message_type == MessageType.ASSISTANT:
            context.assistant_messages += 1
        
        # Update conversation state
        if message_type == MessageType.USER:
            context.state = ConversationState.WAITING_SYSTEM
        elif message_type == MessageType.ASSISTANT:
            context.state = ConversationState.WAITING_USER
        
        # Check for auto-summarization
        if (self.auto_summarize and 
            len(context.messages) >= self.summarization_threshold and
            len(context.messages) % self.summarization_threshold == 0):
            await self._auto_summarize_conversation(conversation_id)
        
        logger.debug(f"Added message {message_id} to conversation {conversation_id}")
        return message_id
    
    async def _analyze_message(self, message: ConversationMessage, context: ConversationContext):
        """Analyze message for sentiment, intent, and entities."""
        try:
            start_time = datetime.now()
            
            # Sentiment analysis
            if self.sentiment_tracking:
                sentiment = await self._analyze_sentiment(message.content)
                message.sentiment = sentiment
                
                # Update context sentiment
                context.sentiment_history.append((message.timestamp, sentiment))
                context.current_sentiment = sentiment
            
            # Intent detection
            if message.message_type == MessageType.USER:
                intent = await self._detect_intent(message.content)
                message.intent = intent
                
                # Update intent history
                if intent:
                    context.intent_history.append(intent)
                    if len(context.intent_history) > 10:  # Keep last 10
                        context.intent_history.pop(0)
            
            # Entity extraction
            if self.entity_tracking:
                entities = await self._extract_entities(message.content)
                message.entities = entities
                
                # Update persistent entities
                for entity in entities:
                    key = f"{entity.type}_{entity.value}"
                    if key not in context.persistent_entities or entity.confidence > context.persistent_entities[key].confidence:
                        context.persistent_entities[key] = entity
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            message.processing_time = processing_time
            
        except Exception as e:
            logger.error(f"Message analysis failed: {e}")
    
    async def _analyze_sentiment(self, content: str) -> SentimentPolarity:
        """Analyze sentiment of message content."""
        content_lower = content.lower()
        
        # Count sentiment keywords
        sentiment_scores = {}
        
        for polarity, keywords in self.sentiment_keywords.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            sentiment_scores[polarity] = score
        
        # Find highest scoring sentiment
        if not any(sentiment_scores.values()):
            return SentimentPolarity.NEUTRAL
        
        return max(sentiment_scores.keys(), key=lambda k: sentiment_scores[k])
    
    async def _detect_intent(self, content: str) -> Optional[IntentType]:
        """Detect user intent from message content."""
        content_lower = content.lower()
        
        # Check patterns for each intent
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    return intent
        
        return IntentType.OTHER
    
    async def _extract_entities(self, content: str) -> List[Entity]:
        """Extract entities from message content."""
        entities = []
        
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    entity = Entity(
                        type=entity_type,
                        value=match.group(),
                        confidence=0.8,  # Simple confidence score
                        start_pos=match.start(),
                        end_pos=match.end()
                    )
                    entities.append(entity)
        
        return entities
    
    async def get_conversation_context(self, conversation_id: str, 
                                     max_messages: Optional[int] = None) -> str:
        """Get conversation context as formatted string.
        
        Args:
            conversation_id: Conversation ID
            max_messages: Maximum messages to include
            
        Returns:
            Formatted conversation context
        """
        context = self.conversations.get(conversation_id)
        if not context:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Get recent messages
        messages = context.messages
        if max_messages:
            messages = messages[-max_messages:]
        
        # Build context string
        context_parts = []
        
        # Add conversation metadata
        context_parts.append(f"CONVERSAZIONE ID: {conversation_id}")
        context_parts.append(f"STATO: {context.state.value}")
        context_parts.append(f"TOPIC CORRENTE: {context.current_topic or 'Non definito'}")
        
        # Add persistent entities
        if context.persistent_entities:
            entities_text = ", ".join([
                f"{entity.type}: {entity.value}" 
                for entity in context.persistent_entities.values()
            ])
            context_parts.append(f"ENTITÀ IDENTIFICATE: {entities_text}")
        
        # Add recent sentiment
        if context.current_sentiment != SentimentPolarity.NEUTRAL:
            context_parts.append(f"SENTIMENT UTENTE: {context.current_sentiment.value}")
        
        # Add summaries if available
        if context.summaries:
            latest_summary = context.summaries[-1]
            context_parts.append(f"RIASSUNTO PRECEDENTE: {latest_summary.summary_text}")
        
        # Add recent messages
        context_parts.append("\nSTORICO MESSAGGI:")
        
        for message in messages:
            role = "UTENTE" if message.message_type == MessageType.USER else "ASSISTENTE"
            timestamp = message.timestamp.strftime("%H:%M")
            context_parts.append(f"[{timestamp}] {role}: {message.content}")
        
        return "\n".join(context_parts)
    
    async def _auto_summarize_conversation(self, conversation_id: str) -> str:
        """Automatically summarize conversation segment."""
        context = self.conversations.get(conversation_id)
        if not context:
            return ""
        
        try:
            # Get messages to summarize (last segment)
            start_idx = max(0, len(context.messages) - self.summarization_threshold)
            messages_to_summarize = context.messages[start_idx:]
            
            # Build summarization prompt
            messages_text = "\n".join([
                f"{'UTENTE' if msg.message_type == MessageType.USER else 'ASSISTENTE'}: {msg.content}"
                for msg in messages_to_summarize
            ])
            
            summarization_prompt = f"""Riassumi la seguente parte di conversazione di supporto tecnico IT:

{messages_text}

Fornisci:
1. RIASSUNTO: Descrizione concisa dei problemi discussi e soluzioni proposte
2. PUNTI CHIAVE: Lista dei punti principali (max 5)
3. ENTITÀ: Software, hardware, codici errore menzionati
4. STATO: Risolto/In corso/Escalation necessaria

Mantieni un tono professionale e conciso."""
            
            # Generate summary
            response = await self.llm_service.generate(
                summarization_prompt,
                GenerationParams(max_tokens=500, temperature=0.3)
            )
            
            # Parse summary (simplified)
            summary_id = str(uuid.uuid4())
            summary = ConversationSummary(
                id=summary_id,
                conversation_id=conversation_id,
                summary_text=response.text,
                messages_count=len(messages_to_summarize),
                time_span=f"{messages_to_summarize[0].timestamp.strftime('%H:%M')} - {messages_to_summarize[-1].timestamp.strftime('%H:%M')}"
            )
            
            context.summaries.append(summary)
            
            logger.info(f"Auto-summarized conversation {conversation_id}")
            return summary_id
            
        except Exception as e:
            logger.error(f"Auto-summarization failed: {e}")
            return ""
    
    async def summarize_conversation(self, conversation_id: str, 
                                   custom_prompt: Optional[str] = None) -> str:
        """Manually summarize entire conversation.
        
        Args:
            conversation_id: Conversation ID
            custom_prompt: Optional custom summarization prompt
            
        Returns:
            Summary ID
        """
        context = self.conversations.get(conversation_id)
        if not context:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        try:
            # Build conversation history
            messages_text = "\n".join([
                f"[{msg.timestamp.strftime('%H:%M')}] {'UTENTE' if msg.message_type == MessageType.USER else 'ASSISTENTE'}: {msg.content}"
                for msg in context.messages
            ])
            
            # Use custom or default prompt
            if custom_prompt:
                prompt = custom_prompt.format(conversation=messages_text)
            else:
                prompt = f"""Crea un riassunto completo della seguente conversazione di supporto tecnico IT:

{messages_text}

STRUTTURA DEL RIASSUNTO:
1. PROBLEMA INIZIALE: Descrizione del problema riportato dall'utente
2. DIAGNOSI: Analisi effettuata e cause identificate
3. SOLUZIONI APPLICATE: Passi di risoluzione seguiti
4. RISULTATO: Stato finale della risoluzione
5. RACCOMANDAZIONI: Suggerimenti per prevenire problemi futuri
6. ENTITÀ COINVOLTE: Hardware, software, utenti, codici errore
7. METRICHE: Tempo di risoluzione, escalation, soddisfazione utente

Mantieni un formato professionale adatto per la documentazione IT."""
            
            # Generate summary
            response = await self.llm_service.generate(
                prompt,
                GenerationParams(max_tokens=1000, temperature=0.3)
            )
            
            # Create summary
            summary_id = str(uuid.uuid4())
            summary = ConversationSummary(
                id=summary_id,
                conversation_id=conversation_id,
                summary_text=response.text,
                key_points=self._extract_key_points(response.text),
                entities=list(context.persistent_entities.values()),
                messages_count=len(context.messages),
                time_span=f"{context.created_at.strftime('%Y-%m-%d %H:%M')} - {context.last_activity.strftime('%Y-%m-%d %H:%M')}"
            )
            
            context.summaries.append(summary)
            
            logger.info(f"Created manual summary for conversation {conversation_id}")
            return summary_id
            
        except Exception as e:
            logger.error(f"Manual summarization failed: {e}")
            raise
    
    def _extract_key_points(self, summary_text: str) -> List[str]:
        """Extract key points from summary text."""
        # Simple extraction based on numbered lists and bullet points
        key_points = []
        
        lines = summary_text.split('\n')
        for line in lines:
            line = line.strip()
            # Look for numbered points or bullet points
            if (re.match(r'^\d+\.', line) or 
                re.match(r'^[-•]', line) or
                'PROBLEMA:' in line.upper() or
                'SOLUZIONE:' in line.upper()):
                key_points.append(line)
        
        return key_points[:5]  # Max 5 key points
    
    async def update_conversation_state(self, 
                                       conversation_id: str, 
                                       new_state: ConversationState,
                                       reason: Optional[str] = None) -> None:
        """Update conversation state.
        
        Args:
            conversation_id: Conversation ID
            new_state: New conversation state
            reason: Optional reason for state change
        """
        context = self.conversations.get(conversation_id)
        if not context:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        old_state = context.state
        context.state = new_state
        context.updated_at = datetime.now()
        
        # Add system message for state change
        await self.add_message(
            conversation_id=conversation_id,
            message_type=MessageType.SYSTEM,
            content=f"Stato conversazione cambiato da {old_state.value} a {new_state.value}",
            metadata={'reason': reason, 'old_state': old_state.value}
        )
        
        # Track escalations
        if new_state == ConversationState.ESCALATED:
            context.escalation_count += 1
        
        logger.info(f"Conversation {conversation_id} state changed: {old_state.value} -> {new_state.value}")
    
    def get_conversation_analytics(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation analytics.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Analytics data
        """
        context = self.conversations.get(conversation_id)
        if not context:
            return {}
        
        # Calculate duration
        duration = (context.last_activity - context.created_at).total_seconds()
        
        # Sentiment analysis
        sentiment_counts = {}
        for _, sentiment in context.sentiment_history:
            sentiment_counts[sentiment.value] = sentiment_counts.get(sentiment.value, 0) + 1
        
        # Intent analysis
        intent_counts = {}
        for intent in context.intent_history:
            intent_counts[intent.value] = intent_counts.get(intent.value, 0) + 1
        
        return {
            'conversation_id': conversation_id,
            'user_id': context.user_id,
            'state': context.state.value,
            'duration_seconds': duration,
            'duration_formatted': str(timedelta(seconds=int(duration))),
            
            # Message statistics
            'total_messages': context.total_messages,
            'user_messages': context.user_messages,
            'assistant_messages': context.assistant_messages,
            'system_messages': context.total_messages - context.user_messages - context.assistant_messages,
            
            # Engagement metrics
            'avg_response_time': context.avg_response_time,
            'escalation_count': context.escalation_count,
            'satisfaction_score': context.satisfaction_score,
            
            # Content analysis
            'sentiment_distribution': sentiment_counts,
            'current_sentiment': context.current_sentiment.value,
            'intent_distribution': intent_counts,
            'entities_identified': len(context.persistent_entities),
            'summaries_created': len(context.summaries),
            
            # Topic analysis
            'current_topic': context.current_topic,
            'topic_changes': len(set(msg.metadata.get('topic') for msg in context.messages if 'topic' in msg.metadata)),
            
            # Timestamps
            'created_at': context.created_at.isoformat(),
            'updated_at': context.updated_at.isoformat(),
            'last_activity': context.last_activity.isoformat(),
        }
    
    def get_active_conversations(self, user_id: Optional[str] = None) -> List[str]:
        """Get list of active conversation IDs.
        
        Args:
            user_id: Optional user ID filter
            
        Returns:
            List of conversation IDs
        """
        active_states = {
            ConversationState.INITIATED,
            ConversationState.ACTIVE,
            ConversationState.WAITING_USER,
            ConversationState.WAITING_SYSTEM,
            ConversationState.ESCALATED
        }
        
        conversations = []
        for conv_id, context in self.conversations.items():
            if context.state in active_states:
                if user_id is None or context.user_id == user_id:
                    conversations.append(conv_id)
        
        return conversations
    
    async def cleanup_old_conversations(self, max_age_hours: int = 24) -> int:
        """Clean up old inactive conversations.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of conversations cleaned up
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        inactive_states = {
            ConversationState.RESOLVED,
            ConversationState.CLOSED,
            ConversationState.ABANDONED
        }
        
        to_remove = []
        for conv_id, context in self.conversations.items():
            if (context.state in inactive_states and 
                context.last_activity < cutoff_time):
                to_remove.append(conv_id)
        
        # Remove old conversations
        for conv_id in to_remove:
            context = self.conversations[conv_id]
            # Remove from active sessions
            if context.session_id in self.active_sessions:
                del self.active_sessions[context.session_id]
            # Remove conversation
            del self.conversations[conv_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old conversations")
        
        return len(to_remove)
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """Get conversation manager statistics."""
        # State distribution
        state_counts = {}
        for context in self.conversations.values():
            state = context.state.value
            state_counts[state] = state_counts.get(state, 0) + 1
        
        # Calculate average metrics
        total_conversations = len(self.conversations)
        if total_conversations > 0:
            avg_duration = sum(
                (ctx.last_activity - ctx.created_at).total_seconds()
                for ctx in self.conversations.values()
            ) / total_conversations
            
            avg_messages = sum(ctx.total_messages for ctx in self.conversations.values()) / total_conversations
            
            avg_satisfaction = sum(
                ctx.satisfaction_score for ctx in self.conversations.values() 
                if ctx.satisfaction_score is not None
            ) / len([ctx for ctx in self.conversations.values() if ctx.satisfaction_score is not None]) if any(
                ctx.satisfaction_score is not None for ctx in self.conversations.values()
            ) else 0
        else:
            avg_duration = avg_messages = avg_satisfaction = 0
        
        return {
            'total_conversations': total_conversations,
            'active_sessions': len(self.active_sessions),
            'state_distribution': state_counts,
            'average_duration_seconds': avg_duration,
            'average_messages_per_conversation': avg_messages,
            'average_satisfaction_score': avg_satisfaction,
            'total_escalations': sum(ctx.escalation_count for ctx in self.conversations.values()),
            'configurations': {
                'max_context_length': self.max_context_length,
                'summarization_threshold': self.summarization_threshold,
                'auto_summarize': self.auto_summarize,
                'sentiment_tracking': self.sentiment_tracking,
                'entity_tracking': self.entity_tracking,
                'conversation_timeout': self.conversation_timeout,
            }
        }