"""Authentication middleware and utilities."""

import time
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ...core.config import settings
from ...core.logging import get_logger

logger = get_logger(__name__)


class JWTAuth:
    """JWT authentication handler."""
    
    def __init__(self, secret_key: str = None, algorithm: str = "HS256"):
        self.secret_key = secret_key or settings.jwt_secret_key or "your-secret-key"
        self.algorithm = algorithm
        self.bearer = HTTPBearer(auto_error=False)
    
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[int] = None
    ) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = time.time() + expires_delta
        else:
            expire = time.time() + (settings.jwt_expiration_hours * 3600)
        
        to_encode.update({
            "exp": expire,
            "iat": time.time(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            # Check expiration
            if payload.get("exp", 0) < time.time():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError as e:
            logger.warning(f"JWT validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials) -> Dict[str, Any]:
        """Get current user from JWT token."""
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing"
            )
        
        return self.verify_token(credentials.credentials)


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for FastAPI."""
    
    # Public endpoints that don't require authentication
    PUBLIC_PATHS = {
        "/health",
        "/health/live",
        "/health/ready",
        "/health/detailed",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics"
    }
    
    # API key protected endpoints
    API_KEY_PATHS = {
        "/api/v1/analytics/dashboard"
    }
    
    def __init__(self, app, jwt_auth: Optional[JWTAuth] = None):
        super().__init__(app)
        self.jwt_auth = jwt_auth or JWTAuth()
    
    async def dispatch(self, request: Request, call_next):
        """Process authentication for incoming requests."""
        path = request.url.path
        
        # Skip authentication for public paths
        if self._is_public_path(path):
            return await call_next(request)
        
        # Check for API key authentication
        if self._is_api_key_path(path):
            if await self._validate_api_key(request):
                return await call_next(request)
        
        # JWT authentication for protected endpoints
        if not await self._validate_jwt(request):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error_code": "UNAUTHORIZED",
                    "message": "Authentication required",
                    "details": {"path": path}
                }
            )
        
        response = await call_next(request)
        return response
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public."""
        return (
            path in self.PUBLIC_PATHS or
            path.startswith("/ws") or  # WebSocket endpoints
            path.startswith("/static") or  # Static files
            path == "/" or  # Root path
            path.startswith("/_") or  # Internal paths
            path.endswith(".ico") or  # Favicon
            path.endswith(".png") or  # Images
            path.endswith(".css") or  # Stylesheets
            path.endswith(".js")  # JavaScript files
        )
    
    def _is_api_key_path(self, path: str) -> bool:
        """Check if path requires API key authentication."""
        return path in self.API_KEY_PATHS
    
    async def _validate_api_key(self, request: Request) -> bool:
        """Validate API key from headers."""
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            return False
        
        # In production, validate against database or secure store
        valid_api_keys = settings.api_keys or ["demo-api-key"]
        
        if api_key in valid_api_keys:
            # Set user context for API key
            request.state.user = {
                "user_id": "api_user",
                "username": "api_user",
                "role": "api",
                "auth_type": "api_key"
            }
            return True
        
        logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
        return False
    
    async def _validate_jwt(self, request: Request) -> bool:
        """Validate JWT token from Authorization header."""
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return False
        
        try:
            # Extract token from "Bearer <token>"
            scheme, token = auth_header.split(" ", 1)
            
            if scheme.lower() != "bearer":
                return False
            
            # Verify token
            payload = self.jwt_auth.verify_token(token)
            
            # Set user context
            request.state.user = payload
            request.state.auth_type = "jwt"
            
            return True
            
        except (ValueError, HTTPException) as e:
            logger.debug(f"JWT validation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected auth error: {e}")
            return False


class AuthRequired:
    """Dependency for endpoints requiring authentication."""
    
    def __init__(self, required_role: Optional[str] = None):
        self.required_role = required_role
    
    async def __call__(self, request: Request) -> Dict[str, Any]:
        """Validate authentication and return user data."""
        user = getattr(request.state, "user", None)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Check role if specified
        if self.required_role:
            user_role = user.get("role")
            if user_role != self.required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{self.required_role}' required"
                )
        
        return user


# Convenience instances
jwt_auth = JWTAuth()
auth_required = AuthRequired()
admin_required = AuthRequired(required_role="admin")