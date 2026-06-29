"use client";

import { useState } from "react";
import { CalendarClock, Plus, Trash2 } from "lucide-react";
import { Card, Button } from "../ui";
import { ApiError } from "@/lib/api";
import {
  getVariables,
  saveVariables,
  type HeureSup,
  type PrimePonct,
  type RetenuePonct,
} from "@/lib/payroll";

const I = "rounded border border-black/15 px-2 py-1 text-sm";
const PERIODE_DEFAUT = new Date().toISOString().slice(0, 7);

export function VariablesMoisPanel() {
  const [mat, setMat] = useState("");
  const [periode, setPeriode] = useState(PERIODE_DEFAUT);
  const [hs, setHs] = useState<HeureSup[]>([]);
  const [primes, setPrimes] = useState<PrimePonct[]>([]);
  const [retenues, setRetenues] = useState<RetenuePonct[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!mat.trim()) return;
    setBusy(true);
    try {
      const v = await getVariables(mat.trim(), periode);
      setHs(v.heures_sup);
      setPrimes(v.primes);
      setRetenues(v.retenues);
      setLoaded(true);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    try {
      await saveVariables(mat.trim(), periode, { heures_sup: hs, primes, retenues });
      setOk(true);
      setErr(null);
      setTimeout(() => setOk(false), 1500);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-4">
      <h3 className="mb-3 flex items-center gap-2 font-semibold">
        <CalendarClock className="h-5 w-5" /> Variables du mois (heures sup, primes, retenues)
      </h3>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input className={`w-40 ${I}`} placeholder="Matricule" value={mat} onChange={(e) => setMat(e.target.value)} />
        <input className={I} type="month" value={periode} onChange={(e) => setPeriode(e.target.value)} />
        <Button disabled={busy || !mat.trim()} onClick={load}>
          Charger
        </Button>
      </div>

      {loaded && (
        <div className="space-y-3">
          {/* Heures supplémentaires */}
          <Section title="Heures supplémentaires">
            {hs.map((h, i) => (
              <div key={i} className="flex items-center gap-1">
                <select
                  className={I}
                  value={h.taux}
                  onChange={(e) => setHs(hs.map((x, j) => (j === i ? { ...x, taux: e.target.value } : x)))}
                >
                  <option value="0.10">+10 %</option>
                  <option value="0.25">+25 %</option>
                  <option value="0.50">+50 %</option>
                  <option value="1.00">+100 %</option>
                </select>
                <input
                  className={`w-24 ${I}`}
                  placeholder="heures"
                  value={h.heures}
                  onChange={(e) => setHs(hs.map((x, j) => (j === i ? { ...x, heures: e.target.value } : x)))}
                />
                <Del onClick={() => setHs(hs.filter((_, j) => j !== i))} />
              </div>
            ))}
            <Add label="Ajouter des heures sup" onClick={() => setHs([...hs, { taux: "0.25", heures: "0" }])} />
          </Section>

          {/* Primes ponctuelles */}
          <Section title="Primes ponctuelles">
            {primes.map((p, i) => (
              <div key={i} className="flex flex-wrap items-center gap-1">
                <input className={`w-40 ${I}`} placeholder="libellé" value={p.libelle} onChange={(e) => setPrimes(primes.map((x, j) => (j === i ? { ...x, libelle: e.target.value } : x)))} />
                <input className={`w-24 ${I}`} placeholder="montant" value={p.montant} onChange={(e) => setPrimes(primes.map((x, j) => (j === i ? { ...x, montant: e.target.value } : x)))} />
                <Chk label="imp." checked={p.imposable} onChange={(v) => setPrimes(primes.map((x, j) => (j === i ? { ...x, imposable: v } : x)))} />
                <Chk label="CNSS" checked={p.soumis_cnss} onChange={(v) => setPrimes(primes.map((x, j) => (j === i ? { ...x, soumis_cnss: v } : x)))} />
                <Del onClick={() => setPrimes(primes.filter((_, j) => j !== i))} />
              </div>
            ))}
            <Add label="Ajouter une prime" onClick={() => setPrimes([...primes, { libelle: "", montant: "0", imposable: true, soumis_cnss: true }])} />
          </Section>

          {/* Retenues ponctuelles */}
          <Section title="Retenues ponctuelles">
            {retenues.map((r, i) => (
              <div key={i} className="flex items-center gap-1">
                <input className={`w-40 ${I}`} placeholder="libellé" value={r.libelle} onChange={(e) => setRetenues(retenues.map((x, j) => (j === i ? { ...x, libelle: e.target.value } : x)))} />
                <input className={`w-24 ${I}`} placeholder="montant" value={r.montant} onChange={(e) => setRetenues(retenues.map((x, j) => (j === i ? { ...x, montant: e.target.value } : x)))} />
                <Del onClick={() => setRetenues(retenues.filter((_, j) => j !== i))} />
              </div>
            ))}
            <Add label="Ajouter une retenue" onClick={() => setRetenues([...retenues, { libelle: "", montant: "0" }])} />
          </Section>

          <div className="flex items-center gap-2">
            <Button disabled={busy} onClick={save}>
              Enregistrer
            </Button>
            {ok && <span className="text-sm text-emerald-600">Enregistré.</span>}
            <span className="text-xs text-muted">Réémettez le bulletin de la période pour appliquer.</span>
          </div>
        </div>
      )}

      {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-muted">{title}</div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}
function Del({ onClick }: { onClick: () => void }) {
  return (
    <button className="rounded p-1 text-red-600 hover:bg-red-50" title="Supprimer" onClick={onClick}>
      <Trash2 className="h-4 w-4" />
    </button>
  );
}
function Add({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Button variant="ghost" onClick={onClick}>
      <Plus className="h-4 w-4" /> {label}
    </Button>
  );
}
function Chk({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-1 text-xs text-muted">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}
