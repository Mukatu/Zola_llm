"""Extracteur MITRE ATT&CK (STIX) → texte RAG défensif, sur fixtures inline.

Aucun réseau : les fixtures reproduisent en miniature les deux schémas STIX
de détection qui coexistent selon la version du bundle ATT&CK (cf. docstring
de `scripts/extract_mitre_attack.py`).
"""

from __future__ import annotations

from scripts.extract_mitre_attack import construire_texte

# ---------------------------------------------------------------- fixtures


def _technique(
    stix_id: str,
    attack_id: str,
    nom: str,
    description: str,
    *,
    detection: str | None = None,
    revoked: bool = False,
    deprecated: bool = False,
) -> dict:
    obj: dict = {
        "type": "attack-pattern",
        "id": stix_id,
        "name": nom,
        "description": description,
        "revoked": revoked,
        "x_mitre_deprecated": deprecated,
        "external_references": [
            {
                "source_name": "mitre-attack",
                "url": "https://attack.mitre.org",
                "external_id": attack_id,
            },
            {"source_name": "quelque-blog", "url": "https://example.com"},  # doit être ignoré
        ],
    }
    if detection is not None:
        obj["x_mitre_detection"] = detection
    return obj


def _mitigation(stix_id: str, nom: str, description: str) -> dict:
    return {"type": "course-of-action", "id": stix_id, "name": nom, "description": description}


def _relation_mitigates(source_ref: str, target_ref: str) -> dict:
    return {
        "type": "relationship",
        "relationship_type": "mitigates",
        "source_ref": source_ref,
        "target_ref": target_ref,
        "revoked": False,
    }


def _relation_detects(source_ref: str, target_ref: str) -> dict:
    return {
        "type": "relationship",
        "relationship_type": "detects",
        "source_ref": source_ref,
        "target_ref": target_ref,
        "revoked": False,
    }


# ---------------------------------------------------------------- tests


def test_extraction_basique_id_description_detection_mitigation() -> None:
    """Cas minimal demandé : 1 technique + 1 mitigation + 1 relation `mitigates`
    + 1 `external_reference` → la section produite contient id, description,
    détection et la mitigation liée."""
    technique = _technique(
        "attack-pattern--aaa",
        "T1078",
        "Valid Accounts",
        "Adversaries may obtain and abuse credentials of existing accounts.",
        detection="Monitor for anomalous logon activity across endpoints.",
    )
    mitigation = _mitigation(
        "course-of-action--bbb",
        "Account Use Policies",
        "Configure account lockout and login time restrictions.",
    )
    relation = _relation_mitigates("course-of-action--bbb", "attack-pattern--aaa")

    texte = construire_texte([technique, mitigation, relation])

    assert "T1078 — Valid Accounts" in texte
    assert "Adversaries may obtain and abuse credentials of existing accounts." in texte
    assert "Monitor for anomalous logon activity across endpoints." in texte
    assert "Account Use Policies : Configure account lockout and login time restrictions." in texte
    # le external_reference hors mitre-attack ne doit pas polluer l'identifiant
    assert "quelque-blog" not in texte


def test_detection_via_strategie_et_analytique_quand_champ_absent() -> None:
    """Sans `x_mitre_detection` (schéma ATT&CK récent), la détection provient
    de la relation `detects` (x-mitre-detection-strategy) + l'analytique
    référencée."""
    technique = _technique(
        "attack-pattern--ccc",
        "T1110",
        "Brute Force",
        "Adversaries may use brute force techniques to gain access to accounts.",
    )
    strategie = {
        "type": "x-mitre-detection-strategy",
        "id": "x-mitre-detection-strategy--ddd",
        "name": "Detection Strategy for Brute Force",
        "x_mitre_analytic_refs": ["x-mitre-analytic--eee"],
    }
    analytique = {
        "type": "x-mitre-analytic",
        "id": "x-mitre-analytic--eee",
        "description": "Monitor authentication logs for repeated failed login attempts from a single source.",
    }
    relation = _relation_detects("x-mitre-detection-strategy--ddd", "attack-pattern--ccc")

    texte = construire_texte([technique, strategie, analytique, relation])

    assert "T1110 — Brute Force" in texte
    assert "Monitor authentication logs for repeated failed login attempts" in texte
    assert "(aucune mitigation associée dans les données STIX)" in texte


def test_technique_revoquee_ou_depreciee_est_ignoree() -> None:
    active = _technique("attack-pattern--f1", "T1001", "Data Obfuscation", "desc")
    revoquee = _technique("attack-pattern--f2", "T2000", "Ancienne technique", "desc", revoked=True)
    depreciee = _technique("attack-pattern--f3", "T2001", "Autre ancienne", "desc", deprecated=True)

    texte = construire_texte([active, revoquee, depreciee])

    assert "T1001 — Data Obfuscation" in texte
    assert "T2000" not in texte
    assert "T2001" not in texte


def test_ordre_par_identifiant_attack() -> None:
    """Trié numériquement, y compris les sous-techniques (Txxxx.yyy)."""
    t2 = _technique("attack-pattern--a", "T1002", "B", "desc")
    t1 = _technique("attack-pattern--b", "T1001", "A", "desc")
    sub = _technique("attack-pattern--c", "T1001.001", "A sub", "desc")

    texte = construire_texte([t2, t1, sub])

    pos_1001 = texte.find("T1001 —")
    pos_1001_sub = texte.find("T1001.001 —")
    pos_1002 = texte.find("T1002 —")
    assert -1 < pos_1001 < pos_1001_sub < pos_1002
