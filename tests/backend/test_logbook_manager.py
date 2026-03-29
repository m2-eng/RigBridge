"""Tests fuer den LogbookManager (Debounce, Coalescing, Sequence-Schutz)."""

import asyncio

import pytest

from src.backend.logbook import LogbookConnectionConfig, LogbookManager
from src.backend.logbook.base_client import BaseLogbookClient
from src.backend.logbook.models import LogbookStatusSnapshot


class _FakeClient(BaseLogbookClient):
    def __init__(self) -> None:
        self.sent: list[LogbookStatusSnapshot] = []

    async def send_status(self, snapshot: LogbookStatusSnapshot) -> bool:
        self.sent.append(snapshot)
        return True


@pytest.mark.asyncio
async def test_debounce_is_clamped_to_minimum_one_second() -> None:
    manager = LogbookManager()
    client = _FakeClient()

    await manager.register_connection(
        LogbookConnectionConfig(
            connection_id='wl',
            connection_type='wavelog',
            debounce_seconds=0,
        ),
        client,
    )

    changed = await manager.update_cached_status(7100000, 'usb', 50.0)
    assert changed is True

    await asyncio.sleep(0.2)
    assert len(client.sent) == 0

    await asyncio.sleep(1.0)
    assert len(client.sent) == 1


@pytest.mark.asyncio
async def test_coalescing_skips_identical_updates() -> None:
    manager = LogbookManager()
    client = _FakeClient()

    await manager.register_connection(
        LogbookConnectionConfig(
            connection_id='wl',
            connection_type='wavelog',
            debounce_seconds=1,
        ),
        client,
    )

    first = await manager.update_cached_status(7150000, 'cw', 10.0)
    second = await manager.update_cached_status(7150000, 'cw', 10.0)

    assert first is True
    assert second is False

    await asyncio.sleep(1.1)
    assert len(client.sent) == 1
    assert client.sent[0].sequence_no == 1


@pytest.mark.asyncio
async def test_sequence_protection_sends_only_latest_snapshot() -> None:
    manager = LogbookManager()
    client = _FakeClient()

    await manager.register_connection(
        LogbookConnectionConfig(
            connection_id='wl',
            connection_type='wavelog',
            debounce_seconds=1,
        ),
        client,
    )

    first = await manager.update_cached_status(14000000, 'usb', 20.0)
    assert first is True
    await asyncio.sleep(0.2)

    second = await manager.update_cached_status(14001000, 'usb', 20.0)
    assert second is True

    await asyncio.sleep(1.1)

    assert len(client.sent) == 1
    assert client.sent[0].frequency_hz == 14001000
    assert client.sent[0].sequence_no == 2


@pytest.mark.asyncio
async def test_partial_frequency_and_mode_are_combined_within_debounce_window() -> None:
    manager = LogbookManager()
    client = _FakeClient()

    await manager.register_connection(
        LogbookConnectionConfig(
            connection_id='wl',
            connection_type='wavelog',
            debounce_seconds=1,
        ),
        client,
    )

    initial = await manager.update_cached_status(144000000, 'fm', 5.0)
    assert initial is True
    await asyncio.sleep(1.1)
    assert len(client.sent) == 1

    changed_frequency = await manager.update_cached_status(144100000, None, None)
    assert changed_frequency is True
    await asyncio.sleep(0.2)

    changed_mode = await manager.update_cached_status(None, 'am', None)
    assert changed_mode is True

    await asyncio.sleep(1.1)

    assert len(client.sent) == 2
    assert client.sent[1].frequency_hz == 144100000
    assert client.sent[1].mode == 'AM'


@pytest.mark.asyncio
async def test_incomplete_frequency_mode_pair_is_discarded_after_debounce() -> None:
    manager = LogbookManager()
    client = _FakeClient()

    await manager.register_connection(
        LogbookConnectionConfig(
            connection_id='wl',
            connection_type='wavelog',
            debounce_seconds=1,
        ),
        client,
    )

    initial = await manager.update_cached_status(430000000, 'fm', 10.0)
    assert initial is True
    await asyncio.sleep(1.1)
    assert len(client.sent) == 1

    changed_frequency = await manager.update_cached_status(431000000, None, None)
    assert changed_frequency is True

    await asyncio.sleep(1.1)

    status = manager.get_status()
    assert len(client.sent) == 1
    assert status['cached_frequency_hz'] is None
    assert status['cached_mode'] is None
    assert status['awaiting_frequency_mode_pair'] is False

    changed_mode = await manager.update_cached_status(None, 'usb', None)
    assert changed_mode is True

    await asyncio.sleep(1.1)

    status = manager.get_status()
    assert len(client.sent) == 1
    assert status['cached_frequency_hz'] is None
    assert status['cached_mode'] is None
