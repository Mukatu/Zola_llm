#!/usr/bin/env python
"""Indexeur du dépôt DU CLIENT pour l'assistant code souverain (`rag_code`).

Parcourt un dépôt (répertoire de travail du client), sélectionne les fichiers
texte pertinents (en respectant `.gitignore` quand c'est un dépôt git), les
découpe **par symbole** (fonctions/classes — `CodeChunker`,
cf. `zolaos.rag.chunking_specialized`), les embed sur la box (bge-m3) et les
insère dans le schéma RAG **`rag_code`**, cloisonné par tenant (tag
``tenant:<id>``, `source_uri` en ``code://<tenant>/<chemin relatif>``).

`rag_code` est un schéma **SENSIBLE** (`SENSITIVE_SCHEMAS`, code propriétaire
du client) : une politique PII explicite est exigée à l'ingestion, comme pour
`rag_tenant`/`rag_erp` (cf. `zolaos.security.pii.require_policy_for_ingest`).
Par défaut `--pii generic` (masque emails/téléphones/IBAN/cartes qui peuvent
traîner dans des commentaires ou fichiers de config) ; défense en profondeur
uniquement — les fichiers à haut risque de secret (`.env`, clés privées…) sont
de toute façon exclus AVANT même d'atteindre le pipeline PII (cf. plus bas).

Réutilise les primitives d'ingestion existantes plutôt que de les réécrire :
- Chunking : `zolaos.rag.chunking_specialized.CodeChunker` (1 chunk = 1 symbole,
  entêtes `# fichier:`/`# symbole:`, fallback générique si langage/format non
  reconnu).
- Embedding (bge-m3) + insertion pgvector : `zolaos.rag.ingest.ingest_text`
  (même fonction que `scripts/ingest_pdf.py` — idempotence native par
  `(source_uri, chunk_index)` + `ON CONFLICT DO NOTHING`).
- Rôle DB : comme `scripts/ingest_pdf.py`, on ingère via le rôle **migrator**
  (propriétaire de tous les schémas `rag_*`, y compris `rag_code`). Le rôle
  `zolaos_code_agent` (R/W sur `rag_code` uniquement) est le rôle **applicatif**
  utilisé par `CodeAgent` pour le retrieval en ligne ; ce script est un batch
  hors-ligne d'onboarding/ré-indexation, pas un composant servi par l'API — il
  suit donc la même convention que les autres CLI d'ingestion du dépôt.

Au-delà du `ON CONFLICT DO NOTHING` (qui ne met pas à jour un chunk existant
si son contenu a changé), ce script assure une **vraie** idempotence de
ré-indexation : avant de réinsérer les chunks d'un fichier, on supprime
d'abord les lignes `rag_code` existantes de même `source_uri`. `--reindex`
va plus loin et purge TOUTES les lignes du tenant avant de tout réindexer
(utile après un renommage/suppression massifs de fichiers).

Usage :
    python scripts/index_codebase.py /chemin/vers/le/depot --tenant acme
    python scripts/index_codebase.py /chemin/vers/le/depot --tenant acme --dry-run
    python scripts/index_codebase.py /chemin/vers/le/depot --tenant acme --reindex
"""

from __future__ import annotations

import argparse
import asyncio
import fnmatch
import subprocess
from pathlib import Path, PurePosixPath

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zolaos.core.logging import get_logger
from zolaos.core.settings import Settings, get_settings
from zolaos.db.models import RAG_MODELS
from zolaos.rag.chunking_specialized import CodeChunker
from zolaos.rag.ingest import ingest_text
from zolaos.security.pii import PIIRedactionPolicy

_log = get_logger("zolaos.scripts.index_codebase")

_SCHEMA = "rag_code"

# =============================================================================
# Sélection des fichiers — logique pure (testable sans DB ni bge-m3)
# =============================================================================

# Répertoires toujours exclus du fallback `os.walk` (dépôts sans git, ou
# filet de sécurité même en mode git : ces répertoires ne doivent jamais être
# indexés même s'ils étaient accidentellement suivis).
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    ".venv_test",
    "dist",
    "build",
    "__pycache__",
    "target",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}

# Fichiers à haut risque de secret : SKIP systématique, quelle que soit la
# politique PII (défense en profondeur — un secret n'est pas une PII, la
# politique PII ne le masquerait pas). Match sur le nom de fichier (basename).
_SECRET_FILE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "id_rsa*",
    "*.keystore",
]

