"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, ExternalLink } from "lucide-react";
import { Card, Button } from "../ui";
import { ApiError } from "@/lib/api";
import { fmt } from "@/lib/data";
import { getBareme, validateBareme, type Bareme } from "@/lib/bareme";

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

export function BaremePanel() {
  const [b, setB] = useState<Bareme | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [by, setBy] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

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
      const r = await validateBareme({ validated, validated_by: by, note });
      setB(r);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec de l'opération");
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
          {b.country.toUpperCase()} · v{b.version}
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
            <strong>Barème non validé</strong> — valeurs sourcées mais non confirmées sur texte
            primaire. L&apos;émission de bulletins définitifs reste verrouillée tant qu&apos;un
            expert paie/fiscal ne l&apos;a pas validé.
          </>
        )}
      </div>

      {/* Paramètres clés */}
      <div className="mb-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <Mini label="SMIG" value={`${fmt(b.smig_xaf)} XAF`} />
        <Mini label="Abattement" value={pct(b.abattement_irpp_taux)} />
        <Mini label="Plafond parts" value={b.plafond_parts} />
        <Mini label="ITS dès" value={String(b.regime_its_depuis_annee)} />
      </div>

      {/* Régimes d'imposition */}
      <div className="mb-3">
        <div className="mb-1 text-xs font-medium text-muted">Régimes d&apos;imposition</div>
        {Object.entries(b.regimes).map(([cle, reg]) => (
          <div key={cle} className="mb-1 text-sm">
            <span className="font-medium uppercase">{cle}</span>{" "}
            <span className="text-muted">{reg.label}</span> :{" "}
            {reg.bareme
              .map(
                (t) =>
                  `${pct(t.taux)}${t.plafond_xaf ? ` ≤${fmt(t.plafond_xaf)}` : " au-delà"}`,
              )
              .join(" · ")}
          </div>
        ))}
      </div>

      {/* Branches CNSS */}
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

      {/* Sources */}
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

      {/* Action de validation */}
      <div className="rounded-md border border-black/10 p-3">
        <div className="mb-2 text-xs font-medium text-muted">
          Décision de conformité (audité par version)
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="w-40 rounded border border-black/15 px-2 py-1 text-sm"
            placeholder="Validé par (nom)"
            value={by}
            onChange={(e) => setBy(e.target.value)}
          />
          <input
            className="flex-1 rounded border border-black/15 px-2 py-1 text-sm"
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
        {!ok && !by && (
          <div className="mt-1 text-xs text-muted">Renseignez le validateur pour activer.</div>
        )}
      </div>

      {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
    </Card>
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
