"""
Zentrale Konfigurationsverwaltung für RigBridge.

Verwaltet Anwendungseinstellungen, Protokollkonfigurationen
und gemeinsame Datenstrukturen.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Any, Dict
from pathlib import Path
from enum import Enum
import json
import os


class LogLevel(str, Enum):
    """Verfügbare Log-Levels."""
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'


@dataclass
class USBConfig:
    """USB/Serial-Verbindungskonfiguration."""
    port: str = '/dev/ttyUSB0'  # Linux-Standard; Windows: 'COM3'
    baud_rate: int = 19200
    data_bits: int = 8
    stop_bits: int = 1
    parity: str = 'N'  # None
    timeout: float = 1.0
    reconnect_interval: int = 5


@dataclass
class APIConfig:
    """REST-API-Konfiguration."""
    host: str = '127.0.0.1'
    port: int = 8080
    enable_https: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    log_level: LogLevel = LogLevel.INFO


@dataclass
class WavelogConfig:
    """Wavelog CAT-Integrationen."""
    enabled: bool = False
    api_url: str = 'https://api.wavelog.local'
    api_key: str = ''
    polling_interval: int = 5


@dataclass
class DeviceConfig:
    """Geräte-Konfiguration."""
    name: str = 'Icom IC-905'
    manufacturer: str = 'icom'  # Hersteller: 'icom', 'yaesu', 'kenwood', etc.
    protocol_file: str = 'ic905'  # YAML-Dateiname ohne Pfad und Endung

    def get_protocol_path(self) -> Path:
        """Konstruiert den vollständigen Pfad zur Protokolldatei."""
        return Path(
            f'protocols/manufacturers/{self.manufacturer}/{self.protocol_file}.yaml'
        )


@dataclass
class RigBridgeConfig:
    """Haupt-Konfigurationsklasse."""
    usb: USBConfig = field(default_factory=USBConfig)
    api: APIConfig = field(default_factory=APIConfig)
    wavelog: WavelogConfig = field(default_factory=WavelogConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    config_file: Optional[Path] = None

    def save(self, path: Optional[Path] = None) -> None:
        """Speichert Konfiguration als JSON-Datei."""
        file_path = path or self.config_file
        if not file_path:
            raise ValueError('config_file not set')

        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        config_dict = {
            'usb': asdict(self.usb),
            'api': {**asdict(self.api), 'log_level': self.api.log_level.value},
            'wavelog': asdict(self.wavelog),
            'device': asdict(self.device),
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load(path: Path) -> 'RigBridgeConfig':
        """Lädt Konfiguration aus JSON-Datei."""
        if not path.exists():
            return RigBridgeConfig(config_file=path)

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        config = RigBridgeConfig(config_file=path)
        if 'usb' in data:
            config.usb = USBConfig(**data['usb'])
        if 'api' in data:
            api_data = data['api']
            if 'log_level' in api_data and isinstance(api_data['log_level'], str):
                api_data['log_level'] = LogLevel(api_data['log_level'])
            config.api = APIConfig(**api_data)
        if 'wavelog' in data:
            config.wavelog = WavelogConfig(**data['wavelog'])
        if 'device' in data:
            config.device = DeviceConfig(**data['device'])

        return config

    def override_from_env(self) -> None:
        """Überschreibt Konfiguration mit Umgebungsvariablen (12-Factor)."""
        # USB
        if port := os.getenv('RIGBRIDGE_USB_PORT'):
            self.usb.port = port
        if baud := os.getenv('RIGBRIDGE_USB_BAUD'):
            self.usb.baud_rate = int(baud)

        # API
        if api_host := os.getenv('RIGBRIDGE_API_HOST'):
            self.api.host = api_host
        if api_port := os.getenv('RIGBRIDGE_API_PORT'):
            self.api.port = int(api_port)
        if log_level := os.getenv('RIGBRIDGE_LOG_LEVEL'):
            self.api.log_level = LogLevel(log_level.upper())

        # Wavelog
        if wavelog_enabled := os.getenv('RIGBRIDGE_WAVELOG_ENABLED'):
            self.wavelog.enabled = wavelog_enabled.lower() == 'true'
        if wavelog_url := os.getenv('RIGBRIDGE_WAVELOG_URL'):
            self.wavelog.api_url = wavelog_url
        if wavelog_key := os.getenv('RIGBRIDGE_WAVELOG_KEY'):
            self.wavelog.api_key = wavelog_key

        # Device
        if device_name := os.getenv('RIGBRIDGE_DEVICE_NAME'):
            self.device.name = device_name


class ConfigManager:
    """Zentrale Config-Verwaltung (Singleton)."""

    _instance: Optional['ConfigManager'] = None
    _config: Optional[RigBridgeConfig] = None

    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def initialize(config_file: Optional[Path] = None) -> RigBridgeConfig:
        """
        Initialisiert die Konfiguration.

        Lade-Reihenfolge:
        1. JSON-Datei (falls vorhanden)
        2. Umgebungsvariablen (überschreibt Datei)
        """
        manager = ConfigManager()
        default_path = Path('config.json')
        config_path = config_file or default_path

        manager._config = RigBridgeConfig.load(config_path)
        manager._config.override_from_env()

        return manager._config

    @staticmethod
    def get() -> RigBridgeConfig:
        """Gibt die aktuelle Konfiguration zurück."""
        manager = ConfigManager()
        if manager._config is None:
            manager._config = ConfigManager.initialize()
        return manager._config

    @staticmethod
    def save(path: Optional[Path] = None) -> None:
        """Speichert die aktuelle Konfiguration."""
        config = ConfigManager.get()
        config.save(path)
