from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.core.exceptions import AppError


class SettingsEncryptionNotConfiguredError(AppError):
    status_code = 500


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().settings_encryption_key
    if not key:
        raise SettingsEncryptionNotConfiguredError(
            "SETTINGS_ENCRYPTION_KEY manquante dans .env — nécessaire pour stocker une clé API "
            "saisie depuis l'onglet Paramètres. Générer une clé : "
            "python -c \"from cryptography.fernet import Fernet; "
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        # Ex: SETTINGS_ENCRYPTION_KEY a changé depuis l'écriture — mieux vaut un message clair
        # qu'une erreur cryptique remontant du client LLM au moment de l'appeler.
        raise SettingsEncryptionNotConfiguredError(
            "Impossible de déchiffrer la clé API stockée — SETTINGS_ENCRYPTION_KEY a-t-elle "
            "changé depuis la sauvegarde ? Ressaisir la clé depuis l'onglet Paramètres."
        ) from exc
