from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.agent.session import session_key_manager

router = APIRouter()

class APIKeyRequest(BaseModel):
    api_key: str = Field(..., description="OpenRouter API Key")

class APIKeyStatusResponse(BaseModel):
    configured: bool

@router.post("/config/api-key", response_model=APIKeyStatusResponse)
async def set_api_key(req: APIKeyRequest):
    if not req.api_key or not req.api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API key is required."
        )

    is_valid, err_msg = await session_key_manager.validate_openrouter_key(req.api_key)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg or "OpenRouter API key is invalid or was rejected."
        )

    session_key_manager.set_api_key(req.api_key)
    return APIKeyStatusResponse(configured=True)

@router.get("/config/api-key/status", response_model=APIKeyStatusResponse)
def get_api_key_status():
    return APIKeyStatusResponse(configured=session_key_manager.is_configured())

@router.delete("/config/api-key", response_model=APIKeyStatusResponse)
def clear_api_key():
    session_key_manager.clear()
    return APIKeyStatusResponse(configured=False)
