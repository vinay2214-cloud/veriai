import os
import logging

logger = logging.getLogger(__name__)


def verify_security_config() -> None:
    """
    Hackathon mode: lightweight startup check.
    Full security (encryption, JWT, retention) planned for v2.
    """
    datasets_dir = os.environ.get("DATASETS_DIR", "data/datasets")
    try:
        os.makedirs(datasets_dir, exist_ok=True)
    except OSError as exc:
        fallback_dir = "/tmp/datasets"
        logger.warning(
            "Failed to create datasets directory at %s (%s). Falling back to %s.",
            datasets_dir, exc, fallback_dir
        )
        os.makedirs(fallback_dir, exist_ok=True)
        # Also update the storage module's ROOT if it was already resolved
        try:
            from . import storage
            storage.DATASETS_ROOT = Path(fallback_dir)
        except Exception:
            pass
    logger.info("[VeriAI] Startup check passed. Running in hackathon mode.")

    logger.info("[VeriAI] Security note: Full AES-256-GCM encryption, JWT auth,")
    logger.info("[VeriAI]   and tamper-evident audit logs planned for production.")