# Extensions binaires connues, exclues sans même lire le contenu (perf).
# La détection par octet nul (`is_binary`) reste le filet de sécurité pour
# tout le reste (extension inconnue, fichier renommé sans extension...).
_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".zip", ".tar", ".gz", ".tgz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".class", ".pyc",
    ".pdf", ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".mov", ".avi", ".wav",
    ".db", ".sqlite", ".sqlite3",
}  # fmt: skip

MAX_FILE_SIZE_BYTES = 1_000_000  # ~1 Mo

# Extension → langage. Sert au tag `lang:<lang>` ET au choix des heuristiques
# de découpage par symbole (`CodeChunker(language=...)`). Un langage absent
# ici (ou une extension inconnue) tombe sur "text" : toujours indexé, mais le
# `CodeChunker` retombera lui-même sur le découpage générique (fenêtre
# glissante) faute de motif de symbole reconnu pour ce langage.
EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".rs": "rust",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".ps1": "powershell",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".scala": "scala",
}

_NULL_BYTE_SNIFF_SIZE = 8192


def is_secret_file(rel_path: str) -> bool:
    """True si le nom de fichier matche un motif à haut risque de secret."""
    name = PurePosixPath(rel_path).name
    return any(fnmatch.fnmatch(name.lower(), pat.lower()) for pat in _SECRET_FILE_PATTERNS)


def has_excluded_dir_component(rel_path: str) -> bool:
    """True si un composant du chemin est un répertoire toujours exclu."""
    return any(part in DEFAULT_EXCLUDE_DIRS for part in PurePosixPath(rel_path).parts[:-1])


def is_binary_by_extension(rel_path: str) -> bool:
    return PurePosixPath(rel_path).suffix.lower() in _BINARY_EXTENSIONS


def is_binary_content(path: Path) -> bool:
    """Détection binaire par octet nul dans les premiers octets du fichier."""
    try:
        with path.open("rb") as f:
            chunk = f.read(_NULL_BYTE_SNIFF_SIZE)
    except OSError:
        return True
    return b"\x00" in chunk


def detect_language(rel_path: str) -> str:
    """Langage déduit de l'extension. "text" si non reconnu (indexé quand même)."""
    ext = PurePosixPath(rel_path).suffix.lower()
    return EXTENSION_LANGUAGE.get(ext, "text")


def build_source_uri(tenant: str, rel_path: str) -> str:
    """`source_uri` stable, cloisonné tenant, chemin relatif en `/`."""
    return f"code://{tenant}/{rel_path}"


def build_tags(tenant: str, lang: str) -> list[str]:
    return [f"tenant:{tenant}", f"lang:{lang}", "type:code"]


def _to_posix(rel_path: str) -> str:
    """Normalise un chemin relatif (séparateurs OS) en POSIX (`/`)."""
    return rel_path.replace("\\", "/")


