"""Advanced TTS Text Processor with Italian language support and emotion injection."""

import asyncio
import re
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime
import unicodedata

from loguru import logger

from voicehelpdeskai.config.manager import get_config_manager


class EmotionType(Enum):
    """Emotion types for speech synthesis."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    EXCITED = "excited"
    CALM = "calm"
    CONCERNED = "concerned"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    APOLOGETIC = "apologetic"


class PauseType(Enum):
    """Types of pauses for speech."""
    SHORT = "short"      # 200ms
    MEDIUM = "medium"    # 500ms
    LONG = "long"        # 800ms
    EXTRA_LONG = "extra_long"  # 1200ms


class CodeSwitchContext(Enum):
    """Contexts for code-switching between languages."""
    TECHNICAL_TERM = "technical_term"
    BRAND_NAME = "brand_name"
    ACRONYM = "acronym"
    SOFTWARE_NAME = "software_name"
    ERROR_MESSAGE = "error_message"
    FILE_PATH = "file_path"
    URL = "url"


@dataclass
class EmotionSettings:
    """Settings for emotion injection."""
    primary_emotion: EmotionType = EmotionType.PROFESSIONAL
    intensity: float = 0.5  # 0.0 to 1.0
    speed_modifier: float = 1.0  # Emotion-based speed adjustment
    pitch_modifier: float = 1.0  # Emotion-based pitch adjustment
    volume_modifier: float = 1.0  # Emotion-based volume adjustment


@dataclass
class ProcessingSettings:
    """Text processing configuration."""
    enable_number_normalization: bool = True
    enable_date_normalization: bool = True
    enable_acronym_expansion: bool = True
    enable_it_pronunciation: bool = True
    enable_emotion_injection: bool = True
    enable_pause_insertion: bool = True
    enable_code_switching: bool = True
    enable_emphasis_detection: bool = True
    
    # Language settings
    primary_language: str = "it"
    secondary_language: str = "en"
    
    # Processing parameters
    max_sentence_length: int = 200
    pause_threshold: int = 50  # Characters before considering pause
    emphasis_markers: List[str] = field(default_factory=lambda: ["!", "IMPORTANTE", "ATTENZIONE", "URGENTE"])


@dataclass
class ProcessedText:
    """Processed text result."""
    original_text: str
    processed_text: str
    emotion_settings: EmotionSettings
    pause_locations: List[Tuple[int, PauseType]]
    code_switches: List[Tuple[int, int, CodeSwitchContext]]
    emphasis_regions: List[Tuple[int, int, float]]  # start, end, strength
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TTSProcessor:
    """Advanced TTS text processor with Italian language support."""
    
    def __init__(self,
                 enable_advanced_processing: bool = True,
                 enable_emotion_detection: bool = True,
                 italian_pronunciation_dict: Optional[str] = None):
        """Initialize TTS processor.
        
        Args:
            enable_advanced_processing: Enable advanced text processing features
            enable_emotion_detection: Enable emotion detection from text
            italian_pronunciation_dict: Path to Italian pronunciation dictionary
        """
        self.config = get_config_manager().get_config()
        self.enable_advanced_processing = enable_advanced_processing
        self.enable_emotion_detection = enable_emotion_detection
        self.italian_pronunciation_dict = italian_pronunciation_dict
        
        # Italian number pronunciation
        self.italian_numbers = {
            '0': 'zero', '1': 'uno', '2': 'due', '3': 'tre', '4': 'quattro',
            '5': 'cinque', '6': 'sei', '7': 'sette', '8': 'otto', '9': 'nove',
            '10': 'dieci', '11': 'undici', '12': 'dodici', '13': 'tredici',
            '14': 'quattordici', '15': 'quindici', '16': 'sedici', '17': 'diciassette',
            '18': 'diciotto', '19': 'diciannove', '20': 'venti', '30': 'trenta',
            '40': 'quaranta', '50': 'cinquanta', '60': 'sessanta', '70': 'settanta',
            '80': 'ottanta', '90': 'novanta', '100': 'cento', '1000': 'mila'
        }
        
        # Italian month names
        self.italian_months = {
            '01': 'gennaio', '02': 'febbraio', '03': 'marzo', '04': 'aprile',
            '05': 'maggio', '06': 'giugno', '07': 'luglio', '08': 'agosto',
            '09': 'settembre', '10': 'ottobre', '11': 'novembre', '12': 'dicembre'
        }
        
        # Italian day names
        self.italian_days = {
            'monday': 'lunedì', 'tuesday': 'martedì', 'wednesday': 'mercoledì',
            'thursday': 'giovedì', 'friday': 'venerdì', 'saturday': 'sabato',
            'sunday': 'domenica'
        }
        
        # IT acronym expansions (Italian)
        self.it_acronyms = {
            'PC': 'pi ci',
            'IT': 'ai ti',
            'USB': 'u es bi',
            'CPU': 'ci pi u',
            'RAM': 'ram',
            'SSD': 'es es di',
            'HDD': 'acca di di',
            'GPU': 'gi pi u',
            'API': 'a pi ai',
            'URL': 'u ar el',
            'HTTP': 'acca ti ti pi',
            'HTTPS': 'acca ti ti pi es',
            'WiFi': 'uai fai',
            'VPN': 'vi pi en',
            'DNS': 'di en es',
            'IP': 'ai pi',
            'OS': 'o es',
            'UI': 'u ai',
            'UX': 'u ics',
            'SQL': 'es cu el',
            'PDF': 'pi di ef',
            'HTML': 'acca ti em el',
            'CSS': 'ci es es',
            'JS': 'javascript',
            'JSON': 'jason',
            'XML': 'ics em el'
        }
        
        # Software pronunciation guides
        self.software_pronunciations = {
            'Microsoft': 'maicrosòft',
            'Google': 'gugl',
            'Chrome': 'crom',
            'Firefox': 'fairfòcs',
            'Outlook': 'àutluk',
            'Excel': 'ecsel',
            'PowerPoint': 'pàuerpoint',
            'Teams': 'tims',
            'Skype': 'scaip',
            'Zoom': 'zum',
            'Adobe': 'adobi',
            'Photoshop': 'fotosciòp',
            'Windows': 'uìndous',
            'Linux': 'lìnucs',
            'macOS': 'mac o es'
        }
        
        # Emotion detection patterns (Italian)
        self.emotion_patterns = {
            EmotionType.HAPPY: [
                r'\b(?:ottimo|perfetto|fantastico|eccellente|bene|grazie|risolto)\b',
                r'\b(?:funziona|risolto|sistemato|fatto|completato)\b',
                r'[!]{1,3}(?=\s|$)'
            ],
            EmotionType.CONCERNED: [
                r'\b(?:problema|errore|guasto|difficoltà|aiuto|supporto)\b',
                r'\b(?:non funziona|non va|rotto|bloccato)\b',
                r'\b(?:preoccupato|ansioso|in difficoltà)\b'
            ],
            EmotionType.ANGRY: [
                r'\b(?:frustrato|arrabbiato|stufo|basta|incredibile)\b',
                r'\b(?:sempre|ancora|solito|ennesimo)\b.*(?:problema|errore)',
                r'[!]{2,}'
            ],
            EmotionType.URGENT: [
                r'\b(?:urgente|critico|importante|subito|immediatamente)\b',
                r'\b(?:emergenza|bloccante|priorità)\b',
                r'MAIUSCOLO{3,}'  # Multiple capital words
            ],
            EmotionType.APOLOGETIC: [
                r'\b(?:scusa|scusi|mi dispiace|perdona|chiedo scusa)\b',
                r'\b(?:mi scuso|perdonami|sono mortificato)\b'
            ],
            EmotionType.PROFESSIONAL: [
                r'\b(?:cortesemente|gentilmente|per favore|la ringrazio)\b',
                r'\b(?:saluti|cordialmente|distinti saluti)\b'
            ]
        }
        
        # Pause insertion patterns (Italian)
        self.pause_patterns = [
            (r'[.!?](?=\s[A-Z])', PauseType.LONG),      # End of sentence
            (r'[,;:](?=\s)', PauseType.MEDIUM),         # Comma, semicolon, colon
            (r'\b(?:quindi|però|tuttavia|inoltre|infatti)(?=\s)', PauseType.SHORT),  # Conjunctions
            (r'(?<=\w)\s*-\s*(?=\w)', PauseType.SHORT), # Dashes
            (r'\s*\([^)]*\)\s*', PauseType.SHORT),      # Parentheses
        ]
        
        # Emphasis detection patterns (Italian)
        self.emphasis_patterns = [
            (r'\*([^*]+)\*', 1.3),          # *text*
            (r'\b[A-Z]{2,}\b', 1.4),        # ALL CAPS words
            (r'\b(?:IMPORTANTE|ATTENZIONE|URGENTE|CRITICO)\b', 1.5),  # Important words
            (r'!+', 1.2),                    # Multiple exclamations
            (r'\b(?:molto|davvero|proprio|estremamente)(?=\s)', 1.2),  # Intensifiers
        ]
        
        # Performance metrics
        self.stats = {
            'total_processed': 0,
            'numbers_normalized': 0,
            'dates_normalized': 0,
            'acronyms_expanded': 0,
            'emotions_detected': 0,
            'pauses_inserted': 0,
            'code_switches_detected': 0,
            'emphasis_regions_found': 0,
            'processing_time': 0.0,
        }
        
        logger.info("TTSProcessor initialized with Italian language support")
    
    async def process_text(self, 
                          text: str,
                          settings: Optional[ProcessingSettings] = None,
                          target_emotion: Optional[EmotionType] = None) -> ProcessedText:
        """Process text for TTS synthesis.
        
        Args:
            text: Input text to process
            settings: Processing configuration
            target_emotion: Override emotion detection with specific emotion
            
        Returns:
            Processed text with metadata
        """
        start_time = time.time()
        
        if not settings:
            settings = ProcessingSettings()
        
        try:
            original_text = text
            processed = text
            
            # Step 1: Basic text cleaning
            processed = await self._clean_text(processed)
            
            # Step 2: Number normalization
            if settings.enable_number_normalization:
                processed = await self._normalize_numbers(processed)
            
            # Step 3: Date normalization
            if settings.enable_date_normalization:
                processed = await self._normalize_dates(processed)
            
            # Step 4: Acronym expansion
            if settings.enable_acronym_expansion:
                processed = await self._expand_acronyms(processed)
            
            # Step 5: IT pronunciation guide
            if settings.enable_it_pronunciation:
                processed = await self._apply_pronunciation_guide(processed)
            
            # Step 6: Emotion detection/injection
            emotion_settings = EmotionSettings()
            if settings.enable_emotion_injection:
                if target_emotion:
                    emotion_settings.primary_emotion = target_emotion
                else:
                    emotion_settings = await self._detect_emotion(processed)
            
            # Step 7: Pause insertion
            pause_locations = []
            if settings.enable_pause_insertion:
                processed, pause_locations = await self._insert_pauses(processed)
            
            # Step 8: Code-switching detection
            code_switches = []
            if settings.enable_code_switching:
                code_switches = await self._detect_code_switches(processed)
            
            # Step 9: Emphasis detection
            emphasis_regions = []
            if settings.enable_emphasis_detection:
                emphasis_regions = await self._detect_emphasis(processed)
            
            # Step 10: Final text cleanup
            processed = await self._final_cleanup(processed, settings)
            
            # Create result
            processing_time = time.time() - start_time
            
            result = ProcessedText(
                original_text=original_text,
                processed_text=processed,
                emotion_settings=emotion_settings,
                pause_locations=pause_locations,
                code_switches=code_switches,
                emphasis_regions=emphasis_regions,
                processing_time=processing_time,
                metadata={
                    'original_length': len(original_text),
                    'processed_length': len(processed),
                    'reduction_ratio': (len(original_text) - len(processed)) / len(original_text) if original_text else 0,
                    'processing_stages': len([s for s in [
                        settings.enable_number_normalization,
                        settings.enable_date_normalization,
                        settings.enable_acronym_expansion,
                        settings.enable_it_pronunciation,
                        settings.enable_emotion_injection,
                        settings.enable_pause_insertion,
                        settings.enable_code_switching,
                        settings.enable_emphasis_detection
                    ] if s]),
                }
            )
            
            # Update statistics
            self._update_stats(result)
            
            logger.debug(f"Processed text in {processing_time:.3f}s: "
                        f"{len(original_text)} -> {len(processed)} chars")
            
            return result
            
        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            # Return minimal processed text
            return ProcessedText(
                original_text=text,
                processed_text=text,
                emotion_settings=EmotionSettings(),
                pause_locations=[],
                code_switches=[],
                emphasis_regions=[],
                processing_time=time.time() - start_time,
                metadata={'error': str(e)}
            )
    
    async def _clean_text(self, text: str) -> str:
        """Basic text cleaning and normalization."""
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Normalize unicode characters
        cleaned = unicodedata.normalize('NFC', cleaned)
        
        # Fix common punctuation issues
        cleaned = re.sub(r'\s*([.!?,:;])\s*', r'\1 ', cleaned)
        cleaned = re.sub(r'\s*([()])\s*', r' \1 ', cleaned)
        
        # Remove multiple consecutive punctuation
        cleaned = re.sub(r'([.!?]){2,}', r'\1', cleaned)
        
        # Clean up spacing
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    async def _normalize_numbers(self, text: str) -> str:
        """Convert numbers to Italian text representation."""
        
        def convert_number(match):
            number = match.group()
            try:
                num = int(number)
                return self._number_to_italian(num)
            except ValueError:
                return number
        
        # Handle simple numbers (1-999999)
        normalized = re.sub(r'\b\d{1,6}\b', convert_number, text)
        
        # Handle decimal numbers
        normalized = re.sub(r'\b(\d+)[,.](\d+)\b', 
                           lambda m: f"{self._number_to_italian(int(m.group(1)))} virgola {self._number_to_italian(int(m.group(2)))}", 
                           normalized)
        
        # Handle percentages
        normalized = re.sub(r'\b(\d+)%\b', 
                           lambda m: f"{self._number_to_italian(int(m.group(1)))} per cento", 
                           normalized)
        
        self.stats['numbers_normalized'] += len(re.findall(r'\b\d+\b', text))
        
        return normalized
    
    def _number_to_italian(self, num: int) -> str:
        """Convert integer to Italian text."""
        if num == 0:
            return "zero"
        
        if str(num) in self.italian_numbers:
            return self.italian_numbers[str(num)]
        
        if num < 100:
            if num <= 20:
                return self.italian_numbers.get(str(num), str(num))
            else:
                tens = (num // 10) * 10
                units = num % 10
                if units == 0:
                    return self.italian_numbers[str(tens)]
                else:
                    return f"{self.italian_numbers[str(tens)]}{self.italian_numbers[str(units)]}"
        
        # For larger numbers, use simplified approach
        if num < 1000:
            hundreds = num // 100
            remainder = num % 100
            result = f"{self.italian_numbers[str(hundreds)]}cento"
            if remainder > 0:
                result += f" {self._number_to_italian(remainder)}"
            return result
        
        # For very large numbers, return as-is with "mila" suffix
        if num < 1000000:
            thousands = num // 1000
            remainder = num % 1000
            result = f"{self._number_to_italian(thousands)} mila"
            if remainder > 0:
                result += f" {self._number_to_italian(remainder)}"
            return result
        
        return str(num)  # Fallback for very large numbers
    
    async def _normalize_dates(self, text: str) -> str:
        """Convert dates to Italian text representation."""
        
        # Handle DD/MM/YYYY format
        def convert_date(match):
            day, month, year = match.groups()
            day_num = int(day)
            month_name = self.italian_months.get(month.zfill(2), month)
            return f"{self._number_to_italian(day_num)} {month_name} {year}"
        
        normalized = re.sub(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', convert_date, text)
        
        # Handle DD-MM-YYYY format
        normalized = re.sub(r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', convert_date, normalized)
        
        # Handle time format (HH:MM)
        def convert_time(match):
            hour, minute = match.groups()
            return f"ore {self._number_to_italian(int(hour))} e {self._number_to_italian(int(minute))}"
        
        normalized = re.sub(r'\b(\d{1,2}):(\d{2})\b', convert_time, normalized)
        
        self.stats['dates_normalized'] += len(re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b', text))
        
        return normalized
    
    async def _expand_acronyms(self, text: str) -> str:
        """Expand IT acronyms to pronunciation-friendly text."""
        
        expanded = text
        
        for acronym, expansion in self.it_acronyms.items():
            # Match whole word acronyms (case insensitive)
            pattern = r'\b' + re.escape(acronym) + r'\b'
            if re.search(pattern, expanded, re.IGNORECASE):
                expanded = re.sub(pattern, expansion, expanded, flags=re.IGNORECASE)
                self.stats['acronyms_expanded'] += 1
        
        return expanded
    
    async def _apply_pronunciation_guide(self, text: str) -> str:
        """Apply Italian pronunciation guide for software names."""
        
        guided = text
        
        for software, pronunciation in self.software_pronunciations.items():
            pattern = r'\b' + re.escape(software) + r'\b'
            if re.search(pattern, guided, re.IGNORECASE):
                guided = re.sub(pattern, pronunciation, guided, flags=re.IGNORECASE)
        
        return guided
    
    async def _detect_emotion(self, text: str) -> EmotionSettings:
        """Detect emotion from text and create appropriate settings."""
        
        emotion_scores = {}
        text_lower = text.lower()
        
        # Score each emotion based on pattern matches
        for emotion, patterns in self.emotion_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches
            
            if score > 0:
                emotion_scores[emotion] = score
        
        # Determine primary emotion
        if emotion_scores:
            primary_emotion = max(emotion_scores, key=emotion_scores.get)
            intensity = min(emotion_scores[primary_emotion] * 0.2, 1.0)
            self.stats['emotions_detected'] += 1
        else:
            primary_emotion = EmotionType.PROFESSIONAL
            intensity = 0.3
        
        # Create emotion-specific settings
        settings = EmotionSettings(
            primary_emotion=primary_emotion,
            intensity=intensity
        )
        
        # Adjust prosodic parameters based on emotion
        if primary_emotion == EmotionType.HAPPY:
            settings.speed_modifier = 1.1
            settings.pitch_modifier = 1.1
            settings.volume_modifier = 1.1
        elif primary_emotion == EmotionType.CONCERNED:
            settings.speed_modifier = 0.95
            settings.pitch_modifier = 0.95
            settings.volume_modifier = 1.0
        elif primary_emotion == EmotionType.ANGRY:
            settings.speed_modifier = 1.15
            settings.pitch_modifier = 1.2
            settings.volume_modifier = 1.2
        elif primary_emotion == EmotionType.URGENT:
            settings.speed_modifier = 1.2
            settings.pitch_modifier = 1.15
            settings.volume_modifier = 1.15
        elif primary_emotion == EmotionType.APOLOGETIC:
            settings.speed_modifier = 0.9
            settings.pitch_modifier = 0.9
            settings.volume_modifier = 0.95
        elif primary_emotion == EmotionType.PROFESSIONAL:
            settings.speed_modifier = 1.0
            settings.pitch_modifier = 1.0
            settings.volume_modifier = 1.0
        
        return settings
    
    async def _insert_pauses(self, text: str) -> Tuple[str, List[Tuple[int, PauseType]]]:
        """Insert intelligent pauses in text."""
        
        pause_locations = []
        processed = text
        
        # Apply pause patterns
        for pattern, pause_type in self.pause_patterns:
            for match in re.finditer(pattern, processed):
                pause_locations.append((match.end(), pause_type))
                self.stats['pauses_inserted'] += 1
        
        # Sort pauses by position
        pause_locations.sort(key=lambda x: x[0])
        
        return processed, pause_locations
    
    async def _detect_code_switches(self, text: str) -> List[Tuple[int, int, CodeSwitchContext]]:
        """Detect code-switching contexts for pronunciation."""
        
        code_switches = []
        
        # Detect technical terms (usually in English)
        technical_patterns = {
            CodeSwitchContext.ERROR_MESSAGE: r'"[^"]*(?:error|exception|failed|timeout)[^"]*"',
            CodeSwitchContext.FILE_PATH: r'[A-Z]:\\[^\\/:*?"<>|\s]*(?:\\[^\\/:*?"<>|\s]*)*',
            CodeSwitchContext.URL: r'https?://[^\s<>"\']+',
            CodeSwitchContext.SOFTWARE_NAME: r'\b(?:Microsoft|Google|Adobe|Mozilla|Apple)\s+\w+\b',
            CodeSwitchContext.TECHNICAL_TERM: r'\b(?:server|database|network|protocol|framework|library)\b',
        }
        
        for context, pattern in technical_patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                code_switches.append((match.start(), match.end(), context))
                self.stats['code_switches_detected'] += 1
        
        return code_switches
    
    async def _detect_emphasis(self, text: str) -> List[Tuple[int, int, float]]:
        """Detect regions that should be emphasized."""
        
        emphasis_regions = []
        
        for pattern, strength in self.emphasis_patterns:
            for match in re.finditer(pattern, text):
                emphasis_regions.append((match.start(), match.end(), strength))
                self.stats['emphasis_regions_found'] += 1
        
        return emphasis_regions
    
    async def _final_cleanup(self, text: str, settings: ProcessingSettings) -> str:
        """Final text cleanup before synthesis."""
        
        # Remove processing markers
        cleaned = re.sub(r'<[^>]+>', '', text)
        
        # Ensure proper spacing
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Split long sentences if needed
        if settings.max_sentence_length > 0:
            sentences = re.split(r'[.!?]+\s*', cleaned)
            processed_sentences = []
            
            for sentence in sentences:
                if len(sentence) > settings.max_sentence_length:
                    # Split at natural pause points
                    parts = re.split(r'[,;:]\s*', sentence)
                    processed_sentences.extend(parts)
                else:
                    processed_sentences.append(sentence)
            
            cleaned = '. '.join(processed_sentences)
        
        return cleaned
    
    def _update_stats(self, result: ProcessedText) -> None:
        """Update processing statistics."""
        self.stats['total_processed'] += 1
        self.stats['processing_time'] += result.processing_time
    
    async def batch_process(self, 
                           texts: List[str],
                           settings: Optional[ProcessingSettings] = None) -> List[ProcessedText]:
        """Process multiple texts in batch."""
        
        tasks = [self.process_text(text, settings) for text in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch processing failed for text {i}: {result}")
                processed_results.append(ProcessedText(
                    original_text=texts[i],
                    processed_text=texts[i],
                    emotion_settings=EmotionSettings(),
                    pause_locations=[],
                    code_switches=[],
                    emphasis_regions=[],
                    metadata={'batch_error': str(result)}
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        stats = self.stats.copy()
        
        if stats['total_processed'] > 0:
            stats['average_processing_time'] = stats['processing_time'] / stats['total_processed']
            stats['numbers_per_text'] = stats['numbers_normalized'] / stats['total_processed']
            stats['acronyms_per_text'] = stats['acronyms_expanded'] / stats['total_processed']
            stats['emotions_detection_rate'] = (stats['emotions_detected'] / stats['total_processed']) * 100
        
        stats.update({
            'italian_numbers_supported': len(self.italian_numbers),
            'acronyms_supported': len(self.it_acronyms),
            'software_pronunciations_supported': len(self.software_pronunciations),
            'emotion_patterns_loaded': len(self.emotion_patterns),
            'advanced_processing_enabled': self.enable_advanced_processing,
            'emotion_detection_enabled': self.enable_emotion_detection,
        })
        
        return stats