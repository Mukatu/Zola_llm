"""Chunkers spécialisés par domaine métier (Polaris-4).

Le `Chunker` générique (sliding window tokens) de `chunking.py` reste valide
pour tout texte non structuré. Ces chunkers spécialisés respectent les
frontières sémantiques d'un domaine :

- `AccountingChunker`  : 1 chunk = N écritures comptables groupées (≤ target_tokens)
- `LegalClauseChunker` : 1 chunk = 1 clause d'un contrat (entête + corps)
- `LegalArticleChunker`: 1 chunk = 1 article d'un texte de loi (CGI, OHADA)
- `MedicalCaseChunker` : 1 chunk = 1 section d'un dossier patient

Chacun retombe automatiquement sur le `Chunker` générique si le pattern attendu
n'est pas détecté dans le texte (fallback robuste — on ne casse jamais
l'ingestion à cause d'un format inattendu).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
        self._fallback._ensure_tokenizer()  # noqa: SLF001
        tok = self._fallback._tokenizer  # noqa: SLF001
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
            _log.info("clause.fallback_generic", reason="not enough clause headers", count=len(positions))
            return self._fallback.chunk(text)

        # Borner par la fin du texte.
        positions.append(len(text))
        clauses = [text[positions[i] : positions[i + 1]].strip() for i in range(len(positions) - 1)]
        clauses = [c for c in clauses if c]

        self._fallback._ensure_tokenizer()  # noqa: SLF001
        tok = self._fallback._tokenizer  # noqa: SLF001
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
# "ARTICLE 100 bis", "Art. L. 1234-5"
_LEGAL_ARTICLE_RE = re.compile(
    r"^(?P<header>(?:Article|ART(?:ICLE)?\.?|Art\.)\s+(?:[LRD]\.?\s*)?\d+(?:[-.]\d+)*(?:\s*(?:bis|ter|quater))?[^\n]{0,80})\s*$",
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
            _log.info("legal_article.fallback_generic", reason="not enough article headers", count=len(positions))
            return self._fallback.chunk(text)

        positions.append(len(text))
        articles = [text[positions[i] : positions[i + 1]].strip() for i in range(len(positions) - 1)]
        articles = [a for a in articles if a]

        self._fallback._ensure_tokenizer()  # noqa: SLF001
        tok = self._fallback._tokenizer  # noqa: SLF001
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
            _log.info("medical.fallback_generic", reason="not enough sections", count=len(positions))
            return self._fallback.chunk(text)

        positions.append(len(text))
        sections = [text[positions[i] : positions[i + 1]].strip() for i in range(len(positions) - 1)]
        sections = [s for s in sections if s]

        self._fallback._ensure_tokenizer()  # noqa: SLF001
        tok = self._fallback._tokenizer  # noqa: SLF001
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
# Registry — sélection du chunker selon le domaine
# =============================================================================

CHUNKER_REGISTRY = {
    "accounting": AccountingChunker,
    "legal_clause": LegalClauseChunker,
    "legal_article": LegalArticleChunker,
    "medical_case": MedicalCaseChunker,
}


def get_specialized_chunker(domain: str) -> AccountingChunker | LegalClauseChunker | LegalArticleChunker | MedicalCaseChunker:
    """Retourne une instance de chunker selon le domaine. ValueError si inconnu."""
    cls = CHUNKER_REGISTRY.get(domain)
    if cls is None:
        raise ValueError(
            f"Domaine de chunking inconnu: {domain!r}. "
            f"Connus: {list(CHUNKER_REGISTRY)}. Utilise zolaos.rag.chunking.Chunker pour le générique."
        )
    return cls()