def _git_tracked_files(repo_dir: Path) -> list[str] | None:
    """Fichiers suivis par git (respecte `.gitignore` — c'est git qui l'applique).

    Retourne `None` si `repo_dir` n'est pas (ou plus) un dépôt git exploitable,
    pour laisser l'appelant retomber sur le parcours `os.walk`.
    """
    if not (repo_dir / ".git").exists():
        return None
    try:
        result = (
            subprocess.run(  # noqa: S603 (repo_dir fourni par l'opérateur, pas une entrée réseau)
                ["git", "-C", str(repo_dir), "ls-files"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                errors="replace",
            )
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        _log.warning("index_codebase.git_ls_files_failed", error=str(exc))
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _walk_files(repo_dir: Path) -> list[str]:
    """Parcours `os.walk` (dépôt sans git) : élague les répertoires exclus."""
    import os

    found: list[str] = []
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIRS]
        for name in files:
            full = Path(root) / name
            rel = _to_posix(str(full.relative_to(repo_dir)))
            found.append(rel)
    return found


class FileSelection:
    """Résultat de la sélection : fichiers à indexer + fichiers ignorés (avec motif)."""

    def __init__(self) -> None:
        self.candidates: list[str] = []
        self.ignored_secret: list[str] = []
        self.ignored_binary: list[str] = []
        self.ignored_too_large: list[str] = []


def collect_files(repo_dir: Path) -> FileSelection:
    """Sélectionne les fichiers à indexer dans `repo_dir`.

    Priorité à `git ls-files` (dépôt git → `.gitignore` déjà appliqué par git) ;
    sinon `os.walk` avec la liste d'exclusion par défaut. Dans les deux cas :
    fichiers à secret exclus, binaires exclus (extension connue OU octet nul
    détecté), fichiers > `MAX_FILE_SIZE_BYTES` exclus.
    """
    selection = FileSelection()
    tracked = _git_tracked_files(repo_dir)
    rel_paths = tracked if tracked is not None else _walk_files(repo_dir)

    for rel in rel_paths:
        rel = _to_posix(rel)
        if has_excluded_dir_component(rel):
            continue
        full = repo_dir / rel
        if not full.is_file():
            continue  # ex: entrée d'index git pour un fichier supprimé en local

        if is_secret_file(rel):
            selection.ignored_secret.append(rel)
            _log.warning("index_codebase.secret_file_skipped", path=rel)
            continue

        try:
            size = full.stat().st_size
        except OSError:
            continue
        if size > MAX_FILE_SIZE_BYTES:
            selection.ignored_too_large.append(rel)
            continue

        if is_binary_by_extension(rel) or is_binary_content(full):
            selection.ignored_binary.append(rel)
            continue

        selection.candidates.append(rel)

    return selection


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# =============================================================================
# Indexation — embedding + insertion (réutilise zolaos.rag.ingest.ingest_text)
# =============================================================================


async def _delete_existing_for_source(session: AsyncSession, source_uri: str) -> int:
    """Purge les chunks `rag_code` existants pour ce `source_uri` (ré-indexation
    idempotente : `ingest_text` seul ne fait qu'un `ON CONFLICT DO NOTHING`, ce
    qui laisserait traîner des chunks obsolètes si le contenu/découpage change).
    """
    model = RAG_MODELS[_SCHEMA]
    stmt = delete(model).where(model.source_uri == source_uri)
    result = await session.execute(stmt)
    return result.rowcount or 0


async def _delete_existing_for_tenant(session: AsyncSession, tenant: str) -> int:
    """Purge TOUTES les lignes `rag_code` du tenant (utilisé par `--reindex`)."""
    model = RAG_MODELS[_SCHEMA]
    stmt = delete(model).where(model.tags.op("@>")([f"tenant:{tenant}"]))
    result = await session.execute(stmt)
    return result.rowcount or 0


async def index_one_file(
    *,
    session: AsyncSession,
    repo_dir: Path,
    rel_path: str,
    tenant: str,
    pii_policy: PIIRedactionPolicy,
) -> int:
    """Indexe un fichier : delete-then-insert (idempotent). Retourne le nb de chunks insérés.

    Retourne 0 sans rien écrire si le fichier est vide après lecture.
    """
    text = _read_text(repo_dir / rel_path)
    if not text.strip():
        return 0

    lang = detect_language(rel_path)
    source_uri = build_source_uri(tenant, rel_path)
    tags = build_tags(tenant, lang)
    chunker = CodeChunker(language=lang, file_path=rel_path)

    await _delete_existing_for_source(session, source_uri)
    return await ingest_text(
        text=text,
        source_uri=source_uri,
        schema=_SCHEMA,
        tags=tags,
        pii_policy=pii_policy,
        source_id=rel_path,
        extra_metadata={"tenant_id": tenant, "language": lang},
        session=session,
        chunker=chunker,
    )


def _dsn_async_migrator(settings: Settings) -> str:
    """DSN async avec le rôle migrator (propriétaire de tous les schémas `rag_*`,
    y compris `rag_code` — même convention que `scripts/ingest_pdf.py`)."""
    return settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")


async def run_dry(repo_dir: Path, tenant: str, selection: FileSelection) -> None:
    """Compte fichiers + chunks SANS embedding ni écriture (comme `ingest_pdf.py`).

    Le comptage de chunks exécute le `CodeChunker` réel (tokenizer bge-m3, en
    cache local/offline) pour rester honnête sur le nombre de chunks produits,
    mais aucun vecteur n'est calculé et aucune connexion base n'est ouverte.
    """
    files_indexed = 0
    total_chunks = 0
    for rel in selection.candidates:
        text = _read_text(repo_dir / rel)
        if not text.strip():
            continue
        lang = detect_language(rel)
        chunker = CodeChunker(language=lang, file_path=rel)
        chunks = chunker.chunk(text)
        if not chunks:
            continue
        files_indexed += 1
        total_chunks += len(chunks)
        print(f"  {rel} ({lang}) → {len(chunks)} chunk(s)")

    _print_summary(
        tenant=tenant,
        files_indexed=files_indexed,
        total_chunks=total_chunks,
        selection=selection,
        dry_run=True,
    )


async def run_index(
    repo_dir: Path,
    tenant: str,
    selection: FileSelection,
    *,
    reindex: bool,
    pii_policy: PIIRedactionPolicy,
) -> None:
    settings = get_settings()
    engine = create_async_engine(_dsn_async_migrator(settings), pool_pre_ping=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    files_indexed = 0
    total_chunks = 0
    try:
        async with sessionmaker() as session:
            if reindex:
                purged = await _delete_existing_for_tenant(session, tenant)
                print(f"--reindex : {purged} chunk(s) existant(s) purgé(s) pour tenant={tenant!r}.")

            for rel in selection.candidates:
                n = await index_one_file(
                    session=session,
                    repo_dir=repo_dir,
                    rel_path=rel,
                    tenant=tenant,
                    pii_policy=pii_policy,
                )
                if n:
                    files_indexed += 1
                    total_chunks += n
                    print(f"  {rel} → {n} chunk(s) inséré(s)")

            await session.commit()
    finally:
        await engine.dispose()

    _print_summary(
        tenant=tenant,
        files_indexed=files_indexed,
        total_chunks=total_chunks,
        selection=selection,
        dry_run=False,
    )


def _print_summary(
    *,
    tenant: str,
    files_indexed: int,
    total_chunks: int,
    selection: FileSelection,
    dry_run: bool,
) -> None:
    n_ignored = (
        len(selection.ignored_secret)
        + len(selection.ignored_binary)
        + len(selection.ignored_too_large)
    )
    print("\n=== Résumé ===")
    print(f"  tenant            : {tenant}")
    print(f"  mode              : {'dry-run' if dry_run else 'indexation réelle'}")
    print(f"  fichiers indexés  : {files_indexed}")
    print(f"  chunks {'comptés' if dry_run else 'insérés'}   : {total_chunks}")
    print(
        f"  fichiers ignorés  : {n_ignored} "
        f"(secrets={len(selection.ignored_secret)}, "
        f"binaires={len(selection.ignored_binary)}, "
        f"trop volumineux={len(selection.ignored_too_large)})"
    )


# =============================================================================
# CLI
# =============================================================================


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Indexe le dépôt DU CLIENT dans le schéma RAG rag_code (cloisonné par "
            "tenant), pour l'assistant code souverain."
        )
    )
    p.add_argument("repo_dir", help="répertoire racine du dépôt client à indexer")
    p.add_argument("--tenant", required=True, help="identifiant du tenant (cloisonnement rag_code)")
    p.add_argument(
        "--reindex",
        action="store_true",
        help="purge TOUTES les lignes rag_code du tenant avant de tout réindexer",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="compte fichiers/chunks sans embedding ni écriture en base",
    )
    p.add_argument(
        "--pii",
        default="generic",
        choices=[pol.value for pol in PIIRedactionPolicy],
        help=(
            "politique PII appliquée à l'ingestion (rag_code est un schéma sensible : "
            "obligatoire). Défaut 'generic' (masque emails/téléphones/IBAN/cartes "
            "qui peuvent traîner dans des commentaires ou fichiers de config)."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    repo_dir = Path(args.repo_dir).resolve()
    if not repo_dir.is_dir():
        print(f"Erreur : {repo_dir} n'est pas un répertoire.")
        return 1

    selection = collect_files(repo_dir)
    print(
        f"Dépôt : {repo_dir}\n"
        f"  {len(selection.candidates)} fichier(s) candidat(s), "
        f"{len(selection.ignored_secret)} secret(s) exclu(s), "
        f"{len(selection.ignored_binary)} binaire(s) exclu(s), "
        f"{len(selection.ignored_too_large)} trop volumineux."
    )

    pii_policy = PIIRedactionPolicy(args.pii)

    if args.dry_run:
        asyncio.run(run_dry(repo_dir, args.tenant, selection))
    else:
        asyncio.run(
            run_index(
                repo_dir,
                args.tenant,
                selection,
                reindex=args.reindex,
                pii_policy=pii_policy,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
