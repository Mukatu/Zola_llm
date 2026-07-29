"""Refresh de licence par le tunnel — résolution cortex, réponse du canal, application box.

Couvre :
- active_license_for_tenant (DB) : active / revoked / expired / none / la plus récente gagne
- TunnelChannel.serve : un `license_pull` déclenche une trame `license` (statut + jeton)
- _apply_license (box) : écrit sur active, retire sur revoked/expired, no-op sur none/sans fichier
- _refresh_loop (box) : désactivé sans intervalle ; émet un `license_pull` sinon
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from zolaos.db.models import LicenseGrant, Tenant
from zolaos.db.session import get_session_factory, reset_engine_cache
from zolaos.licensing.delivery import active_license_for_tenant
from zolaos.tunnel.agent import _apply_license, _refresh_loop
from zolaos.tunnel.channel import TunnelChannel


@pytest.fixture(autouse=True)
def _reset_db_engine_cache():
    reset_engine_cache()
    yield
    reset_engine_cache()


# ----------------------------------------------------------------------------
# Helpers DB
# ----------------------------------------------------------------------------
async def _mk_client_tenant(session) -> Tenant:
    t = Tenant(name=f"client-{uuid.uuid4().hex[:6]}", tenant_type="client", country="cg")
    session.add(t)
    await session.flush()
    return t


def _grant(
    tenant_id: uuid.UUID,
    *,
    token: str = "a.b.c",  # noqa: S107 (jeton factice de test, pas un secret)
    revoked: bool = False,
    expired: bool = False,
    created_at: datetime | None = None,
) -> LicenseGrant:
    now = datetime.now(UTC)
    return LicenseGrant(
        tenant_id=tenant_id,
        license_id="lic-" + uuid.uuid4().hex[:10],
        tier="business",
        modules=["cyber"],
        token=token,
        issued_at=now - timedelta(days=1),
        # expired : dans le passé mais toujours > issued_at (contrainte de fenêtre).
        expires_at=(now - timedelta(hours=1)) if expired else (now + timedelta(days=30)),
        revoked_at=now if revoked else None,
        created_at=created_at or now,
    )


async def _cleanup(tenant_id: uuid.UUID) -> None:
    async with get_session_factory()() as s:
        await s.execute(
            text("DELETE FROM core.license_grants WHERE tenant_id = :t"), {"t": str(tenant_id)}
        )
        await s.execute(text("DELETE FROM core.tenants WHERE id = :t"), {"t": str(tenant_id)})
        await s.commit()


# ----------------------------------------------------------------------------
# active_license_for_tenant (résolution DB, côté cortex)
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_active_license_returns_token() -> None:
    async with get_session_factory()() as s:
        t = await _mk_client_tenant(s)
        s.add(_grant(t.id, token="tok-active"))
        await s.commit()
        tid = t.id
    try:
        assert await active_license_for_tenant(str(tid)) == ("active", "tok-active")
    finally:
        await _cleanup(tid)


@pytest.mark.asyncio
async def test_revoked_and_expired_carry_no_token() -> None:
    async with get_session_factory()() as s:
        t_rev = await _mk_client_tenant(s)
        t_exp = await _mk_client_tenant(s)
        s.add(_grant(t_rev.id, revoked=True))
        s.add(_grant(t_exp.id, expired=True))
        await s.commit()
        rev_id, exp_id = t_rev.id, t_exp.id
    try:
        assert await active_license_for_tenant(str(rev_id)) == ("revoked", None)
        assert await active_license_for_tenant(str(exp_id)) == ("expired", None)
    finally:
        await _cleanup(rev_id)
        await _cleanup(exp_id)


@pytest.mark.asyncio
async def test_no_grant_returns_none() -> None:
    async with get_session_factory()() as s:
        t = await _mk_client_tenant(s)
        await s.commit()
        tid = t.id
    try:
        assert await active_license_for_tenant(str(tid)) == ("none", None)
    finally:
        await _cleanup(tid)


@pytest.mark.asyncio
async def test_most_recent_grant_wins() -> None:
    # Renouvellement : la plus récente porte l'état courant, même si une ancienne
    # est encore « active » (en pratique elle serait révoquée ; on teste l'ordre).
    now = datetime.now(UTC)
    async with get_session_factory()() as s:
        t = await _mk_client_tenant(s)
        s.add(_grant(t.id, token="ancienne", created_at=now - timedelta(minutes=10)))
        s.add(_grant(t.id, token="recente", revoked=True, created_at=now))
        await s.commit()
        tid = t.id
    try:
        assert await active_license_for_tenant(str(tid)) == ("revoked", None)
    finally:
        await _cleanup(tid)


@pytest.mark.asyncio
async def test_bad_tenant_id_returns_none() -> None:
    assert await active_license_for_tenant("pas-un-uuid") == ("none", None)


# ----------------------------------------------------------------------------
# TunnelChannel : un license_pull déclenche une trame license
# ----------------------------------------------------------------------------
class _FakeWS:
    """WebSocket factice : débite des trames entrantes, capture les sortantes."""

    def __init__(self, incoming: list[str]) -> None:
        self.incoming = list(incoming)
        self.sent: list[str] = []

    async def receive_text(self) -> str:
        if self.incoming:
            return self.incoming.pop(0)
        raise RuntimeError("stop")  # termine serve() (géré par l'appelant)

    async def send_text(self, msg: str) -> None:
        self.sent.append(msg)


@pytest.mark.asyncio
async def test_channel_replies_license_on_pull() -> None:
    async with get_session_factory()() as s:
        t = await _mk_client_tenant(s)
        s.add(_grant(t.id, token="tok-livre"))
        await s.commit()
        tid = t.id
    try:
        ws = _FakeWS([json.dumps({"type": "license_pull", "req_id": "r1"})])
        channel = TunnelChannel(str(tid), ws)
        with pytest.raises(RuntimeError):
            await channel.serve()
        frames = [json.loads(m) for m in ws.sent]
        lic = [f for f in frames if f.get("type") == "license"]
        assert len(lic) == 1
        assert lic[0]["status"] == "active"
        assert lic[0]["token"] == "tok-livre"
        assert lic[0]["req_id"] == "r1"
    finally:
        await _cleanup(tid)


# ----------------------------------------------------------------------------
# _apply_license (côté box, écriture fichier — sans DB ni réseau)
# ----------------------------------------------------------------------------
def _box_settings(tmp_path, *, file: str = "license.jwt", interval: float = 3600.0):
    return SimpleNamespace(
        ENTITLEMENT_LICENSE_FILE=str(tmp_path / file) if file else "",
        ENTITLEMENT_REFRESH_SECONDS=interval,
    )


def test_apply_license_writes_active(tmp_path) -> None:
    s = _box_settings(tmp_path)
    _apply_license(s, "active", "tok-123")
    assert (tmp_path / "license.jwt").read_text(encoding="utf-8") == "tok-123"


def test_apply_license_removes_on_revoked(tmp_path) -> None:
    p = tmp_path / "license.jwt"
    p.write_text("ancien", encoding="utf-8")
    _apply_license(_box_settings(tmp_path), "revoked", None)
    assert not p.exists()  # fail-closed au prochain redémarrage


def test_apply_license_removes_on_expired(tmp_path) -> None:
    p = tmp_path / "license.jwt"
    p.write_text("ancien", encoding="utf-8")
    _apply_license(_box_settings(tmp_path), "expired", None)
    assert not p.exists()


def test_apply_license_noop_on_none(tmp_path) -> None:
    p = tmp_path / "license.jwt"
    p.write_text("garder", encoding="utf-8")
    _apply_license(_box_settings(tmp_path), "none", None)
    assert p.read_text(encoding="utf-8") == "garder"  # jamais écrasé sur un cas vide


def test_apply_license_no_file_configured(tmp_path) -> None:
    # Aucun fichier cible → no-op silencieux (ne lève pas).
    _apply_license(_box_settings(tmp_path, file=""), "active", "tok")


# ----------------------------------------------------------------------------
# _refresh_loop (côté box)
# ----------------------------------------------------------------------------
class _SendWS:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, msg: str) -> None:
        self.sent.append(msg)


@pytest.mark.asyncio
async def test_refresh_loop_disabled_without_interval(tmp_path) -> None:
    ws = _SendWS()
    await _refresh_loop(ws, _box_settings(tmp_path, interval=0))
    assert ws.sent == []  # rend la main immédiatement, aucun pull


@pytest.mark.asyncio
async def test_refresh_loop_disabled_without_file(tmp_path) -> None:
    ws = _SendWS()
    await _refresh_loop(ws, _box_settings(tmp_path, file=""))
    assert ws.sent == []


@pytest.mark.asyncio
async def test_refresh_loop_emits_pull(tmp_path) -> None:
    ws = _SendWS()
    task = asyncio.create_task(_refresh_loop(ws, _box_settings(tmp_path, interval=0.01)))
    await asyncio.sleep(0.03)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    assert any(json.loads(m).get("type") == "license_pull" for m in ws.sent)
