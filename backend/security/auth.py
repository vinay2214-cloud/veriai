import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer = HTTPBearer(auto_error=False)
DEMO_API_KEY = os.environ.get("DEMO_API_KEY", "veriai-demo-2026")


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    """
    Hackathon auth: simple API key check.
    Production: JWT with RS256, refresh tokens, revocation.
    """
    if not creds or creds.credentials != DEMO_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Use demo API key for hackathon testing.",
        )
    return {"user_id": "demo_user", "email": "demo@veriai.ai"}
