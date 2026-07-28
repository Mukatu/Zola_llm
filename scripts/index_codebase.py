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

**Indexation incrémentale** (Phase 2) : pour éviter de ré-embedder tout le
dépôt à chaque run (coûteux — bge-m3 + insertion pgvector), deux mécanismes
complémentaires :
- **Skip par hash de contenu** : le sha256 du contenu de chaque fichier est
  stocké dans `extra_metadata.content_sha` des chunks insérés. Avant de
  ré-indexer un fichier, on relit ce hash sur une ligne `rag_code` existante
  du même `source_uri` ; s'il est identique au hash courant, le fichier est
  **skip** (aucun delete, aucun ré-embedding). `--reindex` ignore ce skip.
- **`--since <réf-git>`** : restreint les candidats aux fichiers changés
  depuis cette référence (commits + working tree, via `git diff`) quand
  `repo_dir` est un dépôt git ; les fichiers supprimés depuis cette référence
  voient leurs lignes `rag_code` retirées (sans ré-indexation).

Point d'entrée programmatique : `index_repo()` fait tout (sélection,
filtrage `--since`, skip par hash, embedding+insertion ou dry-run) et
retourne un résumé `{"indexed", "skipped", "deleted", "chunks"}`. C'est la
fonction à importer depuis un endpoint API ; `main()` n'est qu'un wrapper CLI
(parsing argparse) autour d'elle.

Usage :
    python scripts/index_codebase.py /chemin/vers/le/depot --tenant acme
    python scripts/index_codebase.py /chemin/vers/le/depot --tenant acme --dry-run
    python scripts/index_codebase.py /chemin/vers/le/depot --tenant acme --reindex
    python scripts/index_codebase.py /chemin/vers/le/depot --tenant acme --since HEAD~20
"""

from __future__ import annotations

import argparse
import asyncio
import fnmatch
import hashlib
import subprocess
from pathlib import Path, PurePosixPath

from sqlalchemy import delete, select
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


def compute_content_sha(path: Path) -> str:
    """sha256 hexadécimal du contenu brut (octets) du fichier.

    Sert de fondement au skip incrémental : un hash inchangé entre deux runs
    signifie un contenu inchangé, donc aucun besoin de ré-embedder.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _git_diff_name_only(repo_dir: Path, args: list[str]) -> list[str] | None:
    """`git diff --name-only <args>`, ou `None` si la commande échoue."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo_dir), "diff", "--name-only", *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        _log.warning("index_codebase.git_diff_failed", args=args, error=str(exc))
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_changed_since(repo_dir: Path, since_ref: str) -> tuple[set[str], set[str]] | None:
    """Fichiers changés/ajoutés et supprimés depuis `since_ref`.

    Union de deux diffs : `<since_ref> HEAD` (commits déjà faits depuis la réf.)
    et `<since_ref>` seul (compare aussi au working tree — capture les
    modifications non commitées). Les suppressions (`--diff-filter=D`) sont
    calculées séparément et retirées de l'ensemble "changé" : un fichier
    supprimé n'est jamais candidat à la ré-indexation, seulement à la purge.

    Retourne `None` si `repo_dir` n'est pas un dépôt git exploitable (ou si
    l'une des commandes git échoue) — l'appelant doit alors ignorer `--since`.
    """
    if not (repo_dir / ".git").exists():
        return None

    committed = _git_diff_name_only(repo_dir, [since_ref, "HEAD"])
    working = _git_diff_name_only(repo_dir, [since_ref])
    deleted = _git_diff_name_only(repo_dir, ["--diff-filter=D", since_ref])
    if committed is None or working is None or deleted is None:
        return None

    deleted_set = {_to_posix(p) for p in deleted}
    changed = ({_to_posix(p) for p in committed} | {_to_posix(p) for p in working}) - deleted_set
    return changed, deleted_set


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


async def _get_existing_content_sha(session: AsyncSession, source_uri: str) -> str | None:
    """Relit `extra_metadata.content_sha` d'UNE ligne `rag_code` existante pour ce
    `source_uri` (toutes les lignes d'un même fichier partagent le même hash,
    inutile de les comparer toutes). Retourne `None` si aucune ligne n'existe
    encore, ou si l'ancienne ligne n'a pas ce champ (ré-indexation historique
    d'avant l'introduction du skip par hash → traitée comme "changé").
    """
    model = RAG_MODELS[_SCHEMA]
    stmt = select(model.extra_metadata).where(model.source_uri == source_uri).limit(1)
    result = await session.execute(stmt)
    metadata = result.scalar_one_or_none()
    if not metadata:
        return None
    return metadata.get("content_sha")


async def index_one_file(
    *,
    session: AsyncSession,
    repo_dir: Path,
    rel_path: str,
    tenant: str,
    pii_policy: PIIRedactionPolicy,
    content_sha: str | None = None,
) -> int:
    """Indexe un fichier : delete-then-insert (idempotent). Retourne le nb de chunks insérés.

    Retourne 0 sans rien écrire si le fichier est vide après lecture.
    `content_sha` : hash déjà calculé par l'appelant (évite un second calcul
    dans la boucle d'orchestration) ; recalculé si non fourni.
    """
    text = _read_text(repo_dir / rel_path)
    if not text.strip():
        return 0

    lang = detect_language(rel_path)
    source_uri = build_source_uri(tenant, rel_path)
    tags = build_tags(tenant, lang)
    chunker = CodeChunker(language=lang, file_path=rel_path)
    sha = content_sha or compute_content_sha(repo_dir / rel_path)

    await _delete_existing_for_source(session, source_uri)
    return await ingest_text(
        text=text,
        source_uri=source_uri,
        schema=_SCHEMA,
        tags=tags,
        pii_policy=pii_policy,
        source_id=rel_path,
        extra_metadata={"tenant_id": tenant, "language": lang, "content_sha": sha},
        session=session,
        chunker=chunker,
    )


def _dsn_async_migrator(settings: Settings) -> str:
    """DSN async avec le rôle migrator (propriétaire de tous les schémas `rag_*`,
    y compris `rag_code` — même convention que `scripts/ingest_pdf.py`)."""
    return settings.postgres_dsn_migrations.replace("+psycopg", "+asyncpg")


def _dry_run_summary(
    repo_dir: Path,
    tenant: str,
    selection: FileSelection,
    deleted_paths: set[str],
) -> dict[str, int]:
    """Compte fichiers + chunks SANS embedding ni écriture (comme `ingest_pdf.py`).

    Le comptage de chunks exécute le `CodeChunker` réel (tokenizer bge-m3, en
    cache local/offline) pour rester honnête sur le nombre de chunks produits,
    mais aucun vecteur n'est calculé et aucune connexion base n'est ouverte.
    Le skip par hash n'est donc PAS appliqué ici (il exige une lecture DB) :
    tous les candidats (après filtrage `--since` éventuel) sont comptés comme
    "à indexer".
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

    summary = {
        "indexed": files_indexed,
        "skipped": 0,
        "deleted": len(deleted_paths),
        "chunks": total_chunks,
    }
    _print_summary(tenant=tenant, selection=selection, summary=summary, dry_run=True)
    return summary


