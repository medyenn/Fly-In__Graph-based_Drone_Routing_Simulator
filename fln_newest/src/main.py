"""Fly-In command-line entry point."""

from __future__ import annotations

from orchestrator import FlyInApp


def main() -> int:
    """Create the application and run it."""
    return FlyInApp.from_argv().run()
