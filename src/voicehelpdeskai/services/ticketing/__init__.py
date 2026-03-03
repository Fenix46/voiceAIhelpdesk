"""Ticketing service module for VoiceHelpDeskAI."""

from .mock_api import MockTicketAPI
from .service import TicketingService, TicketAdapter
from .analytics import TicketAnalytics
from .test_data import TestDataGenerator

__all__ = [
    "MockTicketAPI",
    "TicketingService", 
    "TicketAdapter",
    "TicketAnalytics",
    "TestDataGenerator"
]