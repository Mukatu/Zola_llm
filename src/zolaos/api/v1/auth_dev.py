"""Auto-login de développement (jeton local sans identifiants).

Évite d'avoir à coller un jeton à la main en local : le frontend appelle
``/v1/auth/dev-token`` s'il n'a pas de jeton (ou après expiration) et l'app
« se connecte » seule. **Désactivé hors dev** (404 en staging/prod) : là,
l'authentification passe par un vrai flux de connexion.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zolaos.core.security import create_access_token
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import User
from zolaos.db.session import get_session

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/dev-token", summary="Jeton de dev (auto-login local) — 404 hors dev")
async def dev_token(
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if settings.APP_ENV != "dev":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    user = (
        (await session.execute(select(User).where(User.is_active.is_(True)).limit(1)))
        .scalars()
        .first()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="no_active_user"
        )
    token = create_access_token(
        str(user.id), settings=settings, extra_claims={"scopes": ["commons:curate"]}
    )
    return {"token": token, "user": user.email}
