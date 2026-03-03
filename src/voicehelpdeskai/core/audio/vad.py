"""Voice Activity Detection (VAD) module with multiple detection algorithms."""

import time
from collections import deque
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field

import numpy as np
from loguru import logger

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    logger.warning("webrtcvad not available - WebRTC VAD will be disabled")

from voicehelpdeskai.config.manager import get_config_manager
from voicehelpdeskai.core.audio.exceptions import VoiceActivityError


class VADMode(Enum):
    """Voice activity detection modes."""
    ENERGY_BASED = "energy_based"
    WEBRTC = "webrtc"
    HYBRID = "hybrid"
    SILENCE_BASED = "silence_based"


class SpeechState(Enum):
    """Speech activity states."""
    SILENCE = "silence"
    SPEECH = "speech"
    TRANSITION_TO_SPEECH = "transition_to_speech"
    TRANSITION_TO_SILENCE = "transition_to_silence"


@dataclass
class VADResult:
    """Voice activity detection result."""
    is_speech: bool
    confidence: float
    energy: float
    state: SpeechState
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_speech": self.is_speech,
            "confidence": self.confidence,
            "energy": self.energy,
            "state": self.state.value,
            "timestamp": self.timestamp,
            "duration": self.duration,
        }


@dataclass
class VADConfig:
    """VAD configuration parameters."""
    mode: VADMode = VADMode.HYBRID
    sample_rate: int = 16000
    frame_duration_ms: int = 30  # WebRTC VAD frame duration (10, 20, 30ms)
    
    # Energy-based parameters
    energy_threshold: float = 0.01
    energy_percentile: int = 95
    min_energy_ratio: float = 2.0
    
    # Silence-based parameters
    silence_threshold: float = 0.005
    min_silence_duration: float = 0.5
    min_speech_duration: float = 0.3
    
    # WebRTC VAD parameters (0-3, 3 = most aggressive)
    webrtc_aggressiveness: int = 2
    
    # Smoothing parameters
    smoothing_window: int = 5
    confidence_threshold: float = 0.5
    
    # Transition parameters
    transition_frames: int = 3
    hangover_frames: int = 10  # Continue speech detection after silence
    
    # Dynamic adaptation
    enable_adaptation: bool = True
    adaptation_rate: float = 0.1
    background_update_rate: float = 0.01


class EnergyBasedVAD:
    """Energy-based voice activity detection."""
    
    def __init__(self, config: VADConfig):
        """Initialize energy-based VAD.
        
        Args:
            config: VAD configuration
        """
        self.config = config
        self.energy_history = deque(maxlen=100)
        self.background_energy = 0.0
        self.adaptive_threshold = config.energy_threshold
        
        # Statistics
        self.total_frames = 0
        self.speech_frames = 0
        
    def detect(self, audio_data: np.ndarray) -> VADResult:
        """Detect voice activity using energy.
        
        Args:
            audio_data: Audio data array
            
        Returns:
            VAD result
        """
        if len(audio_data) == 0:
            return VADResult(
                is_speech=False,
                confidence=0.0,
                energy=0.0,
                state=SpeechState.SILENCE
            )
        
        # Calculate energy (RMS)
        energy = np.sqrt(np.mean(audio_data ** 2))
        
        # Update energy history
        self.energy_history.append(energy)
        self.total_frames += 1
        
        # Update background energy estimate
        self._update_background_energy(energy)
        
        # Adapt threshold if enabled
        if self.config.enable_adaptation:
            self._adapt_threshold()
        
        # Determine speech activity
        is_speech = self._is_speech_energy(energy)
        confidence = self._calculate_confidence(energy)
        
        if is_speech:
            self.speech_frames += 1
        
        return VADResult(
            is_speech=is_speech,
            confidence=confidence,
            energy=energy,
            state=SpeechState.SPEECH if is_speech else SpeechState.SILENCE
        )
    
    def _update_background_energy(self, energy: float):
        """Update background energy estimate."""
        if self.background_energy == 0.0:
            self.background_energy = energy
        else:
            # Use slower adaptation for background
            rate = self.config.background_update_rate
            self.background_energy = (1 - rate) * self.background_energy + rate * energy
    
    def _adapt_threshold(self):
        """Adapt energy threshold based on recent history."""
        if len(self.energy_history) < 10:
            return
        
        # Calculate statistics
        energies = list(self.energy_history)
        mean_energy = np.mean(energies)
        std_energy = np.std(energies)
        
        # Adaptive threshold based on background + ratio
        background_threshold = self.background_energy * self.config.min_energy_ratio
        statistical_threshold = mean_energy + 2 * std_energy
        
        # Use the higher threshold for robustness
        new_threshold = max(background_threshold, statistical_threshold)
        
        # Smooth threshold adaptation
        rate = self.config.adaptation_rate
        self.adaptive_threshold = (1 - rate) * self.adaptive_threshold + rate * new_threshold
    
    def _is_speech_energy(self, energy: float) -> bool:
        """Determine if energy indicates speech."""
        return energy > self.adaptive_threshold
    
    def _calculate_confidence(self, energy: float) -> float:
        """Calculate confidence score for energy-based decision."""
        if self.adaptive_threshold == 0:
            return 0.0
        
        # Confidence based on energy ratio
        ratio = energy / self.adaptive_threshold
        confidence = min(1.0, max(0.0, (ratio - 1.0) / 2.0))
        
        return confidence


