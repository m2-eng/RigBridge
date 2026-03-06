"""
Protocol Layer für RigBridge.

Abstrahiert verschiedene Funkgerät-Protokolle (CI-V, CAT, etc.).
"""

from .base_protocol import BaseProtocol, CommandResult
from .protocol_manager import ProtocolManager
from .civ_protocol import CIVProtocol

__all__ = ['BaseProtocol', 'CommandResult', 'ProtocolManager', 'CIVProtocol']
