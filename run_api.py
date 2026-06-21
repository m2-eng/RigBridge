#!/usr/bin/env python3
"""
RigBridge API Startup-Script.

Startet den FastAPI-Server anhand der config.json Konfiguration.
HTTPS: Bei enable_https=True wird automatisch ein selbst-signiertes Zertifikat
erzeugt (in /tmp/), wenn kein cert_file/key_file konfiguriert ist.
"""

import sys
import argparse
import cProfile
import ipaddress
import socket
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.backend.config import RigBridgeLogger, ConfigManager
from src.backend.api import create_app


def _generate_self_signed_cert(cert_path: Path, key_path: Path) -> None:
    """
    Erzeugt ein selbst-signiertes TLS-Zertifikat mit SAN für localhost und
    alle lokalen IP-Adressen. Gültig für 10 Jahre.
    Erfordert das `cryptography`-Paket (bereits in requirements.txt).
    """
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # SAN: localhost + 127.0.0.1 + ::1 + alle lokalen IPs
    san_names = [
        x509.DNSName('localhost'),
        x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')),
        x509.IPAddress(ipaddress.IPv6Address('::1')),
    ]
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        san_names.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
        san_names.append(x509.DNSName(hostname))
    except Exception:
        pass

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'RigBridge'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'RigBridge'),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)


def _resolve_ssl_files(config, logger) -> tuple[Path | None, Path | None]:
    """
    Ermittelt Pfade zu Zertifikat und Schlüssel.
    Generiert automatisch ein selbst-signiertes Zertifikat, wenn nötig.
    """
    if not config.api.enable_https:
        return None, None

    if config.api.cert_file and config.api.key_file:
        cert = Path(config.api.cert_file)
        key = Path(config.api.key_file)
        if not cert.exists():
            logger.error(f'TLS-Zertifikat nicht gefunden: {cert}')
            return None, None
        if not key.exists():
            logger.error(f'TLS-Schlüssel nicht gefunden: {key}')
            return None, None
        logger.info(f'TLS: Verwende konfiguriertes Zertifikat: {cert}')
        return cert, key

    # Automatisch selbst-signiertes Zertifikat erzeugen
    cert = Path('/tmp/rigbridge-ssl.crt')
    key = Path('/tmp/rigbridge-ssl.key')
    if not cert.exists() or not key.exists():
        logger.info('TLS: Erzeuge selbst-signiertes Zertifikat …')
        try:
            _generate_self_signed_cert(cert, key)
            logger.info(f'TLS: Zertifikat erzeugt: {cert}')
        except Exception as e:
            logger.error(f'TLS: Zertifikat konnte nicht erzeugt werden: {e}')
            return None, None
    else:
        logger.info(f'TLS: Verwende vorhandenes Auto-Zertifikat: {cert}')
    return cert, key


def _run_server(app, config, logger, ssl_certfile=None, ssl_keyfile=None) -> int:
    """Startet den Uvicorn-Server und gibt einen Exit-Code zurück."""
    scheme = 'https' if ssl_certfile else 'http'
    try:
        import uvicorn
        uvicorn.run(
            app,
            host=config.api.host,
            port=config.api.port,
            reload=False,
            workers=1,
            log_config=None,  # Verwende vorkonfigurierte Logger, nicht uvicorn defaults
            ssl_certfile=str(ssl_certfile) if ssl_certfile else None,
            ssl_keyfile=str(ssl_keyfile) if ssl_keyfile else None,
        )
    except ImportError:
        logger.error('uvicorn nicht installiert!')
        logger.error('Installiere mit: pip install uvicorn')
        return 1
    except KeyboardInterrupt:
        logger.info('Server heruntergefahren')
        return 0
    except Exception as e:
        logger.error(f'Fehler beim Server-Start: {e}')
        import traceback
        traceback.print_exc()
        return 1

    return 0


def main(profile_enabled: bool = False, profile_output: str = 'profile.out'):
    """Starte den API-Server basierend auf config.json."""
    config_file = Path('config.json')

    # Konfiguriere Logger
    logger = RigBridgeLogger.get_logger('rigbridge.startup')

    # Verifiziere Config
    if not config_file.exists():
        logger.error(f"config.json nicht gefunden: {config_file.absolute()}")
        return 1

    # Laden Sie die Konfiguration
    try:
        config = ConfigManager.initialize(config_file)
        logger.info(f"Konfiguration geladen: {config_file.absolute()}")
        logger.info(f"Device: {config.device.name}")
        logger.info(f"USB-Port: {config.usb.port} @ {config.usb.baud_rate} baud")
    except Exception as e:
        logger.error(f"Fehler beim Laden der Konfiguration: {e}")
        return 1

    # TLS/SSL auflösen
    ssl_certfile, ssl_keyfile = _resolve_ssl_files(config, logger)
    scheme = 'https' if ssl_certfile else 'http'

    # Erstelle App
    try:
        app = create_app(config_path=config_file)
        logger.info("FastAPI App erstellt")
    except Exception as e:
        logger.error(f"Fehler beim Erstellen der App: {e}")
        return 1

    # Starte uvicorn
    logger.info(f"Starte Server auf {scheme}://{config.api.host}:{config.api.port}")
    logger.info(f"Swagger UI: {scheme}://{config.api.host}:{config.api.port}/api/docs")
    if ssl_certfile:
        logger.info('TLS: HTTPS aktiv (selbst-signiertes Zertifikat – Browser-Warnung akzeptieren)')

    if not profile_enabled:
        return _run_server(app, config, logger, ssl_certfile, ssl_keyfile)

    profiler = cProfile.Profile()
    logger.info(f'cProfile aktiviert, Ausgabe nach: {profile_output}')
    try:
        profiler.enable()
        return _run_server(app, config, logger, ssl_certfile, ssl_keyfile)
    finally:
        profiler.disable()
        profiler.dump_stats(profile_output)
        logger.info(f'cProfile-Daten geschrieben: {profile_output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Startet die RigBridge API')
    parser.add_argument(
        '--profile',
        action='store_true',
        help='Aktiviert cProfile fuer den API-Prozess',
    )
    parser.add_argument(
        '--profile-output',
        default='profile.out',
        help='Ausgabedatei fuer cProfile-Stats (Standard: profile.out)',
    )
    args = parser.parse_args()

    sys.exit(main(profile_enabled=args.profile, profile_output=args.profile_output))
