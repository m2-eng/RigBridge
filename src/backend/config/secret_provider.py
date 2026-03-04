"""Secret-Provider Abstraktion für RigBridge."""

from dataclasses import dataclass
from typing import Protocol
from pathlib import Path

import requests

from .settings import RigBridgeConfig


class SecretProviderError(Exception):
    """Basisklasse für Secret-Provider-Fehler."""


class SecretProviderUnavailableError(SecretProviderError):
    """Secret-Provider ist nicht erreichbar oder nicht nutzbar."""


class SecretNotFoundError(SecretProviderError):
    """Secret-Referenz konnte nicht aufgelöst werden."""


class SecretProvider(Protocol):
    """Interface für Secret-Provider."""

    def get_secret(self, secret_ref: str) -> str:
        """Löst eine Secret-Referenz auf und liefert den Secret-Wert."""


@dataclass
class VaultSecretProvider:
    """HashiCorp Vault Implementierung für SecretProvider."""

    base_url: str
    mount: str
    token_file: str
    timeout_seconds: float = 3.0

    def _read_token(self) -> str:
        token_path = Path(self.token_file)
        if not token_path.exists():
            raise SecretProviderUnavailableError(
                f'Vault token file not found: {token_path}'
            )
        token = token_path.read_text(encoding='utf-8').strip()
        if not token:
            raise SecretProviderUnavailableError('Vault token is empty')
        return token

    def get_secret(self, secret_ref: str) -> str:
        """
        Secret-Referenzformat: "path/to/secret#key".

        Beispiel: "rigbridge/wavelog#api_key"
        """
        if '#' not in secret_ref:
            raise SecretNotFoundError(
                'Invalid secret_ref format. Expected "path#key".'
            )

        secret_path, secret_key = secret_ref.split('#', 1)
        if not secret_path or not secret_key:
            raise SecretNotFoundError(
                'Invalid secret_ref format. Expected "path#key".'
            )

        token = self._read_token()
        url = f'{self.base_url.rstrip("/")}/v1/{self.mount}/data/{secret_path.lstrip("/")}'

        try:
            response = requests.get(
                url,
                headers={'X-Vault-Token': token},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise SecretProviderUnavailableError(
                f'Failed to reach Vault: {exc}'
            ) from exc

        if response.status_code == 404:
            raise SecretNotFoundError(f'Secret path not found: {secret_path}')
        if response.status_code >= 400:
            raise SecretProviderUnavailableError(
                f'Vault request failed with status {response.status_code}'
            )

        payload = response.json()
        value = (
            payload.get('data', {})
            .get('data', {})
            .get(secret_key)
        )
        if not isinstance(value, str) or value == '':
            raise SecretNotFoundError(
                f'Secret key not found or empty: {secret_key}'
            )

        return value


def create_secret_provider(config: RigBridgeConfig) -> SecretProvider:
    """Erstellt den konfigurierten Secret-Provider."""
    provider_name = config.secret_provider.provider.lower()

    if provider_name == 'vault':
        return VaultSecretProvider(
            base_url=config.secret_provider.vault_url,
            mount=config.secret_provider.vault_mount,
            token_file=config.secret_provider.token_file,
        )

    raise SecretProviderUnavailableError(
        f'Unsupported secret provider: {config.secret_provider.provider}'
    )
