"""Tests de `scripts/index_codebase.py` (indexeur du dépôt client → rag_code).

On teste uniquement la LOGIQUE PURE (sélection de fichiers, détection de
langage, construction de source_uri/tags) sur une petite arborescence
temporaire, plus le câblage de l'indexation d'UN fichier avec l'ingestion
(embedding + insertion DB) intégralement mockée. Aucun réseau, aucun Postgres,
aucun bge-m3 : le tokenizer réel et `get_embedding_service()` ne sont jamais
sollicités.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import index_codebase

from zolaos.security.pii import PIIRedactionPolicy


@pytest.fixture
def petit_depot(tmp_path: Path) -> Path:
    """Arborescence minimale : 1 fichier python à indexer, 1 secret et 1
    binaire à ignorer. Pas un dépôt git → exerce le fallback `os.walk`.
    """
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)

    (repo / "src" / "main.py").write_text(
        "def bonjour(nom):\n    return f'Bonjour {nom}'\n",
        encoding="utf-8",
    )
    (repo / ".env").write_text("SECRET_KEY=abc123\n", encoding="utf-8")
    (repo / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00binarydata")

    return repo


# =============================================================================
# Sélection de fichiers
# =============================================================================


def test_collect_files_ignores_secrets_and_binaries(petit_depot: Path) -> None:
    selection = index_codebase.collect_files(petit_depot)

    assert selection.candidates == ["src/main.py"]
    assert selection.ignored_secret == [".env"]
    assert selection.ignored_binary == ["logo.png"]
    assert selection.ignored_too_large == []


def test_collect_files_excludes_default_dirs(tmp_path: Path) -> None:
    repo = tmp_path / "repo2"
    (repo / "node_modules" / "pkg").mkdir(parents=True)
    (repo / "node_modules" / "pkg" / "index.js").write_text("console.log(1);", encoding="utf-8")
    (repo / "app.js").write_text("console.log(2);", encoding="utf-8")

    selection = index_codebase.collect_files(repo)

    assert selection.candidates == ["app.js"]


def test_collect_files_ignores_oversized(tmp_path: Path) -> None:
    repo = tmp_path / "repo3"
    repo.mkdir()
    big = repo / "big.py"
    big.write_bytes(b"a" * (index_codebase.MAX_FILE_SIZE_BYTES + 1))

    selection = index_codebase.collect_files(repo)

    assert selection.candidates == []
    assert selection.ignored_too_large == ["big.py"]


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.local",
        "server.pem",
        "private.key",
        "cert.p12",
        "id_rsa",
        "id_rsa.pub",
        "keystore.keystore",
    ],
)
def test_is_secret_file_patterns(name: str) -> None:
    assert index_codebase.is_secret_file(name) is True


def test_is_secret_file_false_for_regular_code() -> None:
    assert index_codebase.is_secret_file("src/main.py") is False
    assert index_codebase.is_secret_file("keychain.py") is False


# =============================================================================
# Détection de langage
# =============================================================================


@pytest.mark.parametrize(
    ("rel_path", "expected"),
    [
        ("src/main.py", "python"),
        ("app/component.tsx", "typescript"),
        ("app/component.ts", "typescript"),
        ("web/app.js", "javascript"),
        ("cmd/server.go", "go"),
        ("Main.java", "java"),
        ("Program.cs", "csharp"),
        ("lib/model.rb", "ruby"),
        ("src/lib.rs", "rust"),
        ("index.php", "php"),
        ("README.md", "text"),
        ("config.yml", "text"),
        ("data.json", "text"),
        ("notes.txt", "text"),
        ("archive.unknownext", "text"),
    ],
)
def test_detect_language(rel_path: str, expected: str) -> None:
    assert index_codebase.detect_language(rel_path) == expected


# =============================================================================
# source_uri / tags
# =============================================================================


def test_build_source_uri() -> None:
    assert index_codebase.build_source_uri("acme", "src/main.py") == "code://acme/src/main.py"


def test_build_tags() -> None:
    assert index_codebase.build_tags("acme", "python") == [
        "tenant:acme",
        "lang:python",
        "type:code",
    ]


# =============================================================================
# Indexation d'un fichier — embedding + insertion DB entièrement mockés
# =============================================================================


async def test_index_one_file_calls_ingest_text_with_expected_args(
    petit_depot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded: dict[str, object] = {}

    async def fake_ingest_text(**kwargs: object) -> int:
        recorded.update(kwargs)
        return 3  # nb de chunks "insérés" simulé

    monkeypatch.setattr(index_codebase, "ingest_text", fake_ingest_text)

    session = AsyncMock()  # writer factice : session.execute()/flush() sont awaitables

    n = await index_codebase.index_one_file(
        session=session,
        repo_dir=petit_depot,
        rel_path="src/main.py",
        tenant="acme",
        pii_policy=PIIRedactionPolicy.GENERIC,
    )

    assert n == 3
    assert recorded["source_uri"] == "code://acme/src/main.py"
    assert recorded["schema"] == "rag_code"
    assert recorded["tags"] == ["tenant:acme", "lang:python", "type:code"]
    assert recorded["pii_policy"] is PIIRedactionPolicy.GENERIC
    assert recorded["source_id"] == "src/main.py"
    assert recorded["session"] is session
    # Le chunker par symboles doit être celui du code, pas le générique par défaut.
    assert isinstance(recorded["chunker"], index_codebase.CodeChunker)

    # Idempotence : un DELETE par source_uri a bien été tenté sur le writer factice
    # avant l'appel à l'ingestion (defense contre les chunks obsolètes).
    assert session.execute.await_count >= 1


async def test_index_one_file_skips_empty_file_without_touching_ingest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo_vide"
    repo.mkdir()
    (repo / "empty.py").write_text("   \n", encoding="utf-8")

    called = False

    async def fake_ingest_text(**kwargs: object) -> int:
        nonlocal called
        called = True
        return 1

    monkeypatch.setattr(index_codebase, "ingest_text", fake_ingest_text)
    session = AsyncMock()

    n = await index_codebase.index_one_file(
        session=session,
        repo_dir=repo,
        rel_path="empty.py",
        tenant="acme",
        pii_policy=PIIRedactionPolicy.GENERIC,
    )

    assert n == 0
    assert called is False


# =============================================================================
# Indexation incrémentale — `index_repo` : skip par hash, --since, résumé
#
# `ingest_text` et les helpers DB (`_get_existing_content_sha`,
# `_delete_existing_for_source`, `_delete_existing_for_tenant`) sont
# intégralement mockés (dict Python en guise de "base"). Aucun réseau, aucun
# Postgres, aucun bge-m3, aucun git réel.
# =============================================================================


async def test_index_repo_skips_unchanged_file_by_hash(
    petit_depot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store: dict[str, str] = {}  # source_uri -> content_sha, simule rag_code
    ingest_calls: list[dict] = []

    async def fake_ingest_text(**kwargs: object) -> int:
        ingest_calls.append(kwargs)
        extra_metadata = kwargs["extra_metadata"]
        assert isinstance(extra_metadata, dict)
        store[kwargs["source_uri"]] = extra_metadata["content_sha"]
        return 2

    async def fake_get_existing_content_sha(session: object, source_uri: str) -> str | None:
        return store.get(source_uri)

    async def fake_delete_existing_for_source(session: object, source_uri: str) -> int:
        existed = source_uri in store
        store.pop(source_uri, None)
        return 1 if existed else 0

    monkeypatch.setattr(index_codebase, "ingest_text", fake_ingest_text)
    monkeypatch.setattr(index_codebase, "_get_existing_content_sha", fake_get_existing_content_sha)
    monkeypatch.setattr(
        index_codebase, "_delete_existing_for_source", fake_delete_existing_for_source
    )

    session = AsyncMock()

    # Passe 1 : fichier jamais vu -> indexé, hash enregistré.
    summary1 = await index_codebase.index_repo(
        petit_depot, "acme", pii_policy=PIIRedactionPolicy.GENERIC, session=session
    )
    assert summary1 == {"indexed": 1, "skipped": 0, "deleted": 0, "chunks": 2}
    assert len(ingest_calls) == 1

    # Passe 2 : contenu inchangé -> skip, aucun nouvel appel à ingest_text.
    summary2 = await index_codebase.index_repo(
        petit_depot, "acme", pii_policy=PIIRedactionPolicy.GENERIC, session=session
    )
    assert summary2 == {"indexed": 0, "skipped": 1, "deleted": 0, "chunks": 0}
    assert len(ingest_calls) == 1

    # Passe 3 : fichier modifié -> hash différent -> ré-indexé.
    (petit_depot / "src" / "main.py").write_text(
        "def bonjour(nom):\n    return f'Salut {nom}'\n", encoding="utf-8"
    )
    summary3 = await index_codebase.index_repo(
        petit_depot, "acme", pii_policy=PIIRedactionPolicy.GENERIC, session=session
    )
    assert summary3 == {"indexed": 1, "skipped": 0, "deleted": 0, "chunks": 2}
    assert len(ingest_calls) == 2


async def test_index_repo_reindex_ignores_hash_skip(
    petit_depot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main_path = petit_depot / "src" / "main.py"
    current_sha = index_codebase.compute_content_sha(main_path)
    # La "base" connaît déjà le hash courant : sans --reindex, ce serait un skip.
    store = {"code://acme/src/main.py": current_sha}
    purge_calls: list[str] = []

    async def fake_ingest_text(**kwargs: object) -> int:
        return 2

    async def fake_get_existing_content_sha(session: object, source_uri: str) -> str | None:
        return store.get(source_uri)

    async def fake_delete_existing_for_tenant(session: object, tenant: str) -> int:
        purge_calls.append(tenant)
        return 5

    async def fake_delete_existing_for_source(session: object, source_uri: str) -> int:
        return 1

    monkeypatch.setattr(index_codebase, "ingest_text", fake_ingest_text)
    monkeypatch.setattr(index_codebase, "_get_existing_content_sha", fake_get_existing_content_sha)
    monkeypatch.setattr(
        index_codebase, "_delete_existing_for_tenant", fake_delete_existing_for_tenant
    )
    monkeypatch.setattr(
        index_codebase, "_delete_existing_for_source", fake_delete_existing_for_source
    )

    summary = await index_codebase.index_repo(
        petit_depot,
        "acme",
        reindex=True,
        pii_policy=PIIRedactionPolicy.GENERIC,
        session=AsyncMock(),
    )

    # --reindex : le fichier est retraité malgré un hash identique à celui "en base".
    assert summary == {"indexed": 1, "skipped": 0, "deleted": 0, "chunks": 2}
    assert purge_calls == ["acme"]


async def test_index_repo_dry_run_returns_summary_without_touching_db(
    petit_depot: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def fake_ingest_text(**kwargs: object) -> int:
        nonlocal called
        called = True
        return 1

    monkeypatch.setattr(index_codebase, "ingest_text", fake_ingest_text)

    summary = await index_codebase.index_repo(
        petit_depot, "acme", dry_run=True, pii_policy=PIIRedactionPolicy.GENERIC
    )

    assert called is False  # dry-run : aucun embedding
    assert summary == {"indexed": 1, "skipped": 0, "deleted": 0, "chunks": summary["chunks"]}
    assert summary["chunks"] >= 1


def test_git_changed_since_returns_none_when_not_git(tmp_path: Path) -> None:
    repo = tmp_path / "not_a_repo"
    repo.mkdir()
    assert index_codebase._git_changed_since(repo, "HEAD~1") is None


async def test_index_repo_since_filters_changed_and_removes_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo_since"
    (repo / "src").mkdir(parents=True)
    (repo / ".git").mkdir()  # marque un dépôt git, sans invoquer git réellement (mocké plus bas)
    (repo / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (repo / "src" / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")

    class _Result:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_run(cmd: list[str], **kwargs: object) -> _Result:
        if "ls-files" in cmd:
            return _Result("src/a.py\nsrc/b.py\n")
        if "--diff-filter=D" in cmd:
            return _Result("src/deleted.py\n")
        if cmd[-1] == "HEAD":
            return _Result("")  # rien de commité depuis la réf.
        return _Result("src/a.py\n")  # working tree : seul a.py a changé localement

    monkeypatch.setattr(index_codebase.subprocess, "run", fake_run)

    ingest_calls: list[dict] = []
    delete_calls: list[str] = []

    async def fake_ingest_text(**kwargs: object) -> int:
        ingest_calls.append(kwargs)
        return 4

    async def fake_delete_existing_for_source(session: object, source_uri: str) -> int:
        delete_calls.append(source_uri)
        return 1

    async def fake_get_existing_content_sha(session: object, source_uri: str) -> str | None:
        return None  # jamais indexé auparavant -> jamais skip

    monkeypatch.setattr(index_codebase, "ingest_text", fake_ingest_text)
    monkeypatch.setattr(
        index_codebase, "_delete_existing_for_source", fake_delete_existing_for_source
    )
    monkeypatch.setattr(index_codebase, "_get_existing_content_sha", fake_get_existing_content_sha)

    summary = await index_codebase.index_repo(
        repo,
        "acme",
        since="deadbeef",
        pii_policy=PIIRedactionPolicy.GENERIC,
        session=AsyncMock(),
    )

    assert summary == {"indexed": 1, "skipped": 0, "deleted": 1, "chunks": 4}
    assert len(ingest_calls) == 1
    assert ingest_calls[0]["source_uri"] == "code://acme/src/a.py"  # b.py non changé -> exclu
    assert "code://acme/src/deleted.py" in delete_calls
