"""
A simple registry for the application instance.
This allows any module to access the app instance without circular imports.
"""

# The global app instance
_app_instance = None

def register_app(app):
    """Register the application instance"""
    global _app_instance
    _app_instance = app

def get_app():
    """Get the application instance"""
    return _app_instance