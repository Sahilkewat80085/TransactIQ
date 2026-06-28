import time
import logging
from redis import Redis
from fastapi import Request, HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Redis client lazily
_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            _redis_client.ping()
            logger.info("Connected to Redis for rate limiting.")
        except Exception as e:
            logger.warning(
                f"Failed to connect to Redis at {settings.REDIS_URL} for rate limiting: {e}. "
                "Falling back to in-memory rate limiting."
            )
            _redis_client = False
    return _redis_client

# In-memory rate limiting fallback
_in_memory_limits = {}

def check_rate_limit(request: Request, limit: int = 15, window: int = 60):
    """
    Checks the rate limit for the client IP address.
    Uses Redis sliding-window if available, else falls back to in-memory dictionary.
    """
    client_ip = request.client.host if request.client else "unknown_ip"
    current_time = time.time()
    
    redis = get_redis_client()
    if redis:
        key = f"rate_limit:{client_ip}:{request.url.path}"
        try:
            pipe = redis.pipeline()
            # Remove elements outside the window
            pipe.zremrangebyscore(key, 0, current_time - window)
            # Add current request timestamp
            pipe.zadd(key, {str(current_time): current_time})
            # Count elements in sorted set
            pipe.zcard(key)
            # Refresh TTL
            pipe.expire(key, window)
            
            results = pipe.execute()
            request_count = results[2]
            
            if request_count > limit:
                logger.warning(f"Rate limit exceeded for IP {client_ip} on {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later."
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Redis rate limiting exception: {e}. Falling back to in-memory.")
            
    # In-memory sliding window fallback
    key = f"{client_ip}:{request.url.path}"
    if key not in _in_memory_limits:
        _in_memory_limits[key] = []
        
    # Purge expired timestamps
    _in_memory_limits[key] = [t for t in _in_memory_limits[key] if t > current_time - window]
    
    if len(_in_memory_limits[key]) >= limit:
        logger.warning(f"Rate limit exceeded (in-memory) for IP {client_ip} on {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later."
        )
        
    _in_memory_limits[key].append(current_time)
