"""Tests für /api/config Endpunkte und Fehlerformat."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                'usb': {
                    'port': 'COM4',
                    'baud_rate': 115200,
                    'data_bits': 8,
                    'stop_bits': 1,
                    'parity': 'N',
                    'timeout': 1.0,
                    'reconnect_interval': 5,
                },
                'api': {
                    'host': '127.0.0.1',
                    'port': 8080,
                    'enable_https': False,
                    'cert_file': None,
                    'key_file': None,
                    'log_level': 'INFO',
                },
                'wavelog': {
                    'enabled': False,
                    'api_url': 'https://api.wavelog.local',
                    'api_key_or_secret_ref': 'rigbridge/wavelog#api_key',
                    'polling_interval': 5,
                },
                'secret_provider': {
                    'provider': 'vault',
                    'vault_url': 'http://127.0.0.1:8200',
                    'vault_mount': 'secret',
                    'token_file': '/run/secrets/vault_token',
                },
                'device': {
                    'name': 'Icom IC-905',
                    'manufacturer': 'icom',
                    'protocol_file': 'ic905',
                },
            },
            indent=2,
        ),
        encoding='utf-8',
    )


def test_get_config_masks_secret_ref(tmp_path: Path):
    config_path = tmp_path / 'config.json'
    _write_config(config_path)

    app = create_app(config_path=config_path)
    client = TestClient(app)

    response = client.get('/api/config')

    assert response.status_code == 200
    payload = response.json()
    assert payload['wavelog']['api_key_or_secret_ref'] == '***'


def test_put_config_persists_changes(tmp_path: Path):
    config_path = tmp_path / 'config.json'
    _write_config(config_path)

    app = create_app(config_path=config_path)
    client = TestClient(app)

    response = client.put(
        '/api/config',
        json={
            'api': {'port': 8090, 'log_level': 'DEBUG'},
            'wavelog': {'api_key_or_secret_ref': 'rigbridge/wavelog#new_api_key'},
        },
    )

    assert response.status_code == 200
    assert response.json()['success'] is True

    updated = json.loads(config_path.read_text(encoding='utf-8'))
    assert updated['api']['port'] == 8090
    assert updated['api']['log_level'] == 'DEBUG'
    assert updated['wavelog']['api_key_or_secret_ref'] == 'rigbridge/wavelog#new_api_key'


def test_put_config_invalid_log_level_returns_error_contract(tmp_path: Path):
    config_path = tmp_path / 'config.json'
    _write_config(config_path)

    app = create_app(config_path=config_path)
    client = TestClient(app)

    response = client.put('/api/config', json={'api': {'log_level': 'TRACE'}})

    assert response.status_code == 422
    payload = response.json()
    assert payload['error'] is True
    assert payload['code'] == 'HTTP_422'
    assert 'Invalid log_level' in payload['message']


def test_status_reports_degraded_mode_on_secret_provider_failure(tmp_path: Path):
    config_path = tmp_path / 'config.json'
    _write_config(config_path)

    # Wavelog aktivieren und absichtlich ungültigen Token-Pfad setzen
    config_data = json.loads(config_path.read_text(encoding='utf-8'))
    config_data['wavelog']['enabled'] = True
    config_data['secret_provider']['token_file'] = str(tmp_path / 'missing_vault_token')
    config_path.write_text(json.dumps(config_data, indent=2), encoding='utf-8')

    app = create_app(config_path=config_path)
    client = TestClient(app)

    response = client.get('/api/status')

    assert response.status_code == 200
    payload = response.json()
    assert payload['degraded_mode'] is True
    assert payload['secret_provider_available'] is False
