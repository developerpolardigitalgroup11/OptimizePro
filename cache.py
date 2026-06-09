"""Simple in-memory TTL cache. No external dependencies."""

import time
import threading

_cache = {}
_lock = threading.Lock()


def cache_get(key):
    """Get a value from cache. Returns None if expired or missing."""
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if time.time() > entry['expires']:
            del _cache[key]
            return None
        return entry['value']


def cache_set(key, value, ttl_seconds=300):
    """Set a value in cache with TTL."""
    with _lock:
        _cache[key] = {
            'value': value,
            'expires': time.time() + ttl_seconds,
        }


def cache_invalidate(key_prefix=None):
    """Invalidate cache entries. If key_prefix given, only matching keys."""
    with _lock:
        if key_prefix is None:
            _cache.clear()
        else:
            keys_to_delete = [k for k in _cache if k.startswith(key_prefix)]
            for k in keys_to_delete:
                del _cache[k]
