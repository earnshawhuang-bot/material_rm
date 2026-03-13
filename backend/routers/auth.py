"""Auth API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from .. import schemas
from ..auth import create_access_token, get_current_user
from ..services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> schemas.Token:
    """Validate username/password and return JWT token."""
    # 协议上要求 form-data 字段名：username/password
    token = auth_service.login(form_data.username, form_data.password)
    return schemas.Token(access_token=token, token_type="bearer")


@router.get("/me", response_model=schemas.UserInfo)
def me(current_user=Depends(get_current_user)):
    """Return current user info from token."""
    return current_user
