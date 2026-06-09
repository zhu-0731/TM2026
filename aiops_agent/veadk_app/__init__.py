"""VeADK integration layer for the offline diagnosis agent."""

__all__ = ["build_agent"]


def build_agent():
    """Lazily import and build the VeADK agent."""

    from .agent import build_agent as _build_agent

    return _build_agent()
