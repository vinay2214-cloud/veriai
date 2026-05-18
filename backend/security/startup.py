import os
import logging

logger = logging.getLogger(__name__)


def verify_security_config() -> None:
    """
    Hackathon mode: lightweight startup check.
    Full security (encryption, JWT, retention) planned for v2.
    """
    datasets_dir = os.environ.get("DATASETS_DIR", "data/datasets")
    os.makedirs(datasets_dir, exist_ok=True)
    logger.info("[VeriAI] Startup check passed. Running in hackathon mode.")
    logger.info("[VeriAI] Security note: Full AES-256-GCM encryption, JWT auth,")
    logger.info("[VeriAI]   and tamper-evident audit logs planned for production.")
