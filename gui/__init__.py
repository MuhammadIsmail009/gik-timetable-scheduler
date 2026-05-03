"""
gui package
Exposes the single entry point used by main.py to launch the application.

Usage:
    from gui import run
    run()
"""

from gui.main_window import run

__all__ = ["run"]