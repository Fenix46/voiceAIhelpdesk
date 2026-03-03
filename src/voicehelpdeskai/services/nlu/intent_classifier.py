"""Advanced Intent Classification system for IT helpdesk with multi-label support."""

import asyncio
import json
import pickle
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
import numpy as np
from datetime import datetime

from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available - using fallback methods")

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.multioutput import MultiOutputClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available - limited ML functionality")

from voicehelpdeskai.config.manager import get_config_manager


class ITCategory(Enum):
    """IT problem categories."""
    HARDWARE = "hardware"
    SOFTWARE = "software"
    NETWORK = "network"
    ACCOUNT = "account"
    EMAIL = "email"
    SECURITY = "security"
    PRINTER = "printer"
    PHONE = "phone"
    GENERAL = "general"


class UrgencyLevel(Enum):
    """Problem urgency levels."""
    CRITICO = "critico"
    ALTO = "alto"
    MEDIO = "medio"
    BASSO = "basso"


class IntentType(Enum):
    """User intent types."""
    PROBLEM_REPORT = "problem_report"
    INFORMATION_REQUEST = "information_request" 
    INSTALLATION_REQUEST = "installation_request"
    PASSWORD_RESET = "password_reset"
    ACCESS_REQUEST = "access_request"
    COMPLAINT = "complaint"
    FOLLOW_UP = "follow_up"
    ESCALATION = "escalation"
    CLOSURE = "closure"


@dataclass
class IntentPrediction:
    """Intent classification prediction with confidence."""
    intent: IntentType
    confidence: float
    category: ITCategory
    urgency: UrgencyLevel
    explanation: str = ""
    features: Dict[str, Any] = field(default_factory=dict)
    alternative_intents: List[Tuple[IntentType, float]] = field(default_factory=list)


