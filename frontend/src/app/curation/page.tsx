"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, Check, X, Loader2, Users } from "lucide-react";
import { Card, Button } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { listCandidates, validateCandidate, rejectCandidate, type Candidate } from "@/lib/commons";

/**
 * Curation du communs (Phase B) — réservé au scope commons:curate.
 * Pré-filtré par k-anonymat : seuls les candidats corroborés (≥ k origines
 * distinctes) sont proposés. Décision humaine : valider ou rejeter. Rien n'est
 * promu ici — un candidat validé attend la Phase C.
 */
export default function CurationPage() {
  const [cands, setCands] = useState<Candidate[] | null>(null);
  const [k, setK] = useState(3);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    try {
      const r = await listCandidates(true);
      setK(r.k_anonymat);
      setCands(r.candidats);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setErr("Réservé aux curateurs (scope commons:curate).");
      else if (e instanceof ApiError && e.status === 401) setErr("Connexion requise.");
      else setErr("Service indisponible.");
      setCands([]);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function decide(id: string, action: "validate" | "reject") {
    setBusy(id);
    try {
      await (action === "validate" ? validateCandidate(id) : rejectCandidate(id));
      setCands((cs) => (cs ?? []).filter((c) => c.id !== id));
    } catch {
      setErr("Action impossible (candidat déjà traité ?).");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-lg font-semibold">Curation du communs</h1>
          <p className="text-sm text-muted">
            Candidats anonymisés, corroborés par ≥ {k} sources distinctes. Votre décision fait foi —
            aucun n&apos;est promu sans validation.
          </p>
        </div>
      </div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {cands === null ? (
        <Card><p className="text-sm text-muted">Chargement…</p></Card>
      ) : cands.length === 0 && !err ? (
        <Card><p className="text-sm text-muted">Aucun candidat éligible pour le moment.</p></Card>
      ) : (
        cands.map((c) => (
          <Card key={c.id} className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs text-muted">
              <span className="rounded-full bg-black/5 px-2 py-0.5 font-medium uppercase tracking-wide">
                {c.type} · {c.domaine}
              </span>
              <span className="flex items-center gap-1" title="origines distinctes">
                <Users className="h-3.5 w-3.5" /> {c.occurrences} sources
              </span>
            </div>
            <div className="rounded-lg bg-black/[0.03] p-2.5 text-sm">
              {c.type === "categorisation" ? (
                <div className="flex items-center gap-2">
                  <code className="rounded bg-black/5 px-1.5 py-0.5">{c.payload.cle}</code>
                  <span className="text-muted">→</span>
                  <code className="rounded bg-primary/10 px-1.5 py-0.5 text-primary">{c.payload.valeur}</code>
                </div>
              ) : (
                <>
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted">Question</div>
                  <div className="mb-2">{c.payload.question}</div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted">Réponse retenue</div>
                  <div className="whitespace-pre-wrap">{c.payload.reponse}</div>
                </>
              )}
            </div>
            <div className="flex justify-end gap-2">
              <Button onClick={() => decide(c.id, "reject")} disabled={busy === c.id} variant="ghost">
                <X className="h-4 w-4" /> Rejeter
              </Button>
              <Button onClick={() => decide(c.id, "validate")} disabled={busy === c.id}>
                {busy === c.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                Valider
              </Button>
            </div>
          </Card>
        ))
      )}
    </div>
  );
}
