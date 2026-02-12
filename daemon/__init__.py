"""Automation daemon package for wake-word command dispatch."""

from .config import DaemonConfig
from .service import JarvisDaemon

__all__ = ["DaemonConfig", "JarvisDaemon"]
