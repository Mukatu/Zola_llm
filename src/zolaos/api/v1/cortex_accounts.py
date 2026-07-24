"""Cockpit cabinet — gestion des comptes utilisateurs (Zolacortex).

Réservé au profil **cortex** et au rôle **admin** (scope ``admin:users``). Permet à
l'exploitant du cabinet de provisionner et gérer les comptes : lister, créer,
activer/désactiver, changer le rôle, réinitialiser le mot de passe.

Sécurité : chaque mutation exige le jeton CSRF (double-submit) ; un admin ne peut
ni se désactiver ni se rétrograder lui-même (anti-auto-verrouillage) ; le mot de
passe n'est jamais renvoyé ni journalisé (seul un mot de passe temporaire généré
est affiché **une seule fois** à la création / réinitialisation).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.api.auth import Principal, require_admin
from zolaos.api.v1.auth import require_csrf
from zolaos.core.logging import get_logger
from zolaos.core.profiles import require_cortex
from zolaos.core.rbac import ROLE_ADMIN, ROLES, is_valid_role
from zolaos.core.security import hash_password
from zolaos.db.models import User
from zolaos.db.session import get_session

_log = get_logger("zolaos.api.v1.cortex_accounts")

router = APIRouter(
    prefix="/v1/cortex/accounts",
    tags=["cortex", "accounts"],
    dependencies=[Depends(require_cortex), Depends(require_admin)],
)

_MIN_PASSWORD_LEN = 10


def _generate_temp_password() -> str:
    return secrets.token_urlsafe(12)


class AccountOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    tenant_id: str | None
    is_active: bool
    created_at: datetime


def _to_out(user: User) -> AccountOut:
    return AccountOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    session: AsyncSession = Depends(get_session),
) -> list[AccountOut]:
    rows = (
        (await session.execute(select(User).order_by(User.created_at.desc()).limit(500)))
        .scalars()
        .all()
    )
    return [_to_out(u) for u in rows]


class CreateAccountRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    role: str = Field(description=f"Un de : {', '.join(ROLES)}")
    tenant_id: str | None = Field(default=None, max_length=64)
    # Optionnel : si absent, un mot de passe temporaire est généré et renvoyé une fois.
    password: str | None = Field(default=None, min_length=_MIN_PASSWORD_LEN, max_length=1024)


class CreateAccountResponse(BaseModel):
    account: AccountOut
    # Renseigné uniquement si le mot de passe a été généré côté serveur.
    temp_password: str | None = None


@router.post("", response_model=CreateAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: CreateAccountRequest,
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> CreateAccountResponse:
    if not is_valid_role(payload.role):
        raise HTTPException(status_code=422, detail=f"invalid_role: {payload.role}")

    email = payload.email.strip().lower()
    exists = (
        await session.execute(select(User.id).where(User.email == email))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_already_exists")

    temp_password = payload.password or _generate_temp_password()
    user = User(
        email=email,
        display_name=payload.display_name,
        password_hash=hash_password(temp_password),
        is_active=True,
        role=payload.role,
        tenant_id=payload.tenant_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    _log.info("cortex.account.created", extra={"user_id": str(user.id), "role": user.role})
    return CreateAccountResponse(
        account=_to_out(user),
        temp_password=None if payload.password else temp_password,
    )


class UpdateAccountRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = None
    tenant_id: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


async def _get_or_404(session: AsyncSession, account_id: uuid.UUID) -> User:
    user = await session.get(User, account_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account_not_found")
    return user


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: uuid.UUID,
    payload: UpdateAccountRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> AccountOut:
    user = await _get_or_404(session, account_id)

    # Anti-auto-verrouillage : un admin ne peut ni se désactiver ni se rétrograder.
    if user.id == principal.user_id:
        if payload.is_active is False:
            raise HTTPException(status_code=409, detail="cannot_deactivate_self")
        if payload.role is not None and payload.role != ROLE_ADMIN:
            raise HTTPException(status_code=409, detail="cannot_demote_self")

    if payload.role is not None:
        if not is_valid_role(payload.role):
            raise HTTPException(status_code=422, detail=f"invalid_role: {payload.role}")
        user.role = payload.role
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.tenant_id is not None:
        user.tenant_id = payload.tenant_id
    if payload.is_active is not None:
        user.is_active = payload.is_active

    await session.commit()
    await session.refresh(user)
    _log.info("cortex.account.updated", extra={"user_id": str(user.id)})
    return _to_out(user)


class ResetPasswordResponse(BaseModel):
    password: str


@router.post("/{account_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _csrf: None = Depends(require_csrf),
) -> ResetPasswordResponse:
    user = await _get_or_404(session, account_id)
    new_password = _generate_temp_password()
    user.password_hash = hash_password(new_password)
    await session.commit()
    _log.info("cortex.account.password_reset", extra={"user_id": str(user.id)})
    return ResetPasswordResponse(password=new_password)
