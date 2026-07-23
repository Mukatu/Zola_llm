"use client";

import { useCallback, useEffect, useState } from "react";
import { FileSignature, Plus, Trash2 } from "lucide-react";
import { Card, SeverityBadge, Skeleton } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { ApiError } from "@/lib/api";
import {
  listMandates,
  createMandate,
  deleteMandate,
  listResolutions,
  createResolution,
  deleteResolution,
  getEcheances,
  type Mandate,
  type Resolution,
  type SecretariatAlerte,
  type FonctionMandat,
  type StatutMandat,
  type TypeReunion,
} from "@/lib/secretariat";

const TODAY = new Date().toISOString().slice(0, 10);

const FONCTIONS: { value: FonctionMandat; label: string }[] = [
  { value: "gerant", label: "Gérant" },
  { value: "administrateur", label: "Administrateur" },
  { value: "president_ca", label: "Président du CA" },
  { value: "directeur_general", label: "Directeur général" },
  { value: "commissaire_comptes", label: "Commissaire aux comptes" },
  { value: "autre", label: "Autre" },
];

const TYPES_REUNION: { value: TypeReunion; label: string }[] = [
  { value: "AGO", label: "AGO" },
  { value: "AGE", label: "AGE" },
  { value: "CA", label: "CA" },
];

const STATUT_LEVEL: Record<StatutMandat, string> = {
  actif: "low",
  expire: "medium",
  revoque: "high",
};

const STATUT_LABEL: Record<StatutMandat, string> = {
  actif: "Actif",
  expire: "Expiré",
  revoque: "Révoqué",
};

function formatDate(v: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleDateString("fr-FR");
}

function fonctionLabel(f: FonctionMandat): string {
  return FONCTIONS.find((o) => o.value === f)?.label ?? f;
}

