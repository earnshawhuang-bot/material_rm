"""Auth business logic used by routers."""

from __future__ import annotations

from datetime import timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .. import models
from ..auth import authenticate_user, create_access_token
from ..config import settings
from ..database import get_db


def login(username: str, password: str) -> str:
    """Authenticate user and return JWT."""
    db: Session = next(get_db())
    try:
        user = authenticate_user(db, username=username, password=password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )
        return create_access_token(
            subject=user.username,
            expires_delta=timedelta(hours=settings.access_token_expire_hours),
        )
    finally:
        db.close()