async def index_repo(
    repo_dir: Path | str,
    tenant: str,
    *,
    since: str | None = None,
    reindex: bool = False,
    dry_run: bool = False,
    pii_policy: PIIRedactionPolicy = PIIRedactionPolicy.GENERIC,
    session: AsyncSession | None = None,
) -> dict[str, int]:
    """Indexe (incrémentalement) un dépôt client dans `rag_code`.

    Point d'entrée programmatique unique : la CLI (`main`) n'est qu'un wrapper
    argparse autour de cette fonction, qui peut aussi être importée par un
    endpoint API pour déclencher une (ré)indexation.

    Comportement :
    - Sélectionne les fichiers via `collect_files` (respecte `.gitignore`,
      exclut secrets/binaires/volumineux).
    - Si `since` est fourni ET `repo_dir` est un dépôt git : restreint les
      candidats aux fichiers changés depuis cette réf. (`_git_changed_since`)
      et retire du corpus les fichiers supprimés depuis (purge sans
      ré-indexation). Si `repo_dir` n'est pas un dépôt git, `since` est ignoré
      (avertissement loggé) et le comportement complet s'applique.
    - Si `dry_run` : compte fichiers/chunks sans DB ni embedding (le skip par
      hash n'est pas applicable, il nécessite une lecture DB).
    - Sinon, pour chaque candidat : sauf `reindex=True`, compare le sha256 du
      contenu courant à `extra_metadata.content_sha` d'une ligne `rag_code`
      existante pour ce `source_uri` ; identique → **skip** (aucun
      delete/ré-embedding). Différent (ou absent) → delete-then-insert comme
      avant, en enregistrant le nouveau hash.
    - `reindex=True` : purge d'abord TOUTES les lignes du tenant, puis
      réindexe tous les candidats sans jamais skip (comme aujourd'hui).

    `session` : si fournie (tests, appel imbriqué dans une transaction
    existante), elle est utilisée telle quelle et **n'est pas committée** ici
    (à l'appelant de le faire). Sinon, une engine/session dédiée est ouverte,
    committée puis fermée en interne (comportement CLI historique).

    Retourne un résumé : `{"indexed": N, "skipped": N, "deleted": N, "chunks": N}`.
    """
    repo_dir = Path(repo_dir).resolve()
    selection = collect_files(repo_dir)

    deleted_paths: set[str] = set()
    if since:
        git_result = _git_changed_since(repo_dir, since)
        if git_result is None:
            _log.warning(
                "index_codebase.since_ignored_not_git", repo_dir=str(repo_dir), since=since
            )
            print(f"  --since {since} ignoré : {repo_dir} n'est pas un dépôt git exploitable.")
        else:
            changed, deleted_paths = git_result
            selection.candidates = [rel for rel in selection.candidates if rel in changed]
            print(
                f"  --since {since} : {len(selection.candidates)} fichier(s) changé(s) à "
                f"traiter, {len(deleted_paths)} supprimé(s) à retirer de l'index."
            )

    if dry_run:
        return _dry_run_summary(repo_dir, tenant, selection, deleted_paths)

    files_indexed = 0
    files_skipped = 0
    files_deleted = 0
    total_chunks = 0

    async def _process(active_session: AsyncSession) -> None:
        nonlocal files_indexed, files_skipped, files_deleted, total_chunks

        if reindex:
            purged = await _delete_existing_for_tenant(active_session, tenant)
            print(f"--reindex : {purged} chunk(s) existant(s) purgé(s) pour tenant={tenant!r}.")

        for rel in sorted(deleted_paths):
            source_uri = build_source_uri(tenant, rel)
            removed = await _delete_existing_for_source(active_session, source_uri)
            if removed:
                files_deleted += 1
                print(f"  {rel} (supprimé) → {removed} ligne(s) rag_code retirée(s)")

        for rel in selection.candidates:
            content_sha = compute_content_sha(repo_dir / rel)
            source_uri = build_source_uri(tenant, rel)

            if not reindex:
                existing_sha = await _get_existing_content_sha(active_session, source_uri)
                if existing_sha is not None and existing_sha == content_sha:
                    files_skipped += 1
                    continue

            n = await index_one_file(
                session=active_session,
                repo_dir=repo_dir,
                rel_path=rel,
                tenant=tenant,
                pii_policy=pii_policy,
                content_sha=content_sha,
            )
            if n:
                files_indexed += 1
                total_chunks += n
                print(f"  {rel} → {n} chunk(s) inséré(s)")

    if session is not None:
        await _process(session)
    else:
        settings = get_settings()
        engine = create_async_engine(_dsn_async_migrator(settings), pool_pre_ping=True)
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessionmaker() as new_session:
                await _process(new_session)
                await new_session.commit()
        finally:
            await engine.dispose()

    summary = {
        "indexed": files_indexed,
        "skipped": files_skipped,
        "deleted": files_deleted,
        "chunks": total_chunks,
    }
    _print_summary(tenant=tenant, selection=selection, summary=summary, dry_run=False)
    return summary


