"""Module PII redaction — anonymisation pré-ingestion (V2.2 #52, requalifié bloquant).

Politiques d'anonymisation **par domaine** :

  - `NONE`     : aucune modification (réservé aux corpus PUBLICS : CIM-10, OHADA,
                 CGI officiel, conventions collectives publiées…). Doit être
                 explicitement choisi par l'ingesteur.
  - `GENERIC`  : masque les PII communes universelles (email, téléphone, IBAN,
                 numéro de carte). Sans contexte métier.
  - `FISCAL`   : hash les tiers (clients/fournisseurs) en pseudonymes stables
                 (`FR_xxxxx`, `FO_xxxxx`) — préserve le secret professionnel
                 tout en gardant la cohérence d'analyse comptable.
  - `RH`       : masque noms, prénoms, adresses, numéros ID ; salaires →
                 tranches (`[100k-150k FCFA]`).
  - `MEDICAL`  : masque identité patient + numéros assurés ; **conserve
                 les pathologies, posologies et symptômes** (utiles au RAG santé).

L'**ingesteur DOIT** déclarer une politique. `ingest_text(..., pii_policy=...)`
exige un argument explicite. `PIIRedactionPolicy.NONE` doit être un choix
conscient pour un corpus public.

Couverture regex (Phase 2 MVP) — extensible plus tard avec NER (spaCy / Presidio) :
  - Téléphone CG (+242 6/04xxxxxxx, 0xxxxxxxx)
  - Email
  - IBAN / RIB
  - Numéro de carte (Luhn approximatif)
  - Numéro CNSS CG (matricule)
  - Montants FCFA en chiffres (utilisé seulement par politique RH)
  - Noms propres : heuristique (Title Case 2-3 mots) — imparfait mais utile
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum

from zolaos.core.logging import get_logger

_log = get_logger("zolaos.security.pii")


# =============================================================================
# Politiques
# =============================================================================


class PIIRedactionPolicy(str, Enum):
    NONE = "none"  # corpus public — aucune modification
    GENERIC = "generic"  # PII communes (email, tel, IBAN, carte)
    FISCAL = "fiscal"  # tiers comptables → hash pseudonyme stable
    RH = "rh"  # noms/adresses/ID masqués ; salaires → tranches
    MEDICAL = "medical"  # identité patient masquée ; pathologies conservées


# =============================================================================
# Patterns regex
# =============================================================================

# Téléphone Congo : +242 06xxxxxxx, 04xxxxxxx, 05xxxxxxx (format 9 chiffres après l'indicatif)
# Tolère espaces et tirets.
_PHONE_CG = re.compile(
    r"(?:\+?242[\s.\-]?)?(?:0[4-6])[\s.\-]?\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}",
)

_EMAIL = re.compile(r"[\w._%+\-]+@[\w.\-]+\.[A-Za-z]{2,}", re.IGNORECASE)

# IBAN simplifié (FR, CG, BJ, CM, …) — 15 à 34 alphanum avec espaces optionnels.
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[\s]?(?:[A-Z\d]{4}[\s]?){3,7}[A-Z\d]{0,4}\b")

# Carte bancaire (Luhn approximé : 13-19 chiffres avec espaces/tirets éventuels).
_CARD = re.compile(r"\b(?:\d[\s\-]?){13,19}\b")

# Numéro CNSS CG (matricule type 6-12 chiffres précédé de "CNSS" ou "matricule").
# Tolère des mots de liaison ("est", "n°", ":", "=") entre l'étiquette et le nombre,
# dans la limite de ~12 caractères pour éviter de capturer un nombre trop éloigné.
_CNSS = re.compile(
    # `\b` n'est posé qu'après les alternatives qui se terminent par un caractère
    # de mot (lettre). `matr\.` se termine sur un point, donc pas de \b derrière.
    r"(?:\bCNSS|\bmatricule|matr\.|\bn[°o]\s*CNSS|\bN°\s*affilié)"
    r"(?:\s+\w+){0,2}\s*[:#=]?\s*"
    r"(\d{6,12})\b",
    re.IGNORECASE,
)

# Montants FCFA : capture les nombres suivis de FCFA/XAF/F CFA.
_AMOUNT_FCFA = re.compile(
    r"\b(\d{1,3}(?:[\s.,]\d{3})*(?:[\s.,]\d+)?)\s*(?:F\s*CFA|FCFA|XAF|francs?)\b",
    re.IGNORECASE,
)

# Heuristique noms propres : 2-3 mots Title Case consécutifs (ex: "Jean Mabiala", "Marie-Louise Bantsimba").
# Imparfait (capture "République Démocratique"…) — à compléter par NER plus tard.
_NAME_HEURISTIC = re.compile(
    r"\b([A-ZÉÈÀÂÊÎÔÛÇ][a-zéèàâêîôûç]{2,}(?:[\-' ][A-ZÉÈÀÂÊÎÔÛÇ][a-zéèàâêîôûç]{2,}){1,2})\b"
)

# Stop-list pour éviter des faux positifs courants sur l'heuristique noms.
_NAME_STOPLIST = {
    "République",
    "Brazzaville",
    "Pointe",
    "Noire",
    "Pointe Noire",
    "Pointe-Noire",
    "Code Travail",
    "Code Général",
    "Cour Suprême",
    "Loi Finances",
    "Lingala Kituba",
    "République Démocratique",
    "République Congo",
}


# =============================================================================
# Hash pseudonyme stable (pour FISCAL)
# =============================================================================


def _stable_hash(value: str, prefix: str, length: int = 5) -> str:
    """Hash court et stable. Le même `value` produit toujours le même pseudonyme
    → permet à l'analyse comptable de garder la cohérence (le même client est
    toujours `FR_84920`), sans révéler l'identité."""
    h = hashlib.sha256(value.encode("utf-8")).hexdigest().upper()
    return f"{prefix}_{h[:length]}"


