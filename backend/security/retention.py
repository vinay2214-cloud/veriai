"""
Retention manager stub for hackathon.
Production: APScheduler daily job deletes datasets past retention_until.
"""
import logging

logger = logging.getLogger(__name__)


def start_retention_scheduler():
    logger.info("[VeriAI] Retention scheduler: disabled in hackathon mode.")
    return None


def lazy_cleanup():
    return {"checked": 0, "deleted": 0}