def _print_summary(
    *,
    tenant: str,
    selection: FileSelection,
    summary: dict[str, int],
    dry_run: bool,
) -> None:
    n_excluded = (
        len(selection.ignored_secret)
        + len(selection.ignored_binary)
        + len(selection.ignored_too_large)
    )
    print("\n=== Résumé ===")
    print(f"  tenant                       : {tenant}")
    print(f"  mode                         : {'dry-run' if dry_run else 'indexation réelle'}")
    print(f"  fichiers indexés             : {summary['indexed']}")
    print(f"  fichiers ignorés (inchangés) : {summary['skipped']}")
    print(f"  fichiers supprimés           : {summary['deleted']}")
    print(f"  chunks {'comptés' if dry_run else 'insérés'}                : {summary['chunks']}")
    print(
        f"  fichiers exclus              : {n_excluded} "
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
        help="purge TOUTES les lignes rag_code du tenant avant de tout réindexer (ignore le skip par hash)",
    )
    p.add_argument(
        "--since",
        default=None,
        metavar="GIT_REF",
        help=(
            "n'indexe que les fichiers changés depuis cette réf. git (commits + "
            "working tree) ; retire du corpus les fichiers supprimés depuis. "
            "Ignoré (avec avertissement) si repo_dir n'est pas un dépôt git."
        ),
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

    print(f"Dépôt : {repo_dir}")
    pii_policy = PIIRedactionPolicy(args.pii)

    asyncio.run(
        index_repo(
            repo_dir,
            args.tenant,
            since=args.since,
            reindex=args.reindex,
            dry_run=args.dry_run,
            pii_policy=pii_policy,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