class WebRTCVAD:
    """WebRTC-based voice activity detection."""
    
    def __init__(self, config: VADConfig):
        """Initialize WebRTC VAD.
        
        Args:
            config: VAD configuration
        """
        self.config = config
        self.vad = None
        
        if WEBRTCVAD_AVAILABLE:
            try:
                self.vad = webrtcvad.Vad()
                self.vad.set_mode(config.webrtc_aggressiveness)
                
                # Calculate frame size for WebRTC VAD
                self.frame_size = int(config.sample_rate * config.frame_duration_ms / 1000)
                
                logger.info(f"WebRTC VAD initialized with aggressiveness {config.webrtc_aggressiveness}")
                
            except Exception as e:
                logger.error(f"Failed to initialize WebRTC VAD: {e}")
                self.vad = None
        
        # Buffer for frame alignment
        self.buffer = np.array([], dtype=np.float32)
        
        # Statistics
        self.total_frames = 0
        self.speech_frames = 0
    
    def detect(self, audio_data: np.ndarray) -> Optional[VADResult]:
        """Detect voice activity using WebRTC VAD.
        
        Args:
            audio_data: Audio data array
            
        Returns:
            VAD result or None if WebRTC VAD not available
        """
        if not self.vad:
            return None
        
        # Add to buffer
        self.buffer = np.concatenate([self.buffer, audio_data])
        
        results = []
        
        # Process complete frames
        while len(self.buffer) >= self.frame_size:
            frame = self.buffer[:self.frame_size]
            self.buffer = self.buffer[self.frame_size:]
            
            # Convert to 16-bit PCM for WebRTC VAD
            frame_int16 = (frame * 32767).astype(np.int16)
            frame_bytes = frame_int16.tobytes()
            
            try:
                # Run WebRTC VAD
                is_speech = self.vad.is_speech(frame_bytes, self.config.sample_rate)
                
                self.total_frames += 1
                if is_speech:
                    self.speech_frames += 1
                
                # Calculate energy for confidence
                energy = np.sqrt(np.mean(frame ** 2))
                
                result = VADResult(
                    is_speech=is_speech,
                    confidence=1.0 if is_speech else 0.0,  # WebRTC VAD is binary
                    energy=energy,
                    state=SpeechState.SPEECH if is_speech else SpeechState.SILENCE
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"WebRTC VAD processing error: {e}")
                
        # Return last result if available
        return results[-1] if results else None


