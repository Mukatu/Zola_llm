"""Tests unitaires du squelette GED (zolaos.ged.skeleton.build_skeleton).

Génération déterministe, sans LLM : un titre puis, pour chaque section, un
en-tête et — si fournie — une consigne en italique.
"""

from __future__ import annotations

from zolaos.ged.skeleton import build_skeleton


def test_build_skeleton_title_sections_and_guidance() -> None:
    md = build_skeleton(
        "R",
        [
            {"title": "Contexte", "guidance": "g"},
            {"title": "Constats"},
        ],
    )
    assert "# R" in md
    assert "## Contexte" in md
    assert "_g_" in md
    assert "## Constats" in md


def test_build_skeleton_section_without_guidance_has_no_italic_line() -> None:
    md = build_skeleton("Note", [{"title": "Constats"}])
    assert "## Constats" in md
    assert "_" not in md


def test_build_skeleton_empty_sections_has_only_title() -> None:
    md = build_skeleton("Vide", [])
    assert md.strip() == "# Vide"
    assert "##" not in md
