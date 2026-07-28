"""Chunkers spécialisés par domaine métier (Polaris-4).

Le `Chunker` générique (sliding window tokens) de `chunking.py` reste valide
pour tout texte non structuré. Ces chunkers spécialisés respectent les
frontières sémantiques d'un domaine :

- `AccountingChunker`  : 1 chunk = N écritures comptables groupées (≤ target_tokens)
- `LegalClauseChunker` : 1 chunk = 1 clause d'un contrat (entête + corps)
- `LegalArticleChunker`: 1 chunk = 1 article d'un texte de loi (CGI, OHADA)
- `MedicalCaseChunker` : 1 chunk = 1 section d'un dossier patient
- `CodeChunker`        : 1 chunk = 1 symbole de haut niveau (fonction/classe)

Chacun retombe automatiquement sur le `Chunker` générique si le pattern attendu
n'est pas détecté dans le texte (fallback robuste — on ne casse jamais
l'ingestion à cause d'un format inattendu).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from zolaos.core.logging import get_logger
from zolaos.rag.chunking import Chunk, Chunker

_log = get_logger("zolaos.rag.chunking_specialized")


# =============================================================================
# Comptabilité (Grand Livre SYSCOHADA)
# =============================================================================

# Format type : "21/03/2026 ; 411000 ; FACT-2026-001 ; 1 250 000 ; "
# ou "2026-03-21 | 411000 | Facture client ABC | 1250000.00 | 0.00"
# Le motif tolère séparateurs ; , | tab espaces multiples.
_ACCOUNTING_LINE_RE = re.compile(
    r"^\s*"
    r"(?P<date>\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})"
    r"\s*[;|,\t]\s*"
    r"(?P<account>\d{3,8})"
    r"\s*[;|,\t]\s*"
    r"(?P<label>[^;|\t\n]{1,200})"
    r"\s*[;|,\t]\s*"
    r"(?P<debit>-?[\d\s.,]*)"
    r"\s*[;|,\t]\s*"
    r"(?P<credit>-?[\d\s.,]*)"
    r"\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class AccountingEntry:
    date: str
    account: str
    label: str
    debit: str
    credit: str

    def as_chunk_text(self) -> str:
        return (
            f"Date: {self.date} | Compte: {self.account} | "
            f"Libellé: {self.label.strip()} | Débit: {self.debit.strip()} | "
            f"Crédit: {self.credit.strip()}"
        )


class AccountingChunker:
    """Chunker pour Grand Livre / balance générale SYSCOHADA.

    Stratégie : on parse les lignes au format `Date ; Compte ; Libellé ; Débit ; Crédit`
    et on regroupe N écritures consécutives par chunk, en respectant la limite
    `target_tokens` du tokenizer (compteur réutilisé via le Chunker générique).

    Fallback : si aucune ligne ne matche le pattern, on délègue au Chunker
    générique sliding-window (cas d'un texte non comptable ingéré par erreur).
    """

    def __init__(
        self,
        target_tokens: int = 512,
        overlap_tokens: int = 64,
        fallback: Chunker | None = None,
    ) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self._fallback = fallback or Chunker(target_tokens, overlap_tokens)

    def chunk(self, text: str) -> list[Chunk]:
        entries = self._extract_entries(text)
        if not entries:
            _log.info("accounting.fallback_generic", reason="no entries matched")
            return self._fallback.chunk(text)

        # Compteur de tokens : on réutilise le tokenizer du fallback.
        self._fallback._ensure_tokenizer()
        tok = self._fallback._tokenizer
        assert tok is not None

        chunks: list[Chunk] = []
        buffer: list[AccountingEntry] = []
        buffer_tokens = 0
        idx = 0

        def _flush() -> None:
            nonlocal buffer, buffer_tokens, idx
            if not buffer:
                return
            text_block = "\n".join(e.as_chunk_text() for e in buffer)
            chunks.append(Chunk(text=text_block, index=idx, tokens=buffer_tokens))
            idx += 1
            # Overlap : on garde les dernières écritures pour conserver le contexte.
            if self.overlap_tokens > 0 and len(buffer) > 1:
                kept: list[AccountingEntry] = []
                kept_tokens = 0
                for e in reversed(buffer):
                    et = len(tok(e.as_chunk_text(), add_special_tokens=False)["input_ids"])
                    if kept_tokens + et > self.overlap_tokens:
                        break
                    kept.insert(0, e)
                    kept_tokens += et
                buffer = kept
                buffer_tokens = kept_tokens
            else:
                buffer = []
                buffer_tokens = 0

        for entry in entries:
            entry_text = entry.as_chunk_text()
            entry_tokens = len(tok(entry_text, add_special_tokens=False)["input_ids"])
            if buffer_tokens + entry_tokens > self.target_tokens and buffer:
                _flush()
            buffer.append(entry)
            buffer_tokens += entry_tokens

        _flush()
        return chunks

    @staticmethod
    def _extract_entries(text: str) -> list[AccountingEntry]:
        return [
            AccountingEntry(
                date=m.group("date"),
                account=m.group("account"),
                label=m.group("label"),
                debit=m.group("debit"),
                credit=m.group("credit"),
            )
            for m in _ACCOUNTING_LINE_RE.finditer(text)
        ]


# =============================================================================
# Clauses juridiques (contrats)
# =============================================================================

# Détecte les titres de clauses : "Article 1 - Objet", "ARTICLE 12.", "Clause 3 :",
# "1. Période d'essai", "II. Non-concurrence", etc.
_CLAUSE_HEADER_RE = re.compile(
    r"^(?P<header>"
    r"(?:Article|ARTICLE|Clause|CLAUSE)\s+[\dIVXLC]+(?:\.\d+)*[\s.:\-–—]*[^\n]{0,150}"
    r"|"
    r"(?:[\dIVXLC]+\.)\s+[A-ZÉÈÀÂÊÎÔÛÇ][^\n]{2,150}"
    r")\s*$",
    re.MULTILINE,
)


class LegalClauseChunker:
    """Chunker pour contrats (CDI, CDD, baux, NDA, OHADA).

    Stratégie : on découpe sur les frontières de clauses (entêtes type
    "Article N", "Clause N", "N. Titre"). Chaque clause entière forme 1 chunk,
    sauf si elle dépasse target_tokens → on retombe sur sliding-window pour
    cette clause.
    """

    def __init__(
        self,
        target_tokens: int = 512,
        overlap_tokens: int = 64,
        fallback: Chunker | None = None,
    ) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self._fallback = fallback or Chunker(target_tokens, overlap_tokens)

    def chunk(self, text: str) -> list[Chunk]:
        positions = [m.start() for m in _CLAUSE_HEADER_RE.finditer(text)]
        if len(positions) < 2:
            _log.info(
                "clause.fallback_generic", reason="not enough clause headers", count=len(positions)
            )
            return self._fallback.chunk(text)

        # Borner par la fin du texte.
        positions.append(len(text))
        clauses = [text[positions[i] : positions[i + 1]].strip() for i in range(len(positions) - 1)]
        clauses = [c for c in clauses if c]

        self._fallback._ensure_tokenizer()
        tok = self._fallback._tokenizer
        assert tok is not None

        chunks: list[Chunk] = []
        idx = 0
        for clause in clauses:
            tokens = tok(clause, add_special_tokens=False)["input_ids"]
            if len(tokens) <= self.target_tokens:
                chunks.append(Chunk(text=clause, index=idx, tokens=len(tokens)))
                idx += 1
            else:
                # Clause trop longue → on sliding-window dessus, mais on garde
                # l'en-tête comme préfixe pour préserver le contexte.
                sub = self._fallback.chunk(clause)
                for s in sub:
                    chunks.append(Chunk(text=s.text, index=idx, tokens=s.tokens))
                    idx += 1
        return chunks


# =============================================================================
# Articles de loi (CGI, OHADA, Code du travail)
# =============================================================================

# Détecte les titres d'article codifiés type "Article 100", "Art. 100-1",
# "ARTICLE 100 bis", "Art. L. 1234-5", ainsi que le style compact sans espace
# rencontré dans le Code du travail congolais (Droit-Afrique) : "Art.1.-",
# "Art.2.-" — d'où `\s*` (et non `\s+`) entre l'abréviation et le numéro.
_LEGAL_ARTICLE_RE = re.compile(
    r"^(?P<header>(?:Article|ART(?:ICLE)?\.?|Art\.)\s*(?:[LRD]\.?\s*)?\d+(?:[-.]\d+)*(?:\s*(?:bis|ter|quater))?[^\n]{0,80})\s*$",
    re.MULTILINE,
)


class LegalArticleChunker:
    """Chunker pour textes de loi (CGI, OHADA, Code du travail).

    Stratégie : 1 article = 1 chunk (avec son en-tête). Si un article dépasse
    target_tokens (rare), sliding-window.
    """

    def __init__(
        self,
        target_tokens: int = 512,
        overlap_tokens: int = 64,
        fallback: Chunker | None = None,
    ) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self._fallback = fallback or Chunker(target_tokens, overlap_tokens)

    def chunk(self, text: str) -> list[Chunk]:
        positions = [m.start() for m in _LEGAL_ARTICLE_RE.finditer(text)]
        if len(positions) < 2:
            _log.info(
                "legal_article.fallback_generic",
                reason="not enough article headers",
                count=len(positions),
            )
            return self._fallback.chunk(text)

        positions.append(len(text))
        articles = [
            text[positions[i] : positions[i + 1]].strip() for i in range(len(positions) - 1)
        ]
        articles = [a for a in articles if a]

        self._fallback._ensure_tokenizer()
        tok = self._fallback._tokenizer
        assert tok is not None

        chunks: list[Chunk] = []
        idx = 0
        for art in articles:
            tokens = tok(art, add_special_tokens=False)["input_ids"]
            if len(tokens) <= self.target_tokens:
                chunks.append(Chunk(text=art, index=idx, tokens=len(tokens)))
                idx += 1
            else:
                for s in self._fallback.chunk(art):
                    chunks.append(Chunk(text=s.text, index=idx, tokens=s.tokens))
                    idx += 1
        return chunks


# =============================================================================
# Dossiers médicaux
# =============================================================================

# Sections classiques d'un dossier : Anamnèse, Antécédents, Examen clinique,
# Diagnostic, Traitement, Évolution, Conclusion.
_MEDICAL_SECTION_RE = re.compile(
    r"^(?P<header>"
    r"(?:Anamnèse|Antécédents|Examen clinique|Examen physique|"
    r"Diagnostic|Hypothèses diagnostiques|Traitement|Prescription|"
    r"Évolution|Conclusion|Motif de consultation|Histoire de la maladie|"
    r"Recommandations)"
    r"\s*:?[^\n]{0,80})\s*$",
    re.MULTILINE | re.IGNORECASE,
)


class MedicalCaseChunker:
    """Chunker pour dossiers patients structurés.

    Stratégie : 1 section = 1 chunk (Anamnèse, Diagnostic, etc.). Sliding-window
    si une section dépasse target_tokens.
    """

    def __init__(
        self,
        target_tokens: int = 512,
        overlap_tokens: int = 64,
        fallback: Chunker | None = None,
    ) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self._fallback = fallback or Chunker(target_tokens, overlap_tokens)

    def chunk(self, text: str) -> list[Chunk]:
        positions = [m.start() for m in _MEDICAL_SECTION_RE.finditer(text)]
        if len(positions) < 2:
            _log.info(
                "medical.fallback_generic", reason="not enough sections", count=len(positions)
            )
            return self._fallback.chunk(text)

        positions.append(len(text))
        sections = [
            text[positions[i] : positions[i + 1]].strip() for i in range(len(positions) - 1)
        ]
        sections = [s for s in sections if s]

        self._fallback._ensure_tokenizer()
        tok = self._fallback._tokenizer
        assert tok is not None

        chunks: list[Chunk] = []
        idx = 0
        for sec in sections:
            tokens = tok(sec, add_special_tokens=False)["input_ids"]
            if len(tokens) <= self.target_tokens:
                chunks.append(Chunk(text=sec, index=idx, tokens=len(tokens)))
                idx += 1
            else:
                for s in self._fallback.chunk(sec):
                    chunks.append(Chunk(text=s.text, index=idx, tokens=s.tokens))
                    idx += 1
        return chunks


# =============================================================================
# Code source (indexation par symboles : fonctions / classes)
# =============================================================================

# Chaque pattern détecte l'entête d'un symbole de haut niveau (colonne 0, pas
# d'indentation) et capture son nom dans le groupe nommé `name`. Approche
# heuristique par regex — pas un vrai parseur AST — volontairement tolérante :
# mieux vaut un découpage imparfait par symbole qu'une fenêtre glissante aveugle
# qui coupe une fonction en deux.
_PY_SYMBOL_PATTERNS = [
    re.compile(r"^(?:async\s+)?(?:def|class)\s+(?P<name>\w+)", re.MULTILINE),
]

_JS_SYMBOL_PATTERNS = [
    re.compile(
        r"^(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*\*?\s+(?P<name>\w+)",
        re.MULTILINE,
    ),
    re.compile(r"^(?:export\s+(?:default\s+)?)?class\s+(?P<name>\w+)", re.MULTILINE),
    re.compile(
        r"^(?:export\s+)?const\s+(?P<name>\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::[^=]+)?=>",
        re.MULTILINE,
    ),
]

_GO_SYMBOL_PATTERNS = [
    re.compile(r"^func\s+(?:\([^)]*\)\s*)?(?P<name>\w+)", re.MULTILINE),
]

# Java / C# / C++ : pas de mot-clé unique comme `def`/`func`, on repère soit une
# déclaration de classe/interface, soit une signature `modifiers type nom(...)`.
_C_FAMILY_SYMBOL_PATTERNS = [
    re.compile(
        r"^(?:(?:public|private|protected|internal|static|final|abstract|sealed|partial)\s+)*"
        r"(?:class|interface|struct|enum)\s+(?P<name>\w+)",
        re.MULTILINE,
    ),
    re.compile(
        r"^(?:(?:public|private|protected|internal|static|final|virtual|override|async|abstract)\s+)+"
        r"[\w:<>\[\],.]+\s+(?P<name>\w+)\s*\([^;{}]*\)\s*\{?\s*$",
        re.MULTILINE,
    ),
]

_LANGUAGE_SYMBOL_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "python": _PY_SYMBOL_PATTERNS,
    "javascript": _JS_SYMBOL_PATTERNS,
    "go": _GO_SYMBOL_PATTERNS,
    "java": _C_FAMILY_SYMBOL_PATTERNS,
    "csharp": _C_FAMILY_SYMBOL_PATTERNS,
    "cpp": _C_FAMILY_SYMBOL_PATTERNS,
}

_LANGUAGE_ALIASES = {
    "py": "python",
    "python": "python",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "javascript",
    "tsx": "javascript",
    "javascript": "javascript",
    "typescript": "javascript",
    "go": "go",
    "golang": "go",
    "java": "java",
    "cs": "csharp",
    "c#": "csharp",
    "csharp": "csharp",
    "cpp": "cpp",
    "c++": "cpp",
    "c": "cpp",
}

_EXTENSION_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".go": "go",
    ".java": "java",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".h": "cpp",
    ".c": "cpp",
}

# En dessous de ce nombre de tokens, on ne se donne pas la peine de découper
# par symbole : le fichier est trop court, un seul chunk générique suffit.
_CODE_MIN_TOKENS_FOR_SYMBOL_SPLIT = 10


def _find_symbol_headers(text: str, patterns: list[re.Pattern[str]]) -> list[tuple[int, str]]:
    """Retourne les positions (offset, nom) des entêtes de symboles détectés."""
    found: dict[int, str] = {}
    for pat in patterns:
        for m in pat.finditer(text):
            start = m.start()
            if start not in found:
                found[start] = m.groupdict().get("name") or "symbole"
    return sorted(found.items())


def _extend_for_decorators(text: str, positions: list[int]) -> list[int]:
    """Étend chaque position en arrière pour englober les décorateurs/annotations
    (`@decorateur` Python, `@Override` Java) qui précèdent immédiatement le
    symbole — ils lui appartiennent sémantiquement, pas au symbole précédent.
    """
    lines = text.splitlines(keepends=True)
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)
    offset_to_idx = {s: i for i, s in enumerate(starts)}

    extended: list[int] = []
    for pos in positions:
        idx = offset_to_idx.get(pos)
        if idx is None:
            extended.append(pos)
            continue
        while idx > 0 and lines[idx - 1].strip().startswith("@"):
            idx -= 1
        extended.append(starts[idx])
    return extended


class CodeChunker:
    """Chunker pour code source : 1 chunk = 1 symbole de haut niveau.

    Stratégie : on détecte les entêtes de fonctions/classes de haut niveau
    (colonne 0, pas d'indentation) via des heuristiques regex par langage
    (Python, JS/TS, Go, Java/C#/C++) — pas un vrai parseur AST. Chaque symbole
    devient un chunk avec son corps jusqu'au prochain symbole de même niveau.

    - Un symbole qui dépasse `target_tokens` est re-découpé via le `fallback`
      générique (sliding window), en conservant l'entête `# symbole` sur
      chaque sous-chunk.
    - Les petits fragments consécutifs (imports, constantes, petites
      fonctions) sont regroupés dans un même chunk tant que la somme reste
      ≤ `target_tokens`, pour éviter une avalanche de micro-chunks.
    - Chaque chunk est préfixé d'un entête `# symbole: <nom>` (et
      `# fichier: <path>` si `file_path` est fourni) pour rester citable hors
      contexte après retrieval.

    Fallback complet sur le `Chunker` générique si aucun symbole n'est détecté
    (fichier de config, markdown, langage non reconnu) ou si le texte est trop
    court pour justifier un découpage par symbole.
    """

    def __init__(
        self,
        target_tokens: int = 512,
        overlap_tokens: int = 64,
        fallback: Chunker | None = None,
        language: str | None = None,
        file_path: str | None = None,
    ) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self._fallback = fallback or Chunker(target_tokens, overlap_tokens)
        self.language = language
        self.file_path = file_path

    def _resolve_patterns(self) -> list[re.Pattern[str]]:
        if self.language:
            key = _LANGUAGE_ALIASES.get(self.language.strip().lower())
            if key and key in _LANGUAGE_SYMBOL_PATTERNS:
                return _LANGUAGE_SYMBOL_PATTERNS[key]
        if self.file_path:
            ext = Path(self.file_path).suffix.lower()
            key = _EXTENSION_LANGUAGE.get(ext)
            if key:
                return _LANGUAGE_SYMBOL_PATTERNS[key]
        # Langage inconnu : on tente toutes les heuristiques (détection générique
        # multi-langages) plutôt que d'abandonner tout de suite au fallback.
        combined: list[re.Pattern[str]] = []
        for patterns in _LANGUAGE_SYMBOL_PATTERNS.values():
            combined.extend(patterns)
        return combined

    def _render(self, names: list[str], bodies: list[str]) -> str:
        header = f"# fichier: {self.file_path}\n" if self.file_path else ""
        parts = [f"# symbole: {name}\n{body}" for name, body in zip(names, bodies, strict=False)]
        return header + "\n\n".join(parts)

    def chunk(self, text: str) -> list[Chunk]:
        if not text or not text.strip():
            return []

        self._fallback._ensure_tokenizer()
        tok = self._fallback._tokenizer
        assert tok is not None

        def _count(s: str) -> int:
            return len(tok(s, add_special_tokens=False)["input_ids"])

        if _count(text) <= _CODE_MIN_TOKENS_FOR_SYMBOL_SPLIT:
            _log.info("code.fallback_generic", reason="text too short")
            return self._fallback.chunk(text)

        patterns = self._resolve_patterns()
        headers = _find_symbol_headers(text, patterns)
        if not headers:
            _log.info("code.fallback_generic", reason="no symbol detected", language=self.language)
            return self._fallback.chunk(text)

        positions = _extend_for_decorators(text, [p for p, _ in headers])
        names = [n for _, n in headers]

        # Dédoublonnage : deux entêtes qui, après extension pour décorateurs,
        # pointent vers la même ligne (ex. décorateur partagé mal détecté).
        dedup_positions: list[int] = []
        dedup_names: list[str] = []
        for pos, name in zip(positions, names, strict=False):
            if dedup_positions and dedup_positions[-1] == pos:
                continue
            dedup_positions.append(pos)
            dedup_names.append(name)

        segments: list[tuple[str, str]] = []
        if dedup_positions[0] > 0:
            prelude = text[: dedup_positions[0]].strip()
            if prelude:
                segments.append(("prélude", prelude))

        bounds = [*dedup_positions, len(text)]
        for i, name in enumerate(dedup_names):
            body = text[bounds[i] : bounds[i + 1]].strip()
            if body:
                segments.append((name, body))

        chunks: list[Chunk] = []
        idx = 0
        buffer_names: list[str] = []
        buffer_bodies: list[str] = []
        buffer_tokens = 0

        def _flush() -> None:
            nonlocal buffer_names, buffer_bodies, buffer_tokens, idx
            if not buffer_bodies:
                return
            rendered = self._render(buffer_names, buffer_bodies)
            chunks.append(Chunk(text=rendered, index=idx, tokens=_count(rendered)))
            idx += 1
            buffer_names, buffer_bodies, buffer_tokens = [], [], 0

        for name, body in segments:
            body_tokens = _count(body)
            if body_tokens > self.target_tokens:
                _flush()
                # Symbole trop volumineux : re-découpe via le fallback générique,
                # en conservant l'entête `# symbole` sur chaque sous-chunk.
                for sub in self._fallback.chunk(body):
                    sub_text = self._render([name], [sub.text])
                    chunks.append(Chunk(text=sub_text, index=idx, tokens=_count(sub_text)))
                    idx += 1
                continue
            if buffer_bodies and buffer_tokens + body_tokens > self.target_tokens:
                _flush()
            buffer_names.append(name)
            buffer_bodies.append(body)
            buffer_tokens += body_tokens

        _flush()
        return chunks


# =============================================================================
# Registry — sélection du chunker selon le domaine
# =============================================================================

CHUNKER_REGISTRY = {
    "accounting": AccountingChunker,
    "legal_clause": LegalClauseChunker,
    "legal_article": LegalArticleChunker,
    "medical_case": MedicalCaseChunker,
    "code": CodeChunker,
}


def get_specialized_chunker(
    domain: str,
) -> (
    AccountingChunker | LegalClauseChunker | LegalArticleChunker | MedicalCaseChunker | CodeChunker
):
    """Retourne une instance de chunker selon le domaine. ValueError si inconnu."""
    cls = CHUNKER_REGISTRY.get(domain)
    if cls is None:
        raise ValueError(
            f"Domaine de chunking inconnu: {domain!r}. "
            f"Connus: {list(CHUNKER_REGISTRY)}. Utilise zolaos.rag.chunking.Chunker pour le générique."
        )
    return cls()