class VoiceActivityDetector:
    """Advanced voice activity detector with multiple algorithms and smoothing."""
    
    def __init__(self, 
                 config: Optional[VADConfig] = None,
                 config_manager=None):
        """Initialize voice activity detector.
        
        Args:
            config: VAD configuration
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or get_config_manager()
        
        # Use provided config or create from settings
        if config is None:
            settings = self.config_manager.get_settings()
            config = VADConfig(
                sample_rate=settings.audio.sample_rate,
                silence_threshold=settings.audio.silence_threshold,
                min_silence_duration=settings.audio.silence_duration,
            )
        
        self.config = config
        
        # Initialize VAD algorithms
        self.energy_vad = EnergyBasedVAD(config)
        self.webrtc_vad = WebRTCVAD(config) if WEBRTCVAD_AVAILABLE else None
        
        # State tracking
        self.current_state = SpeechState.SILENCE
        self.state_duration = 0.0
        self.last_state_change = time.time()
        
        # Smoothing
        self.result_history = deque(maxlen=config.smoothing_window)
        self.transition_counter = 0
        self.hangover_counter = 0
        
        # Statistics
        self.total_detections = 0
        self.speech_detections = 0
        self.state_changes = 0
        
        # Callbacks
        self.speech_start_callback: Optional[Callable] = None
        self.speech_end_callback: Optional[Callable] = None
        
        logger.info(f"VoiceActivityDetector initialized with mode: {config.mode.value}")
    
    def detect(self, audio_data: np.ndarray) -> VADResult:
        """Detect voice activity in audio data.
        
        Args:
            audio_data: Audio data array
            
        Returns:
            VAD result with smoothed decision
        """
        try:
            current_time = time.time()
            
            # Run detection based on configured mode
            if self.config.mode == VADMode.ENERGY_BASED:
                raw_result = self.energy_vad.detect(audio_data)
                
            elif self.config.mode == VADMode.WEBRTC and self.webrtc_vad:
                raw_result = self.webrtc_vad.detect(audio_data)
                if raw_result is None:
                    # Fallback to energy-based
                    raw_result = self.energy_vad.detect(audio_data)
                    
            elif self.config.mode == VADMode.HYBRID:
                raw_result = self._hybrid_detection(audio_data)
                
            elif self.config.mode == VADMode.SILENCE_BASED:
                raw_result = self._silence_based_detection(audio_data)
                
            else:
                raw_result = self.energy_vad.detect(audio_data)
            
            # Apply smoothing and state logic
            smoothed_result = self._apply_smoothing(raw_result, current_time)
            
            # Update statistics
            self.total_detections += 1
            if smoothed_result.is_speech:
                self.speech_detections += 1
            
            return smoothed_result
            
        except Exception as e:
            logger.error(f"VAD detection error: {e}")
            # Return safe default
            return VADResult(
                is_speech=False,
                confidence=0.0,
                energy=0.0,
                state=SpeechState.SILENCE
            )
    
    def _hybrid_detection(self, audio_data: np.ndarray) -> VADResult:
        """Hybrid detection combining energy and WebRTC VAD.
        
        Args:
            audio_data: Audio data array
            
        Returns:
            Combined VAD result
        """
        # Get results from both algorithms
        energy_result = self.energy_vad.detect(audio_data)
        webrtc_result = self.webrtc_vad.detect(audio_data) if self.webrtc_vad else None
        
        if webrtc_result is None:
            return energy_result
        
        # Combine decisions
        # Speech if either algorithm detects speech, but with confidence weighting
        combined_confidence = (energy_result.confidence + webrtc_result.confidence) / 2
        combined_speech = energy_result.is_speech or webrtc_result.is_speech
        
        # If both agree on speech, increase confidence
        if energy_result.is_speech and webrtc_result.is_speech:
            combined_confidence = min(1.0, combined_confidence * 1.2)
        
        return VADResult(
            is_speech=combined_speech,
            confidence=combined_confidence,
            energy=energy_result.energy,
            state=SpeechState.SPEECH if combined_speech else SpeechState.SILENCE
        )
    
    def _silence_based_detection(self, audio_data: np.ndarray) -> VADResult:
        """Silence-based detection using amplitude thresholds.
        
        Args:
            audio_data: Audio data array
            
        Returns:
            Silence-based VAD result
        """
        if len(audio_data) == 0:
            return VADResult(
                is_speech=False,
                confidence=0.0,
                energy=0.0,
                state=SpeechState.SILENCE
            )
        
        # Calculate RMS energy
        energy = np.sqrt(np.mean(audio_data ** 2))
        
        # Simple threshold-based detection
        is_speech = energy > self.config.silence_threshold
        confidence = min(1.0, energy / self.config.silence_threshold) if self.config.silence_threshold > 0 else 0.0
        
        return VADResult(
            is_speech=is_speech,
            confidence=confidence,
            energy=energy,
            state=SpeechState.SPEECH if is_speech else SpeechState.SILENCE
        )
    
    def _apply_smoothing(self, raw_result: VADResult, current_time: float) -> VADResult:
        """Apply smoothing and state logic to raw VAD result.
        
        Args:
            raw_result: Raw VAD result
            current_time: Current timestamp
            
        Returns:
            Smoothed VAD result
        """
        # Add to history
        self.result_history.append(raw_result)
        
        # Calculate smoothed decision
        if len(self.result_history) < self.config.smoothing_window:
            smoothed_speech = raw_result.is_speech
        else:
            # Majority vote from recent history
            speech_votes = sum(1 for r in self.result_history if r.is_speech)
            smoothed_speech = speech_votes > len(self.result_history) // 2
        
        # Apply state transitions with hysteresis
        new_state = self._determine_state(smoothed_speech, current_time)
        
        # Calculate state duration
        if new_state != self.current_state:
            self.state_duration = 0.0
            self.last_state_change = current_time
            self.state_changes += 1
            
            # Trigger callbacks
            if new_state == SpeechState.SPEECH and self.speech_start_callback:
                self.speech_start_callback(raw_result)
            elif new_state == SpeechState.SILENCE and self.speech_end_callback:
                self.speech_end_callback(raw_result)
                
        else:
            self.state_duration = current_time - self.last_state_change
        
        self.current_state = new_state
        
        # Create smoothed result
        smoothed_result = VADResult(
            is_speech=(new_state == SpeechState.SPEECH),
            confidence=raw_result.confidence,
            energy=raw_result.energy,
            state=new_state,
            timestamp=current_time,
            duration=self.state_duration
        )
        
        return smoothed_result
    
    def _determine_state(self, is_speech: bool, current_time: float) -> SpeechState:
        """Determine speech state with transition logic.
        
        Args:
            is_speech: Current speech detection
            current_time: Current timestamp
            
        Returns:
            New speech state
        """
        if is_speech:
            if self.current_state == SpeechState.SILENCE:
                # Transition to speech
                self.transition_counter += 1
                if self.transition_counter >= self.config.transition_frames:
                    self.transition_counter = 0
                    self.hangover_counter = 0
                    return SpeechState.SPEECH
                else:
                    return SpeechState.TRANSITION_TO_SPEECH
            else:
                # Continue speech
                self.transition_counter = 0
                self.hangover_counter = 0
                return SpeechState.SPEECH
                
        else:
            if self.current_state == SpeechState.SPEECH:
                # Potential transition to silence with hangover
                self.hangover_counter += 1
                if self.hangover_counter >= self.config.hangover_frames:
                    self.transition_counter += 1
                    if self.transition_counter >= self.config.transition_frames:
                        self.transition_counter = 0
                        self.hangover_counter = 0
                        return SpeechState.SILENCE
                    else:
                        return SpeechState.TRANSITION_TO_SILENCE
                else:
                    # Still in hangover period
                    return SpeechState.SPEECH
            else:
                # Continue silence
                self.transition_counter = 0
                self.hangover_counter = 0
                return SpeechState.SILENCE
    
    def set_callbacks(self, 
                     speech_start_callback: Optional[Callable] = None,
                     speech_end_callback: Optional[Callable] = None):
        """Set callbacks for speech events.
        
        Args:
            speech_start_callback: Called when speech starts
            speech_end_callback: Called when speech ends
        """
        self.speech_start_callback = speech_start_callback
        self.speech_end_callback = speech_end_callback
    
    def calibrate(self, audio_data_list: List[np.ndarray], is_speech_labels: List[bool]) -> bool:
        """Calibrate VAD parameters using labeled data.
        
        Args:
            audio_data_list: List of audio chunks
            is_speech_labels: Corresponding speech labels
            
        Returns:
            True if calibration successful
        """
        if len(audio_data_list) != len(is_speech_labels):
            logger.error("Audio data and labels must have same length")
            return False
        
        try:
            # Collect energy values
            speech_energies = []
            silence_energies = []
            
            for audio_data, is_speech in zip(audio_data_list, is_speech_labels):
                energy = np.sqrt(np.mean(audio_data ** 2))
                
                if is_speech:
                    speech_energies.append(energy)
                else:
                    silence_energies.append(energy)
            
            if not speech_energies or not silence_energies:
                logger.error("Need both speech and silence samples for calibration")
                return False
            
            # Calculate optimal threshold
            speech_mean = np.mean(speech_energies)
            silence_mean = np.mean(silence_energies)
            
            # Set threshold between means
            optimal_threshold = (speech_mean + silence_mean) / 2
            
            # Update configuration
            self.config.energy_threshold = optimal_threshold
            self.config.silence_threshold = optimal_threshold * 0.8
            
            # Update energy VAD
            self.energy_vad.adaptive_threshold = optimal_threshold
            
            logger.info(f"VAD calibrated with threshold: {optimal_threshold}")
            return True
            
        except Exception as e:
            logger.error(f"VAD calibration failed: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get VAD statistics.
        
        Returns:
            Dictionary with VAD statistics
        """
        speech_ratio = self.speech_detections / max(self.total_detections, 1)
        
        return {
            "total_detections": self.total_detections,
            "speech_detections": self.speech_detections,
            "speech_ratio": speech_ratio,
            "state_changes": self.state_changes,
            "current_state": self.current_state.value,
            "state_duration": self.state_duration,
            "energy_vad_speech_frames": self.energy_vad.speech_frames,
            "energy_vad_total_frames": self.energy_vad.total_frames,
            "webrtc_available": WEBRTCVAD_AVAILABLE and self.webrtc_vad is not None,
        }
    
    def reset_statistics(self):
        """Reset VAD statistics."""
        self.total_detections = 0
        self.speech_detections = 0
        self.state_changes = 0
        self.current_state = SpeechState.SILENCE
        self.state_duration = 0.0
        
        # Reset sub-detectors
        self.energy_vad.total_frames = 0
        self.energy_vad.speech_frames = 0
        
        if self.webrtc_vad:
            self.webrtc_vad.total_frames = 0
            self.webrtc_vad.speech_frames = 0
    
    def is_currently_speaking(self) -> bool:
        """Check if currently in speech state.
        
        Returns:
            True if in speech state
        """
        return self.current_state == SpeechState.SPEECH
    
    def get_current_state_duration(self) -> float:
        """Get duration of current state.
        
        Returns:
            Duration in seconds
        """
        return time.time() - self.last_state_change