export function SecretariatScreen() {
  const [mandates, setMandates] = useState<Mandate[]>([]);
  const [resolutions, setResolutions] = useState<Resolution[]>([]);
  const [alertes, setAlertes] = useState<SecretariatAlerte[]>([]);
  const [loading, setLoading] = useState(true);
  const [echLoading, setEchLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [mForm, setMForm] = useState({
    titulaire: "",
    fonction: "gerant" as FonctionMandat,
    date_nomination: TODAY,
    duree_annees: "0",
    organe: "",
  });
  const [rForm, setRForm] = useState({
    type_reunion: "AGO" as TypeReunion,
    date_reunion: TODAY,
    objet: "",
    decision: "",
    reference_pv: "",
  });
  const [dateCloture, setDateCloture] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [m, r] = await Promise.all([listMandates(), listResolutions()]);
      setMandates(m.mandates);
      setResolutions(r.resolutions);
      setErr(null);
    } catch (er) {
      setErr(er instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshEcheances = useCallback(async (dateCl?: string) => {
    setEchLoading(true);
    try {
      const e = await getEcheances({ date_cloture: dateCl || undefined, horizon_jours: 90 });
      setAlertes(e.alertes);
      setErr(null);
    } catch {
      setErr("Calcul de l'échéancier impossible.");
    } finally {
      setEchLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    refreshEcheances();
  }, [refresh, refreshEcheances]);

  async function addMandate() {
    if (!mForm.titulaire || !mForm.date_nomination) return;
    try {
      await createMandate({
        titulaire: mForm.titulaire,
        fonction: mForm.fonction,
        date_nomination: mForm.date_nomination,
        duree_annees: Number(mForm.duree_annees) || 0,
        organe: mForm.organe || null,
      });
      setMForm({ titulaire: "", fonction: "gerant", date_nomination: TODAY, duree_annees: "0", organe: "" });
      await refresh();
    } catch {
      setErr("Création du mandat impossible (backend/DB).");
    }
  }
  async function removeMandate(id: string) {
    try {
      await deleteMandate(id);
      await refresh();
    } catch {
      setErr("Suppression du mandat impossible.");
    }
  }

  async function addResolution() {
    if (!rForm.objet || !rForm.date_reunion) return;
    try {
      await createResolution({
        type_reunion: rForm.type_reunion,
        date_reunion: rForm.date_reunion,
        objet: rForm.objet,
        decision: rForm.decision || null,
        reference_pv: rForm.reference_pv || null,
      });
      setRForm({ type_reunion: "AGO", date_reunion: TODAY, objet: "", decision: "", reference_pv: "" });
      await refresh();
    } catch {
      setErr("Création de la résolution impossible (backend/DB).");
    }
  }
  async function removeResolution(id: string) {
    try {
      await deleteResolution(id);
      await refresh();
    } catch {
      setErr("Suppression de la résolution impossible.");
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <FlagshipHeader
        icon={FileSignature}
        title="Secrétariat sociétaire"
        subtitle="Registre des mandats, résolutions d'AG/CA et échéancier légal AUSCGIE — persistant."
      />

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {/* Registre des mandats */}
      <Card>
        <h2 className="mb-2 text-sm font-semibold">Registre des mandats</h2>
        <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Inp value={mForm.titulaire} onChange={(v) => setMForm({ ...mForm, titulaire: v })} placeholder="Titulaire" />
          <select
            value={mForm.fonction}
            onChange={(e) => setMForm({ ...mForm, fonction: e.target.value as FonctionMandat })}
            className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-primary/40"
          >
            {FONCTIONS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <Inp value={mForm.date_nomination} type="date" onChange={(v) => setMForm({ ...mForm, date_nomination: v })} />
          <Inp value={mForm.duree_annees} type="number" onChange={(v) => setMForm({ ...mForm, duree_annees: v })} placeholder="Durée (années)" />
          <Inp value={mForm.organe} onChange={(v) => setMForm({ ...mForm, organe: v })} placeholder="Organe" />
          <button onClick={addMandate} className="flex items-center justify-center gap-1 rounded-lg bg-forest text-white"><Plus className="h-4 w-4" /> Ajouter</button>
        </div>

        {loading ? (
          <Skeleton className="h-10 w-full" />
        ) : mandates.length === 0 ? (
          <p className="text-sm text-muted">Aucun mandat enregistré.</p>
        ) : (
          mandates.map((m) => (
            <div key={m.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span>
                {m.titulaire} <span className="text-xs text-muted">({fonctionLabel(m.fonction)}{m.organe ? ` · ${m.organe}` : ""})</span>
              </span>
              <span className="flex items-center gap-2 text-muted">
                {formatDate(m.date_nomination)} · {m.duree_annees === 0 ? "indéterminée" : `${m.duree_annees} an(s)`}
                <SeverityBadge level={STATUT_LEVEL[m.statut]} />
                <button onClick={(e) => { e.stopPropagation(); removeMandate(m.id); }} className="text-muted hover:text-red-600">
                  <Trash2 className="h-4 w-4" />
                </button>
              </span>
            </div>
          ))
        )}
      </Card>

      {/* Résolutions (AG/PV) */}
      <Card>
        <h2 className="mb-2 text-sm font-semibold">Résolutions (AG/PV)</h2>
        <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
          <select
            value={rForm.type_reunion}
            onChange={(e) => setRForm({ ...rForm, type_reunion: e.target.value as TypeReunion })}
            className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-primary/40"
          >
            {TYPES_REUNION.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <Inp value={rForm.date_reunion} type="date" onChange={(v) => setRForm({ ...rForm, date_reunion: v })} />
          <Inp value={rForm.objet} onChange={(v) => setRForm({ ...rForm, objet: v })} placeholder="Objet" />
          <Inp value={rForm.decision} onChange={(v) => setRForm({ ...rForm, decision: v })} placeholder="Décision" />
          <Inp value={rForm.reference_pv} onChange={(v) => setRForm({ ...rForm, reference_pv: v })} placeholder="Référence PV" />
          <button onClick={addResolution} className="flex items-center justify-center gap-1 rounded-lg bg-forest text-white"><Plus className="h-4 w-4" /> Ajouter</button>
        </div>

        {loading ? (
          <Skeleton className="h-10 w-full" />
        ) : resolutions.length === 0 ? (
          <p className="text-sm text-muted">Aucune résolution enregistrée.</p>
        ) : (
          resolutions.map((r) => (
            <div key={r.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span>
                <b>{r.type_reunion}</b> {r.objet} {r.reference_pv && <span className="text-xs text-muted">({r.reference_pv})</span>}
              </span>
              <span className="flex items-center gap-2 text-muted">
                {formatDate(r.date_reunion)}
                <button onClick={(e) => { e.stopPropagation(); removeResolution(r.id); }} className="text-muted hover:text-red-600">
                  <Trash2 className="h-4 w-4" />
                </button>
              </span>
            </div>
          ))
        )}
      </Card>

      {/* Échéancier légal */}
      <Card>
        <h2 className="mb-2 text-sm font-semibold">Échéancier légal</h2>
        <div className="mb-2 flex items-center gap-2">
          <Inp value={dateCloture} type="date" onChange={setDateCloture} placeholder="Date de clôture d'exercice" />
          <button
            onClick={() => refreshEcheances(dateCloture)}
            className="flex items-center justify-center gap-1 rounded-lg bg-forest px-3 py-1 text-sm text-white"
          >
            Calculer
          </button>
        </div>

        {echLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : alertes.length === 0 ? (
          <p className="text-sm text-muted">Aucune échéance à venir dans l'horizon considéré.</p>
        ) : (
          alertes.map((a, i) => (
            <div key={`${a.categorie}-${a.reference}-${i}`} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span>{a.libelle}</span>
              <span className="flex items-center gap-2 text-muted">
                {formatDate(a.date_cible)} · {a.jours_restants} j
                <SeverityBadge level={a.urgence} />
              </span>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}
