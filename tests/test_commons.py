"""Commons niveau 3 — Phase A : anonymisation + extraction (unitaire, pur)."""

from __future__ import annotations

from zolaos.commons.anonymize import anonymize, content_hash
from zolaos.commons.extraction import feedback_to_candidate, scope_allowed


def test_anonymize_masque_les_identifiants() -> None:
    txt = "Contact jean@exemple.cg au 06 12 34 56 78 pour le dossier."
    out = anonymize(txt)
    assert "[EMAIL]" in out and "[PHONE]" in out
    assert "jean@exemple.cg" not in out


def test_content_hash_stable_et_discriminant() -> None:
    a = {"question": "q", "reponse": "r"}
    assert content_hash(a) == content_hash({"reponse": "r", "question": "q"})  # ordre indépendant
    assert content_hash(a) != content_hash({"question": "q", "reponse": "r2"})


def test_scope_allowed() -> None:
    assert scope_allowed(False, ["legal"], "legal.ohada") is False  # opt-in coupé
    assert scope_allowed(True, ["legal"], "legal.ohada") is True  # pôle autorisé
    assert scope_allowed(True, ["compta"], "legal.ohada") is False  # hors périmètre


def _fb(**kw: object) -> dict[str, object]:
    base = {
        "agent": "legal.ohada",
        "query": "Quel préavis ?",
        "response": "Trois mois.",
        "verdict": "up",
        "correction": None,
    }
    base.update(kw)
    return base


def test_candidate_none_si_opt_out() -> None:
    assert feedback_to_candidate(_fb(), enabled=False, scopes=["legal"]) is None


def test_candidate_qa_si_verdict_up() -> None:
    c = feedback_to_candidate(_fb(), enabled=True, scopes=["legal"])
    assert c is not None and c.type == "qa"
    assert c.domaine == "legal.ohada"
    # anonymat par construction : pas de tenant ni de lien source dans le payload
    assert set(c.payload) == {"domaine", "question", "reponse"}


def test_candidate_correction_prioritaire() -> None:
    c = feedback_to_candidate(_fb(correction="Citer l'article 15."), enabled=True, scopes=["legal"])
    assert c is not None and c.type == "correction"
    assert "article 15" in c.payload["reponse"].lower()


def test_candidate_none_si_down_sans_correction() -> None:
    assert feedback_to_candidate(_fb(verdict="down"), enabled=True, scopes=["legal"]) is None


def test_candidate_anonymise_la_question() -> None:
    c = feedback_to_candidate(
        _fb(query="Le contrat de jean@x.cg ?"), enabled=True, scopes=["legal"]
    )
    assert c is not None
    assert "jean@x.cg" not in c.payload["question"]
    assert "[EMAIL]" in c.payload["question"]
