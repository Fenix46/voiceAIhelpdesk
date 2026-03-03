"""Advanced transcription post-processing with Italian language support."""

import re
import string
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import unicodedata

from loguru import logger

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available - NER and advanced processing disabled")

from voicehelpdeskai.services.stt.whisper_service import TranscriptionResult


@dataclass
class ProcessedTranscription:
    """Processed transcription with enhanced metadata."""
    text: str
    original_text: str
    confidence: float
    language: str
    processing_applied: List[str]
    entities: List[Dict[str, Any]]
    normalized_numbers: List[Dict[str, Any]]
    corrected_words: List[Dict[str, Any]]
    profanity_filtered: bool
    processing_time: float


class TranscriptionProcessor:
    """Advanced transcription processor with Italian language support."""
    
    # Italian punctuation rules
    ITALIAN_PUNCTUATION_RULES = {
        r'\s+([,.!?;:])': r'\1',  # Remove space before punctuation
        r'([,.!?;:])\s*([,.!?;:])': r'\1 \2',  # Ensure space after punctuation
        r'\s*\.\s*\.\s*\.': r'...',  # Normalize ellipsis
        r'\s*\?\s*\!': r'?!',  # Normalize question-exclamation
        r'\s*\!\s*\?': r'!?',  # Normalize exclamation-question
    }
    
    # Italian number words to digits
    ITALIAN_NUMBERS = {
        'zero': '0', 'uno': '1', 'due': '2', 'tre': '3', 'quattro': '4',
        'cinque': '5', 'sei': '6', 'sette': '7', 'otto': '8', 'nove': '9',
        'dieci': '10', 'undici': '11', 'dodici': '12', 'tredici': '13',
        'quattordici': '14', 'quindici': '15', 'sedici': '16', 'diciassette': '17',
        'diciotto': '18', 'diciannove': '19', 'venti': '20', 'trenta': '30',
        'quaranta': '40', 'cinquanta': '50', 'sessanta': '60', 'settanta': '70',
        'ottanta': '80', 'novanta': '90', 'cento': '100', 'mille': '1000',
        'milione': '1000000', 'miliardo': '1000000000'
    }
    
    # Italian month names
    ITALIAN_MONTHS = {
        'gennaio': '01', 'febbraio': '02', 'marzo': '03', 'aprile': '04',
        'maggio': '05', 'giugno': '06', 'luglio': '07', 'agosto': '08',
        'settembre': '09', 'ottobre': '10', 'novembre': '11', 'dicembre': '12'
    }
    
    # Italian IT terms and acronyms expansion
    IT_ACRONYMS = {
        'ai': 'Intelligenza Artificiale',
        'api': 'Application Programming Interface',
        'cpu': 'Central Processing Unit',
        'gpu': 'Graphics Processing Unit',
        'ram': 'Random Access Memory',
        'ssd': 'Solid State Drive',
        'hdd': 'Hard Disk Drive',
        'usb': 'Universal Serial Bus',
        'wifi': 'Wireless Fidelity',
        'bluetooth': 'Bluetooth',
        'vpn': 'Virtual Private Network',
        'dns': 'Domain Name System',
        'ip': 'Internet Protocol',
        'tcp': 'Transmission Control Protocol',
        'udp': 'User Datagram Protocol',
        'http': 'HyperText Transfer Protocol',
        'https': 'HyperText Transfer Protocol Secure',
        'ssl': 'Secure Sockets Layer',
        'tls': 'Transport Layer Security',
        'iot': 'Internet of Things',
        'crm': 'Customer Relationship Management',
        'erp': 'Enterprise Resource Planning',
        'sql': 'Structured Query Language',
        'nosql': 'Not Only SQL',
        'json': 'JavaScript Object Notation',
        'xml': 'eXtensible Markup Language',
        'csv': 'Comma-Separated Values',
        'pdf': 'Portable Document Format',
        'url': 'Uniform Resource Locator',
        'uri': 'Uniform Resource Identifier',
        'gui': 'Graphical User Interface',
        'cli': 'Command Line Interface',
        'ide': 'Integrated Development Environment',
        'sdk': 'Software Development Kit',
        'api': 'Application Programming Interface',
        'rest': 'Representational State Transfer',
        'soap': 'Simple Object Access Protocol',
        'crud': 'Create, Read, Update, Delete',
        'mvc': 'Model-View-Controller',
        'orm': 'Object-Relational Mapping',
        'devops': 'Development Operations',
        'ci': 'Continuous Integration',
        'cd': 'Continuous Deployment',
        'git': 'Git Version Control',
        'svn': 'Subversion',
        'ftp': 'File Transfer Protocol',
        'smtp': 'Simple Mail Transfer Protocol',
        'pop3': 'Post Office Protocol 3',
        'imap': 'Internet Message Access Protocol',
    }
    
    # Common IT asset patterns
    ASSET_PATTERNS = [
        r'\b(?:laptop|desktop|server|workstation)\s+[A-Z0-9-]+\b',
        r'\b(?:PC|pc)\s*[0-9]+\b',
        r'\b[A-Z]{2,4}[0-9]{3,6}\b',  # Asset codes like IT001234
        r'\b(?:printer|stampante)\s+[A-Z0-9-]+\b',
        r'\b(?:IP|ip)\s+(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
        r'\b(?:MAC|mac)\s+(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b',
    ]
    
    # Italian profanity filter (basic implementation)
    ITALIAN_PROFANITY = {
        'cazzo', 'merda', 'stronzo', 'bastardo', 'fottuto', 'dannato',
        'maledetto', 'porco', 'cavolo', 'accidenti'  # Including mild ones
    }
    
    # Common Italian transcription errors and corrections
    ITALIAN_CORRECTIONS = {
        'perchè': 'perché',
        'perche': 'perché',
        'cioè': 'cioè',
        'cioe': 'cioè',
        'più': 'più',
        'piu': 'più',
        'già': 'già',
        'gia': 'già',
        'così': 'così',
        'cosi': 'così',
        'però': 'però',
        'pero': 'però',
        'poichè': 'poiché',
        'poiche': 'poiché',
        'affinchè': 'affinché',
        'affinche': 'affinché',
    }
    
    def __init__(self, 
                 enable_punctuation: bool = True,
                 enable_number_normalization: bool = True,
                 enable_acronym_expansion: bool = True,
                 enable_profanity_filter: bool = True,
                 enable_ner: bool = True,
                 enable_spell_correction: bool = True,
                 profanity_replacement: str = "***"):
        """Initialize transcription processor.
        
        Args:
            enable_punctuation: Enable punctuation normalization
            enable_number_normalization: Enable number and date normalization
            enable_acronym_expansion: Enable IT acronym expansion
            enable_profanity_filter: Enable profanity filtering
            enable_ner: Enable named entity recognition
            enable_spell_correction: Enable basic spell correction
            profanity_replacement: Replacement string for profanity
        """
        self.enable_punctuation = enable_punctuation
        self.enable_number_normalization = enable_number_normalization
        self.enable_acronym_expansion = enable_acronym_expansion
        self.enable_profanity_filter = enable_profanity_filter
        self.enable_ner = enable_ner
        self.enable_spell_correction = enable_spell_correction
        self.profanity_replacement = profanity_replacement
        
        # Load spaCy model for Italian if available
        self.nlp = None
        if SPACY_AVAILABLE and enable_ner:
            try:
                self.nlp = spacy.load("it_core_news_sm")
                logger.info("Loaded Italian spaCy model for NER")
            except OSError:
                try:
                    self.nlp = spacy.load("it_core_news_md")
                    logger.info("Loaded Italian spaCy model (medium) for NER")
                except OSError:
                    logger.warning("Italian spaCy model not found - NER disabled")
        
        # Compile regex patterns for performance
        self.asset_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.ASSET_PATTERNS]
        self.punctuation_patterns = [(re.compile(pattern), replacement) 
                                   for pattern, replacement in self.ITALIAN_PUNCTUATION_RULES.items()]
        
        logger.info("TranscriptionProcessor initialized with Italian language support")
    
    def process(self, transcription: TranscriptionResult) -> ProcessedTranscription:
        """Process transcription with all enabled enhancements.
        
        Args:
            transcription: Original transcription result
            
        Returns:
            ProcessedTranscription with enhancements applied
        """
        start_time = datetime.now()
        original_text = transcription.text
        processed_text = original_text
        processing_applied = []
        entities = []
        normalized_numbers = []
        corrected_words = []
        profanity_filtered = False
        
        try:
            # 1. Basic text cleaning
            processed_text = self._clean_text(processed_text)
            processing_applied.append("text_cleaning")
            
            # 2. Spell correction
            if self.enable_spell_correction:
                processed_text, corrections = self._correct_italian_spelling(processed_text)
                if corrections:
                    corrected_words.extend(corrections)
                    processing_applied.append("spell_correction")
            
            # 3. Punctuation normalization
            if self.enable_punctuation:
                processed_text = self._normalize_punctuation(processed_text)
                processing_applied.append("punctuation_normalization")
            
            # 4. Number and date normalization
            if self.enable_number_normalization:
                processed_text, numbers = self._normalize_numbers_and_dates(processed_text)
                if numbers:
                    normalized_numbers.extend(numbers)
                    processing_applied.append("number_normalization")
            
            # 5. Acronym expansion
            if self.enable_acronym_expansion:
                processed_text = self._expand_acronyms(processed_text)
                processing_applied.append("acronym_expansion")
            
            # 6. Named Entity Recognition
            if self.enable_ner and self.nlp:
                entities = self._extract_entities(processed_text)
                processing_applied.append("named_entity_recognition")
            
            # 7. Asset code recognition
            asset_entities = self._extract_asset_codes(processed_text)
            if asset_entities:
                entities.extend(asset_entities)
                processing_applied.append("asset_recognition")
            
            # 8. Profanity filtering (last to preserve context for other processing)
            if self.enable_profanity_filter:
                processed_text, was_filtered = self._filter_profanity(processed_text)
                if was_filtered:
                    profanity_filtered = True
                    processing_applied.append("profanity_filtering")
            
            # 9. Final text normalization
            processed_text = self._final_normalization(processed_text)
            
        except Exception as e:
            logger.error(f"Error during transcription processing: {e}")
            # Return original text if processing fails
            processed_text = original_text
            processing_applied = ["error_fallback"]
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return ProcessedTranscription(
            text=processed_text,
            original_text=original_text,
            confidence=transcription.confidence,
            language=transcription.language,
            processing_applied=processing_applied,
            entities=entities,
            normalized_numbers=normalized_numbers,
            corrected_words=corrected_words,
            profanity_filtered=profanity_filtered,
            processing_time=processing_time
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return text
            
        # Normalize unicode
        text = unicodedata.normalize('NFKC', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _correct_italian_spelling(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Correct common Italian spelling mistakes."""
        corrections = []
        corrected_text = text
        
        for mistake, correction in self.ITALIAN_CORRECTIONS.items():
            if mistake in corrected_text:
                # Find all occurrences with positions
                positions = []
                start = 0
                while True:
                    pos = corrected_text.find(mistake, start)
                    if pos == -1:
                        break
                    positions.append(pos)
                    start = pos + 1
                
                if positions:
                    corrected_text = corrected_text.replace(mistake, correction)
                    corrections.append({
                        'original': mistake,
                        'corrected': correction,
                        'positions': positions,
                        'type': 'spelling'
                    })
        
        return corrected_text, corrections
    
    def _normalize_punctuation(self, text: str) -> str:
        """Normalize Italian punctuation."""
        for pattern, replacement in self.punctuation_patterns:
            text = pattern.sub(replacement, text)
        
        # Ensure proper capitalization after sentence endings
        text = re.sub(r'([.!?])\s+([a-z])', lambda m: m.group(1) + ' ' + m.group(2).upper(), text)
        
        # Capitalize first letter
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        
        return text
    
    def _normalize_numbers_and_dates(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Normalize Italian numbers and dates."""
        normalized = []
        result_text = text
        
        # Convert Italian number words to digits
        for word, digit in self.ITALIAN_NUMBERS.items():
            pattern = r'\b' + re.escape(word) + r'\b'
            matches = list(re.finditer(pattern, result_text, re.IGNORECASE))
            if matches:
                result_text = re.sub(pattern, digit, result_text, flags=re.IGNORECASE)
                for match in matches:
                    normalized.append({
                        'original': match.group(),
                        'normalized': digit,
                        'type': 'number_word',
                        'position': match.start()
                    })
        
        # Normalize date patterns
        date_patterns = [
            # "15 gennaio 2024" -> "15/01/2024"
            (r'\b(\d{1,2})\s+(' + '|'.join(self.ITALIAN_MONTHS.keys()) + r')\s+(\d{4})\b',
             lambda m: f"{m.group(1)}/{self.ITALIAN_MONTHS[m.group(2).lower()]}/{m.group(3)}"),
            
            # "gennaio 2024" -> "01/2024"
            (r'\b(' + '|'.join(self.ITALIAN_MONTHS.keys()) + r')\s+(\d{4})\b',
             lambda m: f"{self.ITALIAN_MONTHS[m.group(1).lower()]}/{m.group(2)}"),
        ]
        
        for pattern, replacement in date_patterns:
            matches = list(re.finditer(pattern, result_text, re.IGNORECASE))
            for match in matches:
                original = match.group()
                if callable(replacement):
                    normalized_date = replacement(match)
                else:
                    normalized_date = replacement
                
                result_text = result_text.replace(original, normalized_date)
                normalized.append({
                    'original': original,
                    'normalized': normalized_date,
                    'type': 'date',
                    'position': match.start()
                })
        
        # Normalize time patterns
        time_patterns = [
            # "ore 14 e 30" -> "14:30"
            (r'\bore\s+(\d{1,2})\s+e\s+(\d{1,2})\b', r'\1:\2'),
            # "alle 14" -> "14:00"
            (r'\balle\s+(\d{1,2})\b', r'\1:00'),
        ]
        
        for pattern, replacement in time_patterns:
            matches = list(re.finditer(pattern, result_text, re.IGNORECASE))
            for match in matches:
                original = match.group()
                normalized_time = re.sub(pattern, replacement, original, flags=re.IGNORECASE)
                result_text = result_text.replace(original, normalized_time)
                normalized.append({
                    'original': original,
                    'normalized': normalized_time,
                    'type': 'time',
                    'position': match.start()
                })
        
        return result_text, normalized
    
    def _expand_acronyms(self, text: str) -> str:
        """Expand IT acronyms with context awareness."""
        words = text.split()
        expanded_words = []
        
        for i, word in enumerate(words):
            # Clean word for lookup (remove punctuation)
            clean_word = word.lower().strip(string.punctuation)
            
            # Check if it's a known acronym
            if clean_word in self.IT_ACRONYMS:
                # Check context - don't expand if it's part of a URL or technical term
                context_before = ' '.join(words[max(0, i-2):i]).lower()
                context_after = ' '.join(words[i+1:min(len(words), i+3)]).lower()
                
                # Don't expand in certain contexts
                skip_contexts = ['http', 'https', 'www', 'ftp', '.com', '.it', '.org']
                should_skip = any(ctx in context_before + context_after for ctx in skip_contexts)
                
                if not should_skip:
                    # Expand acronym while preserving original punctuation
                    expanded = self.IT_ACRONYMS[clean_word]
                    # Preserve case of first letter
                    if word[0].isupper():
                        expanded = expanded[0].upper() + expanded[1:] if len(expanded) > 1 else expanded.upper()
                    
                    # Add back punctuation
                    for char in word:
                        if char in string.punctuation:
                            expanded += char
                            break
                    
                    expanded_words.append(expanded)
                else:
                    expanded_words.append(word)
            else:
                expanded_words.append(word)
        
        return ' '.join(expanded_words)
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities using spaCy."""
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entities.append({
                'text': ent.text,
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char,
                'confidence': getattr(ent, 'confidence', 1.0),
                'type': 'named_entity'
            })
        
        return entities
    
    def _extract_asset_codes(self, text: str) -> List[Dict[str, Any]]:
        """Extract IT asset codes and identifiers."""
        entities = []
        
        for pattern in self.asset_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                entities.append({
                    'text': match.group(),
                    'label': 'ASSET',
                    'start': match.start(),
                    'end': match.end(),
                    'confidence': 0.9,
                    'type': 'asset_code'
                })
        
        return entities
    
    def _filter_profanity(self, text: str) -> Tuple[str, bool]:
        """Filter profanity from text."""
        was_filtered = False
        words = text.split()
        filtered_words = []
        
        for word in words:
            clean_word = word.lower().strip(string.punctuation)
            if clean_word in self.ITALIAN_PROFANITY:
                filtered_words.append(self.profanity_replacement)
                was_filtered = True
            else:
                filtered_words.append(word)
        
        return ' '.join(filtered_words), was_filtered
    
    def _final_normalization(self, text: str) -> str:
        """Final text normalization and cleanup."""
        if not text:
            return text
        
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Ensure single space after punctuation
        text = re.sub(r'([.!?])\s*', r'\1 ', text)
        text = re.sub(r'([,:;])\s*', r'\1 ', text)
        
        # Remove space before punctuation
        text = re.sub(r'\s+([.!?,:;])', r'\1', text)
        
        # Strip and ensure single space
        text = text.strip()
        
        return text
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            'punctuation_enabled': self.enable_punctuation,
            'number_normalization_enabled': self.enable_number_normalization,
            'acronym_expansion_enabled': self.enable_acronym_expansion,
            'profanity_filter_enabled': self.enable_profanity_filter,
            'ner_enabled': self.enable_ner,
            'spell_correction_enabled': self.enable_spell_correction,
            'spacy_available': SPACY_AVAILABLE,
            'nlp_model_loaded': self.nlp is not None,
            'supported_languages': ['it', 'italian'],
            'it_terms_count': len(self.IT_ACRONYMS),
            'correction_rules_count': len(self.ITALIAN_CORRECTIONS),
        }