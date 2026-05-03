"""Private dataset management endpoints (placeholder)."""
from fastapi import APIRouter, UploadFile, File, Depends
from ..security.auth import get_current_user

router = APIRouter()

# PRIVATE: AUTH REQUIRED
_DATASET_PLACEHOLDER = []


@router.post("/datasets/upload")
async def upload_private_dataset(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    return {
        "status": "placeholder",
        "message": "Private dataset upload endpoint scaffolded. Add auth + storage wiring next.",
        "filename": file.filename,
        "user": user,
    }


@router.get("/datasets/")
async def list_private_datasets(user: dict = Depends(get_current_user)):
    return {"status": "placeholder", "datasets": _DATASET_PLACEHOLDER, "user": user}
