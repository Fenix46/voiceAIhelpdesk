"""Mistral LLM service optimized for Italian helpdesk operations."""

import asyncio
import json
import time
from typing import Dict, List, Optional, AsyncGenerator, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger

from .llm_service import (
    LLMService, 
    ModelConfig, 
    GenerationParams, 
    LLMResponse, 
    StreamingChunk,
    LLMBackend,
    QuantizationType
)

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("Transformers not available - Mistral service disabled")

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("Ollama client not available")


@dataclass
class TicketOperation:
    """Represents a ticket operation that can be performed."""
    operation: str
    ticket_id: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    assignee: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class KnowledgeBaseEntry:
    """Knowledge base entry for RAG integration."""
    id: str
    title: str
    content: str
    category: str
    tags: List[str]
    relevance_score: float = 0.0
    last_updated: datetime = None


class MistralService(LLMService):
    """Mistral 7B service optimized for Italian helpdesk operations."""
    
    # Italian helpdesk system prompts
    SYSTEM_PROMPTS = {
        "helpdesk_assistant": """Sei un assistente AI esperto per un help desk IT italiano. 
Il tuo compito è aiutare gli utenti con problemi tecnici, fornendo soluzioni chiare e pratiche in italiano.

Caratteristiche del tuo comportamento:
- Rispondi sempre in italiano
- Sii professionale ma cordiale
- Fornisci soluzioni step-by-step quando necessario
- Richiedi informazioni aggiuntive se il problema non è chiaro
- Suggerisci escalation quando appropriato
- Mantieni traccia del contesto della conversazione

Puoi eseguire operazioni sui ticket come:
- Creare nuovi ticket
- Aggiornare priorità e stato
- Assegnare ticket ai tecnici
- Cercare nella knowledge base
- Programmare interventi

Rispondi in modo conciso ma completo.""",

        "ticket_classifier": """Analizza la richiesta dell'utente e classifica il tipo di problema IT.

Categorie disponibili:
- HARDWARE: Problemi con computer, stampanti, periferiche
- SOFTWARE: Problemi con applicazioni, sistemi operativi
- NETWORK: Connettività, Wi-Fi, VPN
- EMAIL: Problemi con posta elettronica
- ACCOUNT: Accessi, password, permessi
- TELEFONIA: Telefoni IP, centralino
- SECURITY: Antivirus, firewall, sicurezza
- OTHER: Altri problemi non classificabili

Priorità:
- CRITICA: Sistema giù, blocco totale produttività
- ALTA: Problema che impatta significativamente il lavoro
- MEDIA: Problema che causa disagi minori
- BASSA: Richiesta informazioni, miglioramenti

Rispondi con categoria e priorità.""",

        "solution_provider": """Fornisci una soluzione tecnica dettagliata per il problema descritto.

Struttura la risposta così:
1. DIAGNOSI: Identificazione del problema
2. SOLUZIONE IMMEDIATA: Passi da seguire subito
3. VERIFICA: Come confermare che il problema è risolto
4. PREVENZIONE: Come evitare il problema in futuro

Usa un linguaggio tecnico ma comprensibile. Fornisci comandi specifici quando necessario."""
    }
    
    # Function calling templates
    FUNCTION_TEMPLATES = {
        "create_ticket": {
            "name": "create_ticket",
            "description": "Crea un nuovo ticket di assistenza",
            "parameters": {
                "title": "Titolo del ticket",
                "description": "Descrizione dettagliata del problema",
                "category": "Categoria del problema",
                "priority": "Priorità (BASSA, MEDIA, ALTA, CRITICA)",
                "user_id": "ID utente che ha segnalato"
            }
        },
        "update_ticket": {
            "name": "update_ticket",
            "description": "Aggiorna un ticket esistente",
            "parameters": {
                "ticket_id": "ID del ticket da aggiornare",
                "status": "Nuovo stato (APERTO, IN_LAVORAZIONE, RISOLTO, CHIUSO)",
                "notes": "Note aggiuntive"
            }
        },
        "search_knowledge_base": {
            "name": "search_knowledge_base",
            "description": "Cerca informazioni nella knowledge base",
            "parameters": {
                "query": "Termini di ricerca",
                "category": "Categoria opzionale per filtrare"
            }
        },
        "assign_ticket": {
            "name": "assign_ticket",
            "description": "Assegna un ticket a un tecnico",
            "parameters": {
                "ticket_id": "ID del ticket",
                "assignee": "Nome o ID del tecnico",
                "notes": "Note per l'assegnazione"
            }
        }
    }
    
    def __init__(self, 
                 config: Optional[ModelConfig] = None,
                 enable_rag: bool = True,
                 enable_function_calling: bool = True,
                 conversation_memory_size: int = 10,
                 **kwargs):
        """Initialize Mistral service.
        
        Args:
            config: Model configuration
            enable_rag: Enable RAG integration
            enable_function_calling: Enable function calling
            conversation_memory_size: Size of conversation memory
            **kwargs: Additional arguments for base class
        """
        if config is None:
            config = ModelConfig(
                name="mistral-7b-instruct-v0.1",
                backend=LLMBackend.TRANSFORMERS,
                context_length=8192,
                max_tokens=1024,
                temperature=0.7,
                quantization=QuantizationType.INT8
            )
        
        super().__init__(config, **kwargs)
        
        self.enable_rag = enable_rag
        self.enable_function_calling = enable_function_calling
        self.conversation_memory_size = conversation_memory_size
        
        # Model and tokenizer
        self.model = None
        self.tokenizer = None
        
        # RAG components
        self.knowledge_base: List[KnowledgeBaseEntry] = []
        self.rag_cache: Dict[str, List[KnowledgeBaseEntry]] = {}
        
        # Conversation memory
        self.conversation_memory: Dict[str, List[Dict[str, Any]]] = {}
        
        # Italian-specific optimizations
        self.italian_stopwords = {
            'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'una', 'di', 'a', 'da', 'in', 'con', 
            'su', 'per', 'tra', 'fra', 'e', 'anche', 'se', 'ma', 'però', 'tuttavia'
        }
        
        # Response caching strategies
        self.strategic_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Mistral service initialized with Italian helpdesk optimizations")
    
    async def load_model(self) -> None:
        """Load Mistral model with quantization."""
        if not TRANSFORMERS_AVAILABLE:
            raise RuntimeError("Transformers library not available")
        
        try:
            logger.info(f"Loading Mistral model: {self.config.name}")
            
            # Setup quantization if enabled
            quantization_config = None
            if self.config.quantization != QuantizationType.NONE:
                if self.config.quantization == QuantizationType.INT4:
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_use_double_quant=True
                    )
                elif self.config.quantization == QuantizationType.INT8:
                    quantization_config = BitsAndBytesConfig(
                        load_in_8bit=True,
                        llm_int8_threshold=6.0
                    )
            
            # Load tokenizer
            model_name = "mistralai/Mistral-7B-Instruct-v0.1"
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                cache_dir=self.app_config.ai_models.model_cache_dir
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model
            model_kwargs = {
                'cache_dir': self.app_config.ai_models.model_cache_dir,
                'torch_dtype': torch.float16,
                'device_map': "auto" if self.config.device == "auto" else self.config.device,
            }
            
            if quantization_config:
                model_kwargs['quantization_config'] = quantization_config
            
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                **model_kwargs
            )
            
            # Set model to evaluation mode
            self.model.eval()
            
            logger.success("Mistral model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load Mistral model: {e}")
            raise
    
    async def unload_model(self) -> None:
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            self.model = None
        
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        
        self.memory_manager.cleanup_memory()
        logger.info("Mistral model unloaded")
    
    async def generate(self, 
                      prompt: str, 
                      params: Optional[GenerationParams] = None) -> LLMResponse:
        """Generate response using Mistral model."""
        await self.ensure_loaded()
        
        start_time = time.time()
        params = self.validate_generation_params(params)
        
        # Check cache first
        cache_key = self._generate_cache_key(prompt, params)
        cached_response = self._get_from_cache(cache_key)
        if cached_response:
            self._update_stats(cached_response, cached=True)
            return cached_response
        
        try:
            # Apply RAG if enabled
            enhanced_prompt = await self._apply_rag_enhancement(prompt)
            
            # Apply conversation memory if available
            contextualized_prompt = self._apply_conversation_context(enhanced_prompt)
            
            # Tokenize input
            inputs = self.tokenizer(
                contextualized_prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.config.context_length - params.max_tokens
            )
            
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=params.max_tokens,
                    temperature=params.temperature,
                    top_p=params.top_p,
                    top_k=params.top_k,
                    repetition_penalty=params.repetition_penalty,
                    do_sample=params.temperature > 0.0,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            # Decode response
            response_tokens = outputs[0][inputs['input_ids'].shape[1]:]
            response_text = self.tokenizer.decode(response_tokens, skip_special_tokens=True)
            
            # Post-process response
            response_text = self._post_process_response(response_text)
            
            # Calculate usage
            prompt_tokens = inputs['input_ids'].shape[1]
            completion_tokens = len(response_tokens)
            total_tokens = prompt_tokens + completion_tokens
            
            usage = {
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens
            }
            
            response = LLMResponse(
                text=response_text,
                model=self.config.name,
                usage=usage,
                response_time=time.time() - start_time,
                cached=False
            )
            
            # Cache response strategically
            self._strategic_cache_response(cache_key, response, prompt)
            
            # Update conversation memory
            self._update_conversation_memory("", prompt, response_text)
            
            self._update_stats(response)
            return response
            
        except Exception as e:
            self.stats['errors'] += 1
            self.stats['last_error'] = str(e)
            logger.error(f"Generation failed: {e}")
            raise
    
    async def generate_stream(self, 
                            prompt: str, 
                            params: Optional[GenerationParams] = None) -> AsyncGenerator[StreamingChunk, None]:
        """Generate streaming response."""
        await self.ensure_loaded()
        
        params = self.validate_generation_params(params)
        
        try:
            # Apply RAG and context
            enhanced_prompt = await self._apply_rag_enhancement(prompt)
            contextualized_prompt = self._apply_conversation_context(enhanced_prompt)
            
            # Tokenize
            inputs = self.tokenizer(
                contextualized_prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.config.context_length - params.max_tokens
            )
            
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            generated_text = ""
            generated_tokens = 0
            
            # Generate tokens one by one
            with torch.no_grad():
                for _ in range(params.max_tokens):
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=1,
                        temperature=params.temperature,
                        top_p=params.top_p,
                        top_k=params.top_k,
                        do_sample=params.temperature > 0.0,
                        pad_token_id=self.tokenizer.eos_token_id,
                        eos_token_id=self.tokenizer.eos_token_id,
                    )
                    
                    # Get new token
                    new_token_id = outputs[0][-1].unsqueeze(0).unsqueeze(0)
                    new_token_text = self.tokenizer.decode(new_token_id, skip_special_tokens=True)
                    
                    # Check for stop sequences
                    if params.stop_sequences:
                        should_stop = any(stop in new_token_text for stop in params.stop_sequences)
                        if should_stop:
                            break
                    
                    # Check for EOS
                    if new_token_id.item() == self.tokenizer.eos_token_id:
                        break
                    
                    generated_text += new_token_text
                    generated_tokens += 1
                    
                    # Yield chunk
                    yield StreamingChunk(
                        text=new_token_text,
                        is_complete=False,
                        token_count=generated_tokens
                    )
                    
                    # Update inputs for next iteration
                    inputs['input_ids'] = torch.cat([inputs['input_ids'], new_token_id], dim=1)
                    if 'attention_mask' in inputs:
                        inputs['attention_mask'] = torch.cat([
                            inputs['attention_mask'],
                            torch.ones(1, 1, device=inputs['attention_mask'].device)
                        ], dim=1)
            
            # Final chunk
            yield StreamingChunk(
                text="",
                is_complete=True,
                token_count=generated_tokens,
                metadata={'full_text': generated_text}
            )
            
            # Update conversation memory
            self._update_conversation_memory("", prompt, generated_text)
            
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            yield StreamingChunk(
                text="",
                is_complete=True,
                token_count=0,
                metadata={'error': str(e)}
            )
    
    async def _apply_rag_enhancement(self, prompt: str) -> str:
        """Apply RAG enhancement to prompt."""
        if not self.enable_rag or not self.knowledge_base:
            return prompt
        
        try:
            # Search knowledge base
            relevant_entries = await self._search_knowledge_base(prompt)
            
            if not relevant_entries:
                return prompt
            
            # Build enhanced prompt with context
            context_parts = []
            for entry in relevant_entries[:3]:  # Top 3 results
                context_parts.append(f"DOCUMENTO: {entry.title}\n{entry.content}")
            
            context = "\n\n".join(context_parts)
            
            enhanced_prompt = f"""Utilizza le seguenti informazioni per rispondere alla domanda dell'utente:

{context}

DOMANDA UTENTE: {prompt}

RISPOSTA:"""
            
            return enhanced_prompt
            
        except Exception as e:
            logger.error(f"RAG enhancement failed: {e}")
            return prompt
    
    async def _search_knowledge_base(self, query: str, limit: int = 5) -> List[KnowledgeBaseEntry]:
        """Search knowledge base for relevant entries."""
        if not self.knowledge_base:
            return []
        
        # Simple keyword-based search (can be enhanced with embeddings)
        query_words = set(query.lower().split()) - self.italian_stopwords
        
        scored_entries = []
        for entry in self.knowledge_base:
            # Calculate relevance score
            entry_words = set((entry.title + " " + entry.content).lower().split())
            common_words = query_words.intersection(entry_words)
            
            if common_words:
                score = len(common_words) / len(query_words)
                # Boost score for title matches
                title_words = set(entry.title.lower().split())
                title_matches = query_words.intersection(title_words)
                if title_matches:
                    score += len(title_matches) * 0.5
                
                entry.relevance_score = score
                scored_entries.append(entry)
        
        # Sort by relevance and return top results
        scored_entries.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_entries[:limit]
    
    def _apply_conversation_context(self, prompt: str, session_id: str = "default") -> str:
        """Apply conversation context to prompt."""
        if session_id not in self.conversation_memory:
            return prompt
        
        memory = self.conversation_memory[session_id]
        if not memory:
            return prompt
        
        # Build context from recent conversation
        context_parts = []
        for entry in memory[-3:]:  # Last 3 exchanges
            context_parts.append(f"Utente: {entry['user']}")
            context_parts.append(f"Assistente: {entry['assistant']}")
        
        if context_parts:
            context = "\n".join(context_parts)
            return f"{context}\n\nUtente: {prompt}\nAssistente:"
        
        return prompt
    
    def _update_conversation_memory(self, session_id: str, user_message: str, assistant_message: str):
        """Update conversation memory."""
        if session_id not in self.conversation_memory:
            self.conversation_memory[session_id] = []
        
        memory = self.conversation_memory[session_id]
        memory.append({
            'user': user_message,
            'assistant': assistant_message,
            'timestamp': datetime.now()
        })
        
        # Keep only recent entries
        if len(memory) > self.conversation_memory_size:
            memory.pop(0)
    
    def _strategic_cache_response(self, cache_key: str, response: LLMResponse, prompt: str):
        """Cache response with strategic considerations."""
        if not self.enable_caching:
            return
        
        # Determine if response should be cached based on content
        should_cache = False
        cache_ttl = 3600  # Default 1 hour
        
        # Cache FAQ-type responses longer
        faq_indicators = ['come', 'cosa', 'perché', 'quando', 'dove', 'chi']
        if any(indicator in prompt.lower() for indicator in faq_indicators):
            should_cache = True
            cache_ttl = 7200  # 2 hours
        
        # Cache technical solutions longer
        tech_indicators = ['errore', 'problema', 'non funziona', 'installare', 'configurare']
        if any(indicator in prompt.lower() for indicator in tech_indicators):
            should_cache = True
            cache_ttl = 10800  # 3 hours
        
        # Don't cache personalized responses
        personal_indicators = ['mio', 'mia', 'personal', 'account', 'password']
        if any(indicator in prompt.lower() for indicator in personal_indicators):
            should_cache = False
        
        if should_cache:
            self._add_to_cache(cache_key, response)
            self.strategic_cache[cache_key] = {
                'ttl': cache_ttl,
                'created_at': time.time(),
                'category': self._classify_prompt_category(prompt)
            }
    
    def _classify_prompt_category(self, prompt: str) -> str:
        """Classify prompt into category for strategic caching."""
        prompt_lower = prompt.lower()
        
        categories = {
            'hardware': ['computer', 'stampante', 'mouse', 'tastiera', 'schermo', 'monitor'],
            'software': ['programma', 'applicazione', 'software', 'installare', 'aggiornare'],
            'network': ['internet', 'wifi', 'rete', 'connessione', 'vpn'],
            'email': ['email', 'posta', 'outlook', 'thunderbird', 'mail'],
            'account': ['account', 'login', 'password', 'accesso', 'utente'],
            'security': ['virus', 'malware', 'sicurezza', 'antivirus', 'firewall']
        }
        
        for category, keywords in categories.items():
            if any(keyword in prompt_lower for keyword in keywords):
                return category
        
        return 'general'
    
    def _post_process_response(self, response: str) -> str:
        """Post-process generated response."""
        # Clean up response
        response = response.strip()
        
        # Remove common artifacts
        response = response.replace('<|im_end|>', '')
        response = response.replace('[/INST]', '')
        
        # Ensure proper Italian punctuation
        response = response.replace(' ,', ',')
        response = response.replace(' .', '.')
        response = response.replace(' !', '!')
        response = response.replace(' ?', '?')
        
        return response
    
    async def extract_ticket_operation(self, user_message: str) -> Optional[TicketOperation]:
        """Extract ticket operation from user message."""
        if not self.enable_function_calling:
            return None
        
        # Simple intent extraction (can be enhanced with NLU)
        message_lower = user_message.lower()
        
        # Create ticket intent
        create_indicators = ['crea', 'apri', 'nuovo ticket', 'segnala problema']
        if any(indicator in message_lower for indicator in create_indicators):
            return TicketOperation(
                operation="create_ticket",
                description=user_message,
                category=self._classify_prompt_category(user_message),
                priority=self._extract_priority(user_message)
            )
        
        # Update ticket intent
        update_indicators = ['aggiorna', 'modifica', 'cambia stato']
        if any(indicator in message_lower for indicator in update_indicators):
            return TicketOperation(
                operation="update_ticket",
                ticket_id=self._extract_ticket_id(user_message),
                description=user_message
            )
        
        return None
    
    def _extract_priority(self, message: str) -> str:
        """Extract priority from message."""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['urgente', 'critico', 'bloccante']):
            return 'CRITICA'
        elif any(word in message_lower for word in ['importante', 'alto']):
            return 'ALTA'
        elif any(word in message_lower for word in ['basso', 'minore']):
            return 'BASSA'
        else:
            return 'MEDIA'
    
    def _extract_ticket_id(self, message: str) -> Optional[str]:
        """Extract ticket ID from message."""
        import re
        # Look for patterns like "ticket 12345" or "#12345"
        patterns = [
            r'ticket\s+(\d+)',
            r'#(\d+)',
            r'id\s+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return match.group(1)
        
        return None
    
    def add_knowledge_base_entry(self, entry: KnowledgeBaseEntry) -> None:
        """Add entry to knowledge base."""
        self.knowledge_base.append(entry)
        logger.debug(f"Added knowledge base entry: {entry.title}")
    
    def clear_knowledge_base(self) -> int:
        """Clear knowledge base."""
        count = len(self.knowledge_base)
        self.knowledge_base.clear()
        self.rag_cache.clear()
        return count
    
    def get_conversation_history(self, session_id: str = "default") -> List[Dict[str, Any]]:
        """Get conversation history for session."""
        return self.conversation_memory.get(session_id, [])
    
    def clear_conversation_history(self, session_id: str = "default") -> int:
        """Clear conversation history for session."""
        if session_id in self.conversation_memory:
            count = len(self.conversation_memory[session_id])
            del self.conversation_memory[session_id]
            return count
        return 0
    
    def get_mistral_stats(self) -> Dict[str, Any]:
        """Get Mistral-specific statistics."""
        stats = self.get_stats()
        
        # Add Mistral-specific metrics
        stats.update({
            'knowledge_base_entries': len(self.knowledge_base),
            'active_conversations': len(self.conversation_memory),
            'rag_enabled': self.enable_rag,
            'function_calling_enabled': self.enable_function_calling,
            'strategic_cache_entries': len(self.strategic_cache),
            'total_conversation_turns': sum(
                len(conv) for conv in self.conversation_memory.values()
            )
        })
        
        return stats