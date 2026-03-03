"""Main FastAPI application for VoiceHelpDeskAI."""

import asyncio
import logging
import time
import traceback
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import jwt
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest
import redis.asyncio as redis

from ..core.config import settings
from ..core.logging import get_logger
from ..database import initialize_database
from .endpoints import (
    conversation_router,
    ticket_router,
    analytics_router,
    feedback_router,
    websocket_router,
    sse_router
)
from .middleware.auth import AuthMiddleware, JWTAuth
from .middleware.logging import LoggingMiddleware
from .middleware.security import SecurityMiddleware
from .schemas import ErrorResponse, HealthResponse

# Initialize logger
logger = get_logger(__name__)

# Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
WEBSOCKET_CONNECTIONS = Counter('websocket_connections_total', 'Total WebSocket connections', ['status'])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Redis client for rate limiting and caching
redis_client: Optional[redis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting VoiceHelpDeskAI API server...")
    
    try:
        # Initialize database
        if not initialize_database():
            logger.error("Failed to initialize database")
            raise RuntimeError("Database initialization failed")
        
        # Initialize Redis
        global redis_client
        if settings.redis_url:
            redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()
            logger.info("Redis connection established")
        
        # Initialize other services
        # TODO: Initialize audio processing, STT, TTS, LLM services
        
        logger.info("VoiceHelpDeskAI API server started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down VoiceHelpDeskAI API server...")
        
        if redis_client:
            await redis_client.close()
        
        logger.info("VoiceHelpDeskAI API server stopped")


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="VoiceHelpDeskAI API",
        description="Advanced voice-powered IT helpdesk system with AI-driven ticket management",
        version="1.0.0",
        contact={
            "name": "VoiceHelpDeskAI Team",
            "email": "support@voicehelpdeskai.com"
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT"
        },
        openapi_tags=[
            {
                "name": "health",
                "description": "Health check and system status endpoints"
            },
            {
                "name": "conversations",
                "description": "Voice conversation management"
            },
            {
                "name": "tickets",
                "description": "IT support ticket operations"
            },
            {
                "name": "analytics",
                "description": "Analytics and reporting endpoints"
            },
            {
                "name": "feedback",
                "description": "User feedback and satisfaction"
            },
            {
                "name": "websocket",
                "description": "Real-time audio streaming via WebSocket"
            },
            {
                "name": "sse",
                "description": "Server-Sent Events for real-time updates"
            }
        ],
        lifespan=lifespan,
        docs_url=None,  # Disable default docs
        redoc_url=None  # Disable default redoc
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "Accept",
            "Origin",
            "X-CSRF-Token",
            "X-API-Key"
        ],
        expose_headers=["X-Request-ID", "X-Response-Time"]
    )
    
    # Add security middleware
    if settings.trusted_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.trusted_hosts
        )
    
    # Add compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Add rate limiting middleware
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    
    # Add custom middleware
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(AuthMiddleware)
    
    # Add metrics middleware
    app.add_middleware(MetricsMiddleware)
    
    # Include routers
    app.include_router(
        conversation_router,
        prefix="/api/v1/conversation",
        tags=["conversations"]
    )
    
    app.include_router(
        ticket_router,
        prefix="/api/v1/ticket",
        tags=["tickets"]
    )
    
    app.include_router(
        analytics_router,
        prefix="/api/v1/analytics",
        tags=["analytics"]
    )
    
    app.include_router(
        feedback_router,
        prefix="/api/v1/feedback",
        tags=["feedback"]
    )
    
    app.include_router(
        websocket_router,
        prefix="/ws",
        tags=["websocket"]
    )
    
    app.include_router(
        sse_router,
        prefix="/api/v1/sse",
        tags=["sse"]
    )
    
    # Add health check endpoints
    setup_health_endpoints(app)
    
    # Add documentation endpoints
    setup_docs_endpoints(app)
    
    # Add global exception handler
    setup_exception_handlers(app)
    
    return app


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting Prometheus metrics."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Skip metrics for metrics endpoint
        if request.url.path == "/metrics":
            return await call_next(request)
        
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        REQUEST_DURATION.observe(duration)
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        # Add response time header
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        return response


