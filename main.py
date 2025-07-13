#!/usr/bin/env python3
# main.py

"""
The main entry point for the Job Repair Caddy application.
This script initializes and runs the main application class.
"""

from app_controller import JobScannerApp
import app_registry

if __name__ == "__main__":
    # Create an instance of the main application
    app = JobScannerApp()

    # Register the app instance with the registry
    app_registry.register_app(app)

    # Start the Tkinter event loop
    app.run()
