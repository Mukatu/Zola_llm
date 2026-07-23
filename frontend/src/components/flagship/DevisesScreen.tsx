"use client";

import { useCallback, useEffect, useState } from "react";
import { Coins, Pencil, ShieldAlert, ShieldCheck } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { ApiError } from "@/lib/api";
import { fmt } from "@/lib/data";
import {
  getFxRates,
  editFxRate,
  validateFxRate,
  fxConvert,
  type FxRate,
  type FxRatesView,
} from "@/lib/fx";

// Traduit les codes d'erreur backend (detail JSON `{"detail": "..."}`) en messages FR.
function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  let detail = e.detail;
  try {
    const parsed = JSON.parse(e.detail) as { detail?: string };
    if (parsed?.detail) detail = parsed.detail;
  } catch {
    /* detail n'est pas du JSON — on garde le texte brut */
  }
  if (detail.includes("devise_base_non_editable")) return "La devise de référence (XAF) n'est pas éditable.";
  if (detail.includes("aucun_taux_tenant_a_valider")) return "Saisir d'abord un taux avant de le valider.";
  if (detail.startsWith("taux_non_valide")) {
    const devise = detail.split(":")[1] ?? "";
    return `Conversion indisponible : taux ${devise} non validé.`;
  }
  return fallback;
}

function formatTaux(v: string | null): string {
  if (v === null) return "—";
  return fmt(v);
}

export function DevisesScreen() {
  const [view, setView] = useState<FxRatesView | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [validatedBy, setValidatedBy] = useState("");

  const [editing, setEditing] = useState<string | null>(null);
  const [draftTaux, setDraftTaux] = useState("");
  const [draftSource, setDraftSource] = useState("");

  const [montant, setMontant] = useState("100");
  const [de, setDe] = useState("EUR");
  const [vers, setVers] = useState("XAF");
  const [convResult, setConvResult] = useState<string | null>(null);
  const [convErr, setConvErr] = useState<string | null>(null);
  const [convBusy, setConvBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const v = await getFxRates();
      setView(v);
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Backend indisponible (taux de change)."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function startEdit(r: FxRate) {
    setEditing(r.devise);
    setDraftTaux(r.taux_vers_xaf ?? "");
    setDraftSource(r.source ?? "");
    setErr(null);
  }
  function cancelEdit() {
    setEditing(null);
    setDraftTaux("");
    setDraftSource("");
  }

  async function saveEdit(devise: string) {
    if (!draftTaux) return;
    setBusy(true);
    try {
      const v = await editFxRate(devise, { taux_vers_xaf: draftTaux, source: draftSource });
      setView(v);
      setErr(null);
      cancelEdit();
    } catch (e) {
      setErr(messageFromError(e, "Échec de l'enregistrement du taux."));
    } finally {
      setBusy(false);
    }
  }

  async function setValidation(devise: string, validated: boolean) {
    setBusy(true);
    try {
      const v = await validateFxRate(devise, { validated, validated_by: validatedBy });
      setView(v);
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Échec de l'opération de validation."));
    } finally {
      setBusy(false);
    }
  }

  async function convert() {
    setConvBusy(true);
    setConvErr(null);
    setConvResult(null);
    try {
      const r = await fxConvert({ montant, de, vers });
      setConvResult(r.resultat);
    } catch (e) {
      setConvErr(messageFromError(e, "Conversion impossible."));
    } finally {
      setConvBusy(false);
    }
  }

  const rates = view?.rates ?? [];

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <FlagshipHeader
        icon={Coins}
        title="Devises / Change"
        subtitle="Taux gouvernés (référence XAF, parité fixe EUR/BEAC) — conversion déterministe ; abstention si un taux n'est pas validé."
      />

      {err && (
        <Card className="ring-amber-200">
          <p className="text-sm text-amber-700">{err}</p>
        </Card>
      )}

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Taux de change ({view?.base ?? "XAF"} de référence)</h2>
          <Inp
            value={validatedBy}
            onChange={setValidatedBy}
            placeholder="Validé par (nom)"
            className="w-40"
          />
        </div>

        {loading ? (
          <p className="text-sm text-muted">Chargement…</p>
        ) : rates.length === 0 ? (
          <p className="text-sm text-muted">Aucun taux disponible.</p>
        ) : (
          <div className="divide-y divide-black/5">
            {rates.map((r) => (
              <div key={r.devise} className="py-2">
                {editing === r.devise ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="w-16 font-semibold">{r.devise}</span>
                    <Inp
                      value={draftTaux}
                      onChange={setDraftTaux}
                      type="number"
                      placeholder="Taux vers XAF"
                      className="w-32"
                    />
                    <Inp
                      value={draftSource}
                      onChange={setDraftSource}
                      placeholder="Source"
                      className="flex-1"
                    />
                    <Button disabled={busy || !draftTaux} onClick={() => saveEdit(r.devise)}>
                      Enregistrer
                    </Button>
                    <Button variant="ghost" disabled={busy} onClick={cancelEdit}>
                      Annuler
                    </Button>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="w-16 font-semibold">{r.devise}</span>
                      <span className="text-sm">
                        {formatTaux(r.taux_vers_xaf)}
                        {r.taux_vers_xaf !== null && <span className="text-muted"> XAF</span>}
                      </span>
                      {r.source && <span className="text-xs text-muted">— {r.source}</span>}
                      <span className="text-xs text-muted">
                        ({r.source_donnees === "tenant" ? "édité" : "par défaut"})
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {r.validated ? (
                        <span className="flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
                          <ShieldCheck className="h-3.5 w-3.5" /> validé
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
                          <ShieldAlert className="h-3.5 w-3.5" /> à valider
                        </span>
                      )}
                      {r.editable && (
                        <>
                          <Button variant="ghost" disabled={busy} onClick={() => startEdit(r)}>
                            <Pencil className="h-4 w-4" /> Modifier
                          </Button>
                          {r.validated ? (
                            <Button
                              variant="ghost"
                              disabled={busy}
                              onClick={() => setValidation(r.devise, false)}
                            >
                              Révoquer
                            </Button>
                          ) : (
                            <Button
                              disabled={busy}
                              onClick={() => setValidation(r.devise, true)}
                            >
                              Valider
                            </Button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h2 className="mb-2 text-sm font-semibold">Convertisseur</h2>
        <div className="flex flex-wrap items-center gap-2">
          <Inp value={montant} onChange={setMontant} type="number" placeholder="Montant" className="w-28" />
          <select
            value={de}
            onChange={(e) => setDe(e.target.value)}
            className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-primary/40"
          >
            {rates.map((r) => (
              <option key={r.devise} value={r.devise}>{r.devise}</option>
            ))}
          </select>
          <span className="text-sm text-muted">vers</span>
          <select
            value={vers}
            onChange={(e) => setVers(e.target.value)}
            className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-primary/40"
          >
            {rates.map((r) => (
              <option key={r.devise} value={r.devise}>{r.devise}</option>
            ))}
          </select>
          <Button disabled={convBusy || !montant} onClick={convert}>
            Convertir
          </Button>
        </div>

        {convResult !== null && (
          <p className="mt-3 text-sm">
            <strong>{fmt(montant)} {de}</strong> = <strong>{fmt(convResult)} {vers}</strong>
          </p>
        )}
        {convErr && (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-2 text-sm text-amber-700">
            {convErr}
          </div>
        )}
      </Card>
    </div>
  );
}
