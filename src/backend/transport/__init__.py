"""
Transport Layer - Abstraction für verschiedene Transport-Arten (USB, LAN, etc.)

Dieses Modul stellt eine einheitliche Schnittstelle für verschiedene
Transport-Mechanismen bereit.
"""

from .base_transport import BaseTransport, FrameData
from .usb_connection import USBConnection, MockSerial, create_mock_response_factory
from .connection_state import ConnectionState, TransportStatus
from .transport_manager import TransportManager, TransportType

__all__ = [
    # Base Classes
    "BaseTransport",
    "FrameData",
    # USB Implementation
    "USBConnection",
    "MockSerial",
    "create_mock_response_factory",
    # State Management
    "ConnectionState",
    "TransportStatus",
    # Manager
    "TransportManager",
    "TransportType",
]
