"""SIRH — génération d'artefacts RH (fusion déterministe + composition de prompts).

Doctrine : la **fusion** (contrats en masse) est 100% déterministe (gabarit +
substitution), donc testable. La **rédaction libre** (fiche de poste, grille,
annonce, plan) est déléguée au LLM : ici on compose un **prompt structuré**
depuis les référentiels (RME/RMC) ; le frontend l'envoie à l'agent RH et la
sortie est un **brouillon à valider**.
"""

from __future__ import annotations

from typing import Any

# Gabarit de contrat par défaut (placeholders {{cle}}).
DEFAULT_CONTRAT_TEMPLATE = (
    "CONTRAT DE TRAVAIL ({{type_contrat}})\n\n"
    "Entre l'employeur {{employeur}} et {{nom_complet}} (matricule {{matricule}}),\n"
    "il est convenu ce qui suit :\n"
    "- Poste : {{poste}}\n"
    "- Date de prise de fonction : {{date_debut}}\n"
    "- Rémunération mensuelle brute : {{salaire_xaf}} XAF\n\n"
    "Fait à {{lieu}}, le {{date_edition}}.\n"
    "(Projet — à faire valider par un juriste avant signature.)"
)


def merge_template(template: str, rows: list[dict[str, str]]) -> list[str]:
    """Fusion déterministe : pour chaque ligne, remplace {{cle}} par sa valeur."""
    out: list[str] = []
    for row in rows:
        text = template
        for key, value in row.items():
            text = text.replace("{{" + key + "}}", str(value))
        out.append(text)
    return out


def _puces(items: list[Any]) -> str:
    return "\n".join(f"- {x}" for x in items) if items else "- (non renseigné)"


def compose_prompt(type_doc: str, *, context: dict[str, Any]) -> str:
    """Compose un prompt structuré (déterministe) pour l'agent RH."""
    intitule = context.get("intitule", "(emploi)")
    if type_doc == "fiche_poste":
        comps = [
            f"{c.get('intitule', c.get('code_competence'))} (niveau requis {c.get('niveau_requis', '?')}/4)"
            for c in context.get("competences", [])
        ]
        return (
            f"Rédige une **fiche de poste** complète pour l'emploi « {intitule} ».\n"
            f"Mission principale : {context.get('mission', '(à préciser)')}.\n"
            f"Activités clés :\n{_puces(context.get('activites', []))}\n"
            f"Indicateurs (KPIs) :\n{_puces(context.get('kpis', []))}\n"
            f"Compétences requises :\n{_puces(comps)}\n"
            "Structure : finalité, missions, activités, compétences, conditions, rattachement."
        )
    if type_doc == "grille_entretien":
        comps = [
            f"{c.get('intitule', c.get('code_competence'))} (cible niveau {c.get('niveau_requis', '?')}/4)"
            for c in context.get("competences", [])
        ]
        return (
            f"Rédige une **grille d'entretien structurée** pour le poste « {intitule} ».\n"
            f"Évalue chaque compétence sur 4 niveaux (notions→expert), avec questions et "
            f"indicateurs d'observation :\n{_puces(comps)}"
        )
    if type_doc == "annonce":
        return (
            f"Rédige une **annonce de recrutement** attractive pour « {intitule} » "
            f"(contrat {context.get('type_contrat', 'CDI')}, lieu {context.get('lieu', 'CG')}).\n"
            f"Mission : {context.get('mission', '(à préciser)')}. Ton professionnel, conforme "
            "(pas de critère discriminatoire)."
        )
    if type_doc == "plan_recrutement":
        return (
            f"Propose un **plan de recrutement** pour « {intitule} » : étapes du process, "
            "canaux de sourcing adaptés au contexte (Congo-Brazzaville), planning indicatif "
            "et critères de présélection."
        )
    return f"Rédige un document RH de type « {type_doc} » pour « {intitule} »."