# =============================================================================
# Tranches de salaire (pour RH)
# =============================================================================


def _bucket_amount_fcfa(raw: str) -> str:
    """Transforme un montant FCFA en tranche.
    `raw` est la chaîne capturée (ex: "1 250 000")."""
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return "[XXX FCFA]"
    value = int(digits)
    buckets = [
        (100_000, "<100k FCFA"),
        (250_000, "[100k-250k FCFA]"),
        (500_000, "[250k-500k FCFA]"),
        (1_000_000, "[500k-1M FCFA]"),
        (2_500_000, "[1M-2.5M FCFA]"),
        (5_000_000, "[2.5M-5M FCFA]"),
        (10_000_000, "[5M-10M FCFA]"),
    ]
    for limit, label in buckets:
        if value < limit:
            return label
    return "[>10M FCFA]"


# =============================================================================
# Comptes (statistiques)
# =============================================================================


@dataclass
class RedactionStats:
    """Compteurs de ce qui a été masqué — utile pour audit / observabilité."""

    emails: int = 0
    phones: int = 0
    ibans: int = 0
    cards: int = 0
    cnss: int = 0
    names: int = 0
    amounts: int = 0
    tiers_hashes: dict[str, str] = field(default_factory=dict)  # original → pseudonyme

    def as_dict(self) -> dict[str, int]:
        return {
            "emails": self.emails,
            "phones": self.phones,
            "ibans": self.ibans,
            "cards": self.cards,
            "cnss": self.cnss,
            "names": self.names,
            "amounts": self.amounts,
            "tiers_hashed": len(self.tiers_hashes),
        }


# =============================================================================
# Détection / redaction
# =============================================================================


def _redact_generic(text: str, stats: RedactionStats) -> str:
    """Masque les PII communes universelles."""

    def repl_email(_m: re.Match) -> str:
        stats.emails += 1
        return "[EMAIL]"

    def repl_phone(_m: re.Match) -> str:
        stats.phones += 1
        return "[PHONE]"

    def repl_iban(_m: re.Match) -> str:
        stats.ibans += 1
        return "[IBAN]"

    def repl_card(_m: re.Match) -> str:
        stats.cards += 1
        return "[CARD]"

    def repl_cnss(m: re.Match) -> str:
        stats.cnss += 1
        return f"{m.group(0).split(m.group(1))[0]}[CNSS]"

    text = _EMAIL.sub(repl_email, text)
    text = _PHONE_CG.sub(repl_phone, text)
    text = _IBAN.sub(repl_iban, text)
    text = _CARD.sub(repl_card, text)
    text = _CNSS.sub(repl_cnss, text)
    return text


def _redact_names(text: str, stats: RedactionStats) -> str:
    """Masque les noms propres (heuristique Title Case, avec stop-list)."""

    def repl(m: re.Match) -> str:
        candidate = m.group(1)
        if candidate in _NAME_STOPLIST:
            return candidate
        stats.names += 1
        return "[NOM]"

    return _NAME_HEURISTIC.sub(repl, text)


