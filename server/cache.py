# server/cache.py
import threading
import time
from functools import wraps


def ttl_cache(seconds: float):
    """Memoize a function by its arguments for `seconds` (thread-safe; errors aren't cached)."""

    def decorator(fn):
        entries: dict[tuple, tuple[float, object]] = {}
        lock = threading.Lock()

        @wraps(fn)
        def wrapper(*args):
            now = time.monotonic()
            with lock:
                hit = entries.get(args)
                if hit and now - hit[0] < seconds:
                    return hit[1]
            value = fn(*args)
            with lock:
                entries[args] = (time.monotonic(), value)
            return value

        wrapper.cache_clear = lambda: entries.clear()
        return wrapper

    return decorator
