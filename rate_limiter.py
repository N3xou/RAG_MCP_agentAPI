# rate_limiter.py
"""
Per-Client Rate Limiter using Redis and Leaky Bucket Algorithm
Implements requests per minute (RPM) limits with per-minute resets
"""
import redis
import time
import json
from typing import Dict, Any, Optional, Tuple
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import os


class RateLimiter:
    """
    Leaky Bucket Rate Limiter with Redis backend

    Features:
    - Per-client rate limiting based on X-Client-ID header
    - Leaky bucket algorithm for smooth rate limiting
    - Redis for distributed state management
    - Atomic operations using Lua scripts
    """

    # Client tier configuration (can be overridden via env vars)
    TIER_LIMITS = {
        "basic": int(os.getenv("BASIC_RPM", "10")),  # 10 RPM
        "pro": int(os.getenv("PRO_RPM", "60")),  # 60 RPM
        "vip": int(os.getenv("VIP_RPM", "300")),  # 300 RPM
    }

    # Lua script for atomic leaky bucket operations
    # This ensures race-condition-free updates in distributed environments
    LEAKY_BUCKET_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local leak_rate = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    local ttl = tonumber(ARGV[4])

    -- Get current state
    local state = redis.call('GET', key)
    local tokens, last_ts

    if state then
        local decoded = cjson.decode(state)
        tokens = tonumber(decoded.tokens)
        last_ts = tonumber(decoded.last_ts)
    else
        tokens = 0
        last_ts = now
    end

    -- Calculate leak (tokens that leaked out since last check)
    local elapsed = now - last_ts
    local leaked = leak_rate * elapsed
    tokens = math.max(0, tokens - leaked)

    -- Try to add one token (this request)
    local new_tokens = tokens + 1

    -- Check if we're over capacity
    if new_tokens > capacity then
        -- Rate limited - return current state without updating
        return {0, tokens, capacity}
    else
        -- Allowed - update state
        local new_state = cjson.encode({
            tokens = new_tokens,
            last_ts = now
        })
        redis.call('SETEX', key, ttl, new_state)
        return {1, new_tokens, capacity}
    end
    """

    def __init__(self, redis_url: str = None):
        """
        Initialize rate limiter with Redis connection

        Args:
            redis_url: Redis connection URL (default: redis://localhost:6379)
        """
        redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")

        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            print(f"✓ Connected to Redis at {redis_url}")
        except Exception as e:
            print(f"⚠ Failed to connect to Redis: {e}")
            print("Rate limiting will NOT work without Redis!")
            self.redis_client = None

        # Register Lua script
        if self.redis_client:
            self.script_sha = self.redis_client.script_load(self.LEAKY_BUCKET_SCRIPT)

    def _get_client_tier(self, client_id: str) -> str:
        """
        Determine client tier from client ID

        Expected formats:
        - basic-123 -> basic tier
        - pro-456 -> pro tier
        - vip-789 -> vip tier

        Args:
            client_id: Client identifier from X-Client-ID header

        Returns:
            Tier name (basic, pro, or vip)
        """
        client_id_lower = client_id.lower()

        if client_id_lower.startswith("basic-"):
            return "basic"
        elif client_id_lower.startswith("pro-"):
            return "pro"
        elif client_id_lower.startswith("vip-"):
            return "vip"
        else:
            # Default to basic tier for unknown patterns
            return "basic"

    def _get_limit(self, client_id: str) -> int:
        """
        Get RPM limit for a client

        Args:
            client_id: Client identifier

        Returns:
            Requests per minute limit
        """
        tier = self._get_client_tier(client_id)
        return self.TIER_LIMITS.get(tier, 10)  # Default to 10 if tier not found

    def check_rate_limit(self, client_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request should be allowed based on rate limit

        Args:
            client_id: Client identifier from X-Client-ID header

        Returns:
            Tuple of (allowed: bool, info: dict with limit details)
        """
        if not self.redis_client:
            # If Redis is down, allow all requests (fail-open)
            # In production, you might want to fail-closed instead
            return True, {
                "allowed": True,
                "error": "Redis unavailable - rate limiting disabled"
            }

        # Get client's limit
        limit_rpm = self._get_limit(client_id)

        # Leaky bucket parameters
        capacity = limit_rpm  # Bucket capacity = RPM
        leak_rate = limit_rpm / 60.0  # Leak rate: capacity per minute = capacity/60 per second

        # Current time
        now = time.time()

        # Redis key
        key = f"rl:{client_id}"

        # TTL: keep state for 2 minutes (allows recovery after silence)
        ttl = 120

        try:
            # Execute Lua script atomically
            result = self.redis_client.evalsha(
                self.script_sha,
                1,  # Number of keys
                key,
                capacity,
                leak_rate,
                now,
                ttl
            )

            allowed = bool(result[0])
            current_tokens = float(result[1])
            capacity_limit = float(result[2])

            # Calculate remaining capacity
            remaining = max(0, int(capacity_limit - current_tokens))

            # Calculate reset time (when bucket will be empty)
            # At current leak rate, how long until tokens = 0?
            seconds_until_reset = int(current_tokens / leak_rate) if leak_rate > 0 else 60
            reset_timestamp = int(now + seconds_until_reset)

            # Calculate retry-after (when bucket will have room for 1 more)
            if not allowed:
                # Time until 1 token leaks out
                retry_after = int(1.0 / leak_rate) if leak_rate > 0 else 1
            else:
                retry_after = 0

            return allowed, {
                "allowed": allowed,
                "client_id": client_id,
                "limit_rpm": limit_rpm,
                "remaining": remaining,
                "reset_timestamp": reset_timestamp,
                "retry_after": retry_after,
                "tier": self._get_client_tier(client_id)
            }

        except redis.exceptions.NoScriptError:
            # Script not loaded, reload it
            self.script_sha = self.redis_client.script_load(self.LEAKY_BUCKET_SCRIPT)
            # Retry once
            return self.check_rate_limit(client_id)

        except Exception as e:
            print(f"Rate limiter error: {e}")
            # Fail-open on errors
            return True, {
                "allowed": True,
                "error": str(e)
            }

    async def check_request(self, request: Request) -> Optional[JSONResponse]:
        """
        Middleware function to check rate limit for incoming request

        Args:
            request: FastAPI Request object

        Returns:
            None if allowed, JSONResponse with 429 if rate limited
        """
        # Extract client ID from header
        client_id = request.headers.get("X-Client-ID")

        # Reject if missing
        if not client_id:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_client_id",
                    "message": "X-Client-ID header is required"
                }
            )

        # Check rate limit
        allowed, info = self.check_rate_limit(client_id)

        # Add rate limit headers to request state for response
        request.state.rate_limit_info = info

        if not allowed:
            # Rate limited - return 429
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "client_id": info["client_id"],
                    "limit_rpm": info["limit_rpm"],
                    "tier": info["tier"],
                    "message": f"Rate limit exceeded. You are on the '{info['tier']}' tier with {info['limit_rpm']} requests per minute."
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit_rpm"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset_timestamp"]),
                    "Retry-After": str(info["retry_after"])
                }
            )

        # Allowed - continue to endpoint
        return None

    def get_stats(self, client_id: str) -> Dict[str, Any]:
        """
        Get current rate limit stats for a client

        Args:
            client_id: Client identifier

        Returns:
            Dictionary with current state
        """
        if not self.redis_client:
            return {"error": "Redis unavailable"}

        key = f"rl:{client_id}"

        try:
            state = self.redis_client.get(key)
            if state:
                decoded = json.loads(state)
                limit_rpm = self._get_limit(client_id)

                return {
                    "client_id": client_id,
                    "tier": self._get_client_tier(client_id),
                    "limit_rpm": limit_rpm,
                    "current_tokens": decoded["tokens"],
                    "last_update": decoded["last_ts"]
                }
            else:
                return {
                    "client_id": client_id,
                    "tier": self._get_client_tier(client_id),
                    "limit_rpm": self._get_limit(client_id),
                    "current_tokens": 0,
                    "message": "No recent activity"
                }
        except Exception as e:
            return {"error": str(e)}


# Global rate limiter instance
rate_limiter = RateLimiter()