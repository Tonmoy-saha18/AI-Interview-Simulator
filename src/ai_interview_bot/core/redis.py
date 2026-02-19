"""Redis client for session storage and caching."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from .config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None

SESSION_KEY_PREFIX = "session:"
SESSION_TTL_SECONDS = 3600 * 6  # 6 hours — active sessions expire after this


async def get_redis() -> aioredis.Redis:
    """Return the Redis client singleton, creating it on first call."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Shut down the Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


# ---------------------------------------------------------------------------
# Session state persistence
# ---------------------------------------------------------------------------


def _session_key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


async def save_session_state(session_id: str, state: Dict[str, Any]) -> None:
    """Persist the full graph state snapshot to Redis."""
    try:
        client = await get_redis()
        await client.set(
            _session_key(session_id),
            json.dumps(state, default=str),
            ex=SESSION_TTL_SECONDS,
        )
    except Exception:
        logger.warning("Failed to save session %s to Redis", session_id, exc_info=True)


async def load_session_state(session_id: str) -> Optional[Dict[str, Any]]:
    """Load a session state snapshot from Redis, or *None* if missing/expired."""
    try:
        client = await get_redis()
        raw = await client.get(_session_key(session_id))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("Failed to load session %s from Redis", session_id, exc_info=True)
        return None


async def delete_session_state(session_id: str) -> None:
    """Remove the session state from Redis (e.g. on completion)."""
    try:
        client = await get_redis()
        await client.delete(_session_key(session_id))
    except Exception:
        logger.warning("Failed to delete session %s from Redis", session_id, exc_info=True)
