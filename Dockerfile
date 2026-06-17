# syntax=docker/dockerfile:1.7
# ===== Stage 1 : builder =====
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

# ----- torch CPU-only via constraint (économise ~3 Go de wheels NVIDIA) -----
# sentence-transformers tire torch ; la version par défaut sur Linux pull tout
# le toolchain CUDA (cudnn + cublas + cufft + triton + ...). On n'a pas de GPU
# NVIDIA dans le conteneur (l'inférence LLM tourne sur llama-server natif
# Windows avec Vulkan/Radeon 8060S), et bge-m3 tournera en CPU dans le conteneur.
#
# Le piège : un simple pre-install de torch+cpu est écrasé par le install
# suivant du package qui re-résout les deps et préfère torch+cu (même version,
# variant local différent, pip ne les unifie pas). Solution : --constraint
# force pip à respecter `torch==2.x.y+cpu` même pendant la résolution des deps
# transitives. L'extra-index PyTorch CPU permet à pip de trouver ce wheel.
RUN echo "torch==2.12.0+cpu" > /build/constraints-cpu.txt && \
    pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        --constraint /build/constraints-cpu.txt \
        .

# ===== Stage 2 : runtime =====
FROM python:3.12-slim AS runtime

# Security-IP-2 : profil de build (box | cortex). Détermine si les actifs
# Polaris (overlays, prompts cabinet, endpoints Cortex, templates rapport)
# sont **physiquement présents** dans l'image livrée.
#   - box (DÉFAUT, principe du moindre privilège) : actifs Polaris STRIPÉS
#     post-COPY. L'image livrée chez un client ne contient AUCUN secret cabinet.
#   - cortex : tous les actifs présents. Réservé au déploiement chez Polaris.
ARG ZOLAOS_PROFILE=box

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages" \
    ZOLAOS_PROMPTS_DIR="/app/agents/prompts" \
    HF_HOME="/tmp/hf_cache" \
    XDG_CACHE_HOME="/tmp/.cache" \
    ZOLAOS_PROFILE=${ZOLAOS_PROFILE}

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Utilisateur non-root
RUN groupadd -r zolaos && useradd -r -g zolaos -d /app -s /sbin/nologin zolaos

WORKDIR /app

COPY --from=builder /install /install
COPY --chown=zolaos:zolaos src/ ./src/
COPY --chown=zolaos:zolaos agents/ ./agents/
COPY --chown=zolaos:zolaos infra/postgres/ ./infra/postgres/
COPY --chown=zolaos:zolaos infra/scripts/ ./infra/scripts/
COPY --chown=zolaos:zolaos alembic.ini ./
COPY --chown=zolaos:zolaos alembic/ ./alembic/

# Security-IP-2 : strip des actifs Polaris si profil=box. Échoue le build si
# un fichier Polaris résiduel est détecté (sanity check final dans le script).
RUN if [ "$ZOLAOS_PROFILE" = "box" ]; then \
        echo "[Dockerfile] Build profil BOX — strip des actifs Polaris" && \
        sh /app/infra/scripts/strip_polaris_assets.sh && \
        chown -R zolaos:zolaos /install /app/agents /app/src; \
    else \
        echo "[Dockerfile] Build profil CORTEX — actifs Polaris conservés"; \
    fi

USER zolaos

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "zolaos.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
