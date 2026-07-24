"""Audit de durcissement — checklist déterministe **défensive** (Cyber-1).

À partir de faits de configuration **déclarés** (l'utilisateur renseigne l'état
de son système), le moteur évalue une base de durcissement indicative (inspirée
CIS Benchmarks / ANSSI / NIST CSF) : chaque contrôle → conforme | non conforme |
à vérifier (si non renseigné — jamais fabriqué). Aucune action active, aucun
scan, aucune capacité offensive. Le LLM ne fait que narrer/prioriser.

La base est **indicative** et paramétrable (même doctrine que le barème de paie /
les seuils fintech : jamais de valeur normative figée sans validation experte).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel

# Fonctions NIST CSF (catégories de cadre, non normatives ici).
Fonction = Literal["identify", "protect", "detect", "respond", "recover"]
Severite = Literal["critical", "high", "medium", "low"]
Statut = Literal["conforme", "non_conforme", "a_verifier"]

_RANG_SEVERITE: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class Controle(BaseModel):
    """Un point de durcissement. ``cle`` = fait de config attendu (True = conforme)."""

    cle: str
    libelle: str
    fonction: Fonction
    severite: Severite
    remediation: str


# Base de durcissement indicative (à adapter au contexte CG / valider en cabinet).
# Chaque contrôle est formulé pour que le fait booléen True = bonne pratique.
BASELINE: tuple[Controle, ...] = (
    Controle(
        cle="inventaire_actifs",
        libelle="Inventaire des actifs (matériels, logiciels, comptes) tenu à jour",
        fonction="identify",
        severite="medium",
        remediation="Tenir un inventaire des actifs et des accès ; sans visibilité, pas de protection.",
    ),
    Controle(
        cle="registre_donnees_perso",
        libelle="Registre des traitements de données personnelles (Loi 29-2019)",
        fonction="identify",
        severite="high",
        remediation="Documenter les traitements de données à caractère personnel (base légale, durée, accès).",
    ),
    Controle(
        cle="mfa_admin",
        libelle="Authentification forte (MFA) sur les accès à privilèges",
        fonction="protect",
        severite="critical",
        remediation="Activer le MFA sur les comptes administrateurs et les accès distants.",
    ),
    Controle(
        cle="ssh_root_desactive",
        libelle="Connexion root/administrateur directe désactivée (SSH)",
        fonction="protect",
        severite="high",
        remediation="Interdire la connexion root directe ; passer par un compte nominatif + élévation.",
    ),
    Controle(
        cle="politique_mdp",
        libelle="Politique de mots de passe robuste (longueur, rotation compromis)",
        fonction="protect",
        severite="medium",
        remediation="Imposer des mots de passe longs, uniques ; bloquer les mots de passe compromis.",
    ),
    Controle(
        cle="moindre_privilege",
        libelle="Moindre privilège / séparation des rôles sur les comptes",
        fonction="protect",
        severite="high",
        remediation="Limiter les droits au strict nécessaire ; réviser périodiquement les habilitations.",
    ),
    Controle(
        cle="chiffrement_repos",
        libelle="Chiffrement des données au repos (disques, sauvegardes)",
        fonction="protect",
        severite="high",
        remediation="Chiffrer les supports contenant des données sensibles et les sauvegardes.",
    ),
    Controle(
        cle="tls_applique",
        libelle="TLS/HTTPS imposé sur les services exposés",
        fonction="protect",
        severite="high",
        remediation="Forcer HTTPS/TLS et désactiver les protocoles obsolètes.",
    ),
    Controle(
        cle="pare_feu_deny",
        libelle="Pare-feu en refus par défaut (n'ouvrir que le nécessaire)",
        fonction="protect",
        severite="high",
        remediation="Configurer le pare-feu en deny-by-default ; n'ouvrir que les ports utiles.",
    ),
    Controle(
        cle="correctifs_a_jour",
        libelle="Correctifs de sécurité (OS et applicatifs) appliqués",
        fonction="protect",
        severite="critical",
        remediation="Appliquer les correctifs de sécurité sans délai ; automatiser quand c'est possible.",
    ),
    Controle(
        cle="protection_poste",
        libelle="Protection des postes/serveurs (antivirus / EDR)",
        fonction="detect",
        severite="medium",
        remediation="Déployer une protection endpoint à jour sur postes et serveurs.",
    ),
    Controle(
        cle="journalisation",
        libelle="Journalisation centralisée des accès et événements",
        fonction="detect",
        severite="medium",
        remediation="Centraliser les journaux (authentification, accès) et les conserver.",
    ),
    Controle(
        cle="revue_journaux",
        libelle="Revue périodique des journaux / alertes",
        fonction="detect",
        severite="low",
        remediation="Revoir régulièrement les journaux et définir des alertes sur événements sensibles.",
    ),
    Controle(
        cle="plan_reponse_incident",
        libelle="Plan de réponse à incident documenté",
        fonction="respond",
        severite="medium",
        remediation="Documenter qui fait quoi en cas d'incident ; tester le plan au moins annuellement.",
    ),
    Controle(
        cle="sauvegardes_testees",
        libelle="Sauvegardes réalisées ET restauration testée",
        fonction="recover",
        severite="critical",
        remediation="Sauvegarder régulièrement et **tester les restaurations** ; une sauvegarde non testée n'en est pas une.",
    ),
)


class ConfigAudit(BaseModel):
    """Faits de configuration déclarés. ``None`` = non renseigné (→ à vérifier)."""

    model_config = {"extra": "forbid"}

    inventaire_actifs: bool | None = None
    registre_donnees_perso: bool | None = None
    mfa_admin: bool | None = None
    ssh_root_desactive: bool | None = None
    politique_mdp: bool | None = None
    moindre_privilege: bool | None = None
    chiffrement_repos: bool | None = None
    tls_applique: bool | None = None
    pare_feu_deny: bool | None = None
    correctifs_a_jour: bool | None = None
    protection_poste: bool | None = None
    journalisation: bool | None = None
    revue_journaux: bool | None = None
    plan_reponse_incident: bool | None = None
    sauvegardes_testees: bool | None = None


class Finding(BaseModel):
    cle: str
    libelle: str
    fonction: Fonction
    severite: Severite
    statut: Statut
    remediation: str


class AuditResult(BaseModel):
    score_conformite: Decimal  # % des contrôles évalués qui sont conformes
    nb_conforme: int
    nb_non_conforme: int
    nb_a_verifier: int
    niveau: str  # sévérité max parmi les non-conformités (ou "aucun")
    par_fonction: dict[str, dict[str, int]]  # fonction NIST → {conforme, non_conforme, a_verifier}
    findings: list[Finding]
    reference_cadre: str


def _statut(fait: bool | None) -> Statut:
    if fait is None:
        return "a_verifier"
    return "conforme" if fait else "non_conforme"


def auditer(
    config: ConfigAudit | Mapping[str, bool | None],
    *,
    controles: Sequence[Controle] = BASELINE,
) -> AuditResult:
    """Évalue la base de durcissement sur des faits déclarés (déterministe).

    ``controles`` permet de fournir une base **gouvernée** (sévérités ajustées,
    contrôles désactivés) au lieu de la base indicative par défaut.
    """
    faits = config.model_dump() if isinstance(config, ConfigAudit) else dict(config)

    findings: list[Finding] = []
    par_fonction: dict[str, dict[str, int]] = {}
    nb_conforme = nb_non_conforme = nb_a_verifier = 0
    pire = -1

    for ctrl in controles:
        statut = _statut(faits.get(ctrl.cle))
        findings.append(
            Finding(
                cle=ctrl.cle,
                libelle=ctrl.libelle,
                fonction=ctrl.fonction,
                severite=ctrl.severite,
                statut=statut,
                remediation=ctrl.remediation,
            )
        )
        bucket = par_fonction.setdefault(
            ctrl.fonction, {"conforme": 0, "non_conforme": 0, "a_verifier": 0}
        )
        bucket[statut] += 1
        if statut == "conforme":
            nb_conforme += 1
        elif statut == "non_conforme":
            nb_non_conforme += 1
            pire = max(pire, _RANG_SEVERITE[ctrl.severite])
        else:
            nb_a_verifier += 1

    evalues = nb_conforme + nb_non_conforme
    score = (
        (Decimal(nb_conforme) / Decimal(evalues) * Decimal("100")).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        if evalues > 0
        else Decimal("0")
    )
    niveau = next(k for k, v in _RANG_SEVERITE.items() if v == pire) if pire >= 0 else "aucun"

    # Priorité : non-conformes d'abord (par sévérité décroissante), puis à vérifier.
    ordre_statut = {"non_conforme": 0, "a_verifier": 1, "conforme": 2}
    findings.sort(key=lambda f: (ordre_statut[f.statut], -_RANG_SEVERITE[f.severite]))

    return AuditResult(
        score_conformite=score,
        nb_conforme=nb_conforme,
        nb_non_conforme=nb_non_conforme,
        nb_a_verifier=nb_a_verifier,
        niveau=niveau,
        par_fonction=par_fonction,
        findings=findings,
        reference_cadre=(
            "Base de durcissement indicative (inspirée CIS Benchmarks / ANSSI / NIST CSF) — "
            "défensive, à adapter au contexte et à valider en cabinet."
        ),
    )
