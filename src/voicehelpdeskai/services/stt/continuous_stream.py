"""Continuous transcription stream with real-time processing and corrections."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, AsyncGenerator, Callable, Any, Deque
from enum import Enum
import threading
from datetime import datetime, timedelta

import numpy as np
from loguru import logger

from voicehelpdeskai.services.stt.whisper_service import WhisperService, TranscriptionResult
from voicehelpdeskai.services.stt.transcription_processor import TranscriptionProcessor, ProcessedTranscription
from voicehelpdeskai.core.audio.vad import VoiceActivityDetector
from voicehelpdeskai.config.manager import get_config_manager


class TranscriptionState(Enum):
    """States for transcription processing."""
    PARTIAL = "partial"
    FINAL = "final"
    CORRECTED = "corrected"
    INTERRUPTED = "interrupted"


@dataclass
class StreamingTranscription:
    """Streaming transcription result with state management."""
    text: str
    confidence: float
    state: TranscriptionState
    timestamp: datetime
    chunk_id: int
    processing_time: float
    is_speech: bool = True
    overlap_corrected: bool = False
    context_corrected: bool = False
    interruption_detected: bool = False
    speaker_changed: bool = False
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamBuffer:
    """Buffer for managing streaming audio chunks with overlap."""
    audio_data: np.ndarray
    timestamp: datetime
    chunk_id: int
    duration: float
    sample_rate: int
    processed: bool = False
    is_silence: bool = False


class ContinuousTranscriptionStream:
    """Manages continuous real-time transcription with advanced features."""
    
    def __init__(self,
                 whisper_service: WhisperService,
                 transcription_processor: Optional[TranscriptionProcessor] = None,
                 chunk_duration: float = 1.0,
                 overlap_duration: float = 0.2,
                 silence_threshold: float = 0.01,
                 silence_duration: float = 2.0,
                 max_buffer_size: int = 50,
                 enable_vad: bool = True,
                 enable_context_correction: bool = True,
                 enable_interruption_detection: bool = True,
                 language: Optional[str] = None):
        """Initialize continuous transcription stream.
        
        Args:
            whisper_service: WhisperService instance
            transcription_processor: Optional transcription processor
            chunk_duration: Duration of each audio chunk in seconds
            overlap_duration: Overlap between chunks in seconds
            silence_threshold: VAD silence threshold
            silence_duration: Duration of silence before finalizing transcription
            max_buffer_size: Maximum number of chunks to buffer
            enable_vad: Enable voice activity detection
            enable_context_correction: Enable context-based corrections
            enable_interruption_detection: Enable interruption detection
            language: Target language (None for auto-detection)
        """
        self.whisper_service = whisper_service
        self.processor = transcription_processor or TranscriptionProcessor()
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.max_buffer_size = max_buffer_size
        self.enable_vad = enable_vad
        self.enable_context_correction = enable_context_correction
        self.enable_interruption_detection = enable_interruption_detection
        self.language = language
        
        # Initialize VAD if enabled
        self.vad = None
        if enable_vad:
            try:
                self.vad = VoiceActivityDetector(
                    threshold=silence_threshold,
                    min_speech_duration=0.1,
                    min_silence_duration=silence_duration
                )
                logger.info("Voice Activity Detection enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize VAD: {e}")
                self.enable_vad = False
        
        # Stream state
        self.is_streaming = False
        self.chunk_counter = 0
        self.buffer: Deque[StreamBuffer] = deque(maxlen=max_buffer_size)
        self.transcription_history: Deque[StreamingTranscription] = deque(maxlen=100)
        self.context_window: Deque[str] = deque(maxlen=10)  # For context-based corrections
        
        # Threading and synchronization
        self.stream_lock = threading.RLock()
        self.processing_tasks: Dict[int, asyncio.Task] = {}
        
        # Performance metrics
        self.stats = {
            'chunks_processed': 0,
            'partial_transcriptions': 0,
            'final_transcriptions': 0,
            'corrections_applied': 0,
            'interruptions_detected': 0,
            'average_processing_time': 0.0,
            'total_processing_time': 0.0,
            'vad_speech_percentage': 0.0,
        }
        
        # Configuration
        self.config = get_config_manager().get_config()
        
        logger.info("ContinuousTranscriptionStream initialized")
    
    async def start_stream(self) -> None:
        """Start the transcription stream."""
        if self.is_streaming:
            logger.warning("Stream is already active")
            return
        
        await self.whisper_service.warmup()
        self.is_streaming = True
        self.chunk_counter = 0
        self.stats = {k: 0.0 for k in self.stats.keys()}  # Reset stats
        
        logger.info("Continuous transcription stream started")
    
    async def stop_stream(self) -> None:
        """Stop the transcription stream and cleanup."""
        self.is_streaming = False
        
        # Wait for pending tasks to complete
        if self.processing_tasks:
            logger.info(f"Waiting for {len(self.processing_tasks)} pending tasks...")
            await asyncio.gather(*self.processing_tasks.values(), return_exceptions=True)
            self.processing_tasks.clear()
        
        # Clear buffers
        with self.stream_lock:
            self.buffer.clear()
            self.transcription_history.clear()
            self.context_window.clear()
        
        logger.info("Continuous transcription stream stopped")
    
    async def process_audio_chunk(self, 
                                audio_data: np.ndarray,
                                sample_rate: int = 16000) -> AsyncGenerator[StreamingTranscription, None]:
        """Process an audio chunk and yield transcription results.
        
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Audio sample rate
            
        Yields:
            StreamingTranscription results
        """
        if not self.is_streaming:
            logger.warning("Stream not active - call start_stream() first")
            return
        
        chunk_id = self.chunk_counter
        self.chunk_counter += 1
        timestamp = datetime.now()
        duration = len(audio_data) / sample_rate
        
        # Create buffer entry
        buffer_entry = StreamBuffer(
            audio_data=audio_data.copy(),
            timestamp=timestamp,
            chunk_id=chunk_id,
            duration=duration,
            sample_rate=sample_rate
        )
        
        # Voice activity detection
        is_speech = True
        if self.enable_vad and self.vad:
            try:
                is_speech = await self._detect_speech(audio_data, sample_rate)
                buffer_entry.is_silence = not is_speech
                
                # Update VAD stats
                speech_chunks = sum(1 for b in self.buffer if not b.is_silence)
                total_chunks = len(self.buffer)
                if total_chunks > 0:
                    self.stats['vad_speech_percentage'] = speech_chunks / total_chunks * 100
            except Exception as e:
                logger.error(f"VAD processing failed: {e}")
        
        # Add to buffer
        with self.stream_lock:
            self.buffer.append(buffer_entry)
        
        # Skip processing if silence (but still yield silence indicator)
        if not is_speech:
            yield StreamingTranscription(
                text="",
                confidence=0.0,
                state=TranscriptionState.PARTIAL,
                timestamp=timestamp,
                chunk_id=chunk_id,
                processing_time=0.0,
                is_speech=False
            )
            return
        
        # Process transcription
        async for transcription in self._process_chunk_with_context(buffer_entry):
            yield transcription
    
    async def _detect_speech(self, audio_data: np.ndarray, sample_rate: int) -> bool:
        """Detect speech in audio chunk using VAD."""
        try:
            # Run VAD in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                self.vad.is_speech, 
                audio_data, 
                sample_rate
            )
        except Exception as e:
            logger.error(f"VAD detection failed: {e}")
            return True  # Assume speech on error
    
    async def _process_chunk_with_context(self, 
                                        buffer_entry: StreamBuffer) -> AsyncGenerator[StreamingTranscription, None]:
        """Process chunk with context and overlap handling."""
        start_time = time.time()
        
        try:
            # Create audio segment with overlap
            audio_segment = await self._create_audio_segment_with_overlap(buffer_entry)
            
            # Transcribe audio segment
            transcription_result = await self.whisper_service.transcribe_audio(
                audio_segment,
                language=self.language,
                word_timestamps=True,
                vad_filter=False,  # We handle VAD separately
                temperature=0.0
            )
            
            # Process transcription
            processed_transcription = self.processor.process(transcription_result)
            
            # Apply context-based corrections
            corrected_text = processed_transcription.text
            context_corrected = False
            
            if self.enable_context_correction:
                corrected_text, context_corrected = await self._apply_context_corrections(
                    corrected_text, buffer_entry.chunk_id
                )
            
            # Detect interruptions
            interruption_detected = False
            if self.enable_interruption_detection:
                interruption_detected = await self._detect_interruption(
                    processed_transcription, buffer_entry
                )
            
            # Determine transcription state
            state = self._determine_transcription_state(
                processed_transcription, buffer_entry, context_corrected, interruption_detected
            )
            
            # Create streaming transcription
            streaming_transcription = StreamingTranscription(
                text=corrected_text,
                confidence=processed_transcription.confidence,
                state=state,
                timestamp=buffer_entry.timestamp,
                chunk_id=buffer_entry.chunk_id,
                processing_time=time.time() - start_time,
                is_speech=True,
                overlap_corrected=False,  # Will be set by overlap processing
                context_corrected=context_corrected,
                interruption_detected=interruption_detected,
                language=transcription_result.language,
                metadata={
                    'words_count': len(processed_transcription.text.split()),
                    'processing_applied': processed_transcription.processing_applied,
                    'entities': processed_transcription.entities,
                }
            )
            
            # Handle overlap corrections
            streaming_transcription = await self._handle_overlap_corrections(streaming_transcription)
            
            # Update context window
            if streaming_transcription.text.strip():
                with self.stream_lock:
                    self.context_window.append(streaming_transcription.text)
            
            # Store in history
            with self.stream_lock:
                self.transcription_history.append(streaming_transcription)
            
            # Update statistics
            self._update_stats(streaming_transcription)
            
            yield streaming_transcription
            
        except Exception as e:
            logger.error(f"Error processing chunk {buffer_entry.chunk_id}: {e}")
            
            # Yield error transcription
            yield StreamingTranscription(
                text="",
                confidence=0.0,
                state=TranscriptionState.INTERRUPTED,
                timestamp=buffer_entry.timestamp,
                chunk_id=buffer_entry.chunk_id,
                processing_time=time.time() - start_time,
                is_speech=True,
                interruption_detected=True,
                metadata={'error': str(e)}
            )
    
    async def _create_audio_segment_with_overlap(self, buffer_entry: StreamBuffer) -> np.ndarray:
        """Create audio segment with overlap from previous chunks."""
        overlap_samples = int(self.overlap_duration * buffer_entry.sample_rate)
        
        with self.stream_lock:
            # Get previous chunks for overlap
            relevant_chunks = [
                b for b in self.buffer 
                if b.chunk_id < buffer_entry.chunk_id and not b.is_silence
            ]
            
            if not relevant_chunks:
                return buffer_entry.audio_data
            
            # Get the most recent chunk for overlap
            prev_chunk = relevant_chunks[-1]
            
            # Create overlap
            if len(prev_chunk.audio_data) >= overlap_samples:
                overlap_audio = prev_chunk.audio_data[-overlap_samples:]
                combined_audio = np.concatenate([overlap_audio, buffer_entry.audio_data])
                return combined_audio
            else:
                return buffer_entry.audio_data
    
    async def _apply_context_corrections(self, text: str, chunk_id: int) -> tuple[str, bool]:
        """Apply context-based corrections to transcription."""
        if not text.strip() or not self.context_window:
            return text, False
        
        corrected_text = text
        corrected = False
        
        try:
            # Get recent context
            context = " ".join(list(self.context_window)[-3:])  # Last 3 transcriptions
            
            # Context-based word corrections
            context_corrections = await self._get_context_corrections(corrected_text, context)
            
            for original, correction in context_corrections.items():
                if original in corrected_text:
                    corrected_text = corrected_text.replace(original, correction)
                    corrected = True
            
            # Sentence completion based on context
            if corrected_text.endswith(('e', 'o', 'a', 'i')) and context:
                completion = await self._complete_sentence_from_context(corrected_text, context)
                if completion and completion != corrected_text:
                    corrected_text = completion
                    corrected = True
            
        except Exception as e:
            logger.error(f"Context correction failed: {e}")
        
        return corrected_text, corrected
    
    async def _get_context_corrections(self, text: str, context: str) -> Dict[str, str]:
        """Get context-based word corrections."""
        corrections = {}
        
        # Simple rule-based corrections based on context
        text_words = text.lower().split()
        context_words = context.lower().split()
        
        # Common Italian homophone corrections based on context
        homophones = {
            'ce': 'c\'è',    # if context suggests existence
            'cè': 'c\'è',
            'perchè': 'perché',
            'perche': 'perché',
            'piu': 'più',
            'gia': 'già',
            'cosi': 'così',
            'pero': 'però',
        }
        
        for word in text_words:
            if word in homophones:
                corrections[word] = homophones[word]
        
        return corrections
    
    async def _complete_sentence_from_context(self, text: str, context: str) -> Optional[str]:
        """Complete incomplete sentences using context."""
        # This is a simple implementation - could be enhanced with ML models
        
        # Check for common incomplete patterns
        if text.strip().endswith(' e'):
            # Look for common completions in context
            if 'problema' in context.lower():
                return text + ' risolto'
            elif 'sistema' in context.lower():
                return text + ' funzionante'
        
        return None
    
    async def _detect_interruption(self, 
                                 transcription: ProcessedTranscription,
                                 buffer_entry: StreamBuffer) -> bool:
        """Detect if transcription was interrupted."""
        # Check for sudden confidence drop
        if transcription.confidence < 0.3:
            return True
        
        # Check for incomplete sentences
        text = transcription.text.strip()
        if text and not text[-1] in '.!?':
            # Check if it ends abruptly without common sentence endings
            endings = ['e', 'o', 'a', 'i', 'che', 'per', 'con', 'di', 'da', 'in', 'su']
            if any(text.lower().endswith(' ' + ending) for ending in endings):
                return True
        
        # Check audio level changes (simple implementation)
        if len(buffer_entry.audio_data) > 0:
            audio_level = np.abs(buffer_entry.audio_data).mean()
            if audio_level < self.silence_threshold * 2:  # Very low audio
                return True
        
        return False
    
    def _determine_transcription_state(self,
                                     transcription: ProcessedTranscription,
                                     buffer_entry: StreamBuffer,
                                     context_corrected: bool,
                                     interruption_detected: bool) -> TranscriptionState:
        """Determine the state of the transcription."""
        if interruption_detected:
            return TranscriptionState.INTERRUPTED
        
        if context_corrected:
            return TranscriptionState.CORRECTED
        
        # Check for sentence completeness
        text = transcription.text.strip()
        if text and text[-1] in '.!?':
            return TranscriptionState.FINAL
        
        # Check confidence and length
        if transcription.confidence > 0.8 and len(text.split()) >= 3:
            return TranscriptionState.PARTIAL
        
        return TranscriptionState.PARTIAL
    
    async def _handle_overlap_corrections(self, 
                                        transcription: StreamingTranscription) -> StreamingTranscription:
        """Handle overlap corrections between chunks."""
        if not self.transcription_history:
            return transcription
        
        try:
            # Get recent transcriptions for overlap detection
            recent_transcriptions = list(self.transcription_history)[-3:]
            
            # Simple overlap detection and correction
            for prev_transcription in reversed(recent_transcriptions):
                if self._detect_text_overlap(prev_transcription.text, transcription.text):
                    corrected_text = self._merge_overlapping_text(
                        prev_transcription.text, 
                        transcription.text
                    )
                    if corrected_text != transcription.text:
                        transcription.text = corrected_text
                        transcription.overlap_corrected = True
                        self.stats['corrections_applied'] += 1
                        break
        
        except Exception as e:
            logger.error(f"Overlap correction failed: {e}")
        
        return transcription
    
    def _detect_text_overlap(self, prev_text: str, current_text: str) -> bool:
        """Detect if two texts have overlapping content."""
        if not prev_text or not current_text:
            return False
        
        prev_words = prev_text.lower().split()
        current_words = current_text.lower().split()
        
        # Check for word overlap at the end of prev and start of current
        for i in range(1, min(len(prev_words), len(current_words)) + 1):
            if prev_words[-i:] == current_words[:i]:
                return True
        
        return False
    
    def _merge_overlapping_text(self, prev_text: str, current_text: str) -> str:
        """Merge overlapping texts."""
        prev_words = prev_text.split()
        current_words = current_text.split()
        
        # Find the longest overlap
        max_overlap = 0
        overlap_length = 0
        
        for i in range(1, min(len(prev_words), len(current_words)) + 1):
            if [w.lower() for w in prev_words[-i:]] == [w.lower() for w in current_words[:i]]:
                if i > max_overlap:
                    max_overlap = i
                    overlap_length = i
        
        if overlap_length > 0:
            # Merge by removing overlap from current text
            merged_words = prev_words + current_words[overlap_length:]
            return ' '.join(merged_words)
        
        # No overlap found - concatenate with space
        return prev_text + ' ' + current_text
    
    def _update_stats(self, transcription: StreamingTranscription) -> None:
        """Update performance statistics."""
        self.stats['chunks_processed'] += 1
        self.stats['total_processing_time'] += transcription.processing_time
        self.stats['average_processing_time'] = (
            self.stats['total_processing_time'] / self.stats['chunks_processed']
        )
        
        if transcription.state == TranscriptionState.PARTIAL:
            self.stats['partial_transcriptions'] += 1
        elif transcription.state == TranscriptionState.FINAL:
            self.stats['final_transcriptions'] += 1
        
        if transcription.interruption_detected:
            self.stats['interruptions_detected'] += 1
        
        if transcription.context_corrected or transcription.overlap_corrected:
            self.stats['corrections_applied'] += 1
    
    async def get_context_summary(self) -> Dict[str, Any]:
        """Get current context summary."""
        with self.stream_lock:
            return {
                'active_chunks': len(self.buffer),
                'transcription_history_length': len(self.transcription_history),
                'context_window_size': len(self.context_window),
                'is_streaming': self.is_streaming,
                'current_chunk_id': self.chunk_counter,
                'pending_tasks': len(self.processing_tasks),
                'recent_transcriptions': [
                    {
                        'text': t.text[:50] + '...' if len(t.text) > 50 else t.text,
                        'state': t.state.value,
                        'confidence': t.confidence,
                        'timestamp': t.timestamp.isoformat()
                    }
                    for t in list(self.transcription_history)[-5:]
                ]
            }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats_copy = self.stats.copy()
        
        # Add calculated metrics
        if stats_copy['chunks_processed'] > 0:
            stats_copy['partial_percentage'] = (
                stats_copy['partial_transcriptions'] / stats_copy['chunks_processed'] * 100
            )
            stats_copy['final_percentage'] = (
                stats_copy['final_transcriptions'] / stats_copy['chunks_processed'] * 100
            )
            stats_copy['interruption_percentage'] = (
                stats_copy['interruptions_detected'] / stats_copy['chunks_processed'] * 100
            )
            stats_copy['correction_percentage'] = (
                stats_copy['corrections_applied'] / stats_copy['chunks_processed'] * 100
            )
        
        return stats_copy
    
    async def reset_context(self) -> None:
        """Reset context and history."""
        with self.stream_lock:
            self.context_window.clear()
            self.transcription_history.clear()
            self.buffer.clear()
        
        logger.info("Stream context reset")
    
    async def set_language(self, language: Optional[str]) -> None:
        """Change the target language for transcription."""
        self.language = language
        logger.info(f"Stream language set to: {language or 'auto-detect'}")