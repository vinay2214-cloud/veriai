"""Feedback endpoint.
Stores human feedback and triggers weight recalibration when needed.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from ..models import FeedbackEntry, FeedbackResponse
from ..services.feedback_service import store_feedback, get_feedback_history
from ..services.training_service import check_retrain_trigger, train_model

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(entry: FeedbackEntry, background_tasks: BackgroundTasks):
    """Store feedback and optionally trigger retraining."""
    try:
        await store_feedback(entry.audit_id, entry.correct, entry.bias_flag, entry.notes or "")

        # Non-blocking async feedback loop trigger
        should_retrain = await check_retrain_trigger()
        if should_retrain:
            background_tasks.add_task(train_model)
    except Exception:
        logger.exception("Failed to store feedback for %s", entry.audit_id)
        raise HTTPException(status_code=503, detail="Unable to record feedback right now.")

    status = "received"
    return FeedbackResponse(status=status)


@router.get("/feedback/history")
async def feedback_history():
    """Return recent feedback entries."""
    try:
        return await get_feedback_history()
    except Exception:
        logger.exception("Failed to load feedback history")
        return []
