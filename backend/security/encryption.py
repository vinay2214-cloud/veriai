"""AES-256-GCM encryption utilities for dataset-at-rest protection."""
from __future__ import annotations

import base64
import json
import os
from typing import Dict

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _b64_decode(value: str) -> bytes:
    """Decode URL-safe/base64 input with permissive padding handling."""
    raw = value.strip().encode("utf-8")
    raw += b"=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(raw)


class DatasetEncryptor:
    """Encrypt/decrypt dataset payloads with AAD ownership binding."""

    def __init__(self, master_key: str | None = None) -> None:
        secret = (master_key or os.getenv("VERIAI_MASTER_KEY") or os.getenv("DB_ENCRYPTION_KEY") or "").strip()
        if not secret:
            raise RuntimeError("VERIAI_MASTER_KEY (or DB_ENCRYPTION_KEY) is required for encryption.")

        try:
            self._master_key = _b64_decode(secret)
        except Exception:
            self._master_key = secret.encode("utf-8")

        if len(self._master_key) < 32:
            raise RuntimeError("Encryption master key material is too short (need >= 32 bytes after decode).")

        self._iterations = 310_000

    def _derive_key(self, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self._iterations,
        )
        return kdf.derive(self._master_key)

    @staticmethod
    def _aad_bytes(user_id: str, dataset_id: str, sha256: str, timestamp: str) -> bytes:
        aad_payload = {
            "user_id": str(user_id),
            "dataset_id": str(dataset_id),
            "sha256": str(sha256),
            "timestamp": str(timestamp),
        }
        return json.dumps(aad_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def encrypt(
        self,
        plaintext: bytes,
        *,
        user_id: str,
        dataset_id: str,
        sha256: str,
        timestamp: str,
    ) -> Dict[str, str]:
        """Encrypt bytes and bind ciphertext to user/dataset identity via AAD."""
        salt = os.urandom(32)  # fresh per-file salt
        nonce = os.urandom(12)  # AES-GCM nonce
        key = self._derive_key(salt)
        aad = self._aad_bytes(user_id=user_id, dataset_id=dataset_id, sha256=sha256, timestamp=timestamp)

        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
        return {
            "ciphertext_b64": base64.urlsafe_b64encode(ciphertext).decode("utf-8"),
            "salt_b64": base64.urlsafe_b64encode(salt).decode("utf-8"),
            "nonce_b64": base64.urlsafe_b64encode(nonce).decode("utf-8"),
        }

    def decrypt(
        self,
        *,
        ciphertext_b64: str,
        salt_b64: str,
        nonce_b64: str,
        user_id: str,
        dataset_id: str,
        sha256: str,
        timestamp: str,
    ) -> bytes:
        """Decrypt bytes and enforce AAD ownership/identity checks."""
        ciphertext = _b64_decode(ciphertext_b64)
        salt = _b64_decode(salt_b64)
        nonce = _b64_decode(nonce_b64)

        key = self._derive_key(salt)
        aad = self._aad_bytes(user_id=user_id, dataset_id=dataset_id, sha256=sha256, timestamp=timestamp)

        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, aad)

