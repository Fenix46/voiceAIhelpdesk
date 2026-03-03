"""Audio processing module for VoiceHelpDeskAI."""

from voicehelpdeskai.core.audio.processor import AudioProcessor
from voicehelpdeskai.core.audio.stream_manager import AudioStreamManager
from voicehelpdeskai.core.audio.vad import VoiceActivityDetector
from voicehelpdeskai.core.audio.queue_system import AudioQueue, PriorityAudioQueue
from voicehelpdeskai.core.audio.exceptions import (
    AudioError,
    AudioDeviceError,
    AudioFormatError,
    AudioProcessingError,
    VoiceActivityError,
    StreamingError,
)

__all__ = [
    "AudioProcessor",
    "AudioStreamManager", 
    "VoiceActivityDetector",
    "AudioQueue",
    "PriorityAudioQueue",
    "AudioError",
    "AudioDeviceError",
    "AudioFormatError",
    "AudioProcessingError",
    "VoiceActivityError",
    "StreamingError",
]