def setup_health_endpoints(app: FastAPI):
    """Setup health check endpoints."""
    
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["health"],
        summary="Basic health check",
        description="Returns basic health status of the API"
    )
    async def health_check():
        """Basic health check endpoint."""
        return HealthResponse(
            status="healthy",
            timestamp=time.time(),
            version="1.0.0"
        )
    
    @app.get(
        "/health/detailed",
        response_model=Dict[str, Any],
        tags=["health"],
        summary="Detailed health check",
        description="Returns detailed health status including dependencies"
    )
    async def detailed_health_check():
        """Detailed health check with dependency status."""
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "1.0.0",
            "checks": {}
        }
        
        # Check database
        try:
            from ..database import DatabaseManager
            db_manager = DatabaseManager()
            db_health = db_manager.health_check()
            health_status["checks"]["database"] = db_health
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Check Redis
        try:
            if redis_client:
                await redis_client.ping()
                health_status["checks"]["redis"] = {"status": "healthy"}
            else:
                health_status["checks"]["redis"] = {"status": "not_configured"}
        except Exception as e:
            health_status["checks"]["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Check services
        try:
            # TODO: Add checks for STT, TTS, LLM services
            health_status["checks"]["services"] = {"status": "healthy"}
        except Exception as e:
            health_status["checks"]["services"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        return health_status
    
    @app.get(
        "/health/ready",
        tags=["health"],
        summary="Readiness check",
        description="Returns 200 if service is ready to accept traffic"
    )
    async def readiness_check():
        """Kubernetes readiness probe endpoint."""
        # Check critical dependencies
        try:
            if redis_client:
                await redis_client.ping()
            return {"status": "ready"}
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not ready"
            )
    
    @app.get(
        "/health/live",
        tags=["health"],
        summary="Liveness check",
        description="Returns 200 if service is alive"
    )
    async def liveness_check():
        """Kubernetes liveness probe endpoint."""
        return {"status": "alive"}
    
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(generate_latest(), media_type="text/plain")


def setup_docs_endpoints(app: FastAPI):
    """Setup custom documentation endpoints."""
    
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """Custom Swagger UI with authentication."""
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - Swagger UI",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
        )
    
    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc_html():
        """Custom ReDoc documentation."""
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
        )
    
    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_schema():
        """Custom OpenAPI schema."""
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        
        # Add security schemes
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key"
            }
        }
        
        # Add global security requirement
        openapi_schema["security"] = [
            {"BearerAuth": []},
            {"ApiKeyAuth": []}
        ]
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema


def setup_exception_handlers(app: FastAPI):
    """Setup global exception handlers."""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code="HTTP_ERROR",
                message=exc.detail,
                details={"status_code": exc.status_code}
            ).dict()
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle value errors."""
        logger.error(f"Value error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error_code="VALIDATION_ERROR",
                message=str(exc),
                details={"type": "value_error"}
            ).dict()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions."""
        logger.error(f"Unhandled exception: {exc}")
        logger.error(traceback.format_exc())
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error_code="INTERNAL_ERROR",
                message="An internal server error occurred",
                details={
                    "type": type(exc).__name__,
                    "request_id": getattr(request.state, "request_id", None)
                }
            ).dict()
        )
    
    @app.exception_handler(asyncio.TimeoutError)
    async def timeout_error_handler(request: Request, exc: asyncio.TimeoutError):
        """Handle timeout errors."""
        logger.error(f"Timeout error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            content=ErrorResponse(
                error_code="TIMEOUT_ERROR",
                message="Request timed out",
                details={"type": "timeout"}
            ).dict()
        )


# Create the main application
app = create_application()

# Make app available for uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )