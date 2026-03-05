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
from collections import deque


class InMemoryLogHandler(logging.Handler):
    """Handler, der die letzten Logs im Memory speichert (max. 1000 Zeilen)."""

    MAX_LOGS = 1000
    # Regex zum Entfernen von ANSI-Escape-Sequenzen
    ANSI_ESCAPE_PATTERN = re.compile(r'\033\[[0-9;]*m')

    def __init__(self):
        super().__init__()
        self.log_records = deque(maxlen=self.MAX_LOGS)
        # Erstelle einen Dummy-Formatter für formatTime()
        self._formatter = logging.Formatter()

    @staticmethod
    def _remove_ansi_codes(text: str) -> str:
        """Entfernt ANSI-Escape-Codes aus einem String."""
        return InMemoryLogHandler.ANSI_ESCAPE_PATTERN.sub('', text)

    def emit(self, record: logging.LogRecord):
        """Speichert Log-Eintrag im Memory mit formatiertem Original-Zeitstempel."""
        try:
            # Formatiere den Zeitstempel wie in StructuredFormatter: YYYY-MM-DD HH:MM:SS.mmm
            dt_str = self._formatter.formatTime(record, "%Y-%m-%d %H:%M:%S")
            timestamp = f"{dt_str}.{int(record.msecs):03d}"

            # Speichere nur die rohe Nachricht, nicht die formatierte Ausgabe
            msg = record.getMessage()
            # Entferne ANSI-Farb-Codes falls vorhanden
            clean_msg = self._remove_ansi_codes(msg)
            self.log_records.append({
                'timestamp': timestamp,
                'level': record.levelname,
                'name': record.name,
                'message': clean_msg,
            })
        except Exception:
            self.handleError(record)

    def get_logs(
        self,
        limit: Optional[int] = None,
        level: Optional[str] = None,
        newest_first: bool = False,
    ) -> list:
        """
        Gibt die letzten Logs zurück.

        Args:
            limit: Max. Anzahl der Logs (Standard: alle)
            level: Optionales Log-Level (z.B. 'INFO', 'ERROR')
            newest_first: Wenn True, neueste Eintraege zuerst

        Returns:
            Liste von Log-Dicts mit timestamp, level, name, message
        """
        logs = list(self.log_records)

        if level:
            wanted = level.upper()
            logs = [entry for entry in logs if entry.get('level', '').upper() == wanted]

        if limit:
            logs = logs[-limit:]

        if newest_first:
            logs.reverse()

        return logs


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
        self._memory_handler = InMemoryLogHandler()
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

            # Memory-Handler (für Web-UI Logs)
            instance._memory_handler.setLevel(instance.default_level)
            instance._memory_handler.setFormatter(StructuredFormatter())
            instance._memory_handler.addFilter(instance._redaction_filter)
            logger.addHandler(instance._memory_handler)

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

    @staticmethod
    def get_memory_handler() -> InMemoryLogHandler:
        """Gibt den globalen InMemoryLogHandler für Web-UI Logs zurück."""
        instance = RigBridgeLogger()
        return instance._memory_handler

    @staticmethod
    def get_logs(
        limit: Optional[int] = None,
        level: Optional[str] = None,
        newest_first: bool = False,
    ) -> list:
        """
        Gibt die zuletzt gesammelten Logs zurück.

        Args:
            limit: Max. Anzahl der Logs (Standard: alle)
            level: Optionales Log-Level (z.B. 'INFO', 'ERROR')
            newest_first: Wenn True, neueste Eintraege zuerst

        Returns:
            Liste von Log-Dicts mit timestamp, level, name, message
        """
        instance = RigBridgeLogger()
        return instance._memory_handler.get_logs(
            limit=limit,
            level=level,
            newest_first=newest_first,
        )