@dataclass
class TrainingExample:
    """Training example for intent classification."""
    text: str
    intent: IntentType
    category: ITCategory
    urgency: UrgencyLevel
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class IntentClassifier:
    """Advanced multi-label intent classifier for IT helpdesk."""
    
    def __init__(self,
                 model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                 confidence_threshold: float = 0.7,
                 fallback_threshold: float = 0.5,
                 enable_llm_fallback: bool = True,
                 cache_embeddings: bool = True):
        """Initialize intent classifier.
        
        Args:
            model_name: Sentence transformer model name
            confidence_threshold: Minimum confidence for predictions
            fallback_threshold: Threshold for LLM fallback
            enable_llm_fallback: Enable LLM for ambiguous cases
            cache_embeddings: Cache text embeddings
        """
        self.config = get_config_manager().get_config()
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.fallback_threshold = fallback_threshold
        self.enable_llm_fallback = enable_llm_fallback
        self.cache_embeddings = cache_embeddings
        
        # Models
        self.sentence_model = None
        self.intent_classifier = None
        self.category_classifier = None
        self.urgency_classifier = None
        
        # Training data and features
        self.training_examples: List[TrainingExample] = []
        self.intent_embeddings: Dict[IntentType, np.ndarray] = {}
        self.category_embeddings: Dict[ITCategory, np.ndarray] = {}
        
        # Embedding cache
        self.embedding_cache: Dict[str, np.ndarray] = {}
        
        # Italian IT-specific patterns
        self.intent_patterns = {
            IntentType.PROBLEM_REPORT: [
                r'\b(?:problema|errore|guasto|non funziona|rotto|difettoso|bloccato)\b',
                r'\b(?:crash|freeze|si spegne|si riavvia|lento)\b',
                r'\b(?:help|aiuto|supporto|assistenza)\b'
            ],
            IntentType.INFORMATION_REQUEST: [
                r'\b(?:come|cosa|quando|dove|perché|chi|quale)\b',
                r'\b(?:informazioni|dettagli|spiegazione|documentazione)\b',
                r'\b(?:manuale|guida|tutorial|istruzioni)\b'
            ],
            IntentType.INSTALLATION_REQUEST: [
                r'\b(?:installa|installazione|setup|configurare|aggiungere)\b',
                r'\b(?:nuovo|nuova|software|programma|app|applicazione)\b'
            ],
            IntentType.PASSWORD_RESET: [
                r'\b(?:password|pwd|accesso|login|credenziali)\b',
                r'\b(?:reset|ripristino|cambiare|dimenticato|scaduto)\b'
            ],
            IntentType.ACCESS_REQUEST: [
                r'\b(?:accesso|permessi|autorizzazione|abilitazione)\b',
                r'\b(?:cartella|directory|file|sistema|server)\b'
            ]
        }
        
        self.category_patterns = {
            ITCategory.HARDWARE: [
                r'\b(?:computer|pc|laptop|desktop|workstation)\b',
                r'\b(?:monitor|schermo|display|tastiera|keyboard|mouse)\b',
                r'\b(?:stampante|printer|scanner|webcam|microfono)\b',
                r'\b(?:disco|hard disk|ssd|memoria|ram|cpu|scheda)\b'
            ],
            ITCategory.SOFTWARE: [
                r'\b(?:programma|software|app|applicazione|sistema operativo)\b',
                r'\b(?:windows|office|excel|word|outlook|chrome|firefox)\b',
                r'\b(?:antivirus|driver|aggiornamento|update|patch)\b',
                r'\b(?:crash|freeze|errore software|bug)\b'
            ],
            ITCategory.NETWORK: [
                r'\b(?:internet|rete|network|connessione|wifi|ethernet)\b',
                r'\b(?:vpn|firewall|router|switch|modem)\b',
                r'\b(?:ip|dns|dhcp|ping|banda|velocità)\b',
                r'\b(?:disconnesso|offline|lento|timeout)\b'
            ],
            ITCategory.ACCOUNT: [
                r'\b(?:account|utente|user|profilo|credenziali)\b',
                r'\b(?:active directory|dominio|login|accesso)\b',
                r'\b(?:password|pwd|authentication|autorizzazione)\b'
            ],
            ITCategory.EMAIL: [
                r'\b(?:email|mail|posta|outlook|thunderbird)\b',
                r'\b(?:inviare|ricevere|allegato|spam|phishing)\b',
                r'\b(?:casella|mailbox|imap|pop3|smtp)\b'
            ]
        }
        
        self.urgency_patterns = {
            UrgencyLevel.CRITICO: [
                r'\b(?:urgente|critico|bloccante|emergenza|subito)\b',
                r'\b(?:production down|sistema giù|non funziona niente)\b',
                r'\b(?:tutti|everyone|whole team|intera azienda)\b'
            ],
            UrgencyLevel.ALTO: [
                r'\b(?:importante|priorità alta|asap|prima possibile)\b',
                r'\b(?:lavoro bloccato|non posso lavorare|deadline)\b',
                r'\b(?:cliente|customer|meeting|presentazione)\b'
            ],
            UrgencyLevel.MEDIO: [
                r'\b(?:quando possibile|appena potete|medio)\b',
                r'\b(?:fastidioso|scomodo|rallenta)\b'
            ],
            UrgencyLevel.BASSO: [
                r'\b(?:quando avete tempo|non urgente|info|curiosità)\b',
                r'\b(?:miglioramento|suggestion|enhancement)\b'
            ]
        }
        
        # Initialize default training data
        self._initialize_training_data()
        
        # Performance metrics
        self.stats = {
            'total_classifications': 0,
            'high_confidence_predictions': 0,
            'llm_fallback_used': 0,
            'average_confidence': 0.0,
            'classification_time': 0.0,
            'cache_hits': 0,
        }
        
        logger.info("IntentClassifier initialized")
    
    async def initialize(self) -> None:
        """Initialize models and embeddings."""
        try:
            # Load sentence transformer
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                logger.info(f"Loading sentence transformer: {self.model_name}")
                self.sentence_model = SentenceTransformer(self.model_name)
                
                # Generate reference embeddings
                await self._generate_reference_embeddings()
                
                # Train classifiers if sklearn available
                if SKLEARN_AVAILABLE and self.training_examples:
                    await self._train_classifiers()
                
                logger.success("IntentClassifier models loaded successfully")
            else:
                logger.warning("Sentence transformers not available - using pattern matching only")
                
        except Exception as e:
            logger.error(f"Failed to initialize IntentClassifier: {e}")
            raise
    
    async def _generate_reference_embeddings(self) -> None:
        """Generate reference embeddings for intents and categories."""
        try:
            # Intent reference texts (Italian)
            intent_references = {
                IntentType.PROBLEM_REPORT: [
                    "Il computer non funziona",
                    "C'è un problema con il software",
                    "Il sistema è in errore",
                    "Non riesco ad accedere"
                ],
                IntentType.INFORMATION_REQUEST: [
                    "Come posso configurare questa funzione?",
                    "Quali sono i requisiti di sistema?",
                    "Dove trovo la documentazione?",
                    "Cosa devo fare per installare?"
                ],
                IntentType.INSTALLATION_REQUEST: [
                    "Vorrei installare un nuovo software",
                    "Ho bisogno di configurare un programma",
                    "Potreste aggiungere questa applicazione?",
                    "Setup nuovo sistema"
                ],
                IntentType.PASSWORD_RESET: [
                    "Ho dimenticato la password",
                    "Non riesco a fare il login",
                    "Password scaduta",
                    "Reset credenziali"
                ],
                IntentType.ACCESS_REQUEST: [
                    "Ho bisogno dei permessi per questa cartella",
                    "Non posso accedere al server",
                    "Autorizzazione per il sistema",
                    "Abilitazione account"
                ]
            }
            
            # Category reference texts
            category_references = {
                ITCategory.HARDWARE: [
                    "Il computer non si accende",
                    "Problema con la stampante",
                    "Monitor non funziona",
                    "Tastiera rotta"
                ],
                ITCategory.SOFTWARE: [
                    "Errore nell'applicazione",
                    "Il programma va in crash",
                    "Aggiornamento software",
                    "Sistema operativo lento"
                ],
                ITCategory.NETWORK: [
                    "Problema di connessione internet",
                    "VPN non funziona",
                    "Rete wifi lenta",
                    "Server non raggiungibile"
                ],
                ITCategory.ACCOUNT: [
                    "Problema con l'account utente",
                    "Login non funziona",
                    "Password da cambiare",
                    "Autorizzazioni mancanti"
                ]
            }
            
            # Generate embeddings for intents
            for intent, texts in intent_references.items():
                embeddings = self.sentence_model.encode(texts)
                self.intent_embeddings[intent] = np.mean(embeddings, axis=0)
            
            # Generate embeddings for categories  
            for category, texts in category_references.items():
                embeddings = self.sentence_model.encode(texts)
                self.category_embeddings[category] = np.mean(embeddings, axis=0)
                
            logger.info("Reference embeddings generated successfully")
            
        except Exception as e:
            logger.error(f"Failed to generate reference embeddings: {e}")
    
    async def _train_classifiers(self) -> None:
        """Train ML classifiers on training data."""
        if not self.training_examples or not SKLEARN_AVAILABLE:
            return
        
        try:
            # Prepare training data
            texts = [ex.text for ex in self.training_examples]
            embeddings = self.sentence_model.encode(texts)
            
            # Prepare labels
            intent_labels = [ex.intent.value for ex in self.training_examples]
            category_labels = [ex.category.value for ex in self.training_examples]
            urgency_labels = [ex.urgency.value for ex in self.training_examples]
            
            # Train classifiers
            self.intent_classifier = LogisticRegression(random_state=42)
            self.intent_classifier.fit(embeddings, intent_labels)
            
            self.category_classifier = LogisticRegression(random_state=42)
            self.category_classifier.fit(embeddings, category_labels)
            
            self.urgency_classifier = LogisticRegression(random_state=42)
            self.urgency_classifier.fit(embeddings, urgency_labels)
            
            logger.info(f"Trained classifiers on {len(self.training_examples)} examples")
            
        except Exception as e:
            logger.error(f"Failed to train classifiers: {e}")
    
    async def classify_intent(self, text: str) -> IntentPrediction:
        """Classify intent with confidence scoring.
        
        Args:
            text: Input text to classify
            
        Returns:
            IntentPrediction with confidence and metadata
        """
        start_time = time.time()
        
        try:
            # Get text embedding
            embedding = await self._get_embedding(text)
            
            # Multi-method classification
            pattern_results = self._classify_with_patterns(text)
            embedding_results = await self._classify_with_embeddings(text, embedding) if embedding is not None else {}
            ml_results = await self._classify_with_ml(embedding) if embedding is not None and self.intent_classifier else {}
            
            # Combine results
            combined_prediction = self._combine_predictions(
                text, pattern_results, embedding_results, ml_results
            )
            
            # Check if LLM fallback needed
            if (combined_prediction.confidence < self.fallback_threshold and 
                self.enable_llm_fallback):
                combined_prediction = await self._llm_fallback_classification(text, combined_prediction)
            
            # Update statistics
            processing_time = time.time() - start_time
            self._update_stats(combined_prediction, processing_time)
            
            logger.debug(f"Classified intent in {processing_time:.3f}s: "
                        f"{combined_prediction.intent.value} (confidence: {combined_prediction.confidence:.3f})")
            
            return combined_prediction
            
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            # Return default prediction
            return IntentPrediction(
                intent=IntentType.PROBLEM_REPORT,
                confidence=0.1,
                category=ITCategory.GENERAL,
                urgency=UrgencyLevel.MEDIO,
                explanation=f"Classification failed: {str(e)}"
            )
    
    async def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get text embedding with caching."""
        if not self.sentence_model:
            return None
            
        # Check cache first
        if self.cache_embeddings and text in self.embedding_cache:
            self.stats['cache_hits'] += 1
            return self.embedding_cache[text]
        
        try:
            embedding = self.sentence_model.encode([text])[0]
            
            # Cache embedding
            if self.cache_embeddings:
                self.embedding_cache[text] = embedding
                
                # Limit cache size
                if len(self.embedding_cache) > 1000:
                    # Remove oldest entries
                    keys_to_remove = list(self.embedding_cache.keys())[:100]
                    for key in keys_to_remove:
                        del self.embedding_cache[key]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    def _classify_with_patterns(self, text: str) -> Dict[str, Any]:
        """Classify using regex patterns."""
        import re
        
        text_lower = text.lower()
        results = {
            'intent_scores': {},
            'category_scores': {},
            'urgency_scores': {}
        }
        
        # Intent classification
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches * 0.3  # Weight per match
            results['intent_scores'][intent] = min(score, 1.0)
        
        # Category classification
        for category, patterns in self.category_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches * 0.4
            results['category_scores'][category] = min(score, 1.0)
        
        # Urgency classification
        for urgency, patterns in self.urgency_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches * 0.5
            results['urgency_scores'][urgency] = min(score, 1.0)
        
        return results
    
    async def _classify_with_embeddings(self, text: str, embedding: np.ndarray) -> Dict[str, Any]:
        """Classify using embedding similarity."""
        results = {
            'intent_scores': {},
            'category_scores': {}
        }
        
        try:
            # Intent similarity
            for intent, ref_embedding in self.intent_embeddings.items():
                similarity = cosine_similarity([embedding], [ref_embedding])[0][0]
                results['intent_scores'][intent] = max(0, similarity)
            
            # Category similarity
            for category, ref_embedding in self.category_embeddings.items():
                similarity = cosine_similarity([embedding], [ref_embedding])[0][0]
                results['category_scores'][category] = max(0, similarity)
                
        except Exception as e:
            logger.error(f"Embedding classification failed: {e}")
        
        return results
    
    async def _classify_with_ml(self, embedding: np.ndarray) -> Dict[str, Any]:
        """Classify using trained ML models."""
        results = {
            'intent_scores': {},
            'category_scores': {},
            'urgency_scores': {}
        }
        
        try:
            embedding = embedding.reshape(1, -1)
            
            # Intent classification
            if self.intent_classifier:
                intent_probs = self.intent_classifier.predict_proba(embedding)[0]
                intent_classes = self.intent_classifier.classes_
                for intent_str, prob in zip(intent_classes, intent_probs):
                    try:
                        intent = IntentType(intent_str)
                        results['intent_scores'][intent] = prob
                    except ValueError:
                        pass
            
            # Category classification
            if self.category_classifier:
                category_probs = self.category_classifier.predict_proba(embedding)[0]
                category_classes = self.category_classifier.classes_
                for category_str, prob in zip(category_classes, category_probs):
                    try:
                        category = ITCategory(category_str)
                        results['category_scores'][category] = prob
                    except ValueError:
                        pass
            
            # Urgency classification
            if self.urgency_classifier:
                urgency_probs = self.urgency_classifier.predict_proba(embedding)[0]
                urgency_classes = self.urgency_classifier.classes_
                for urgency_str, prob in zip(urgency_classes, urgency_probs):
                    try:
                        urgency = UrgencyLevel(urgency_str)
                        results['urgency_scores'][urgency] = prob
                    except ValueError:
                        pass
                        
        except Exception as e:
            logger.error(f"ML classification failed: {e}")
        
        return results
    
    def _combine_predictions(self, 
                           text: str,
                           pattern_results: Dict[str, Any],
                           embedding_results: Dict[str, Any],
                           ml_results: Dict[str, Any]) -> IntentPrediction:
        """Combine predictions from different methods."""
        
        # Weights for different methods
        pattern_weight = 0.3
        embedding_weight = 0.4
        ml_weight = 0.3
        
        # Combine intent scores
        combined_intent_scores = {}
        all_intents = set()
        if 'intent_scores' in pattern_results:
            all_intents.update(pattern_results['intent_scores'].keys())
        if 'intent_scores' in embedding_results:
            all_intents.update(embedding_results['intent_scores'].keys())
        if 'intent_scores' in ml_results:
            all_intents.update(ml_results['intent_scores'].keys())
        
        for intent in all_intents:
            score = 0
            if 'intent_scores' in pattern_results:
                score += pattern_results['intent_scores'].get(intent, 0) * pattern_weight
            if 'intent_scores' in embedding_results:
                score += embedding_results['intent_scores'].get(intent, 0) * embedding_weight
            if 'intent_scores' in ml_results:
                score += ml_results['intent_scores'].get(intent, 0) * ml_weight
            combined_intent_scores[intent] = score
        
        # Combine category scores
        combined_category_scores = {}
        all_categories = set()
        if 'category_scores' in pattern_results:
            all_categories.update(pattern_results['category_scores'].keys())
        if 'category_scores' in embedding_results:
            all_categories.update(embedding_results['category_scores'].keys())
        if 'category_scores' in ml_results:
            all_categories.update(ml_results['category_scores'].keys())
        
        for category in all_categories:
            score = 0
            if 'category_scores' in pattern_results:
                score += pattern_results['category_scores'].get(category, 0) * pattern_weight
            if 'category_scores' in embedding_results:
                score += embedding_results['category_scores'].get(category, 0) * embedding_weight
            if 'category_scores' in ml_results:
                score += ml_results['category_scores'].get(category, 0) * ml_weight
            combined_category_scores[category] = score
        
        # Combine urgency scores
        combined_urgency_scores = {}
        all_urgencies = set()
        if 'urgency_scores' in pattern_results:
            all_urgencies.update(pattern_results['urgency_scores'].keys())
        if 'urgency_scores' in ml_results:
            all_urgencies.update(ml_results['urgency_scores'].keys())
        
        for urgency in all_urgencies:
            score = 0
            if 'urgency_scores' in pattern_results:
                score += pattern_results['urgency_scores'].get(urgency, 0) * 0.6
            if 'urgency_scores' in ml_results:
                score += ml_results['urgency_scores'].get(urgency, 0) * 0.4
            combined_urgency_scores[urgency] = score
        
        # Get best predictions
        best_intent = max(combined_intent_scores.items(), key=lambda x: x[1]) if combined_intent_scores else (IntentType.PROBLEM_REPORT, 0.1)
        best_category = max(combined_category_scores.items(), key=lambda x: x[1]) if combined_category_scores else (ITCategory.GENERAL, 0.1)
        best_urgency = max(combined_urgency_scores.items(), key=lambda x: x[1]) if combined_urgency_scores else (UrgencyLevel.MEDIO, 0.1)
        
        # Calculate overall confidence
        confidence = np.mean([best_intent[1], best_category[1], best_urgency[1]])
        
        # Generate explanation
        explanation = self._generate_explanation(text, best_intent, best_category, best_urgency)
        
        # Get alternative intents
        alternative_intents = sorted(
            [(intent, score) for intent, score in combined_intent_scores.items() if intent != best_intent[0]],
            key=lambda x: x[1],
            reverse=True
        )[:3]
        
        return IntentPrediction(
            intent=best_intent[0],
            confidence=confidence,
            category=best_category[0],
            urgency=best_urgency[0],
            explanation=explanation,
            alternative_intents=alternative_intents,
            features={
                'intent_scores': combined_intent_scores,
                'category_scores': combined_category_scores,
                'urgency_scores': combined_urgency_scores,
                'methods_used': ['patterns', 'embeddings', 'ml']
            }
        )
    
    def _generate_explanation(self, 
                            text: str, 
                            intent_result: Tuple[IntentType, float],
                            category_result: Tuple[ITCategory, float],
                            urgency_result: Tuple[UrgencyLevel, float]) -> str:
        """Generate human-readable explanation for the classification."""
        
        intent, intent_conf = intent_result
        category, category_conf = category_result
        urgency, urgency_conf = urgency_result
        
        explanations = []
        
        # Intent explanation
        if intent_conf > 0.7:
            explanations.append(f"Il testo indica chiaramente un '{intent.value}'")
        elif intent_conf > 0.4:
            explanations.append(f"Il testo sembra indicare un '{intent.value}' con media confidenza")
        else:
            explanations.append(f"Classificato come '{intent.value}' per default")
        
        # Category explanation
        if category_conf > 0.6:
            explanations.append(f"Categoria identificata come '{category.value}' con buona confidenza")
        else:
            explanations.append(f"Categoria '{category.value}' assegnata con bassa confidenza")
        
        # Urgency explanation
        if urgency_conf > 0.5:
            explanations.append(f"Urgenza classificata come '{urgency.value}' basata su indicatori nel testo")
        else:
            explanations.append(f"Urgenza '{urgency.value}' assegnata per default")
        
        return ". ".join(explanations) + "."
    
    async def _llm_fallback_classification(self, 
                                         text: str, 
                                         initial_prediction: IntentPrediction) -> IntentPrediction:
        """Use LLM for ambiguous cases."""
        try:
            from voicehelpdeskai.services.llm import get_llm_manager
            
            llm_manager = get_llm_manager()
            
            prompt = f"""Classifica la seguente richiesta di supporto IT:

