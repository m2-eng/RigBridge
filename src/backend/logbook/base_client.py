"""Basisklasse fuer Logbook-Clients."""

from abc import ABC, abstractmethod

from .models import LogbookStatusSnapshot


class BaseLogbookClient(ABC):
    """Abstrakte Basisklasse fuer konkrete Logbook-Adapter."""

    @abstractmethod
    async def send_status(self, snapshot: LogbookStatusSnapshot) -> bool:
        """Sendet einen Snapshot an ein Logbuch."""

    async def close(self) -> None:
        """Optionales Cleanup fuer abgeleitete Klassen."""
        return None
