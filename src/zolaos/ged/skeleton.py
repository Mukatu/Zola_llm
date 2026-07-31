"""Génération du squelette d'un livrable depuis un modèle (déterministe, markdown).

Sème le contenu initial d'un livrable à partir des sections du modèle : un titre,
puis pour chaque section son en-tête et sa consigne (en italique). Pas de LLM ici —
le squelette est structurel ; la rédaction (assistée par le corpus) viendra ensuite.
"""

from __future__ import annotations

from typing import Any


def build_skeleton(title: str, sections: list[dict[str, Any]]) -> str:
    """Contenu markdown initial : `# titre` + pour chaque section `## titre` + consigne."""
    lines: list[str] = [f"# {title.strip() or 'Livrable'}", ""]
    for s in sections or []:
        section_title = str(s.get("title", "")).strip() or "Section"
        lines.append(f"## {section_title}")
        guidance = str(s.get("guidance", "")).strip()
        if guidance:
            lines.append("")
            lines.append(f"_{guidance}_")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
