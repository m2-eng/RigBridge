"""
Zentralisiertes Logging-System für RigBridge.

Bietet ein einheitliches Format für strukturierte Log-Ausgaben
auf stdout und optional in Logdateien.
"""

import logging
import sys
import re
from typing import Optional
from pathlib import Path


class SecretRedactionFilter(logging.Filter):
    """Maskiert sensible Werte in Log-Nachrichten."""

    PATTERNS = [
        re.compile(r'(?i)(api[_-]?key\s*[=:]\s*)([^\s,;]+)'),
        re.compile(r'(?i)(token\s*[=:]\s*)([^\s,;]+)'),
        re.compile(r'(?i)(authorization\s*:\s*bearer\s+)([^\s,;]+)'),
        re.compile(r'(?i)(password\s*[=:]\s*)([^\s,;]+)'),
        re.compile(r'(?i)(secret\s*[=:]\s*)([^\s,;]+)'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        sanitized = message

        for pattern in self.PATTERNS:
            sanitized = pattern.sub(r'\1***', sanitized)

        if sanitized != message:
            record.msg = sanitized
            record.args = ()

        return True


class StructuredFormatter(logging.Formatter):
    """
    Formatter für strukturierte, maschinell lesbare Log-Ausgaben mit Farben.

    Format: [TIMESTAMP] [LEVEL] [MODULE] MESSAGE

    Farben je Level:
    - DEBUG: Lila/Magenta
    - INFO: Grün
    - WARNING: Orange/Gelb
    - ERROR: Rot
    """

    # ANSI-Farbcodes
    COLORS = {
        logging.DEBUG: '\033[95m',    # Magenta/Lila
        logging.INFO: '\033[92m',     # Grün
        logging.WARNING: '\033[93m',  # Gelb/Orange
        logging.ERROR: '\033[91m',    # Rot
        logging.CRITICAL: '\033[91m', # Rot
    }
    RESET = '\033[0m'
    TIMESTAMP_COLOR = '\033[96m'  # Cyan/Türkis

    def format(self, record: logging.LogRecord) -> str:
        """Formatiert Log-Eintrag nach einheitlichem Schema mit Farben und Millisekunden."""
        # Zeitstempel mit Millisekunden
        dt_str = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        timestamp = f"{dt_str}.{int(record.msecs):03d}"

        color = self.COLORS.get(record.levelno, '')

        return (
            f'{self.TIMESTAMP_COLOR}[{timestamp}]{self.RESET} '
            f'{color}[{record.levelname:8s}]{self.RESET} '
            f'[{record.name:<26s}] '
            f'{record.getMessage()}'
        )


class RigBridgeLogger:
    """Zentrale Logger-Verwaltung für RigBridge."""

    _instance: Optional['RigBridgeLogger'] = None
    _loggers: dict = {}

    def __new__(cls) -> 'RigBridgeLogger':
        """Singleton-Pattern für Logger-Verwaltung."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialisiert das Logger-System (einmalig)."""
        if self._initialized:
            return

        # Basis-Setup
        self.default_level = logging.INFO
        self.log_file: Optional[Path] = None
        self._redaction_filter = SecretRedactionFilter()
        self._initialized = True

    @staticmethod
    def get_logger(module_name: str) -> logging.Logger:
        """
        Gibt einen Logger für das angegebene Modul zurück.

        Args:
            module_name: Name des Moduls (z.B. 'src.backend.api.routes')

        Returns:
            Konfigurierter Logger für das Modul.
        """
        instance = RigBridgeLogger()

        if module_name not in instance._loggers:
            logger = logging.getLogger(module_name)
            logger.setLevel(instance.default_level)
            logger.propagate = False

            # StdOut-Handler
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setLevel(instance.default_level)
            stdout_handler.setFormatter(StructuredFormatter())
            stdout_handler.addFilter(instance._redaction_filter)
            logger.addHandler(stdout_handler)

            # Datei-Handler (optional)
            if instance.log_file:
                file_handler = logging.FileHandler(
                    instance.log_file, encoding='utf-8'
                )
                file_handler.setLevel(instance.default_level)
                file_handler.setFormatter(StructuredFormatter())
                file_handler.addFilter(instance._redaction_filter)
                logger.addHandler(file_handler)

            instance._loggers[module_name] = logger

        return instance._loggers[module_name]

    @staticmethod
    def configure(
        level: int = logging.INFO,
        log_file: Optional[str] = None,
    ) -> None:
        """
        Konfiguriert das globale Logger-System.

        Args:
            level: Log-Level (DEBUG, INFO, WARNING, ERROR)
            log_file: Optionaler Pfad zu Logdatei.
        """
        instance = RigBridgeLogger()
        instance.default_level = level
        instance.log_file = Path(log_file) if log_file else None

        # Alle bestehenden Logger aktualisieren
        for logger in instance._loggers.values():
            logger.setLevel(level)
            for handler in logger.handlers:
                handler.setLevel(level)

    @staticmethod
    def get_redaction_filter() -> SecretRedactionFilter:
        """Gibt den global verwendeten Secret-Redaction-Filter zurück."""
        instance = RigBridgeLogger()
        return instance._redaction_filter
