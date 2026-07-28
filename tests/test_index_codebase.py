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
