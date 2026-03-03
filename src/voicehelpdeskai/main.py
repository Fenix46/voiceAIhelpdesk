"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from voicehelpdeskai.api.router import api_router
from voicehelpdeskai.core.config import settings
from voicehelpdeskai.core.logging import configure_logging
from voicehelpdeskai.database.base import create_tables


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Configure logging first
    configure_logging()
    
    # Create FastAPI instance
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered Voice Help Desk System with real-time audio processing",
        openapi_url=f"{settings.api_v1_str}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        debug=settings.debug,
    )
    
    # Add security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API router
    app.include_router(api_router, prefix=settings.api_v1_str)
    
    return app


# Create application instance
app = create_application()


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    from loguru import logger
    
    logger.info("Starting VoiceHelpDeskAI application")
    
    # Create database tables
    create_tables()
    
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    from loguru import logger
    
    logger.info("Shutting down VoiceHelpDeskAI application")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to VoiceHelpDeskAI",
        "version": settings.app_version,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "voicehelpdeskai.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )