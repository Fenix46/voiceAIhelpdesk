"""Request/Response logging middleware."""

import json
import time
import uuid
from typing import Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from ...core.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging."""
    
    # Sensitive headers to mask in logs
    SENSITIVE_HEADERS = {
        "authorization",
        "x-api-key",
        "cookie",
        "x-csrf-token",
        "x-auth-token"
    }
    
    # Paths to skip logging for (health checks, metrics, etc.)
    SKIP_LOGGING_PATHS = {
        "/health/live",
        "/health/ready", 
        "/metrics"
    }
    
    # Maximum request/response body size to log (bytes)
    MAX_BODY_SIZE = 10000
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Process request and response logging."""
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        start_time = time.time()
        path = request.url.path
        
        # Skip logging for certain paths
        if path in self.SKIP_LOGGING_PATHS:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        
        # Log request
        await self._log_request(request, request_id)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            await self._log_response(request, response, duration, request_id)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "duration": duration,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request details."""
        try:
            # Get user info if available
            user_info = getattr(request.state, "user", {})
            user_id = user_info.get("user_id", "anonymous")
            
            # Prepare request data
            request_data = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": self._mask_sensitive_headers(dict(request.headers)),
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "user_id": user_id,
                "content_type": request.headers.get("content-type"),
                "content_length": request.headers.get("content-length")
            }
            
            # Log request body for certain content types
            if await self._should_log_body(request):
                body = await self._get_request_body(request)
                if body:
                    request_data["body"] = body
            
            logger.info(
                f"Incoming request: {request.method} {request.url.path}",
                extra=request_data
            )
            
        except Exception as e:
            logger.error(f"Failed to log request: {e}")
    
    async def _log_response(
        self, 
        request: Request, 
        response: Response, 
        duration: float,
        request_id: str
    ):
        """Log response details."""
        try:
            # Get user info if available
            user_info = getattr(request.state, "user", {})
            user_id = user_info.get("user_id", "anonymous")
            
            # Prepare response data
            response_data = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": round(duration, 3),
                "response_headers": self._mask_sensitive_headers(dict(response.headers)),
                "user_id": user_id,
                "content_type": response.headers.get("content-type"),
                "content_length": response.headers.get("content-length")
            }
            
            # Log response body for certain content types and status codes
            if await self._should_log_response_body(request, response):
                body = await self._get_response_body(response)
                if body:
                    response_data["body"] = body
            
            # Determine log level based on status code
            if response.status_code >= 500:
                log_level = "error"
            elif response.status_code >= 400:
                log_level = "warning"
            else:
                log_level = "info"
            
            log_message = f"Response: {response.status_code} {request.method} {request.url.path} ({duration:.3f}s)"
            
            getattr(logger, log_level)(log_message, extra=response_data)
            
        except Exception as e:
            logger.error(f"Failed to log response: {e}")
    
    def _mask_sensitive_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Mask sensitive header values."""
        masked = {}
        
        for key, value in headers.items():
            if key.lower() in self.SENSITIVE_HEADERS:
                if len(value) > 8:
                    masked[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    masked[key] = "***masked***"
            else:
                masked[key] = value
        
        return masked
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address handling proxies."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    async def _should_log_body(self, request: Request) -> bool:
        """Determine if request body should be logged."""
        content_type = request.headers.get("content-type", "")
        
        # Log JSON and form data
        if any(ct in content_type.lower() for ct in ["application/json", "application/x-www-form-urlencoded"]):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) <= self.MAX_BODY_SIZE:
                return True
        
        return False
    
    async def _should_log_response_body(self, request: Request, response: Response) -> bool:
        """Determine if response body should be logged."""
        # Only log for errors or specific endpoints
        if response.status_code >= 400:
            return True
        
        # Log for specific paths (e.g., auth endpoints)
        if request.url.path.startswith("/api/v1/auth"):
            return True
        
        return False
    
    async def _get_request_body(self, request: Request) -> Optional[str]:
        """Get request body as string."""
        try:
            body = await request.body()
            if not body:
                return None
            
            # Try to decode as JSON for pretty printing
            try:
                decoded = body.decode("utf-8")
                if request.headers.get("content-type", "").startswith("application/json"):
                    json_data = json.loads(decoded)
                    return json.dumps(json_data, indent=2)
                return decoded
            except (UnicodeDecodeError, json.JSONDecodeError):
                return f"<binary data: {len(body)} bytes>"
                
        except Exception as e:
            logger.error(f"Failed to read request body: {e}")
            return None
    
    async def _get_response_body(self, response: Response) -> Optional[str]:
        """Get response body as string."""
        try:
            # Only handle simple responses, not streaming
            if isinstance(response, StreamingResponse):
                return "<streaming response>"
            
            if hasattr(response, 'body') and response.body:
                body = response.body
                if isinstance(body, bytes):
                    try:
                        decoded = body.decode("utf-8")
                        # Try to format JSON
                        if response.headers.get("content-type", "").startswith("application/json"):
                            json_data = json.loads(decoded)
                            return json.dumps(json_data, indent=2)
                        return decoded
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        return f"<binary data: {len(body)} bytes>"
                return str(body)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to read response body: {e}")
            return None