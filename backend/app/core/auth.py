
import secrets
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from backend.app.core.config import settings

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    """
    Dependency that validates the presence and value of the X-API-Key header.
    Fail-closed: If settings.API_KEY is unset or empty, it rejects all requests
    with a 401 Unauthorized status (safer for production).
    """
    if not settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is not configured on the server."
        )
    if not api_key or not secrets.compare_digest(api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header"
        )
    return api_key
