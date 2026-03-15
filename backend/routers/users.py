"""User management APIs (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_password_hash, require_admin
from ..database import get_db

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/", response_model=schemas.UserListResponse)
def list_users(
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    """返回所有用户列表。"""
    users = db.query(models.SysUser).order_by(models.SysUser.id).all()
    return schemas.UserListResponse(items=users)


@router.post("/", response_model=schemas.UserInfo, status_code=status.HTTP_201_CREATED)
def create_user(
    body: schemas.UserCreateRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    """创建新用户（管理员操作）。"""
    existing = db.query(models.SysUser).filter_by(username=body.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户名 '{body.username}' 已存在",
        )

    user = models.SysUser(
        username=body.username,
        password_hash=get_password_hash(body.password),
        display_name=body.display_name,
        department=body.department,
        plant=body.plant,
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=schemas.UserInfo)
def update_user(
    user_id: int,
    body: schemas.UserUpdateRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    """更新用户信息（可选更新密码）。"""
    user = db.query(models.SysUser).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.department is not None:
        user.department = body.department
    if body.plant is not None:
        user.plant = body.plant
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = get_password_hash(body.password)

    db.commit()
    db.refresh(user)
    return user
