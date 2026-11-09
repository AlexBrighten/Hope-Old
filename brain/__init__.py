"""
brain package for Hope AI agent.
Provides LocalBrain (Ollama integration) and router (query classification & dispatch).
"""

from brain.local_brain import LocalBrain
from brain.router import route_query, strip_routing_prefix

__all__ = ["LocalBrain", "route_query", "strip_routing_prefix"]
