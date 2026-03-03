"""Advanced Entity Extraction for IT helpdesk with fuzzy matching and validation."""

import asyncio
import re
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Tuple
from datetime import datetime
import difflib

from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available - using fallback methods")

try:
    import spacy
    from spacy.lang.it import Italian
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available - using regex-only extraction")

from voicehelpdeskai.config.manager import get_config_manager


class EntityType(Enum):
    """IT-specific entity types."""
    ASSET_CODE = "asset_code"
    MATRICOLA = "matricola" 
    SOFTWARE_NAME = "software_name"
    SOFTWARE_VERSION = "software_version"
    ERROR_CODE = "error_code"
    ERROR_MESSAGE = "error_message"
    IP_ADDRESS = "ip_address"
    HOSTNAME = "hostname"
    USER_ID = "user_id"
    EMAIL = "email"
    PHONE_NUMBER = "phone_number"
    DEPARTMENT = "department"
    LOCATION = "location"
    HARDWARE_MODEL = "hardware_model"
    SERIAL_NUMBER = "serial_number"
    TICKET_ID = "ticket_id"
    DATE_TIME = "date_time"
    FILE_PATH = "file_path"
    URL = "url"
    PORT = "port"
    PRIORITY_LEVEL = "priority_level"


@dataclass
class ExtractedEntity:
    """Extracted entity with metadata."""
    text: str
    entity_type: EntityType
    confidence: float
    start_pos: int
    end_pos: int
    normalized_value: Optional[str] = None
    validation_status: str = "unknown"  # valid, invalid, uncertain
    metadata: Dict[str, Any] = field(default_factory=dict)
    fuzzy_match: bool = False
    original_text: Optional[str] = None  # For typo corrections


@dataclass
class ValidationRule:
    """Validation rule for entity types."""
    entity_type: EntityType
    pattern: str
    validator_func: Optional[callable] = None
    examples: List[str] = field(default_factory=list)
    description: str = ""


