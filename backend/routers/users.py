"""User management APIs (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_admin

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/")
def list_users(current_admin=Depends(require_admin)):
    """P0 仅保留接口占位，后续补齐用户列表增删改。"""
    return {
        "message": "用户管理功能待补齐",
        "admin": current_admin.username,
    }
