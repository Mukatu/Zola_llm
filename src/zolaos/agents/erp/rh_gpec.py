"""SIRH — Référentiels & GPEC (déterministe).

Socle partagé recrutement/développement : RME (emplois), RMC (compétences),
profil requis par emploi, matrice opérationnelle (collaborateur × compétence →
note 0-4). Calculs **déterministes** : tableau croisé, analyse d'écart GPEC,
risque de perte de compétence clé. Le LLM (séparément) génère fiches/grilles/plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel, Field


class EmployeeRef(BaseModel):
    matricule: str
    nom_complet: str
    code_emploi: str | None = None


class SkillRef(BaseModel):
    code_competence: str
    domaine: str = "technique"
    intitule: str = ""


class RoleSkillRef(BaseModel):
    code_emploi: str
    code_competence: str
    niveau_requis: int = Field(default=0, ge=0, le=4)


class EmpSkillRef(BaseModel):
    matricule: str
    code_competence: str
    note: int = Field(default=0, ge=0, le=4)


@dataclass(frozen=True)
class MatrixRow:
    matricule: str
    nom_complet: str
    code_emploi: str | None
    notes: dict[str, int]


@dataclass(frozen=True)
class EcartLigne:
    code_competence: str
    niveau_requis: int
    niveau_detenu: int
    ecart: int


@dataclass(frozen=True)
class GpecEmploye:
    matricule: str
    nom_complet: str
    code_emploi: str | None
    couverture_pct: str
    ecarts: list[EcartLigne] = field(default_factory=list)


@dataclass(frozen=True)
class CompetenceCritique:
    code_competence: str
    experts: int
    requise_par_emplois: int


def matrix(
    employees: list[EmployeeRef],
    skills: list[SkillRef],
    notes: list[EmpSkillRef],
) -> dict[str, object]:
    """Tableau croisé collaborateur × compétence (note 0-4 ; défaut 0)."""
    codes = sorted({s.code_competence for s in skills})
    note_map = {(n.matricule, n.code_competence): n.note for n in notes}
    lignes = [
        MatrixRow(
            matricule=e.matricule,
            nom_complet=e.nom_complet,
            code_emploi=e.code_emploi,
            notes={c: note_map.get((e.matricule, c), 0) for c in codes},
        )
        for e in employees
    ]
    return {
        "competences": codes,
        "lignes": [
            {
                "matricule": row.matricule,
                "nom_complet": row.nom_complet,
                "code_emploi": row.code_emploi,
                "notes": row.notes,
            }
            for row in lignes
        ],
    }


def gpec_gap(
    employees: list[EmployeeRef],
    role_skills: list[RoleSkillRef],
    notes: list[EmpSkillRef],
) -> dict[str, object]:
    """Analyse d'écart GPEC : requis (par emploi) − détenu (matrice)."""
    req_by_emploi: dict[str, list[tuple[str, int]]] = {}
    for rs in role_skills:
        req_by_emploi.setdefault(rs.code_emploi, []).append((rs.code_competence, rs.niveau_requis))
    held = {(n.matricule, n.code_competence): n.note for n in notes}

    par_employe: list[GpecEmploye] = []
    for e in employees:
        requis = req_by_emploi.get(e.code_emploi or "", [])
        ecarts: list[EcartLigne] = []
        atteints = 0
        for code, niveau in requis:
            detenu = held.get((e.matricule, code), 0)
            ecart = max(0, niveau - detenu)
            if ecart == 0:
                atteints += 1
            ecarts.append(EcartLigne(code, niveau, detenu, ecart))
        couverture = (Decimal(atteints) / Decimal(len(requis)) * 100) if requis else Decimal("0")
        par_employe.append(
            GpecEmploye(
                matricule=e.matricule,
                nom_complet=e.nom_complet,
                code_emploi=e.code_emploi,
                couverture_pct=str(couverture.quantize(Decimal("0.1"))),
                ecarts=ecarts,
            )
        )

    # Risque de perte de compétence clé : compétence requise sans expert (note 4).
    experts: dict[str, int] = {}
    for n in notes:
        if n.note >= 4:
            experts[n.code_competence] = experts.get(n.code_competence, 0) + 1
    requise_count: dict[str, int] = {}
    for rs in role_skills:
        requise_count[rs.code_competence] = requise_count.get(rs.code_competence, 0) + 1
    critiques = [
        CompetenceCritique(code, experts.get(code, 0), n)
        for code, n in sorted(requise_count.items())
        if experts.get(code, 0) == 0
    ]

    return {
        "par_employe": [
            {
                "matricule": g.matricule,
                "nom_complet": g.nom_complet,
                "code_emploi": g.code_emploi,
                "couverture_pct": g.couverture_pct,
                "ecarts": [
                    {
                        "code_competence": x.code_competence,
                        "niveau_requis": x.niveau_requis,
                        "niveau_detenu": x.niveau_detenu,
                        "ecart": x.ecart,
                    }
                    for x in g.ecarts
                ],
            }
            for g in par_employe
        ],
        "experts_par_competence": experts,
        "competences_critiques": [
            {
                "code_competence": c.code_competence,
                "experts": c.experts,
                "requise_par_emplois": c.requise_par_emplois,
            }
            for c in critiques
        ],
    }
