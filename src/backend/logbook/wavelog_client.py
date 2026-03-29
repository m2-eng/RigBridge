"""Wavelog-Adapter fuer den generischen Logbook-Manager."""

from .base_client import BaseLogbookClient
from .models import LogbookStatusSnapshot
from ..cat.cat_client import WavelogCatClient


class WavelogLogbookClient(BaseLogbookClient):
    """Adapter, der WavelogCatClient in das Logbook-Interface einpasst."""

    def __init__(self, cat_client: WavelogCatClient):
        self._cat_client = cat_client

    async def send_status(self, snapshot: LogbookStatusSnapshot) -> bool:
        if snapshot.frequency_hz is None or snapshot.mode is None:
            return False

        return await self._cat_client.send_radio_status(
            frequency_hz=snapshot.frequency_hz,
            mode=snapshot.mode,
            power_w=snapshot.power_w,
        )

    async def close(self) -> None:
        await self._cat_client.close()
