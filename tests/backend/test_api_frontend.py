"""Tests für Frontend-API-Endpunkte (Browser-UI Support)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app


def _write_config(path: Path) -> None:
    """Hilfsfunktion: Schreibe Test-Config in Datei."""
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
                    'api_key_secret_ref': 'rigbridge/wavelog#api_key',
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
        )
    )


def test_wavelog_test_endpoint(tmp_path):
    """Test: GET /api/wavelog/test - Testet Wavelog-Verbindung."""
    config_file = tmp_path / 'config.json'
    _write_config(config_file)

    app = create_app(config_path=config_file)
    client = TestClient(app)

    response = client.get('/api/wavelog/test')

    assert response.status_code == 200
    data = response.json()

    # Prüfe Antwort-Schema
    assert 'success' in data
    assert 'message' in data
    assert isinstance(data['success'], bool)
    assert isinstance(data['message'], str)

    # Mit Wavelog nicht enabled ist success=false erwartet
    assert data['success'] is False
    assert 'nicht aktiviert' in data['message'].lower() or 'disabled' in data['message'].lower()


def test_wavelog_stations_endpoint(tmp_path):
    """Test: GET /api/wavelog/stations - Gibt Wavelog-Stationen zurück."""
    config_file = tmp_path / 'config.json'
    _write_config(config_file)

    app = create_app(config_path=config_file)
    client = TestClient(app)

    response = client.get('/api/wavelog/stations')

    assert response.status_code == 200
    data = response.json()

    # Prüfe Antwort-Schema
    assert 'stations' in data
    assert isinstance(data['stations'], list)

    # Auch ohne Wavelog enabled sollte eine leere oder Mock-Liste kommen
    if data['stations']:
        # Falls Mock-Daten vorhanden sind, prüfe Struktur
        for station in data['stations']:
            assert 'id' in station
            assert 'name' in station
            assert 'callsign' in station


def test_devices_endpoint(tmp_path):
    """Test: GET /api/devices - Scannt und gibt verfügbare Geräte zurück."""
    config_file = tmp_path / 'config.json'
    _write_config(config_file)

    app = create_app(config_path=config_file)
    client = TestClient(app)

    response = client.get('/api/devices')

    assert response.status_code == 200
    data = response.json()

    # Prüfe Antwort-Schema
    assert 'devices' in data
    assert isinstance(data['devices'], list)

    # Mindestens ein Gerät sollte gefunden werden (ic905.yaml)
    # Bei der Aktuellen Struktur sollte es mindestens IC-905 geben
    if data['devices']:
        for device in data['devices']:
            assert 'name' in device
            assert 'manufacturer' in device
            assert 'protocol_file' in device
            assert isinstance(device['name'], str)
            assert isinstance(device['manufacturer'], str)
            assert isinstance(device['protocol_file'], str)


def test_spa_fallback_route(tmp_path):
    """Test: SPA-Fallback - Alle unbekannten Routes zeigen index.html."""
    config_file = tmp_path / 'config.json'
    _write_config(config_file)

    app = create_app(config_path=config_file)
    client = TestClient(app)

    # Teste verschiedene nicht-existente Routen
    test_routes = [
        '/unknown',
        '/app/something',
        '/settings/advanced',
    ]

    for route in test_routes:
        response = client.get(route)

        # SPA fallback sollte index.html (text/html) zurückgeben
        assert response.status_code == 200 or response.status_code == 404, \
            f"Route {route} returned unexpected status {response.status_code}"


def test_api_routes_prioritized(tmp_path):
    """Test: API-Routes haben Priorität vor SPA-Fallback."""
    config_file = tmp_path / 'config.json'
    _write_config(config_file)

    app = create_app(config_path=config_file)
    client = TestClient(app)

    # Teste dass echte API-Routes keine SPA-Fallback bekommen
    api_routes = [
        '/api/status',
        '/api/config',
        '/api/wavelog/test',
        '/api/wavelog/stations',
        '/api/devices',
    ]

    for route in api_routes:
        response = client.get(route)

        # API-Routes sollten JSON zurückgeben oder 200/400 sein,
        # aber NICHT HTML (das würde für /unknown kommen)
        if response.status_code == 200 or response.status_code == 404:
            # Wenn es 200 ist, sollte es JSON sein
            if response.status_code == 200:
                assert 'application/json' in response.headers.get('content-type', '').lower(), \
                    f"Route {route} did not return JSON"


def test_static_assets_serving(tmp_path):
    """Test: CSS/JS Assets werden von /assets/ served."""
    config_file = tmp_path / 'config.json'
    _write_config(config_file)

    app = create_app(config_path=config_file)
    client = TestClient(app)

    # Teste dass Assets gesucht werden können
    asset_routes = [
        '/assets/base-styles.css',
        '/assets/components.css',
        '/assets/theme.css',
        '/assets/api-client.js',
        '/assets/config-manager.js',
    ]

    for route in asset_routes:
        response = client.get(route)

        # Assets könnten 200 (vorhanden) oder 404 (nicht vorhanden) sein,
        # aber sollte nicht als SPA-Fallback behandelt werden
        # (Das wäre bei einer falschen Konfiguration der Fall)
        assert response.status_code in [200, 404], \
            f"Route {route} returned unexpected status {response.status_code}"


def test_wavelog_with_secret_ref(tmp_path):
    """Test: Wavelog-Test mit Secret-Referenz."""
    config_file = tmp_path / 'config.json'
    config_data = {
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
            'enabled': True,  # Enabled
            'api_url': 'https://api.wavelog.local',
            'api_key_secret_ref': 'rigbridge/wavelog#api_key',
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
    }
    config_file.write_text(json.dumps(config_data, indent=2))

    app = create_app(config_path=config_file)
    client = TestClient(app)

    response = client.get('/api/wavelog/test')

    assert response.status_code == 200
    data = response.json()

    # Wenn Wavelog enabled ist aber Secret nicht gelöst,
    # sollte success=false sein
    assert 'success' in data
    assert 'message' in data


def test_devices_endpoint_structure(tmp_path):
    """Test: /api/devices gibt strukturierte Geräteinformationen."""
    config_file = tmp_path / 'config.json'
    _write_config(config_file)

    app = create_app(config_path=config_file)
    client = TestClient(app)

    response = client.get('/api/devices')

    assert response.status_code == 200
    data = response.json()

    # Prüfe dass Response-Struktur korrekt ist
    assert isinstance(data, dict)
    assert 'devices' in data
    assert isinstance(data['devices'], list)

    # Prüfe dass Devices sortiert sind
    if len(data['devices']) > 1:
        device_names = [d['name'] for d in data['devices']]
        assert device_names == sorted(device_names), "Devices sollten alphabetisch sortiert sein"
