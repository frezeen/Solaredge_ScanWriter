"""
GUI Core Components - Separazione responsabilità
"""

from .config_handler import ConfigHandler
from .state_manager import StateManager
from .unified_toggle_handler import UnifiedToggleHandler
from .middleware import (
    ErrorHandlerMiddleware,
    RequestLoggingMiddleware,
    CORSMiddleware,
    SecurityHeadersMiddleware,
    create_middleware_stack
)

__all__ = [
    'ConfigHandler',
    'StateManager',
    'UnifiedToggleHandler',
    'ErrorHandlerMiddleware',
    'RequestLoggingMiddleware',
    'CORSMiddleware',
    'SecurityHeadersMiddleware',
    'create_middleware_stack'
]
