#!/usr/bin/env python3
"""Generate base64 secrets for VeriAI environment variables."""
from __future__ import annotations

import base64
import secrets


def _b64_secret(num_bytes: int) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(num_bytes)).decode("utf-8")


def main() -> None:
    print("# WARNING: NEVER commit .env or secrets to git.")
    print("# Copy these into your local/deployment environment variables.\n")
    print(f"VERIAI_MASTER_KEY={_b64_secret(64)}")  # 64-byte secret
    print(f"JWT_SECRET={_b64_secret(32)}")         # 32-byte secret
    print(f"DB_ENCRYPTION_KEY={_b64_secret(32)}")  # 32-byte secret


if __name__ == "__main__":
    main()

