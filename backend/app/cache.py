"""Tiny in-memory TTL cache.

This is deliberately not Redis: Redis costs money on every free tier we're
using, and a process-local cache is enough to stop a burst of dashboard
requests from re-hitting Supabase or an external API within the same TTL
window. The durable cache is the Supabase table itself, written by the
scheduled refresh jobs — this decorator just avoids redundant reads on top
of that within a short window.
"""
import time
import functools
from typing import Any, Callable

_store: dict[str, tuple[float, Any]] = {}


def ttl_cache(seconds: int = 900):
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__module__}.{func.__qualname__}:{args}:{sorted(kwargs.items())}"
            now = time.time()
            cached = _store.get(key)
            if cached and now - cached[0] < seconds:
                return cached[1]
            result = await func(*args, **kwargs)
            _store[key] = (now, result)
            return result

        return wrapper

    return decorator


def clear_cache() -> None:
    _store.clear()
