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
        self._awaiting_frequency_mode_pair = False

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
            previous_snapshot = self._snapshot
            next_snapshot = self._build_next_snapshot(
                frequency_hz=frequency_hz,
                mode=mode,
                power_w=power_w,
            )
            if next_snapshot is None:
                return False
            self._snapshot = next_snapshot

            updated_fields = []
            if previous_snapshot is None or previous_snapshot.frequency_hz != next_snapshot.frequency_hz:
                updated_fields.append('frequency_hz')
            if previous_snapshot is None or previous_snapshot.mode != next_snapshot.mode:
                updated_fields.append('mode')
            if previous_snapshot is None or previous_snapshot.power_w != next_snapshot.power_w:
                updated_fields.append('power_w')

            logger.debug(
                'Logbook cache updated '
                f'(sequence={next_snapshot.sequence_no}, '
                f'updated_fields={updated_fields}, '
                f'frequency_hz={next_snapshot.frequency_hz}, '
                f'mode={next_snapshot.mode}, '
                f'power_w={next_snapshot.power_w}, '
                f'awaiting_pair={self._awaiting_frequency_mode_pair})'
            )

            for runtime in self._connections.values():
                if not runtime.config.enabled:
                    continue
                if runtime.pending_task and not runtime.pending_task.done():
                    runtime.pending_task.cancel()
                runtime.pending_task = asyncio.create_task(
                    self._debounced_send(runtime.config.connection_id, next_snapshot.sequence_no)
                )

            return True

    def _build_next_snapshot(
        self,
        frequency_hz: Optional[int],
        mode: Optional[str],
        power_w: Optional[float],
    ) -> Optional[LogbookStatusSnapshot]:
        """Führt Voll- und Teilupdates zusammen, ohne alte Frequency/Mode-Paare zu vermischen."""

        old = self._snapshot
        normalized_mode = str(mode).upper() if mode is not None else None

        if frequency_hz is None and mode is None and power_w is None:
            return None

        if frequency_hz is None and mode is None:
            if old is None:
                return None
            next_frequency_hz = old.frequency_hz
            next_mode = old.mode
            next_power_w = power_w if power_w is not None else old.power_w
        else:
            if old and self._awaiting_frequency_mode_pair:
                base_frequency_hz = old.frequency_hz
                base_mode = old.mode
                base_power_w = old.power_w
            else:
                base_frequency_hz = None
                base_mode = None
                base_power_w = old.power_w if old else None

            next_frequency_hz = frequency_hz if frequency_hz is not None else base_frequency_hz
            next_mode = normalized_mode if normalized_mode is not None else base_mode
            next_power_w = power_w if power_w is not None else base_power_w

        if old and (
            old.frequency_hz == next_frequency_hz
            and old.mode == next_mode
            and old.power_w == next_power_w
        ):
            # Coalescing: identische Daten nicht erneut schedulen.
            return None

        self._awaiting_frequency_mode_pair = next_frequency_hz is None or next_mode is None

        return LogbookStatusSnapshot(
            frequency_hz=next_frequency_hz,
            mode=next_mode,
            power_w=next_power_w,
            last_update_ts=monotonic(),
            sequence_no=1 if old is None else old.sequence_no + 1,
        )

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
        if snapshot is None or snapshot.frequency_hz is None or snapshot.mode is None:
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

            if current.frequency_hz is None or current.mode is None:
                self._snapshot = LogbookStatusSnapshot(
                    frequency_hz=None,
                    mode=None,
                    power_w=current.power_w,
                    last_update_ts=monotonic(),
                    sequence_no=current.sequence_no,
                )
                self._awaiting_frequency_mode_pair = False
                logger.debug(
                    'Incomplete logbook status discarded after debounce '
                    f'(sequence={current.sequence_no}, '
                    f'frequency_hz={current.frequency_hz}, '
                    f'mode={current.mode}, '
                    f'power_w={current.power_w}, '
                    f'debounce_seconds={debounce_seconds})'
                )
                return

            logger.debug(
                'Sending debounced logbook status '
                f'(connection_id={connection_id}, '
                f'sequence={current.sequence_no}, '
                f'frequency_hz={current.frequency_hz}, '
                f'mode={current.mode}, '
                f'power_w={current.power_w}, '
                f'debounce_seconds={debounce_seconds})'
            )

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
                self._awaiting_frequency_mode_pair = False
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
            'awaiting_frequency_mode_pair': self._awaiting_frequency_mode_pair,
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
