"""
Authentication and Authorization for MNX Gateway
Production-ready API key authentication with role-based access
"""

import os
import time
from functools import wraps
from typing import Optional, Set

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware


class APIKeyAuth:
    """API Key authentication manager"""
    
    def __init__(self):
        # Load API keys from environment
        self.api_keys = self._load_api_keys()
        self.public_endpoints = {"/health", "/metrics", "/", "/docs", "/redoc", "/openapi.json"}
    
    def _load_api_keys(self) -> dict:
        """Load API keys from environment variables"""
        keys = {}
        
        # Admin API key
        admin_key = os.getenv("MNX_ADMIN_API_KEY")
        if admin_key:
            keys[admin_key] = {"role": "admin", "name": "admin"}
        
        # Write API key for event ingestion
        write_key = os.getenv("MNX_WRITE_API_KEY") 
        if write_key:
            keys[write_key] = {"role": "write", "name": "event_writer"}
        
        # Read API key for queries
        read_key = os.getenv("MNX_READ_API_KEY")
        if read_key:
            keys[read_key] = {"role": "read", "name": "event_reader"}
        
        # Default development key if no keys configured
        if not keys:
            dev_key = "dev-12345-abcdef"
            keys[dev_key] = {"role": "admin", "name": "development"}
            print(f"⚠️  Using development API key: {dev_key}")
        
        return keys
    
    def validate_api_key(self, api_key: str) -> Optional[dict]:
        """Validate API key and return user info"""
        return self.api_keys.get(api_key)
    
    def check_permission(self, user_info: dict, endpoint: str, method: str) -> bool:
        """Check if user has permission for endpoint and method"""
        role = user_info.get("role", "")
        
        # Admin can do everything
        if role == "admin":
            return True
        
        # Write role can POST events
        if role == "write" and method == "POST" and endpoint.startswith("/v1/events"):
            return True
        
        # Read role can GET events and health
        if role == "read" and method == "GET":
            return True
        
        return False


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for API key authentication"""
    
    def __init__(self, app, auth_manager: APIKeyAuth):
        super().__init__(app)
        self.auth = auth_manager
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for public endpoints
        if request.url.path in self.auth.public_endpoints:
            response = await call_next(request)
            return response
        
        # Check for API key in header
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
        
        if api_key and api_key.startswith("Bearer "):
            api_key = api_key[7:]  # Remove "Bearer " prefix
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required. Provide in X-API-Key header or Authorization: Bearer <key>",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Validate API key
        user_info = self.auth.validate_api_key(api_key)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Check permissions
        if not self.auth.check_permission(user_info, request.url.path, request.method):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for {request.method} {request.url.path}"
            )
        
        # Add user info to request state
        request.state.user = user_info
        
        response = await call_next(request)
        return response


# Rate limiting classes
class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, max_requests: int = 1000, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # {client_id: [(timestamp, count), ...]}
    
    def is_allowed(self, client_id: str) -> tuple[bool, dict]:
        """Check if request is allowed and return rate limit info"""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old entries
        if client_id in self.requests:
            self.requests[client_id] = [
                (ts, count) for ts, count in self.requests[client_id] 
                if ts > window_start
            ]
        else:
            self.requests[client_id] = []
        
        # Count requests in current window
        current_requests = sum(count for ts, count in self.requests[client_id])
        
        # Check if allowed
        allowed = current_requests < self.max_requests
        
        if allowed:
            # Add this request
            self.requests[client_id].append((now, 1))
        
        # Rate limit info
        info = {
            "limit": self.max_requests,
            "remaining": max(0, self.max_requests - current_requests - (1 if allowed else 0)),
            "reset": int(now + self.window_seconds),
            "window": self.window_seconds
        }
        
        return allowed, info


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, app, rate_limiter: RateLimiter):
        super().__init__(app)
        self.rate_limiter = rate_limiter
    
    async def dispatch(self, request: Request, call_next):
        # Get client identifier (API key or IP)
        client_id = (
            request.headers.get("X-API-Key") or 
            request.headers.get("Authorization", "").replace("Bearer ", "") or
            request.client.host
        )
        
        # Check rate limit
        allowed, info = self.rate_limiter.is_allowed(client_id)
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(info["window"])
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response