TESTO: "{text}"

Fornisci:
1. INTENT: {[intent.value for intent in IntentType]}
2. CATEGORIA: {[cat.value for cat in ITCategory]}
3. URGENZA: {[urg.value for urg in UrgencyLevel]}
4. CONFIDENZA: (0.0-1.0)
5. SPIEGAZIONE: Breve motivazione

Formato risposta:
INTENT: [intent]
CATEGORIA: [categoria]
URGENZA: [urgenza]
CONFIDENZA: [numero]
SPIEGAZIONE: [testo]"""

            response = await llm_manager.generate_response(prompt)
            
            # Parse LLM response
            llm_prediction = self._parse_llm_response(response.text, initial_prediction)
            llm_prediction.features['llm_fallback'] = True
            
            self.stats['llm_fallback_used'] += 1
            
            return llm_prediction
            
        except Exception as e:
            logger.error(f"LLM fallback failed: {e}")
            return initial_prediction
    
    def _parse_llm_response(self, response_text: str, fallback: IntentPrediction) -> IntentPrediction:
        """Parse LLM response into structured prediction."""
        try:
            lines = response_text.strip().split('\n')
            parsed = {}
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    parsed[key.strip().upper()] = value.strip()
            
            # Parse intent
            intent = fallback.intent
            if 'INTENT' in parsed:
                try:
                    intent = IntentType(parsed['INTENT'].lower())
                except ValueError:
                    pass
            
            # Parse category
            category = fallback.category
            if 'CATEGORIA' in parsed:
                try:
                    category = ITCategory(parsed['CATEGORIA'].lower())
                except ValueError:
                    pass
            
            # Parse urgency
            urgency = fallback.urgency
            if 'URGENZA' in parsed:
                try:
                    urgency = UrgencyLevel(parsed['URGENZA'].lower())
                except ValueError:
                    pass
            
            # Parse confidence
            confidence = fallback.confidence
            if 'CONFIDENZA' in parsed:
                try:
                    confidence = float(parsed['CONFIDENZA'])
                except ValueError:
                    pass
            
            # Parse explanation
            explanation = parsed.get('SPIEGAZIONE', fallback.explanation)
            
            return IntentPrediction(
                intent=intent,
                confidence=confidence,
                category=category,
                urgency=urgency,
                explanation=explanation,
                features={**fallback.features, 'llm_enhanced': True}
            )
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return fallback
    
    def _initialize_training_data(self) -> None:
        """Initialize with default Italian IT training examples."""
        examples = [
            # Hardware problems
            TrainingExample(
                "Il computer non si accende più da stamattina",
                IntentType.PROBLEM_REPORT, ITCategory.HARDWARE, UrgencyLevel.ALTO
            ),
            TrainingExample(
                "La stampante HP non stampa i documenti",
                IntentType.PROBLEM_REPORT, ITCategory.PRINTER, UrgencyLevel.MEDIO
            ),
            TrainingExample(
                "Monitor schermo nero, solo cursore lampeggiante",
                IntentType.PROBLEM_REPORT, ITCategory.HARDWARE, UrgencyLevel.ALTO
            ),
            
            # Software problems
            TrainingExample(
                "Excel va in crash quando apro file grandi",
                IntentType.PROBLEM_REPORT, ITCategory.SOFTWARE, UrgencyLevel.MEDIO
            ),
            TrainingExample(
                "Windows Update bloccato al 50%",
                IntentType.PROBLEM_REPORT, ITCategory.SOFTWARE, UrgencyLevel.MEDIO
            ),
            TrainingExample(
                "Antivirus segnala trojan, sistema molto lento",
                IntentType.PROBLEM_REPORT, ITCategory.SECURITY, UrgencyLevel.CRITICO
            ),
            
            # Network problems
            TrainingExample(
                "Non riesco a connettermi alla VPN aziendale",
                IntentType.PROBLEM_REPORT, ITCategory.NETWORK, UrgencyLevel.ALTO
            ),
            TrainingExample(
                "Internet lentissimo, pagine web non si caricano",
                IntentType.PROBLEM_REPORT, ITCategory.NETWORK, UrgencyLevel.MEDIO
            ),
            
            # Account issues
            TrainingExample(
                "Ho dimenticato la password dell'account",
                IntentType.PASSWORD_RESET, ITCategory.ACCOUNT, UrgencyLevel.MEDIO
            ),
            TrainingExample(
                "Non posso accedere alla cartella condivisa",
                IntentType.ACCESS_REQUEST, ITCategory.ACCOUNT, UrgencyLevel.MEDIO
            ),
            
            # Information requests
            TrainingExample(
                "Come si configura Outlook per la nuova email?",
                IntentType.INFORMATION_REQUEST, ITCategory.EMAIL, UrgencyLevel.BASSO
            ),
            TrainingExample(
                "Quali sono i requisiti per installare il nuovo software?",
                IntentType.INFORMATION_REQUEST, ITCategory.SOFTWARE, UrgencyLevel.BASSO
            ),
            
            # Installation requests
            TrainingExample(
                "Vorrei installare Adobe Photoshop sul mio PC",
                IntentType.INSTALLATION_REQUEST, ITCategory.SOFTWARE, UrgencyLevel.BASSO
            ),
            TrainingExample(
                "Potreste configurarmi Teams per le videochiamate?",
                IntentType.INSTALLATION_REQUEST, ITCategory.SOFTWARE, UrgencyLevel.MEDIO
            )
        ]
        
        self.training_examples = examples
        logger.info(f"Initialized with {len(examples)} training examples")
    
    def add_training_example(self, example: TrainingExample) -> None:
        """Add new training example."""
        self.training_examples.append(example)
    
    def _update_stats(self, prediction: IntentPrediction, processing_time: float) -> None:
        """Update classification statistics."""
        self.stats['total_classifications'] += 1
        self.stats['classification_time'] = (
            self.stats['classification_time'] * (self.stats['total_classifications'] - 1) + processing_time
        ) / self.stats['total_classifications']
        
        if prediction.confidence >= self.confidence_threshold:
            self.stats['high_confidence_predictions'] += 1
        
        self.stats['average_confidence'] = (
            self.stats['average_confidence'] * (self.stats['total_classifications'] - 1) + prediction.confidence
        ) / self.stats['total_classifications']
    
    def get_stats(self) -> Dict[str, Any]:
        """Get classification statistics."""
        stats = self.stats.copy()
        
        if stats['total_classifications'] > 0:
            stats['high_confidence_rate'] = (
                stats['high_confidence_predictions'] / stats['total_classifications'] * 100
            )
            stats['llm_fallback_rate'] = (
                stats['llm_fallback_used'] / stats['total_classifications'] * 100
            )
            stats['cache_hit_rate'] = (
                stats['cache_hits'] / stats['total_classifications'] * 100
            ) if stats['cache_hits'] > 0 else 0.0
        
        stats.update({
            'model_loaded': self.sentence_model is not None,
            'training_examples': len(self.training_examples),
            'cached_embeddings': len(self.embedding_cache),
            'confidence_threshold': self.confidence_threshold,
            'fallback_threshold': self.fallback_threshold,
        })
        
        return stats
    
    async def batch_classify(self, texts: List[str]) -> List[IntentPrediction]:
        """Classify multiple texts in batch for efficiency."""
        predictions = []
        
        # Process in batches for memory efficiency
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_predictions = []
            
            for text in batch:
                prediction = await self.classify_intent(text)
                batch_predictions.append(prediction)
            
            predictions.extend(batch_predictions)
        
        return predictions