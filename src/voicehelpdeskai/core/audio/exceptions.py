"""Audio processing exceptions."""


class AudioError(Exception):
    """Base exception for audio-related errors."""
    pass


class AudioDeviceError(AudioError):
    """Exception raised when audio device operations fail."""
    pass


class AudioFormatError(AudioError):
    """Exception raised for audio format conversion errors."""
    pass


class AudioProcessingError(AudioError):
    """Exception raised during audio processing operations."""
    pass


class VoiceActivityError(AudioError):
    """Exception raised for voice activity detection errors."""
    pass


class StreamingError(AudioError):
    """Exception raised for audio streaming errors."""
    pass


class AudioQueueError(AudioError):
    """Exception raised for audio queue operations."""
    pass


class NoiseReductionError(AudioProcessingError):
    """Exception raised during noise reduction operations."""
    pass


class ResamplingError(AudioProcessingError):
    """Exception raised during audio resampling."""
    pass