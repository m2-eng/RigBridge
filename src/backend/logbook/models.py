"""Modelle fuer die Logbook-Integration."""

from dataclasses import dataclass
from typing import Optional


MIN_DEBOUNCE_SECONDS = 1
MAX_DEBOUNCE_SECONDS = 5


@dataclass
class LogbookStatusSnapshot:
    """Status-Snapshot fuer den Versand an Logbuecher."""

    frequency_hz: Optional[int]
    mode: Optional[str]
    power_w: Optional[float]
    last_update_ts: float
    sequence_no: int


@dataclass
class LogbookConnectionConfig:
    """Konfiguration einer Logbook-Verbindung."""

    connection_id: str
    connection_type: str
    enabled: bool = True
    debounce_seconds: int = MIN_DEBOUNCE_SECONDS

    def normalized_debounce(self) -> int:
        """Begrenzt debounce auf den erlaubten Bereich [1, 5] Sekunden."""

        if self.debounce_seconds < MIN_DEBOUNCE_SECONDS:
            return MIN_DEBOUNCE_SECONDS
        if self.debounce_seconds > MAX_DEBOUNCE_SECONDS:
            return MAX_DEBOUNCE_SECONDS
        return self.debounce_seconds
