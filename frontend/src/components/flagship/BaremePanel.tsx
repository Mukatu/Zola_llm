"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, ExternalLink, Pencil, Plus, Trash2 } from "lucide-react";
import { Card, Button } from "../ui";
import { ApiError } from "@/lib/api";
import { fmt } from "@/lib/data";
import {
  getBareme,
  editBareme,
  validateBareme,
  type Bareme,
  type CnssBranche,
  type BaremeRegime,
} from "@/lib/bareme";

function ConfBadge({ niveau }: { niveau: string }) {
  const n = niveau.toLowerCase();
  const cls =
    n.startsWith("élev") || n.startsWith("elev")
      ? "bg-green-100 text-green-700"
      : n.startsWith("moy")
        ? "bg-amber-100 text-amber-700"
        : "bg-red-100 text-red-700";
  return <span className={`rounded px-1.5 py-0.5 text-xs ${cls}`}>{niveau}</span>;
}

const pct = (t: string) => `${(parseFloat(t) * 100).toFixed(2).replace(/\.00$/, "")} %`;
const I = "rounded border border-black/15 px-2 py-1 text-sm";

interface Draft {
  smig_xaf: string;
  abattement_irpp_taux: string;
  plafond_parts: string;
  impot_minimum_annuel_xaf: string;
  regime_its_depuis_annee: number;
  regimes: Record<string, BaremeRegime>;
  cnss_branches: CnssBranche[];
}

