"""Audio-related database models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Text

from voicehelpdeskai.database.base import Base


class AudioFile(Base):
    """Audio file model."""
    
    __tablename__ = "audio_files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    duration = Column(Float, nullable=True)  # Duration in seconds
    format = Column(String, nullable=False)  # Audio format (wav, mp3, etc.)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    transcription = Column(Text, nullable=True)
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)