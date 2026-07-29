"""Application À CHAUD de l'entitlement (révocation sans redémarrage).

Couvre :
- EntitlementState : enforcement off → None ; JWT valide → jeu effectif ; absent →
  fail-closed frozenset() ; refresh() recharge le fichier et signale le changement.
- require_module (garde runtime) : 404 si le module n'est pas dans l'état courant,
  passe si couvert / si enforcement off / si aucun état.
- Bout en bout via l'app : GET /v1/box/entitlement puis révocation (fichier retiré)
  + POST /v1/box/entitlement/refresh → le jeu autorisé tombe à vide (à chaud).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from zolaos.api.entitlement_gate import require_module
from zolaos.core.settings import Settings
from zolaos.licensing import EntitlementState
from zolaos.licensing.entitlement import Entitlement, sign_entitlement

# --- Paire de clés dédiée -----------------------------------------------------
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIV = _key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()
_PUB = (
    _key.public_key()
    .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    .decode()
)


def _token(tier: str, modules: list[str] | None = None) -> str:
    now = datetime.now(UTC)
    ent = Entitlement(
        tenant_id="acme",
        tier=tier,
        modules=modules or [],
        license_id="lic-" + tier,
        issued_at=now,
        expires_at=now + timedelta(days=365),
    )
    return sign_entitlement(ent, private_key_pem=_PRIV)


def _settings(*, file: Path | None = None, jwt: str = "", enforced: bool = True) -> Settings:
    return Settings(
        ZOLAOS_PROFILE="box",
        POSTGRES_PASSWORD_APP="x",
        POSTGRES_PASSWORD_MIGRATIONS="x",
        JWT_SECRET="x" * 32,
        ENTITLEMENT_ENFORCED=enforced,
        ENTITLEMENT_PUBLIC_KEY=_PUB,
        ENTITLEMENT_LICENSE_FILE=str(file) if file else "",
        ENTITLEMENT_LICENSE_JWT=jwt,
    )


# ----------------------------------------------------------------------------
# EntitlementState
# ----------------------------------------------------------------------------
def test_state_enforcement_off_allows_all() -> None:
    st = EntitlementState.from_settings(_settings(enforced=False))
    assert st.allowed is None
    assert st.is_allowed("cyber") is True


def test_state_valid_jwt_resolves_effective_modules() -> None:
    st = EntitlementState.from_settings(_settings(jwt=_token("business", ["cyber"])))
    assert st.allowed == frozenset({"erp", "sirh", "bi", "crm", "marketing", "cyber"})
    assert st.is_allowed("cyber") is True
    assert st.is_allowed("fintech") is False


def test_state_missing_license_fail_closed() -> None:
    st = EntitlementState.from_settings(_settings())  # enforced, ni jwt ni fichier
    assert st.allowed == frozenset()
    assert st.is_allowed("erp") is False


def test_state_refresh_picks_up_file_changes(tmp_path: Path) -> None:
    lic = tmp_path / "license.jwt"
    lic.write_text(_token("business", ["cyber"]), encoding="utf-8")
    settings = _settings(file=lic)
    st = EntitlementState.from_settings(settings)
    assert "cyber" in st.allowed

    # Révocation : fichier retiré → refresh signale un changement, fail-closed.
    lic.unlink()
    assert st.refresh() is True
    assert st.allowed == frozenset()

    # Nouvelle licence réduite → refresh reflète le nouveau jeu.
    lic.write_text(_token("starter"), encoding="utf-8")
    assert st.refresh() is True
    assert st.allowed == frozenset({"erp"})

    # Ré-appliquer la même licence → aucun changement.
    assert st.refresh() is False


# ----------------------------------------------------------------------------
# Garde runtime require_module (mini-app, sans DB)
# ----------------------------------------------------------------------------
def _gate_app() -> FastAPI:
    app = FastAPI()

    @app.get("/cyber", dependencies=[Depends(require_module("cyber"))])
    def _cyber() -> dict:
        return {"ok": True}

    @app.get("/fintech", dependencies=[Depends(require_module("fintech"))])
    def _fintech() -> dict:
        return {"ok": True}

    return app


def test_require_module_404_when_not_allowed() -> None:
    app = _gate_app()
    app.state.entitlement_state = EntitlementState(frozenset({"cyber"}))
    c = TestClient(app)
    assert c.get("/cyber").status_code == 200  # couvert
    r = c.get("/fintech")
    assert r.status_code == 404  # non couvert → 404
    assert r.json()["detail"] == "module_not_licensed"


def test_require_module_passes_when_enforcement_off_or_no_state() -> None:
    app = _gate_app()
    c = TestClient(app)
    # Enforcement off (allowed=None) → tout passe.
    app.state.entitlement_state = EntitlementState(None)
    assert c.get("/fintech").status_code == 200
    # Aucun état (profil non-box) → passe aussi.
    app.state.entitlement_state = None
    assert c.get("/fintech").status_code == 200


# ----------------------------------------------------------------------------
# Bout en bout : révocation à chaud via l'endpoint box
# ----------------------------------------------------------------------------
def test_hot_revocation_via_box_endpoint(tmp_path: Path) -> None:
    # conftest neutralise require_box_auth/csrf → l'endpoint est joignable en test.
    from zolaos.api.main import create_app

    lic = tmp_path / "license.jwt"
    lic.write_text(_token("starter"), encoding="utf-8")
    app = create_app(settings=_settings(file=lic))
    with TestClient(app) as c:
        # État initial : seul erp couvert.
        r0 = c.get("/v1/box/entitlement")
        assert r0.status_code == 200, r0.text
        assert r0.json() == {"enforced": True, "allowed_modules": ["erp"]}

        # Révocation : le fichier disparaît → refresh à chaud → plus aucun module.
        lic.unlink()
        r1 = c.post("/v1/box/entitlement/refresh")
        assert r1.status_code == 200, r1.text
        body = r1.json()
        assert body["changed"] is True
        assert body["allowed_modules"] == []

        # Confirmé par un GET ultérieur (l'état vivant a changé, sans redémarrage).
        assert c.get("/v1/box/entitlement").json()["allowed_modules"] == []