export function BaremePanel() {
  const [b, setB] = useState<Bareme | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [by, setBy] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);

  async function load() {
    try {
      setB(await getBareme());
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Erreur de chargement");
    }
  }
  useEffect(() => {
    void load();
  }, []);

  async function act(validated: boolean) {
    setBusy(true);
    try {
      setB(await validateBareme({ validated, validated_by: by, note }));
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec de l'opération");
    } finally {
      setBusy(false);
    }
  }

  function startEdit() {
    if (!b) return;
    setDraft(
      structuredClone({
        smig_xaf: b.smig_xaf,
        abattement_irpp_taux: b.abattement_irpp_taux,
        plafond_parts: b.plafond_parts,
        impot_minimum_annuel_xaf: b.impot_minimum_annuel_xaf,
        regime_its_depuis_annee: b.regime_its_depuis_annee,
        regimes: b.regimes,
        cnss_branches: b.cnss_branches,
      }),
    );
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    try {
      setB(await editBareme({ ...draft, edited_by: by }));
      setDraft(null);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec de l'enregistrement");
    } finally {
      setBusy(false);
    }
  }

  if (!b) {
    return (
      <Card className="p-4">
        <div className="text-sm text-muted">Barème de paie…</div>
        {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
      </Card>
    );
  }

  const ok = b.effectivement_valide;
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-semibold">
          {ok ? (
            <ShieldCheck className="h-5 w-5 text-green-600" />
          ) : (
            <ShieldAlert className="h-5 w-5 text-amber-600" />
          )}
          Barème de paie · Conformité
        </h3>
        <span className="text-xs text-muted">
          {b.country.toUpperCase()} · v{b.version} ·{" "}
          {b.source_donnees === "tenant" ? "barème édité" : "barème par défaut"}
        </span>
      </div>

      <div
        className={`mb-3 rounded-md border p-3 text-sm ${
          ok ? "border-green-200 bg-green-50" : "border-amber-200 bg-amber-50"
        }`}
      >
        {ok ? (
          <>
            <strong>Barème validé</strong> — émission de bulletins définitifs autorisée.
            {b.validation.validated_by && (
              <span className="text-muted">
                {" "}
                Validé par {b.validation.validated_by}
                {b.validation.validated_at && ` le ${b.validation.validated_at.slice(0, 10)}`}.
              </span>
            )}
          </>
        ) : (
          <>
            <strong>Barème non validé</strong> — l&apos;émission de bulletins définitifs reste
            verrouillée tant qu&apos;un expert paie/fiscal ne l&apos;a pas validé. Toute modification
            du barème ré-active ce verrou.
          </>
        )}
      </div>

      {draft ? (
        <Editor
          draft={draft}
          setDraft={setDraft}
          onSave={save}
          onCancel={() => setDraft(null)}
          busy={busy}
        />
      ) : (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <Mini label="SMIG" value={`${fmt(b.smig_xaf)} XAF`} />
            <Mini label="Abattement" value={pct(b.abattement_irpp_taux)} />
            <Mini label="Plafond parts" value={b.plafond_parts} />
            <Mini label="ITS dès" value={String(b.regime_its_depuis_annee)} />
          </div>

          <div className="mb-3">
            <div className="mb-1 text-xs font-medium text-muted">Régimes d&apos;imposition</div>
            {Object.entries(b.regimes).map(([cle, reg]) => (
              <div key={cle} className="mb-1 text-sm">
                <span className="font-medium uppercase">{cle}</span>{" "}
                <span className="text-muted">{reg.label}</span> :{" "}
                {reg.bareme
                  .map(
                    (t) => `${pct(t.taux)}${t.plafond_xaf ? ` ≤${fmt(t.plafond_xaf)}` : " au-delà"}`,
                  )
                  .join(" · ")}
              </div>
            ))}
          </div>

          <div className="mb-3 overflow-x-auto">
            <div className="mb-1 text-xs font-medium text-muted">Cotisations CNSS</div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th className="pr-2">Branche</th>
                  <th className="pr-2 text-right">Salarié</th>
                  <th className="pr-2 text-right">Employeur</th>
                  <th className="pr-2 text-right">Plafond/mois</th>
                </tr>
              </thead>
              <tbody>
                {b.cnss_branches.map((br) => (
                  <tr key={br.nom} className="border-t border-black/5">
                    <td className="py-1 pr-2">{br.label || br.nom}</td>
                    <td className="pr-2 text-right">{pct(br.taux_salarie)}</td>
                    <td className="pr-2 text-right">{pct(br.taux_employeur)}</td>
                    <td className="pr-2 text-right text-muted">
                      {br.plafond_mensuel_xaf ? fmt(br.plafond_mensuel_xaf) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mb-3">
            <div className="mb-1 text-xs font-medium text-muted">Sources</div>
            <ul className="space-y-1 text-sm">
              {b.sources.map((s) => (
                <li key={s.url} className="flex items-center gap-2">
                  <ConfBadge niveau={s.confiance} />
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-blue-600 hover:underline"
                  >
                    {s.label} <ExternalLink className="h-3 w-3" />
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-md border border-black/10 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium text-muted">
                Décision de conformité (auditée par version)
              </span>
              <Button variant="ghost" onClick={startEdit}>
                <Pencil className="h-4 w-4" /> Modifier le barème
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                className={`w-40 ${I}`}
                placeholder="Validé par (nom)"
                value={by}
                onChange={(e) => setBy(e.target.value)}
              />
              <input
                className={`flex-1 ${I}`}
                placeholder="Note (réf. texte, date d'effet…)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              {ok ? (
                <Button variant="ghost" disabled={busy} onClick={() => act(false)}>
                  Révoquer
                </Button>
              ) : (
                <Button disabled={busy || !by} onClick={() => act(true)}>
                  Valider le barème
                </Button>
              )}
            </div>
          </div>
        </>
      )}

      {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
    </Card>
  );
}

function Editor({
  draft,
  setDraft,
  onSave,
  onCancel,
  busy,
}: {
  draft: Draft;
  setDraft: (d: Draft) => void;
  onSave: () => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const patch = (p: Partial<Draft>) => setDraft({ ...draft, ...p });
  const setBranch = (i: number, p: Partial<CnssBranche>) =>
    patch({ cnss_branches: draft.cnss_branches.map((b, j) => (j === i ? { ...b, ...p } : b)) });

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
        Toute modification crée une nouvelle version et exige une nouvelle validation experte
        avant émission. Taux en décimal (0.04 = 4 %).
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Field label="SMIG (XAF)">
          <input
            className={`w-full ${I}`}
            value={draft.smig_xaf}
            onChange={(e) => patch({ smig_xaf: e.target.value })}
          />
        </Field>
        <Field label="Abattement (déc.)">
          <input
            className={`w-full ${I}`}
            value={draft.abattement_irpp_taux}
            onChange={(e) => patch({ abattement_irpp_taux: e.target.value })}
          />
        </Field>
        <Field label="Plafond parts">
          <input
            className={`w-full ${I}`}
            value={draft.plafond_parts}
            onChange={(e) => patch({ plafond_parts: e.target.value })}
          />
        </Field>
        <Field label="ITS dès (année)">
          <input
            className={`w-full ${I}`}
            value={String(draft.regime_its_depuis_annee)}
            onChange={(e) => patch({ regime_its_depuis_annee: parseInt(e.target.value) || 0 })}
          />
        </Field>
      </div>

      {/* Branches CNSS */}
      <div>
        <div className="mb-1 text-xs font-medium text-muted">Cotisations CNSS</div>
        {draft.cnss_branches.map((br, i) => (
          <div key={i} className="mb-1 flex flex-wrap items-center gap-1">
            <input
              className={`w-40 ${I}`}
              placeholder="branche"
              value={br.label || br.nom}
              onChange={(e) => setBranch(i, { label: e.target.value })}
            />
            <input
              className={`w-20 ${I}`}
              title="taux salarié"
              value={br.taux_salarie}
              onChange={(e) => setBranch(i, { taux_salarie: e.target.value })}
            />
            <input
              className={`w-20 ${I}`}
              title="taux employeur"
              value={br.taux_employeur}
              onChange={(e) => setBranch(i, { taux_employeur: e.target.value })}
            />
            <input
              className={`w-28 ${I}`}
              title="plafond mensuel"
              value={br.plafond_mensuel_xaf ?? ""}
              onChange={(e) =>
                setBranch(i, { plafond_mensuel_xaf: e.target.value || null })
              }
            />
            <button
              className="rounded p-1 text-red-600 hover:bg-red-50"
              title="Supprimer"
              onClick={() =>
                patch({ cnss_branches: draft.cnss_branches.filter((_, j) => j !== i) })
              }
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <Button
          variant="ghost"
          onClick={() =>
            patch({
              cnss_branches: [
                ...draft.cnss_branches,
                {
                  nom: `branche_${draft.cnss_branches.length + 1}`,
                  label: "",
                  taux_salarie: "0",
                  taux_employeur: "0",
                  plafond_mensuel_xaf: null,
                },
              ],
            })
          }
        >
          <Plus className="h-4 w-4" /> Ajouter une branche
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <Button disabled={busy} onClick={onSave}>
          Enregistrer
        </Button>
        <Button variant="ghost" disabled={busy} onClick={onCancel}>
          Annuler
        </Button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs text-muted">
      {label}
      <div className="mt-0.5">{children}</div>
    </label>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-black/5 px-3 py-2">
      <div className="text-xs text-muted">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}
