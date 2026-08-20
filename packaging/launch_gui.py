"""PyInstaller entry point for the window.

A separate launcher because srebook.gui.app uses relative imports, which break
when a module is run as a top-level script.
"""
from srebook.gui.app import main

raise SystemExit(main())
