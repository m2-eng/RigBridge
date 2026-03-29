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


API_HOST_FIXED = '0.0.0.0'
API_PORT_DEFAULT = 8080


def is_running_in_container() -> bool:
    """Erkennt, ob RigBridge aktuell in einem Container läuft."""
    if os.environ.get('RIGBRIDGE_RUNTIME', '').strip().lower() == 'container':
        return True

    if os.environ.get('DOCKER_CONTAINER', '').strip() == '1':
        return True

    return Path('/.dockerenv').exists()


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
    host: str = API_HOST_FIXED
    port: int = API_PORT_DEFAULT
    health_check_enabled: bool = True
    enable_https: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    log_level: LogLevel = LogLevel.INFO


@dataclass
class WavelogConfig:
    """Wavelog CAT-Integrationen."""
    enabled: bool = False
    api_url: str = 'https://api.wavelog.local'
    api_key_or_secret_ref: str = ''
    polling_interval: int = 5
    logbook_update_interval: int = 2
    radio_name: str = 'ICOM IC-905'
    station_id: Optional[str] = None
    wavelog_gate_http_base: str = 'http://localhost:54321'
    wavelog_gate_ws_url: str = 'ws://localhost:54322'


@dataclass
class SecretProviderConfig:
    """Secret-Provider-Konfiguration."""
    provider: str = 'vault'
    vault_url: str = 'http://127.0.0.1:8200'
    vault_mount: str = 'secret'
    token_file: str = '/run/secrets/vault_token'


@dataclass
class DeviceConfig:
    """Geräte-Konfiguration."""
    name: str = 'Icom IC-905'
    manufacturer: str = 'icom'  # Hersteller: 'icom', 'yaesu', 'kenwood', etc.
    protocol_file: str = 'ic905'  # YAML-Dateiname ohne Pfad und Endung
    controller_address: int = 0xE0  # Controller-Adresse (CI-V)
    radio_address: int = 0xA4  # Funkgerät-Adresse (CI-V)

    def get_manufacturer_path(self) -> Path:
        """Konstruiert den vollständigen Pfad zur Herstellerdatei."""
        return Path(
            f'protocols/manufacturers/{self.manufacturer}.yaml'
        )

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
    secret_provider: SecretProviderConfig = field(default_factory=SecretProviderConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    config_file: Optional[Path] = None

    def save(self, path: Optional[Path] = None) -> None:
        """Speichert Konfiguration als JSON-Datei."""
        file_path = path or self.config_file
        if not file_path:
            raise ValueError('config_file not set')

        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Device-Config mit Hex-Adressen
        device_dict = asdict(self.device)
        device_dict['controller_address'] = f"0x{self.device.controller_address:02X}"
        device_dict['radio_address'] = f"0x{self.device.radio_address:02X}"

        config_dict = {
            'usb': asdict(self.usb),
            'api': {
                'port': self.api.port,
                'health_check_enabled': self.api.health_check_enabled,
                'enable_https': self.api.enable_https,
                'cert_file': self.api.cert_file,
                'key_file': self.api.key_file,
                'log_level': self.api.log_level.value,
            },
            'wavelog': asdict(self.wavelog),
            'secret_provider': asdict(self.secret_provider),
            'device': device_dict,
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
            api_data = data['api'].copy()
            api_data.pop('host', None)  # Legacy-Feld aus älteren config.json ignorieren.
            if 'log_level' in api_data and isinstance(api_data['log_level'], str):
                api_data['log_level'] = LogLevel(api_data['log_level'])
            config.api = APIConfig(**api_data)
        if 'wavelog' in data:
            config.wavelog = WavelogConfig(**data['wavelog'])
        if 'secret_provider' in data:
            config.secret_provider = SecretProviderConfig(**data['secret_provider'])
        if 'device' in data:
            device_data = data['device'].copy()
            # Konvertiere Hex-Strings zu int
            if 'controller_address' in device_data:
                addr = device_data['controller_address']
                device_data['controller_address'] = int(addr, 16) if isinstance(addr, str) else addr
            if 'radio_address' in device_data:
                addr = device_data['radio_address']
                device_data['radio_address'] = int(addr, 16) if isinstance(addr, str) else addr
            config.device = DeviceConfig(**device_data)

        return config


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
        """
        manager = ConfigManager()
        default_path = Path('config.json')
        config_path = config_file or default_path

        manager._config = RigBridgeConfig.load(config_path)

        # API-Host kommt aus einer zentralen Quelle und ist nicht nutzerkonfigurierbar.
        manager._config.api.host = API_HOST_FIXED

        # Im Container bleibt der API-Port aus Sicherheits- und Mapping-Gründen fix.
        if is_running_in_container():
            manager._config.api.port = API_PORT_DEFAULT

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
