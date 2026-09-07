from fastapi import APIRouter, HTTPException, status

from backend.app.api.schemas import LoginRequest, LoginResponse
from backend.app.auth.security import authenticate, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    user = authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user)
    return LoginResponse(access_token=token, role=user.role.value, username=user.username)
