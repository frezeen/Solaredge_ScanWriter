"""Flows package - Data collection orchestration handlers

This package exports all flow handlers for use by main.py and GUI.
Each flow is independent and can run in isolation.
"""

from flows.api_flow import run_api_flow
from flows.web_flow import run_web_flow
from flows.realtime_flow import run_realtime_flow
from flows.gme_flow import run_gme_flow
from flows.scan_flow import run_scan_flow
from flows.gui_flow import run_gui_mode

__all__ = [
    'run_api_flow',
    'run_web_flow',
    'run_realtime_flow',
    'run_gme_flow',
    'run_scan_flow',
    'run_gui_mode',
]
