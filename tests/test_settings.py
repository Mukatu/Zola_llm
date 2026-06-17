"""Tests des settings — vérifie que les défauts sont sûrs."""

from __future__ import annotations

from zolaos.core.settings import Settings


def test_default_country_is_cg() -> None:
    s = Settings()
    assert s.DEFAULT_COUNTRY == "cg"


def test_external_fallback_default_off() -> None:
    s = Settings()
    assert s.ENABLE_EXTERNAL_FALLBACK is False
    assert s.EXTERNAL_FALLBACK_BUDGET_MONTHLY_USD == 0.0


def test_dsn_app_is_constructed() -> None:
    s = Settings(
        POSTGRES_HOST="db.local",
        POSTGRES_PORT=5433,
        POSTGRES_DB="mydb",
        POSTGRES_USER_APP="usr",
        POSTGRES_PASSWORD_APP="pwd",  # noqa: S106
    )
    assert s.postgres_dsn_app == "postgresql+asyncpg://usr:pwd@db.local:5433/mydb"


def test_cors_origin_list_parsing() -> None:
    s = Settings(CORS_ORIGINS="http://a.com, http://b.com ,http://c.com")
    assert s.cors_origin_list == ["http://a.com", "http://b.com", "http://c.com"]
