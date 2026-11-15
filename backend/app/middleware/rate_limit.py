"""
Rate limiting middleware for expensive operations.

Implements sliding window rate limiting with configurable limits:
- Query operations: 20 per minute per user
- Ingestion operations: 5 per hour per user
- IP-level limit: 100 requests per minute (DDoS protection)

For production, consider using Redis-backed rate limiting for
multi-instance deployments.
"""

import time
import logging
from collections import defaultdict, deque
from typing import Dict, Deque, Tuple, Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter for API endpoints.
    
    Tracks requests per user and per IP to prevent abuse of:
    - Expensive RAG query operations
    - Resource-intensive document ingestion
    - General API flooding (DDoS)
    """
    
    def __init__(
        self,
        app,
        query_limit_per_minute: int = 20,
        ingest_limit_per_hour: int = 5,
        ip_limit_per_minute: int = 100,
    ):
        super().__init__(app)
        self.query_limit_per_minute = query_limit_per_minute
        self.ingest_limit_per_hour = ingest_limit_per_hour
        self.ip_limit_per_minute = ip_limit_per_minute
        
        # Storage: {user_id: deque([(timestamp, operation)])}
        self._user_windows: Dict[str, Deque[Tuple[float, str]]] = defaultdict(deque)
        
        # Storage: {ip: deque([timestamp])}
        self._ip_windows: Dict[str, Deque[float]] = defaultdict(deque)
    
    async def dispatch(self, request: Request, call_next):
        """
        Check rate limits before forwarding request.
        """
        # Extract identifiers
        user_id = self._get_user_id(request)
        client_ip = request.client.host if request.client else "unknown"
        
        now = time.time()
        path = request.url.path
        method = request.method
        
        # Classify operation type
        operation = self._classify_operation(path, method)
        
        # 1. Check IP-level rate limit (applies to all requests)
        if not self._check_ip_limit(client_ip, now):
            logger.warning(
                f"IP rate limit exceeded ip={client_ip} path={path}"
            )
            raise HTTPException(
                status_code=429,
                detail="Too many requests from this IP address. Please try again later.",
            )
        
        # 2. Check user-level rate limit (applies to classified operations)
        if user_id and operation:
            if not self._check_user_limit(user_id, operation, now):
                logger.warning(
                    f"User rate limit exceeded user_id={user_id} operation={operation} path={path}"
                )
                
                # Provide specific error message based on operation
                if operation == "query":
                    detail = (
                        f"Query rate limit exceeded. "
                        f"Maximum {self.query_limit_per_minute} queries per minute allowed. "
                        f"Please wait before submitting more queries."
                    )
                else:  # ingest
                    detail = (
                        f"Ingestion rate limit exceeded. "
                        f"Maximum {self.ingest_limit_per_hour} document uploads per hour allowed. "
                        f"Please wait before uploading more documents."
                    )
                
                raise HTTPException(status_code=429, detail=detail)
        
        # Forward request
        response = await call_next(request)
        return response
    
    def _get_user_id(self, request: Request) -> Optional[str]:
        """
        Extract user_id from request state (set by auth middleware).
        """
        return getattr(request.state, "user_id", None)
    
    def _classify_operation(self, path: str, method: str) -> Optional[str]:
        """
        Classify request into rate-limited operation category.
        
        Returns:
            "query" | "ingest" | None
        """
        if method != "POST":
            return None
        
        # Query operations
        if any(keyword in path for keyword in ["/query", "/ask", "/compare", "/summarize"]):
            return "query"
        
        # Ingestion operations
        if any(keyword in path for keyword in ["/ingest", "/upload", "/documents"]):
            if "delete" not in path:  # Don't rate limit deletions
                return "ingest"
        
        return None
    
    def _check_ip_limit(self, ip: str, now: float) -> bool:
        """
        Check IP-level rate limit (sliding window).
        
        Returns:
            True if request allowed, False if limit exceeded
        """
        window = self._ip_windows[ip]
        
        # Remove requests older than 60 seconds
        while window and window[0] < now - 60:
            window.popleft()
        
        # Check limit
        if len(window) >= self.ip_limit_per_minute:
            return False
        
        # Record request
        window.append(now)
        return True
    
    def _check_user_limit(self, user_id: str, operation: str, now: float) -> bool:
        """
        Check user-level rate limit for specific operation (sliding window).
        
        Returns:
            True if request allowed, False if limit exceeded
        """
        window = self._user_windows[user_id]
        
        # Determine window and limit based on operation
        if operation == "query":
            cutoff = now - 60  # 1 minute window
            limit = self.query_limit_per_minute
        else:  # ingest
            cutoff = now - 3600  # 1 hour window
            limit = self.ingest_limit_per_hour
        
        # Remove old entries
        while window and window[0][0] < cutoff:
            window.popleft()
        
        # Count operations of this type in current window
        count = sum(1 for _, op in window if op == operation)
        
        # Check limit
        if count >= limit:
            return False
        
        # Record request
        window.append((now, operation))
        return True
    
    def get_stats(self, user_id: Optional[str] = None, ip: Optional[str] = None) -> dict:
        """
        Get rate limit statistics for debugging/monitoring.
        
        Args:
            user_id: Get stats for specific user
            ip: Get stats for specific IP
        
        Returns:
            Dict with current usage statistics
        """
        stats = {}
        now = time.time()
        
        if user_id and user_id in self._user_windows:
            window = self._user_windows[user_id]
            
            # Count recent operations
            query_count = sum(
                1 for ts, op in window 
                if op == "query" and ts > now - 60
            )
            ingest_count = sum(
                1 for ts, op in window 
                if op == "ingest" and ts > now - 3600
            )
            
            stats["user"] = {
                "user_id": user_id,
                "queries_last_minute": query_count,
                "query_limit": self.query_limit_per_minute,
                "ingestions_last_hour": ingest_count,
                "ingest_limit": self.ingest_limit_per_hour,
            }
        
        if ip and ip in self._ip_windows:
            window = self._ip_windows[ip]
            recent = sum(1 for ts in window if ts > now - 60)
            
            stats["ip"] = {
                "ip": ip,
                "requests_last_minute": recent,
                "limit": self.ip_limit_per_minute,
            }
        
        return stats


# Monitoring endpoint helper
def get_rate_limit_stats(request: Request) -> dict:
    """
    Helper function to expose rate limit stats for monitoring.
    Can be used in health check or admin endpoints.
    """
    middleware = None
    for m in request.app.user_middleware:
        if isinstance(m, RateLimitMiddleware):
            middleware = m
            break
    
    if not middleware:
        return {"error": "Rate limit middleware not found"}
    
    user_id = getattr(request.state, "user_id", None)
    client_ip = request.client.host if request.client else None
    
    return middleware.get_stats(user_id=user_id, ip=client_ip)
