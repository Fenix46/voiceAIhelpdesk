"""Security middleware for API protection."""

import hashlib
import hmac
import time
from typing import Dict, List, Optional, Set
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ...core.config import settings
from ...core.logging import get_logger

logger = get_logger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware with various protection mechanisms."""
    
    def __init__(self, app):
        super().__init__(app)
        
        # IP-based rate limiting
        self.request_counts: Dict[str, List[float]] = {}
        self.blocked_ips: Set[str] = set()
        
        # Request size limits
        self.max_request_size = settings.max_request_size or 10 * 1024 * 1024  # 10MB
        self.max_json_size = settings.max_json_size or 1024 * 1024  # 1MB
        
        # Security headers
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY", 
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        }
    
    async def dispatch(self, request: Request, call_next):
        """Apply security checks and headers."""
        client_ip = self._get_client_ip(request)
        
        try:
            # Check if IP is blocked
            if client_ip in self.blocked_ips:
                return self._create_blocked_response("IP address blocked")
            
            # Apply rate limiting
            if not await self._check_rate_limit(client_ip, request):
                return self._create_rate_limit_response()
            
            # Validate request size
            if not await self._validate_request_size(request):
                return self._create_error_response(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    "Request too large"
                )
            
            # Validate content type for POST/PUT requests
            if not self._validate_content_type(request):
                return self._create_error_response(
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    "Unsupported media type"
                )
            
            # Check for suspicious patterns
            if await self._detect_suspicious_activity(request):
                logger.warning(f"Suspicious activity detected from {client_ip}: {request.url.path}")
                # Don't block immediately, but log for monitoring
            
            # Validate webhook signatures if applicable
            if request.url.path.startswith("/webhook/"):
                if not await self._validate_webhook_signature(request):
                    return self._create_error_response(
                        status.HTTP_401_UNAUTHORIZED,
                        "Invalid webhook signature"
                    )
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            self._add_security_headers(response)
            
            return response
            
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            # Don't expose internal errors
            return self._create_error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Internal server error"
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address with proxy support."""
        # Check X-Forwarded-For header
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to client host
        return request.client.host if request.client else "unknown"
    
    async def _check_rate_limit(self, client_ip: str, request: Request) -> bool:
        """Check IP-based rate limiting."""
        current_time = time.time()
        window_size = 60  # 1 minute window
        max_requests = settings.rate_limit_requests or 100
        
        # Clean old entries
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                req_time for req_time in self.request_counts[client_ip]
                if current_time - req_time < window_size
            ]
        else:
            self.request_counts[client_ip] = []
        
        # Add current request
        self.request_counts[client_ip].append(current_time)
        
        # Check limit
        if len(self.request_counts[client_ip]) > max_requests:
            # Block IP for repeated violations
            violation_count = len([
                req_time for req_time in self.request_counts[client_ip][-max_requests:]
                if current_time - req_time < 10  # Last 10 seconds
            ])
            
            if violation_count > max_requests / 2:
                self.blocked_ips.add(client_ip)
                logger.warning(f"IP {client_ip} blocked for rate limit violations")
            
            return False
        
        return True
    
    async def _validate_request_size(self, request: Request) -> bool:
        """Validate request size limits."""
        content_length = request.headers.get("content-length")
        
        if content_length:
            try:
                size = int(content_length)
                
                # Check overall size limit
                if size > self.max_request_size:
                    return False
                
                # Check JSON size limit
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type and size > self.max_json_size:
                    return False
                
            except ValueError:
                return False
        
        return True
    
    def _validate_content_type(self, request: Request) -> bool:
        """Validate content type for requests with body."""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            
            # Allow common content types
            allowed_types = [
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
                "text/plain",
                "audio/wav",
                "audio/mpeg",
                "audio/ogg",
                "audio/webm"
            ]
            
            if not any(allowed in content_type.lower() for allowed in allowed_types):
                return False
        
        return True
    
    async def _detect_suspicious_activity(self, request: Request) -> bool:
        """Detect suspicious request patterns."""
        path = request.url.path.lower()
        query = str(request.query_params).lower()
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Check for common attack patterns
        suspicious_patterns = [
            # SQL injection
            "union select", "drop table", "delete from", "insert into",
            "'; --", "' or '1'='1", "' or 1=1",
            
            # XSS
            "<script", "javascript:", "onload=", "onerror=", "onclick=",
            
            # Path traversal
            "../", "..\\", "%2e%2e", "etc/passwd", "web.config",
            
            # Command injection
            "| cat", "&& cat", "; cat", "$(", "`",
            
            # File inclusion
            "php://", "file://", "data://", "expect://",
            
            # Admin panel scanning
            "/admin", "/wp-admin", "/phpmyadmin", "/administrator",
        ]
        
        # Check path and query parameters
        full_request = f"{path} {query}"
        
        for pattern in suspicious_patterns:
            if pattern in full_request:
                return True
        
        # Check for bot user agents (basic check)
        bot_indicators = ["bot", "crawler", "spider", "scan"]
        if any(indicator in user_agent for indicator in bot_indicators):
            # Not necessarily suspicious, but worth logging
            pass
        
        return False
    
    async def _validate_webhook_signature(self, request: Request) -> bool:
        """Validate webhook signature for secure webhooks."""
        if not settings.webhook_secret:
            return True  # No secret configured, skip validation
        
        signature_header = request.headers.get("x-hub-signature-256")
        if not signature_header:
            return False
        
        try:
            # Get request body
            body = await request.body()
            
            # Calculate expected signature
            expected_signature = hmac.new(
                settings.webhook_secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures (time-safe comparison)
            expected_header = f"sha256={expected_signature}"
            return hmac.compare_digest(signature_header, expected_header)
            
        except Exception as e:
            logger.error(f"Webhook signature validation error: {e}")
            return False
    
    def _add_security_headers(self, response):
        """Add security headers to response."""
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        # Add HSTS only for HTTPS
        if hasattr(response, 'scope') and response.scope.get("scheme") == "https":
            response.headers["Strict-Transport-Security"] = self.security_headers["Strict-Transport-Security"]
    
    def _create_rate_limit_response(self) -> JSONResponse:
        """Create rate limit exceeded response."""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
                "details": {"retry_after": 60}
            },
            headers={"Retry-After": "60"}
        )
    
    def _create_blocked_response(self, message: str) -> JSONResponse:
        """Create blocked IP response."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error_code": "IP_BLOCKED",
                "message": message,
                "details": {"contact": "support@voicehelpdeskai.com"}
            }
        )
    
    def _create_error_response(self, status_code: int, message: str) -> JSONResponse:
        """Create generic error response."""
        return JSONResponse(
            status_code=status_code,
            content={
                "error_code": "SECURITY_ERROR",
                "message": message,
                "details": {}
            }
        )
    
    def unblock_ip(self, ip_address: str):
        """Manually unblock an IP address."""
        if ip_address in self.blocked_ips:
            self.blocked_ips.remove(ip_address)
            logger.info(f"IP {ip_address} unblocked")
    
    def get_blocked_ips(self) -> Set[str]:
        """Get list of currently blocked IPs."""
        return self.blocked_ips.copy()
    
    def get_rate_limit_status(self, ip_address: str) -> Dict[str, any]:
        """Get rate limit status for an IP."""
        current_time = time.time()
        window_size = 60
        
        if ip_address in self.request_counts:
            recent_requests = [
                req_time for req_time in self.request_counts[ip_address]
                if current_time - req_time < window_size
            ]
            return {
                "ip": ip_address,
                "requests_in_window": len(recent_requests),
                "max_requests": settings.rate_limit_requests or 100,
                "window_size": window_size,
                "is_blocked": ip_address in self.blocked_ips
            }
        
        return {
            "ip": ip_address,
            "requests_in_window": 0,
            "max_requests": settings.rate_limit_requests or 100,
            "window_size": window_size,
            "is_blocked": ip_address in self.blocked_ips
        }