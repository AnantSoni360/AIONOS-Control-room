"""
middleware/rate_limit.py - slowapi rate limiter for AIONOS.

Import `limiter` and use @limiter.limit("N/minute") on route handlers.
The SlowAPIMiddleware is registered in main.py.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
