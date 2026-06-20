"""Configuration centralisée — chargée depuis l'environnement via Pydantic."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings de l'application ZolaOS.

    Toutes les valeurs proviennent d'un `.env` ou de l'environnement. Aucune
    valeur sensible ne doit avoir de défaut en clair.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ===== Application =====
    APP_NAME: str = "zolaos"
    APP_ENV: Literal["dev", "staging", "prod"] = "dev"
    # Profil de déploiement (Polaris addendum V3) :
    #   - "box"   : déploiement chez le client (Zolabox) — restreint
    #   - "cortex": déploiement chez le cabinet conseil (Zolacortex) — élargi
    # Défaut "box" = principe du moindre privilège.
    ZOLAOS_PROFILE: Literal["box", "cortex"] = "box"
    APP_HOST: str = "0.0.0.0"  # noqa: S104  (bind sur toutes interfaces volontaire en conteneur)
    APP_PORT: int = 8000
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"
    DEFAULT_COUNTRY: str = Field(default="cg", pattern=r"^[a-z]{2}$")

    # ===== PostgreSQL =====
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "zolaos"
    POSTGRES_USER_APP: str = "zolaos_app"
    POSTGRES_PASSWORD_APP: SecretStr = SecretStr("")
    POSTGRES_USER_MIGRATIONS: str = "zolaos_migrator"
    POSTGRES_PASSWORD_MIGRATIONS: SecretStr = SecretStr("")

    # ===== Redis =====
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr = SecretStr("")
    REDIS_DB: int = 0

    # ===== MinIO =====
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ROOT_USER: str = "zolaos_minio"
    MINIO_ROOT_PASSWORD: SecretStr = SecretStr("")
    MINIO_BUCKET_DEFAULT: str = "zolaos"
    MINIO_SECURE: bool = False

    # ===== LLM local =====
    # Backend par défaut : llama.cpp (serveur OpenAI-compatible /v1/chat/completions).
    # Alternative production : ollama (route /api/chat) sur serveur Linux + ROCm/CUDA.
    LLM_BACKEND: Literal["llamacpp", "ollama"] = "llamacpp"
    # Routeur + brigade tournent sur le modèle léger (8B). Port 11434 par défaut.
    LLM_HOST_ROUTER: str = "http://host.docker.internal:11434"
    LLM_MODEL_ROUTER: str = "llama-3-8b"
    LLM_MODEL_BRIGADE: str = "llama-3-8b"
    # Méta-agent Planning tourne sur le modèle lourd (70B). Port 11435 par défaut
    # (lancé par un second processus llama-server quand on l'active).
    LLM_HOST_CORE: str = "http://host.docker.internal:11435"
    LLM_MODEL_CORE: str = "llama-3-70b"
    LLM_TIMEOUT_SECONDS: int = 120
    # Auth Bearer si on met un reverse-proxy (Caddy) devant llama-server.
    LLM_API_KEY: SecretStr = SecretStr("")

    # ===== Fallback API externe (DÉSACTIVÉ par défaut) =====
    ENABLE_EXTERNAL_FALLBACK: bool = False
    ANTHROPIC_API_KEY: SecretStr = SecretStr("")
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    EXTERNAL_FALLBACK_BUDGET_MONTHLY_USD: float = 0.0

    # ===== Sécurité =====
    JWT_SECRET: SecretStr = SecretStr("")
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    API_KEY_PEPPER: SecretStr = SecretStr("")
    ENCRYPTION_KEY_AUDIT: SecretStr = SecretStr("")

    # ===== Connector Framework (Phase 4 §2.4) =====
    # Délai d'attente par défaut (s) injecté aux connecteurs HTTP si non précisé
    # dans leur config. Les connecteurs vivent dans les deux profils (box/cortex).
    CONNECTOR_DEFAULT_TIMEOUT_SECONDS: int = 30

    # ===== Embeddings =====
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_DEVICE: Literal["cpu", "cuda"] = "cpu"

    # ===== Observabilité =====
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_SERVICE_NAME: str = "zolaos"

    # ===== CORS =====
    CORS_ORIGINS: str = "http://localhost:3000"

    # ===== Rate limiting =====
    RATE_LIMIT_PER_MINUTE: int = 60

    # ===== Computed =====
    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_dsn_app(self) -> str:
        pwd = self.POSTGRES_PASSWORD_APP.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER_APP}:{pwd}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_dsn_migrations(self) -> str:
        pwd = self.POSTGRES_PASSWORD_MIGRATIONS.get_secret_value()
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER_MIGRATIONS}:{pwd}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retourne l'instance unique de Settings (cache process-wide)."""
    return Settings()
