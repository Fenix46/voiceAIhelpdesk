"""Main API router."""

from fastapi import APIRouter

from voicehelpdeskai.api.endpoints import voice, websocket, upload

# Create main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])