def _redact_fiscal_tiers(text: str, stats: RedactionStats) -> str:
    """Repère les noms de tiers (clients/fournisseurs) et les remplace par un
    hash pseudonyme stable. Heuristique : Title Case multi-mots, après des
    libellés type 'Client', 'Fournisseur', 'Société', 'SARL', etc.

    Approche pragmatique Phase 2 MVP : on hashe TOUS les Title Case multi-mots,
    en gardant la stop-list. À affiner avec un NER d'entité plus tard.
    """

    def repl(m: re.Match) -> str:
        candidate = m.group(1)
        if candidate in _NAME_STOPLIST:
            return candidate
        pseudo = stats.tiers_hashes.get(candidate)
        if pseudo is None:
            # FR = "tiers" (client OU fournisseur) en MVP. Plus tard, distinguer
            # FR_xxxxx / FO_xxxxx selon contexte (préfixe "Client:" / "Fournisseur:").
            pseudo = _stable_hash(candidate, "FR")
            stats.tiers_hashes[candidate] = pseudo
            stats.names += 1
        return pseudo

    return _NAME_HEURISTIC.sub(repl, text)


def _redact_rh(text: str, stats: RedactionStats) -> str:
    """Politique RH : noms + identifiants + adresses masqués ; salaires → tranches."""
    text = _redact_generic(text, stats)
    text = _redact_names(text, stats)

    def repl_amount(m: re.Match) -> str:
        stats.amounts += 1
        return _bucket_amount_fcfa(m.group(1))

    text = _AMOUNT_FCFA.sub(repl_amount, text)
    return text


def _redact_medical(text: str, stats: RedactionStats) -> str:
    """Politique MÉDICAL : identité patient masquée, pathologies conservées
    (on ne touche pas aux montants ni au vocabulaire médical)."""
    text = _redact_generic(text, stats)
    text = _redact_names(text, stats)
    return text


def _redact_fiscal(text: str, stats: RedactionStats) -> str:
    """Politique FISCAL : tiers hashés (cohérence préservée), PII communes masquées,
    montants **conservés** (essentiels à l'analyse comptable)."""
    text = _redact_generic(text, stats)
    text = _redact_fiscal_tiers(text, stats)
    return text


# =============================================================================
# API publique
# =============================================================================


def redact_text(text: str, policy: PIIRedactionPolicy) -> tuple[str, RedactionStats]:
    """Applique la politique d'anonymisation. Retourne (texte_anonymisé, stats).

    Cas spécial : si `policy == NONE`, retourne le texte tel quel + stats vides.
    Le choix de NONE doit être un acte conscient (corpus public).
    """
    stats = RedactionStats()
    if policy == PIIRedactionPolicy.NONE:
        _log.info("pii.redact", policy=policy.value, action="passthrough")
        return text, stats

    if policy == PIIRedactionPolicy.GENERIC:
        out = _redact_generic(text, stats)
    elif policy == PIIRedactionPolicy.FISCAL:
        out = _redact_fiscal(text, stats)
    elif policy == PIIRedactionPolicy.RH:
        out = _redact_rh(text, stats)
    elif policy == PIIRedactionPolicy.MEDICAL:
        out = _redact_medical(text, stats)
    else:
        raise ValueError(f"Politique inconnue: {policy}")

    _log.info(
        "pii.redact",
        policy=policy.value,
        input_chars=len(text),
        output_chars=len(out),
        stats=stats.as_dict(),
    )
    return out, stats


# =============================================================================
# Garde-fou pour l'ingestion (intégration ingest.py)
# =============================================================================

# Schémas RAG qui contiennent ou peuvent contenir des PII : politique exigée explicitement.
SENSITIVE_SCHEMAS = {"rag_health", "rag_legal", "rag_erp"}


def require_policy_for_ingest(schema: str, policy: PIIRedactionPolicy | None) -> PIIRedactionPolicy:
    """Bloque l'ingestion d'un schéma sensible sans politique explicite.

    Lève ValueError si :
    - le schéma est sensible ET policy est None (oubli) ;
    - le schéma N'est PAS sensible mais une politique non-NONE est passée
      (sur-anonymisation potentielle d'un corpus public).
    """
    if schema in SENSITIVE_SCHEMAS:
        if policy is None:
            raise ValueError(
                f"Schéma RAG sensible ({schema}) : `pii_policy` est obligatoire. "
                f"Choisis explicitement parmi : {[p.value for p in PIIRedactionPolicy]}. "
                f"Utilise PIIRedactionPolicy.NONE uniquement pour un corpus PUBLIC "
                f"(CIM-10, OHADA, CGI officiel)."
            )
        return policy
    # Schéma non sensible : on accepte None (→ NONE par défaut), pas d'imposition.
    return policy or PIIRedactionPolicy.NONE
