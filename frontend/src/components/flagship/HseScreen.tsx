"use client";

import { useCallback, useEffect, useState } from "react";
import { HardHat, Plus, Trash2, AlertTriangle } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { ApiError } from "@/lib/api";
import {
  listRisques,
  createRisque,
  deleteRisque,
  hseCartographie,
  listIncidents,
  createIncident,
  deleteIncident,
  hseIndicators,
  type RisqueRec,
  type RisqueEvalue,
  type IncidentRec,
  type HseIndicators,
} from "@/lib/operations";

const TODAY = new Date().toISOString().slice(0, 10);
const DEMO_RISQUES = [
  { id_externe: "R1", libelle: "Incendie atelier", probabilite: 2, gravite: 4 },
  { id_externe: "R2", libelle: "Électrocution", probabilite: 5, gravite: 4 },
  { id_externe: "R3", libelle: "TMS bureau", probabilite: 3, gravite: 2 },
];

export function HseScreen() {
  const [risques, setRisques] = useState<RisqueRec[]>([]);
  const [carto, setCarto] = useState<RisqueEvalue[]>([]);
  const [incidents, setIncidents] = useState<IncidentRec[]>([]);
  const [indic, setIndic] = useState<HseIndicators | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [rForm, setRForm] = useState({ libelle: "", probabilite: "3", gravite: "3" });
  const [iForm, setIForm] = useState({ gravite: "mineur", jours: "0" });

  const refresh = useCallback(async () => {
    try {
      const [r, c, i, ind] = await Promise.all([
        listRisques(),
        hseCartographie(),
        listIncidents(),
        hseIndicators(200000),
      ]);
      setRisques(r.risques);
      setCarto(c.risques);
      setIncidents(i.incidents);
      setIndic(ind);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function addRisque() {
    if (!rForm.libelle) return;
    try {
      await createRisque({
        id_externe: `R-${Date.now()}`,
        libelle: rForm.libelle,
        probabilite: Number(rForm.probabilite) || 1,
        gravite: Number(rForm.gravite) || 1,
      });
      setRForm({ libelle: "", probabilite: "3", gravite: "3" });
      await refresh();
    } catch {
      setErr("Création risque impossible (backend/DB).");
    }
  }
  async function addIncident() {
    try {
      await createIncident({
        id_externe: `I-${Date.now()}`,
        date_incident: TODAY,
        gravite: iForm.gravite,
        jours_arret: Number(iForm.jours) || 0,
      });
      setIForm({ gravite: "mineur", jours: "0" });
      await refresh();
    } catch {
      setErr("Déclaration d'incident impossible.");
    }
  }
  async function seedDemo() {
    try {
      for (const r of DEMO_RISQUES) await createRisque(r);
      await refresh();
    } catch {
      setErr("Initialisation de la démo impossible.");
    }
  }

  const critByRef = Object.fromEntries(carto.map((c) => [c.reference, c]));
  const isEmpty = risques.length === 0 && incidents.length === 0;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={HardHat} title="HSE / RSE" subtitle="Cartographie des risques (criticité = probabilité × gravité) + journal des incidents — persistant." />

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {indic && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Risques" value={String(risques.length)} />
          <Kpi label="Incidents" value={String(indic.statistiques.total ?? 0)} />
          <Kpi label="Taux de fréquence" value={indic.taux_frequence} />
          <Kpi label="Taux de gravité" value={indic.taux_gravite} />
        </div>
      )}

      {isEmpty && (
        <Card>
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-muted">Aucun risque ni incident. Registre <b>persistant</b> : chargez une démo.</p>
            <Button onClick={seedDemo}><Plus className="h-4 w-4" /> Charger une démo</Button>
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Risques + criticité */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Cartographie des risques</h2>
          <div className="mb-2 grid grid-cols-[1fr_60px_60px_36px] gap-2">
            <Inp value={rForm.libelle} onChange={(v) => setRForm({ ...rForm, libelle: v })} placeholder="Risque" />
            <Inp value={rForm.probabilite} type="number" onChange={(v) => setRForm({ ...rForm, probabilite: v })} placeholder="P" />
            <Inp value={rForm.gravite} type="number" onChange={(v) => setRForm({ ...rForm, gravite: v })} placeholder="G" />
            <button onClick={addRisque} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {[...risques]
            .sort((a, b) => (critByRef[b.id_externe]?.criticite ?? 0) - (critByRef[a.id_externe]?.criticite ?? 0))
            .map((r) => {
              const c = critByRef[r.id_externe];
              return (
                <div key={r.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
                  <span className="flex items-center gap-2">{c && <Urg level={c.niveau} />} {r.libelle} <span className="text-xs text-muted">P{r.probabilite}×G{r.gravite}</span></span>
                  <span className="flex items-center gap-2 text-muted">
                    criticité <b className="text-ink">{c?.criticite ?? r.probabilite * r.gravite}</b>
                    <button onClick={() => deleteRisque(r.id).then(refresh)} className="hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
                  </span>
                </div>
              );
            })}
        </Card>

        {/* Incidents */}
        <Card>
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold"><AlertTriangle className="h-4 w-4 text-amber-600" /> Incidents</h2>
          <div className="mb-2 grid grid-cols-[1fr_90px_36px] gap-2">
            <select value={iForm.gravite} onChange={(e) => setIForm({ ...iForm, gravite: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              {["mineur", "grave", "critique"].map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
            <Inp value={iForm.jours} type="number" onChange={(v) => setIForm({ ...iForm, jours: v })} placeholder="j arrêt" />
            <button onClick={addIncident} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {incidents.length === 0 && <p className="text-sm text-muted">Aucun incident déclaré.</p>}
          {incidents.map((i) => (
            <div key={i.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span><b>{i.gravite}</b> <span className="text-xs text-muted">{i.date_incident} · {i.jours_arret} j arrêt</span></span>
              <button onClick={() => deleteIncident(i.id).then(refresh)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </Card>
  );
}