class EntityExtractor:
    """Advanced entity extractor for IT helpdesk with fuzzy matching."""
    
    def __init__(self,
                 model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                 fuzzy_threshold: float = 0.8,
                 enable_spacy: bool = True,
                 enable_fuzzy_matching: bool = True,
                 enable_validation: bool = True):
        """Initialize entity extractor.
        
        Args:
            model_name: Sentence transformer model for similarity matching
            fuzzy_threshold: Threshold for fuzzy string matching
            enable_spacy: Use spaCy for named entity recognition
            enable_fuzzy_matching: Enable fuzzy matching for typos
            enable_validation: Enable entity validation
        """
        self.config = get_config_manager().get_config()
        self.model_name = model_name
        self.fuzzy_threshold = fuzzy_threshold
        self.enable_spacy = enable_spacy
        self.enable_fuzzy_matching = enable_fuzzy_matching
        self.enable_validation = enable_validation
        
        # Models
        self.sentence_model = None
        self.spacy_model = None
        
        # Entity patterns (Italian-specific)
        self.entity_patterns = {
            EntityType.ASSET_CODE: [
                r'\b(?:asset|codice|matricola)[\s:]*([A-Z]{2,4}\d{4,8})\b',
                r'\b([A-Z]{2}\d{6})\b',  # Common asset format
                r'\b(PC\d{4,6}|WS\d{4,6}|SRV\d{4,6})\b'  # PC/Workstation/Server codes
            ],
            
            EntityType.MATRICOLA: [
                r'\bmatricola[\s:]*(\d{4,8})\b',
                r'\bmtr[\s:]*(\d{4,8})\b',
                r'\b(?:dipendente|emp)[\s:]*(\d{4,8})\b'
            ],
            
            EntityType.SOFTWARE_NAME: [
                r'\b(Microsoft\s+(?:Office|Word|Excel|PowerPoint|Outlook|Teams)(?:\s+\d{4})?)\b',
                r'\b(Adobe\s+(?:Photoshop|Acrobat|Reader|Creative Suite))\b',
                r'\b(Google\s+(?:Chrome|Drive|Docs|Sheets))\b',
                r'\b(Mozilla\s+Firefox)\b',
                r'\b(Skype(?:\s+for\s+Business)?)\b',
                r'\b(Zoom|Slack|Discord)\b',
                r'\b(Windows\s+(?:10|11|Server\s+\d{4}))\b',
                r'\b(SAP|Oracle|Salesforce)\b'
            ],
            
            EntityType.SOFTWARE_VERSION: [
                r'\bversione[\s:]*(\d+(?:\.\d+)*(?:\.\d+)*)\b',
                r'\bv\.?(\d+(?:\.\d+)*)\b',
                r'\b(\d+(?:\.\d+)+)(?:\s*build\s*\d+)?\b'
            ],
            
            EntityType.ERROR_CODE: [
                r'\berrore[\s:]*(\d{1,4})\b',
                r'\berror[\s:]*(\d{1,4})\b',
                r'\b(0x[0-9A-Fa-f]{8})\b',  # Windows error codes
                r'\b([A-Z]{2,4}\d{2,4})\b',  # Application-specific codes
                r'\b(HTTP\s*[45]\d{2})\b'  # HTTP error codes
            ],
            
            EntityType.ERROR_MESSAGE: [
                r'"([^"]{10,100})"',  # Quoted error messages
                r'\berror[e\s:]*["\']([^"\']{10,100})["\']\b',
                r'\bmessaggio[:\s]*["\']([^"\']{10,100})["\']\b'
            ],
            
            EntityType.IP_ADDRESS: [
                r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
                r'\b([0-9a-fA-F:]{2,39})\b'  # IPv6 simplified
            ],
            
            EntityType.HOSTNAME: [
                r'\b([a-zA-Z][a-zA-Z0-9\-]{2,15})\b(?:\.[a-zA-Z]{2,4})?',
                r'\b(srv|pc|ws|dc)[-_]?([a-zA-Z0-9\-]{2,15})\b',
                r'\b([a-zA-Z0-9\-]+\.(?:local|corp|domain))\b'
            ],
            
            EntityType.USER_ID: [
                r'\b(?:user|utente|login)[\s:]*([a-zA-Z][a-zA-Z0-9\._]{2,20})\b',
                r'\b([a-zA-Z]\.[a-zA-Z]{2,15})\b',  # Common format: n.cognome
                r'\b([a-zA-Z]{2,15}\.[a-zA-Z]{2,15})\b'  # nome.cognome
            ],
            
            EntityType.EMAIL: [
                r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
            ],
            
            EntityType.PHONE_NUMBER: [
                r'\b(\+39[\s\-]?\d{2,3}[\s\-]?\d{6,7})\b',  # Italian numbers
                r'\b(\d{2,4}[\s\-]?\d{6,8})\b',  # Internal extensions
                r'\b(\+\d{1,3}[\s\-]?\d{4,14})\b'  # International
            ],
            
            EntityType.HARDWARE_MODEL: [
                r'\b(Dell\s+(?:Latitude|OptiPlex|Precision|PowerEdge)\s+[A-Z0-9]{3,10})\b',
                r'\b(HP\s+(?:ProBook|EliteBook|Pavilion|ProDesk)\s+[A-Z0-9]{3,10})\b',
                r'\b(Lenovo\s+(?:ThinkPad|IdeaPad|ThinkCentre)\s+[A-Z0-9]{3,10})\b',
                r'\b(MacBook\s+(?:Pro|Air)\s+\d{2}"\s*\d{4}?)\b'
            ],
            
            EntityType.SERIAL_NUMBER: [
                r'\bserial[\s:]*([A-Z0-9]{8,20})\b',
                r'\bsn[\s:]*([A-Z0-9]{8,20})\b',
                r'\b([A-Z]{2}[A-Z0-9]{6,18})\b'  # Common serial format
            ],
            
            EntityType.TICKET_ID: [
                r'\bticket[\s#:]*(\d{4,10})\b',
                r'\b(?:INC|REQ|CHG|PRB)[\s#:]*(\d{4,10})\b',
                r'\b([A-Z]{2,4}-\d{4,8})\b'
            ],
            
            EntityType.FILE_PATH: [
                r'\b([A-Z]:\\[^<>:"|?*\s]+(?:\\[^<>:"|?*\s]+)*)\b',  # Windows paths
                r'\b(/[^<>:"|?*\s]+(?:/[^<>:"|?*\s]+)*)\b',  # Unix paths
                r'\b(\\\\[^<>:"|?*\s]+(?:\\[^<>:"|?*\s]+)+)\b'  # UNC paths
            ],
            
            EntityType.URL: [
                r'\b(https?://[^\s<>"\']+)\b',
                r'\b(www\.[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}(?:/[^\s]*)?)\b'
            ],
            
            EntityType.PORT: [
                r'\bporta[\s:]*(\d{1,5})\b',
                r'\bport[\s:]*(\d{1,5})\b',
                r':(\d{1,5})\b'
            ]
        }
        
        # Known entities database (for fuzzy matching)
        self.known_entities = {
            EntityType.SOFTWARE_NAME: {
                "Microsoft Office", "Microsoft Word", "Microsoft Excel", "Microsoft PowerPoint",
                "Microsoft Outlook", "Microsoft Teams", "Adobe Photoshop", "Adobe Acrobat",
                "Google Chrome", "Mozilla Firefox", "Skype for Business", "Zoom",
                "Windows 10", "Windows 11", "SAP", "Oracle", "Salesforce"
            },
            EntityType.HARDWARE_MODEL: {
                "Dell Latitude", "Dell OptiPlex", "HP ProBook", "HP EliteBook", 
                "Lenovo ThinkPad", "MacBook Pro", "MacBook Air"
            },
            EntityType.DEPARTMENT: {
                "IT", "Informatica", "Risorse Umane", "HR", "Amministrazione",
                "Contabilità", "Marketing", "Vendite", "Produzione", "Logistica"
            }
        }
        
        # Validation rules
        self.validation_rules = self._initialize_validation_rules()
        
        # Performance tracking
        self.stats = {
            'total_extractions': 0,
            'entities_found': 0,
            'fuzzy_matches': 0,
            'validation_passed': 0,
            'validation_failed': 0,
            'extraction_time': 0.0,
            'spacy_used': 0,
            'regex_used': 0,
        }
        
        logger.info("EntityExtractor initialized")
    
    async def initialize(self) -> None:
        """Initialize models and resources."""
        try:
            # Load sentence transformer if available
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                logger.info(f"Loading sentence transformer: {self.model_name}")
                self.sentence_model = SentenceTransformer(self.model_name)
                logger.success("Sentence transformer loaded")
            
            # Load spaCy model if available and enabled
            if SPACY_AVAILABLE and self.enable_spacy:
                try:
                    self.spacy_model = spacy.load("it_core_news_sm")
                    logger.success("spaCy Italian model loaded")
                except OSError:
                    logger.warning("spaCy Italian model not found, using blank model")
                    self.spacy_model = Italian()
            
            logger.success("EntityExtractor models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize EntityExtractor: {e}")
            raise
    
    async def extract_entities(self, text: str, 
                             entity_types: Optional[List[EntityType]] = None) -> List[ExtractedEntity]:
        """Extract entities from text.
        
        Args:
            text: Input text to analyze
            entity_types: Optional list of specific entity types to extract
            
        Returns:
            List of extracted entities with metadata
        """
        start_time = time.time()
        
        try:
            entities = []
            
            # Use all types if none specified
            types_to_extract = entity_types or list(EntityType)
            
            # Extract using regex patterns
            regex_entities = self._extract_with_regex(text, types_to_extract)
            entities.extend(regex_entities)
            
            # Extract using spaCy if available
            if self.spacy_model:
                spacy_entities = self._extract_with_spacy(text, types_to_extract)
                entities.extend(spacy_entities)
                self.stats['spacy_used'] += 1
            
            # Apply fuzzy matching for corrections
            if self.enable_fuzzy_matching:
                entities = await self._apply_fuzzy_matching(text, entities)
            
            # Validate entities
            if self.enable_validation:
                entities = self._validate_entities(entities)
            
            # Remove duplicates and overlaps
            entities = self._remove_duplicates_and_overlaps(entities)
            
            # Sort by position
            entities.sort(key=lambda x: x.start_pos)
            
            # Update statistics
            processing_time = time.time() - start_time
            self.stats['total_extractions'] += 1
            self.stats['entities_found'] += len(entities)
            self.stats['extraction_time'] += processing_time
            self.stats['regex_used'] += 1
            
            logger.debug(f"Extracted {len(entities)} entities in {processing_time:.3f}s")
            
            return entities
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
    
    def _extract_with_regex(self, text: str, entity_types: List[EntityType]) -> List[ExtractedEntity]:
        """Extract entities using regex patterns."""
        entities = []
        
        for entity_type in entity_types:
            if entity_type not in self.entity_patterns:
                continue
                
            patterns = self.entity_patterns[entity_type]
            
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Get the matched text (first group or whole match)
                    entity_text = match.group(1) if match.groups() else match.group(0)
                    
                    entity = ExtractedEntity(
                        text=entity_text,
                        entity_type=entity_type,
                        confidence=0.8,  # Base confidence for regex
                        start_pos=match.start(1) if match.groups() else match.start(),
                        end_pos=match.end(1) if match.groups() else match.end(),
                        metadata={
                            'extraction_method': 'regex',
                            'pattern': pattern,
                            'full_match': match.group(0)
                        }
                    )
                    
                    entities.append(entity)
        
        return entities
    
    def _extract_with_spacy(self, text: str, entity_types: List[EntityType]) -> List[ExtractedEntity]:
        """Extract entities using spaCy NER."""
        if not self.spacy_model:
            return []
        
        entities = []
        
        try:
            doc = self.spacy_model(text)
            
            # Map spaCy labels to our entity types
            label_mapping = {
                'PERSON': [EntityType.USER_ID],
                'ORG': [EntityType.DEPARTMENT],
                'GPE': [EntityType.LOCATION],
                'MISC': [EntityType.SOFTWARE_NAME, EntityType.HARDWARE_MODEL],
            }
            
            for ent in doc.ents:
                if ent.label_ in label_mapping:
                    for entity_type in label_mapping[ent.label_]:
                        if entity_type in entity_types:
                            entity = ExtractedEntity(
                                text=ent.text,
                                entity_type=entity_type,
                                confidence=0.7,  # Base confidence for spaCy
                                start_pos=ent.start_char,
                                end_pos=ent.end_char,
                                metadata={
                                    'extraction_method': 'spacy',
                                    'spacy_label': ent.label_,
                                    'spacy_confidence': getattr(ent, 'confidence', 0.7)
                                }
                            )
                            entities.append(entity)
        
        except Exception as e:
            logger.error(f"spaCy extraction failed: {e}")
        
        return entities
    
    async def _apply_fuzzy_matching(self, text: str, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Apply fuzzy matching to correct typos and find similar entities."""
        if not self.enable_fuzzy_matching:
            return entities
        
        corrected_entities = []
        
        for entity in entities:
            # Check if entity type has known entities for fuzzy matching
            if entity.entity_type in self.known_entities:
                known_set = self.known_entities[entity.entity_type]
                
                # Find best fuzzy match
                best_match = difflib.get_close_matches(
                    entity.text,
                    known_set,
                    n=1,
                    cutoff=self.fuzzy_threshold
                )
                
                if best_match and best_match[0] != entity.text:
                    # Create corrected entity
                    corrected_entity = ExtractedEntity(
                        text=best_match[0],
                        entity_type=entity.entity_type,
                        confidence=entity.confidence * 0.9,  # Reduce confidence for fuzzy match
                        start_pos=entity.start_pos,
                        end_pos=entity.end_pos,
                        normalized_value=best_match[0],
                        fuzzy_match=True,
                        original_text=entity.text,
                        metadata={
                            **entity.metadata,
                            'fuzzy_correction': True,
                            'similarity_score': difflib.SequenceMatcher(None, entity.text, best_match[0]).ratio()
                        }
                    )
                    corrected_entities.append(corrected_entity)
                    self.stats['fuzzy_matches'] += 1
                    continue
            
            corrected_entities.append(entity)
        
        return corrected_entities
    
    def _validate_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Validate extracted entities using validation rules."""
        validated_entities = []
        
        for entity in entities:
            # Get validation rules for entity type
            rules = [rule for rule in self.validation_rules if rule.entity_type == entity.entity_type]
            
            if not rules:
                entity.validation_status = "unknown"
                validated_entities.append(entity)
                continue
            
            # Apply validation rules
            validation_passed = False
            
            for rule in rules:
                # Pattern validation
                if re.match(rule.pattern, entity.text):
                    validation_passed = True
                    break
                
                # Custom validator function
                if rule.validator_func and rule.validator_func(entity.text):
                    validation_passed = True
                    break
            
            entity.validation_status = "valid" if validation_passed else "invalid"
            
            # Update confidence based on validation
            if validation_passed:
                entity.confidence = min(entity.confidence * 1.1, 1.0)
                self.stats['validation_passed'] += 1
            else:
                entity.confidence *= 0.8
                self.stats['validation_failed'] += 1
            
            # Keep entity even if validation failed (for manual review)
            validated_entities.append(entity)
        
        return validated_entities
    
    def _remove_duplicates_and_overlaps(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Remove duplicate and overlapping entities."""
        if not entities:
            return entities
        
        # Sort by position and confidence (descending)
        entities_sorted = sorted(entities, key=lambda x: (x.start_pos, -x.confidence))
        
        filtered_entities = []
        
        for entity in entities_sorted:
            # Check for overlaps with existing entities
            overlaps = False
            
            for existing in filtered_entities:
                # Check if entities overlap
                if (entity.start_pos < existing.end_pos and 
                    entity.end_pos > existing.start_pos):
                    
                    # Keep the entity with higher confidence
                    if entity.confidence > existing.confidence:
                        filtered_entities.remove(existing)
                        filtered_entities.append(entity)
                    overlaps = True
                    break
            
            if not overlaps:
                filtered_entities.append(entity)
        
        return filtered_entities
    
    def _initialize_validation_rules(self) -> List[ValidationRule]:
        """Initialize validation rules for different entity types."""
        rules = []
        
        # IP Address validation
        def validate_ip(ip: str) -> bool:
            try:
                parts = ip.split('.')
                if len(parts) != 4:
                    return False
                return all(0 <= int(part) <= 255 for part in parts)
            except:
                return False
        
        rules.append(ValidationRule(
            entity_type=EntityType.IP_ADDRESS,
            pattern=r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',
            validator_func=validate_ip,
            description="Validate IPv4 addresses"
        ))
        
        # Email validation
        rules.append(ValidationRule(
            entity_type=EntityType.EMAIL,
            pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            description="Validate email addresses"
        ))
        
        # Port validation
        def validate_port(port: str) -> bool:
            try:
                port_num = int(port)
                return 1 <= port_num <= 65535
            except:
                return False
        
        rules.append(ValidationRule(
            entity_type=EntityType.PORT,
            pattern=r'^\d{1,5}$',
            validator_func=validate_port,
            description="Validate port numbers (1-65535)"
        ))
        
        return rules
    
    async def batch_extract(self, texts: List[str], 
                          entity_types: Optional[List[EntityType]] = None) -> List[List[ExtractedEntity]]:
        """Extract entities from multiple texts in batch."""
        results = []
        
        for text in texts:
            entities = await self.extract_entities(text, entity_types)
            results.append(entities)
        
        return results
    
    def get_entity_by_type(self, entities: List[ExtractedEntity], 
                          entity_type: EntityType) -> List[ExtractedEntity]:
        """Filter entities by type."""
        return [entity for entity in entities if entity.entity_type == entity_type]
    
    def get_high_confidence_entities(self, entities: List[ExtractedEntity], 
                                   threshold: float = 0.8) -> List[ExtractedEntity]:
        """Get entities above confidence threshold."""
        return [entity for entity in entities if entity.confidence >= threshold]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        stats = self.stats.copy()
        
        if stats['total_extractions'] > 0:
            stats['average_entities_per_extraction'] = stats['entities_found'] / stats['total_extractions']
            stats['average_extraction_time'] = stats['extraction_time'] / stats['total_extractions']
            stats['fuzzy_match_rate'] = (stats['fuzzy_matches'] / stats['entities_found'] * 100) if stats['entities_found'] > 0 else 0
            stats['validation_success_rate'] = (stats['validation_passed'] / (stats['validation_passed'] + stats['validation_failed']) * 100) if (stats['validation_passed'] + stats['validation_failed']) > 0 else 0
        
        stats.update({
            'models_loaded': {
                'sentence_transformer': self.sentence_model is not None,
                'spacy': self.spacy_model is not None,
            },
            'features_enabled': {
                'fuzzy_matching': self.enable_fuzzy_matching,
                'validation': self.enable_validation,
                'spacy_ner': self.enable_spacy,
            },
            'entity_types_supported': len(self.entity_patterns),
            'known_entities_count': sum(len(entities) for entities in self.known_entities.values()),
            'validation_rules_count': len(self.validation_rules),
        })
        
        return stats