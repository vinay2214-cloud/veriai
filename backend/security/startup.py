"""Startup security checks with demo-mode tolerance."""
from __future__ import annotations

import os
from pathlib import Path


REQUIRED_SECRETS = ("VERIAI_MASTER_KEY", "JWT_SECRET", "DB_ENCRYPTION_KEY")


def _is_demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "true").strip().lower() == "true"


def verify_security_config() -> None:
    """Validate required secrets and initialize secure dataset directory.

    Behavior:
    - DEMO_MODE=true: warn only if secrets/dir setup fail.
    - DEMO_MODE=false: raise RuntimeError on missing secrets or setup failure.
    """
    demo_mode = _is_demo_mode()
    missing = [key for key in REQUIRED_SECRETS if not os.getenv(key, "").strip()]

    if missing:
        msg = (
            f"Missing required security env vars: {', '.join(missing)}. "
            "Set these in environment/.env before private operations."
        )
        if demo_mode:
            print(f"WARNING: {msg}")
        else:
            raise RuntimeError(msg)

    datasets_dir = Path(os.getenv("DATASETS_DIR", "/data/datasets"))
    try:
        datasets_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(datasets_dir, 0o700)
    except Exception as exc:
        # Fallback to /tmp on read-only filesystems
        fallback = Path("/tmp/datasets")
        try:
            fallback.mkdir(parents=True, exist_ok=True)
            os.environ["DATASETS_DIR"] = str(fallback)
            msg = f"Using fallback datasets dir {fallback} (original {datasets_dir} failed: {exc})"
        except Exception:
            msg = f"Failed to initialize secure datasets directory at {datasets_dir}: {exc}"
        if demo_mode:
            print(f"WARNING: {msg}")
        else:
            raise RuntimeError(msg) from exc

