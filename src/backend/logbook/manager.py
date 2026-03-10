"""Logbook-Manager mit Debounce, Coalescing und Sequence-Schutz."""

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Any, Awaitable, Callable, Dict, Optional

from ..config.logger import RigBridgeLogger
from .base_client import BaseLogbookClient
from .models import LogbookConnectionConfig, LogbookStatusSnapshot


logger = RigBridgeLogger.get_logger(__name__)


@dataclass
class _ConnectionRuntime:
    config: LogbookConnectionConfig
    client: BaseLogbookClient
    pending_task: Optional[asyncio.Task] = None
    last_sent_sequence: int = 0
    last_send_ts: Optional[float] = None
    last_error: Optional[str] = None


class LogbookManager:
    """Verwaltet mehrere Logbook-Verbindungen und koordiniert den Versand."""

    def __init__(self) -> None:
        self._connections: Dict[str, _ConnectionRuntime] = {}
        self._snapshot: Optional[LogbookStatusSnapshot] = None
        self._lock = asyncio.Lock()
        self._poll_task: Optional[asyncio.Task] = None
        self._running = False

    async def register_connection(
        self,
        config: LogbookConnectionConfig,
        client: BaseLogbookClient,
    ) -> None:
        """Registriert eine Verbindung inklusive Client-Adapter."""

        async with self._lock:
            existing = self._connections.get(config.connection_id)
            if existing and existing.pending_task and not existing.pending_task.done():
                existing.pending_task.cancel()
            if existing:
                await existing.client.close()

            self._connections[config.connection_id] = _ConnectionRuntime(
                config=config,
                client=client,
            )

    async def clear_connections(self) -> None:
        """Entfernt alle Verbindungen und stoppt laufende Jobs."""

        async with self._lock:
            runtimes = list(self._connections.values())
            self._connections.clear()

        for runtime in runtimes:
            if runtime.pending_task and not runtime.pending_task.done():
                runtime.pending_task.cancel()
            await runtime.client.close()

    async def start_polling(
        self,
        status_provider: Callable[[], Awaitable[Dict[str, Any]]],
        interval_seconds: int,
    ) -> None:
        """Startet Polling fuer Radio-Status."""

        if self._running:
            return

        self._running = True
        interval_seconds = max(1, int(interval_seconds))

        async def _loop() -> None:
            while self._running:
                try:
                    status = await status_provider()
                    await self.update_cached_status(
                        frequency_hz=status.get('frequency_hz'),
                        mode=status.get('mode'),
                        power_w=status.get('power_w'),
                    )
                except Exception as exc:
                    logger.debug(f'Logbook polling failed: {exc}')
                await asyncio.sleep(interval_seconds)

        self._poll_task = asyncio.create_task(_loop())

    async def stop_polling(self) -> None:
        """Stoppt den Polling-Task."""

        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

    async def update_cached_status(
        self,
        frequency_hz: Optional[int],
        mode: Optional[str],
        power_w: Optional[float],
    ) -> bool:
        """Schreibt Status in Cache; coalesced bei unveraenderten Werten."""

        async with self._lock:
            if frequency_hz is None or mode is None:
                return False

            normalized_mode = str(mode).upper()
            old = self._snapshot

            if old and (
                old.frequency_hz == frequency_hz
                and old.mode == normalized_mode
                and old.power_w == power_w
            ):
                # Coalescing: identische Daten nicht erneut schedulen.
                return False

            next_sequence = 1 if old is None else old.sequence_no + 1
            now = monotonic()
            self._snapshot = LogbookStatusSnapshot(
                frequency_hz=frequency_hz,
                mode=normalized_mode,
                power_w=power_w,
                last_update_ts=now,
                sequence_no=next_sequence,
            )

            for runtime in self._connections.values():
                if not runtime.config.enabled:
                    continue
                if runtime.pending_task and not runtime.pending_task.done():
                    runtime.pending_task.cancel()
                runtime.pending_task = asyncio.create_task(
                    self._debounced_send(runtime.config.connection_id, next_sequence)
                )

            return True

    async def flush_now(self) -> Dict[str, bool]:
        """Sendet den aktuell gecachten Status sofort an alle aktiven Verbindungen."""

        async with self._lock:
            snapshot = self._snapshot
            ids = [
                connection_id
                for connection_id, runtime in self._connections.items()
                if runtime.config.enabled
            ]

        results: Dict[str, bool] = {}
        if snapshot is None:
            return results

        for connection_id in ids:
            results[connection_id] = await self._send_snapshot(connection_id, snapshot)
        return results

    async def _debounced_send(self, connection_id: str, sequence_no: int) -> None:
        runtime = self._connections.get(connection_id)
        if not runtime:
            return

        debounce_seconds = runtime.config.normalized_debounce()
        await asyncio.sleep(debounce_seconds)

        async with self._lock:
            current = self._snapshot
            if current is None:
                return

            # Idempotenz/Ordering: nur senden, wenn die geplante Sequence noch aktuell ist.
            if current.sequence_no != sequence_no:
                return

            if runtime.last_sent_sequence >= sequence_no:
                return

            # Extra Guard: wirklich stabil fuer debounce_seconds unveraendert.
            if (monotonic() - current.last_update_ts) < debounce_seconds:
                return

        await self._send_snapshot(connection_id, current)

    async def _send_snapshot(self, connection_id: str, snapshot: LogbookStatusSnapshot) -> bool:
        runtime = self._connections.get(connection_id)
        if not runtime:
            return False

        try:
            success = await runtime.client.send_status(snapshot)
            if success:
                runtime.last_sent_sequence = snapshot.sequence_no
                runtime.last_send_ts = monotonic()
                runtime.last_error = None
            else:
                runtime.last_error = 'send_failed'
            return success
        except Exception as exc:
            runtime.last_error = str(exc)
            return False

    def get_status(self) -> Dict[str, Any]:
        """Liefert den Manager-Status fuer API/Diagnose."""

        snapshot = self._snapshot
        send_timestamps = [
            runtime.last_send_ts
            for runtime in self._connections.values()
            if runtime.last_send_ts is not None
        ]
        return {
            'running': self._running,
            'cached_sequence': snapshot.sequence_no if snapshot else 0,
            'cached_frequency_hz': snapshot.frequency_hz if snapshot else None,
            'cached_mode': snapshot.mode if snapshot else None,
            'cached_power_w': snapshot.power_w if snapshot else None,
            'last_send_ts': max(send_timestamps) if send_timestamps else None,
            'connections': {
                connection_id: {
                    'enabled': runtime.config.enabled,
                    'type': runtime.config.connection_type,
                    'debounce_seconds': runtime.config.normalized_debounce(),
                    'last_sent_sequence': runtime.last_sent_sequence,
                    'last_send_ts': runtime.last_send_ts,
                    'last_error': runtime.last_error,
                }
                for connection_id, runtime in self._connections.items()
            },
        }
