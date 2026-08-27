"""Fly-In entry point."""

from __future__ import annotations
from orchestrator import FlyInApp


def main() -> int:
    """Create the application and run it."""
    return FlyInApp.from_argv().run()


if __name__ == '__main__':
    main()
