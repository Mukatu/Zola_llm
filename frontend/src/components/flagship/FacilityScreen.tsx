"use client";

import { useCallback, useEffect, useState } from "react";
import { Wrench, Plus, Trash2 } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp, Urg } from "./_shared";
import { ApiError } from "@/lib/api";
import {
  listAssets,
  createAsset,
  deleteAsset,
  listEcheances,
  createEcheance,
  deleteEcheance,
  facilityEcheancier,
  type AssetRec,
  type EcheanceRec,
  type FacilityAlerte,
} from "@/lib/operations";

const TODAY = new Date().toISOString().slice(0, 10);
const DEMO_ASSETS = [
  { id_externe: "V1", libelle: "Camion livraison", type_actif: "vehicule", maintenance_intervalle_jours: 90, derniere_maintenance: "2026-04-01" },
  { id_externe: "G1", libelle: "Groupe électrogène", type_actif: "equipement", maintenance_intervalle_jours: 30, derniere_maintenance: "2026-06-10" },
];
const DEMO_ECHE = [
  { id_externe: "E1", type_echeance: "assurance", libelle: "Assurance flotte", date_echeance: "2026-07-10" },
  { id_externe: "E2", type_echeance: "controle", libelle: "Visite technique camion", date_echeance: "2026-07-02" },
];

export function FacilityScreen() {
  const [assets, setAssets] = useState<AssetRec[]>([]);
  const [echeances, setEcheances] = useState<EcheanceRec[]>([]);
  const [res, setRes] = useState<{ maintenances: FacilityAlerte[]; echeances: FacilityAlerte[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [aForm, setAForm] = useState({ libelle: "", intervalle: "90", derniere: TODAY });
  const [eForm, setEForm] = useState({ libelle: "", type: "assurance", date: TODAY });

  const refresh = useCallback(async () => {
    try {
      const [a, e, r] = await Promise.all([listAssets(), listEcheances(), facilityEcheancier(30)]);
      setAssets(a.assets);
      setEcheances(e.echeances);
      setRes(r);
      setErr(null);
    } catch (er) {
      setErr(er instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function addAsset() {
    if (!aForm.libelle) return;
    try {
      await createAsset({
        id_externe: `A-${Date.now()}`,
        libelle: aForm.libelle,
        maintenance_intervalle_jours: Number(aForm.intervalle) || 0,
        derniere_maintenance: aForm.derniere || null,
      });
      setAForm({ libelle: "", intervalle: "90", derniere: TODAY });
      await refresh();
    } catch {
      setErr("Création actif impossible (backend/DB).");
    }
  }
  async function addEcheance() {
    if (!eForm.libelle) return;
    try {
      await createEcheance({ id_externe: `E-${Date.now()}`, type_echeance: eForm.type, libelle: eForm.libelle, date_echeance: eForm.date });
      setEForm({ libelle: "", type: eForm.type, date: TODAY });
      await refresh();
    } catch {
      setErr("Création échéance impossible.");
    }
  }
  async function seedDemo() {
    try {
      for (const a of DEMO_ASSETS) await createAsset(a);
      for (const e of DEMO_ECHE) await createEcheance(e);
      await refresh();
    } catch {
      setErr("Initialisation de la démo impossible.");
    }
  }

  const items = res ? [...res.maintenances, ...res.echeances].sort((a, b) => a.jours_restants - b.jours_restants) : [];
  const isEmpty = assets.length === 0 && echeances.length === 0;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={Wrench} title="Moyens Généraux" subtitle="Registre des actifs + échéancier (maintenance préventive, assurances, contrôles) — persistant." />

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {isEmpty && (
        <Card>
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-muted">Aucun actif ni échéance. Registre <b>persistant</b> : chargez une démo.</p>
            <Button onClick={seedDemo}><Plus className="h-4 w-4" /> Charger une démo</Button>
          </div>
        </Card>
      )}

      {/* Échéancier */}
      {items.length > 0 && (
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Échéancier (30 j)</h2>
          {items.map((a) => (
            <div key={a.categorie + a.reference} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span className="flex items-center gap-2"><Urg level={a.urgence} /> {a.libelle} <span className="text-xs text-muted">({a.categorie})</span></span>
              <span className="text-muted">{a.date_cible} · {a.jours_restants < 0 ? `${-a.jours_restants} j de retard` : `dans ${a.jours_restants} j`}</span>
            </div>
          ))}
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Actifs */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Actifs (maintenance préventive)</h2>
          <div className="mb-2 grid grid-cols-[1fr_70px_120px_36px] gap-2">
            <Inp value={aForm.libelle} onChange={(v) => setAForm({ ...aForm, libelle: v })} placeholder="Actif" />
            <Inp value={aForm.intervalle} type="number" onChange={(v) => setAForm({ ...aForm, intervalle: v })} placeholder="Inter." />
            <Inp value={aForm.derniere} type="date" onChange={(v) => setAForm({ ...aForm, derniere: v })} />
            <button onClick={addAsset} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {assets.map((a) => (
            <div key={a.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span><b>{a.libelle}</b> <span className="text-xs text-muted">{a.maintenance_intervalle_jours} j</span></span>
              <button onClick={() => deleteAsset(a.id).then(refresh)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </Card>

        {/* Échéances */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Échéances</h2>
          <div className="mb-2 grid grid-cols-[1fr_110px_120px_36px] gap-2">
            <Inp value={eForm.libelle} onChange={(v) => setEForm({ ...eForm, libelle: v })} placeholder="Libellé" />
            <select value={eForm.type} onChange={(e) => setEForm({ ...eForm, type: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              {["assurance", "controle", "contrat", "autre"].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <Inp value={eForm.date} type="date" onChange={(v) => setEForm({ ...eForm, date: v })} />
            <button onClick={addEcheance} className="grid place-items-center rounded-lg bg-primary text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {echeances.map((e) => (
            <div key={e.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span><b>{e.libelle}</b> <span className="text-xs text-muted">{e.type_echeance} · {e.date_echeance}</span></span>
              <button onClick={() => deleteEcheance(e.id).then(refresh)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
