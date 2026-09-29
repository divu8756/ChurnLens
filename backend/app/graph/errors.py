"""Exceptions nodes raise to control the graph."""


class FatalNodeError(Exception):
    """Raised by a node when the run cannot continue (routes to error_node)."""
