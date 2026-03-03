"""Advanced Whisper STT service with optimizations for Italian language support."""

import asyncio
import hashlib
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, AsyncGenerator
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
from loguru import logger

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    try:
        import whisper
        FASTER_WHISPER_AVAILABLE = False
        logger.warning("faster-whisper not available, falling back to openai-whisper")
    except ImportError:
        logger.error("No Whisper implementation available")
        raise ImportError("Please install either faster-whisper or openai-whisper")

from voicehelpdeskai.config.manager import get_config_manager


@dataclass
class TranscriptionResult:
    """Result of transcription with metadata."""
    text: str
    language: str
    language_probability: float
    confidence: float
    words: List[Dict[str, Any]]
    segments: List[Dict[str, Any]]
    processing_time: float
    model_used: str


@dataclass
class WordTimestamp:
    """Word-level timestamp information."""
    word: str
    start: float
    end: float
    confidence: float


class WhisperService:
    """Advanced Whisper STT service with Italian language optimizations."""
    
    # Italian language variants and dialects
    ITALIAN_LANGUAGE_CODES = ['it', 'it-IT', 'it-CH']
    
    # Common Italian accents and regional variations
    ITALIAN_ACCENT_MAPPING = {
        'à': ['a', 'à'],
        'è': ['e', 'è', 'é'],
        'é': ['e', 'è', 'é'],
        'ì': ['i', 'ì'],
        'ò': ['o', 'ò', 'ó'],
        'ó': ['o', 'ò', 'ó'],
        'ù': ['u', 'ù'],
    }
    
    # Italian IT terms and acronyms
    IT_TERMS = {
        'ai': 'AI',
        'api': 'API',
        'cpu': 'CPU',
        'gpu': 'GPU',
        'ram': 'RAM',
        'ssd': 'SSD',
        'hdd': 'HDD',
        'usb': 'USB',
        'wifi': 'Wi-Fi',
        'vpn': 'VPN',
        'dns': 'DNS',
        'ip': 'IP',
        'tcp': 'TCP',
        'udp': 'UDP',
        'http': 'HTTP',
        'https': 'HTTPS',
        'ssl': 'SSL',
        'tls': 'TLS',
        'iot': 'IoT',
        'crm': 'CRM',
        'erp': 'ERP',
        'sql': 'SQL',
        'nosql': 'NoSQL',
    }
    
    def __init__(self, 
                 model_size: str = "medium",
                 device: Optional[str] = None,
                 compute_type: str = "auto",
                 cpu_threads: int = 0,
                 num_workers: int = 1):
        """Initialize Whisper service.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to use (auto, cpu, cuda)
            compute_type: Compute type for quantization (int8, int16, float16, float32)
            cpu_threads: Number of CPU threads (0 for auto)
            num_workers: Number of worker threads for parallel processing
        """
        self.config = get_config_manager().get_config()
        self.model_size = model_size
        self.device = device or self._detect_optimal_device()
        self.compute_type = self._optimize_compute_type(compute_type)
        self.cpu_threads = cpu_threads or self._detect_optimal_cpu_threads()
        self.num_workers = num_workers
        
        self.model = None
        self.model_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=num_workers)
        self._model_loaded = False
        
        # Performance tracking
        self.stats = {
            'total_transcriptions': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
        }
        
        logger.info(f"WhisperService initialized: model={model_size}, device={self.device}, "
                   f"compute_type={self.compute_type}, threads={self.cpu_threads}")
    
    def _detect_optimal_device(self) -> str:
        """Detect the optimal device for inference."""
        if torch.cuda.is_available():
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            if gpu_memory >= 8:
                return "cuda"
            else:
                logger.warning(f"GPU has only {gpu_memory:.1f}GB, using CPU for better stability")
                return "cpu"
        return "cpu"
    
    def _optimize_compute_type(self, compute_type: str) -> str:
        """Optimize compute type based on device and available memory."""
        if compute_type != "auto":
            return compute_type
            
        if self.device == "cuda":
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            if gpu_memory >= 12:
                return "float16"
            elif gpu_memory >= 8:
                return "int8"
            else:
                return "int8"
        else:
            return "int8"  # CPU works well with int8
    
    def _detect_optimal_cpu_threads(self) -> int:
        """Detect optimal number of CPU threads."""
        import os
        cpu_count = os.cpu_count() or 4
        return min(8, max(2, cpu_count // 2))
    
    async def load_model(self) -> None:
        """Load the Whisper model asynchronously."""
        if self._model_loaded:
            return
            
        def _load():
            with self.model_lock:
                if self._model_loaded:
                    return
                    
                try:
                    if FASTER_WHISPER_AVAILABLE:
                        logger.info(f"Loading faster-whisper model: {self.model_size}")
                        self.model = WhisperModel(
                            model_size_or_path=self.model_size,
                            device=self.device,
                            compute_type=self.compute_type,
                            cpu_threads=self.cpu_threads,
                            download_root=str(Path(self.config.ai_models.model_cache_dir) / "whisper")
                        )
                    else:
                        logger.info(f"Loading openai-whisper model: {self.model_size}")
                        self.model = whisper.load_model(
                            self.model_size,
                            device=self.device,
                            download_root=str(Path(self.config.ai_models.model_cache_dir) / "whisper")
                        )
                    
                    self._model_loaded = True
                    logger.success(f"Whisper model loaded successfully")
                    
                except Exception as e:
                    logger.error(f"Failed to load Whisper model: {e}")
                    raise
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, _load)
    
    async def transcribe_audio(self, 
                             audio_data: Union[np.ndarray, str, Path],
                             language: Optional[str] = None,
                             task: str = "transcribe",
                             word_timestamps: bool = True,
                             vad_filter: bool = True,
                             temperature: float = 0.0) -> TranscriptionResult:
        """Transcribe audio with advanced options.
        
        Args:
            audio_data: Audio data as numpy array or file path
            language: Target language code (None for auto-detection)
            task: Task type ("transcribe" or "translate")
            word_timestamps: Enable word-level timestamps
            vad_filter: Enable voice activity detection filtering
            temperature: Sampling temperature (0.0 for deterministic)
            
        Returns:
            TranscriptionResult with full metadata
        """
        await self.load_model()
        
        start_time = time.time()
        
        def _transcribe():
            try:
                if FASTER_WHISPER_AVAILABLE:
                    return self._transcribe_faster_whisper(
                        audio_data, language, task, word_timestamps, vad_filter, temperature
                    )
                else:
                    return self._transcribe_openai_whisper(
                        audio_data, language, task, word_timestamps, temperature
                    )
            except Exception as e:
                logger.error(f"Transcription failed: {e}")
                raise
        
        # Run transcription in thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, _transcribe)
        
        processing_time = time.time() - start_time
        result.processing_time = processing_time
        
        # Update statistics
        self.stats['total_transcriptions'] += 1
        self.stats['total_processing_time'] += processing_time
        self.stats['average_processing_time'] = (
            self.stats['total_processing_time'] / self.stats['total_transcriptions']
        )
        
        logger.info(f"Transcription completed in {processing_time:.2f}s: "
                   f"language={result.language}, confidence={result.confidence:.3f}")
        
        return result
    
    def _transcribe_faster_whisper(self, 
                                 audio_data: Union[np.ndarray, str, Path],
                                 language: Optional[str],
                                 task: str,
                                 word_timestamps: bool,
                                 vad_filter: bool,
                                 temperature: float) -> TranscriptionResult:
        """Transcribe using faster-whisper."""
        # Prepare transcription parameters
        options = {
            "language": language,
            "task": task,
            "word_timestamps": word_timestamps,
            "vad_filter": vad_filter,
            "temperature": temperature,
            "initial_prompt": self._get_italian_prompt() if not language or language.startswith('it') else None,
        }
        
        # Remove None values
        options = {k: v for k, v in options.items() if v is not None}
        
        segments, info = self.model.transcribe(audio_data, **options)
        segments = list(segments)  # Convert generator to list
        
        # Extract text and build result
        text = " ".join([segment.text.strip() for segment in segments])
        text = self._post_process_italian_text(text)
        
        # Calculate average confidence
        confidence = np.mean([segment.avg_logprob for segment in segments]) if segments else 0.0
        confidence = np.exp(confidence)  # Convert log probability to probability
        
        # Build word timestamps
        words = []
        for segment in segments:
            if hasattr(segment, 'words') and segment.words:
                for word in segment.words:
                    words.append({
                        'word': word.word.strip(),
                        'start': word.start,
                        'end': word.end,
                        'confidence': np.exp(word.probability) if hasattr(word, 'probability') else confidence
                    })
        
        # Build segments info
        segments_info = []
        for i, segment in enumerate(segments):
            segments_info.append({
                'id': i,
                'text': segment.text.strip(),
                'start': segment.start,
                'end': segment.end,
                'confidence': np.exp(segment.avg_logprob),
                'no_speech_prob': getattr(segment, 'no_speech_prob', 0.0)
            })
        
        return TranscriptionResult(
            text=text,
            language=info.language,
            language_probability=info.language_probability,
            confidence=confidence,
            words=words,
            segments=segments_info,
            processing_time=0.0,  # Will be set by caller
            model_used=f"faster-whisper-{self.model_size}"
        )
    
    def _transcribe_openai_whisper(self, 
                                 audio_data: Union[np.ndarray, str, Path],
                                 language: Optional[str],
                                 task: str,
                                 word_timestamps: bool,
                                 temperature: float) -> TranscriptionResult:
        """Transcribe using openai-whisper."""
        options = {
            "language": language,
            "task": task,
            "word_timestamps": word_timestamps,
            "temperature": temperature,
        }
        
        # Remove None values
        options = {k: v for k, v in options.items() if v is not None}
        
        result = self.model.transcribe(audio_data, **options)
        
        text = result["text"].strip()
        text = self._post_process_italian_text(text)
        
        # Extract words if available
        words = []
        if "words" in result:
            words = [
                {
                    'word': word['word'].strip(),
                    'start': word['start'],
                    'end': word['end'],
                    'confidence': word.get('probability', 0.8)
                }
                for word in result["words"]
            ]
        
        # Build segments info
        segments = result.get("segments", [])
        segments_info = []
        for segment in segments:
            segments_info.append({
                'id': segment['id'],
                'text': segment['text'].strip(),
                'start': segment['start'],
                'end': segment['end'],
                'confidence': segment.get('avg_logprob', -1.0),
                'no_speech_prob': segment.get('no_speech_prob', 0.0)
            })
        
        # Calculate average confidence
        confidence = np.mean([s['confidence'] for s in segments_info]) if segments_info else 0.8
        
        return TranscriptionResult(
            text=text,
            language=result.get("language", "unknown"),
            language_probability=1.0,  # OpenAI whisper doesn't provide this
            confidence=confidence,
            words=words,
            segments=segments_info,
            processing_time=0.0,  # Will be set by caller
            model_used=f"openai-whisper-{self.model_size}"
        )
    
    def _get_italian_prompt(self) -> str:
        """Get Italian language prompt to improve recognition."""
        return (
            "Trascrivi accuratamente questo audio in italiano. "
            "Presta attenzione agli accenti regionali e ai termini tecnici IT. "
            "Usa la punteggiatura appropriata."
        )
    
    def _post_process_italian_text(self, text: str) -> str:
        """Post-process Italian text for better accuracy."""
        if not text:
            return text
            
        # Normalize IT terms
        words = text.split()
        processed_words = []
        
        for word in words:
            # Clean punctuation for lookup
            clean_word = word.lower().strip('.,!?;:()[]{}"\'-')
            
            # Check for IT terms
            if clean_word in self.IT_TERMS:
                # Replace with proper case, preserving punctuation
                processed_word = word.lower().replace(clean_word, self.IT_TERMS[clean_word])
                # Restore original case for first letter if it was capitalized
                if word[0].isupper():
                    processed_word = processed_word[0].upper() + processed_word[1:]
                processed_words.append(processed_word)
            else:
                processed_words.append(word)
        
        return ' '.join(processed_words)
    
    async def detect_language(self, audio_data: Union[np.ndarray, str, Path]) -> Tuple[str, float]:
        """Detect language from audio.
        
        Args:
            audio_data: Audio data as numpy array or file path
            
        Returns:
            Tuple of (language_code, probability)
        """
        await self.load_model()
        
        def _detect():
            if FASTER_WHISPER_AVAILABLE:
                # Use faster-whisper's language detection
                segments, info = self.model.transcribe(
                    audio_data,
                    language=None,
                    task="transcribe",
                    vad_filter=True,
                    word_timestamps=False
                )
                # Consume generator to get info
                list(segments)
                return info.language, info.language_probability
            else:
                # Use openai-whisper's language detection
                result = self.model.transcribe(audio_data, language=None)
                return result.get("language", "unknown"), 1.0
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _detect)
    
    async def transcribe_streaming(self, 
                                 audio_chunks: AsyncGenerator[np.ndarray, None],
                                 language: Optional[str] = None) -> AsyncGenerator[TranscriptionResult, None]:
        """Transcribe streaming audio chunks.
        
        Args:
            audio_chunks: Async generator of audio chunks
            language: Target language (None for auto-detection)
            
        Yields:
            TranscriptionResult for each chunk
        """
        await self.load_model()
        
        chunk_id = 0
        async for chunk in audio_chunks:
            try:
                result = await self.transcribe_audio(
                    chunk,
                    language=language,
                    word_timestamps=True,
                    vad_filter=True
                )
                result.chunk_id = chunk_id
                chunk_id += 1
                yield result
            except Exception as e:
                logger.error(f"Failed to transcribe chunk {chunk_id}: {e}")
                # Yield empty result to maintain stream
                yield TranscriptionResult(
                    text="",
                    language="unknown",
                    language_probability=0.0,
                    confidence=0.0,
                    words=[],
                    segments=[],
                    processing_time=0.0,
                    model_used=f"faster-whisper-{self.model_size}"
                )
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        # Whisper supports these languages
        return [
            'en', 'zh', 'de', 'es', 'ru', 'ko', 'fr', 'ja', 'pt', 'tr', 'pl', 'ca', 'nl',
            'ar', 'sv', 'it', 'id', 'hi', 'fi', 'vi', 'he', 'uk', 'el', 'ms', 'cs', 'ro',
            'da', 'hu', 'ta', 'no', 'th', 'ur', 'hr', 'bg', 'lt', 'la', 'mi', 'ml', 'cy',
            'sk', 'te', 'fa', 'lv', 'bn', 'sr', 'az', 'sl', 'kn', 'et', 'mk', 'br', 'eu',
            'is', 'hy', 'ne', 'mn', 'bs', 'kk', 'sq', 'sw', 'gl', 'mr', 'pa', 'si', 'km',
            'sn', 'yo', 'so', 'af', 'oc', 'ka', 'be', 'tg', 'sd', 'gu', 'am', 'yi', 'lo',
            'uz', 'fo', 'ht', 'ps', 'tk', 'nn', 'mt', 'sa', 'lb', 'my', 'bo', 'tl', 'mg',
            'as', 'tt', 'haw', 'ln', 'ha', 'ba', 'jw', 'su'
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return self.stats.copy()
    
    async def warmup(self) -> None:
        """Warm up the model with a small audio sample."""
        await self.load_model()
        
        # Create a small silent audio sample for warmup
        sample_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
        
        try:
            await self.transcribe_audio(
                sample_audio,
                language="it",
                word_timestamps=False,
                vad_filter=False
            )
            logger.info("Whisper service warmed up successfully")
        except Exception as e:
            logger.warning(f"Warmup failed: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
        logger.info("WhisperService shut down")