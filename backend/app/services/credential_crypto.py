import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings

_DEV_ENCRYPTION_SEED = b"neutron-development-credential-key"

_warned_dev_key = False


def _fernet() -> Fernet:
    global _warned_dev_key
    key = settings.credential_encryption_key
    if key:
        return Fernet(key.encode("utf-8"))
    if not _warned_dev_key:
        import logging
        logging.getLogger("uvicorn.error").warning(
            "CREDENTIAL_ENCRYPTION_KEY is not set — using insecure development key. "
            "Set CREDENTIAL_ENCRYPTION_KEY in production."
        )
        _warned_dev_key = True
    digest = hashlib.sha256(_DEV_ENCRYPTION_SEED).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")