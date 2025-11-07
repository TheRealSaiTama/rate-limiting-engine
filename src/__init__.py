"""Rate limiting engine package."""

from .token_bucket import is_allowed

__all__ = ["is_allowed"]
