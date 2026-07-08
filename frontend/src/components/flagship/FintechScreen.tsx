"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import {
  Landmark,
  Gauge,
  ShieldCheck,
  ScanSearch,
  ClipboardList,
  BarChart3,
  Plus,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Save,
  Info,
} from "lucide-react";
import { Card, Button, Skeleton } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { ApiError } from "@/lib/api";
import {
  scoreCredit,
  evaluateKyc,
  evaluateAml,
  createApplication,
  listApplications,
  decideApplication,
  deleteApplication,
  createKycRecord,
  listKycRecords,
  decideKycRecord,
  deleteKycRecord,
  getPortfolio,
  PIECES_KYC,
  type CreditScore,
  type KycResult,
  type AmlResult,
  type TransactionInput,
  type CreditApplication,
  type KycRecordItem,
  type PortfolioStats,
} from "@/lib/fintech";

type Tab = "scoring" | "kyc" | "aml" | "registre" | "pilotage";
const EMPLOIS = ["salarie_public", "salarie_prive", "independant", "informel"];
const SECTEURS = ["", "change_manuel", "immobilier", "transfert_fonds", "or_metaux_precieux", "jeux_paris"];

const fmt = (s: string) => Number(s).toLocaleString("fr-FR");

export function FintechScreen() {
  const [tab, setTab] = useState<Tab>(() => {
    if (typeof window !== "undefined") {
      const t = new URLSearchParams(window.location.search).get("tab");
      if (t === "kyc" || t === "aml" || t === "registre" || t === "pilotage") return t;
    }
    return "scoring";
  });
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader
        icon={Landmark}
        title="Fintech — crédit & conformité"
        subtitle="Scoring de crédit (EMF) et KYC/AML — aide à la décision déterministe et explicable."
      />
      <div className="flex flex-wrap gap-2">
        <TabBtn active={tab === "scoring"} onClick={() => setTab("scoring")} icon={Gauge} label="Scoring crédit" />
        <TabBtn active={tab === "kyc"} onClick={() => setTab("kyc")} icon={ShieldCheck} label="KYC" />
        <TabBtn active={tab === "aml"} onClick={() => setTab("aml")} icon={ScanSearch} label="Surveillance AML" />
        <TabBtn active={tab === "registre"} onClick={() => setTab("registre")} icon={ClipboardList} label="Registre" />
        <TabBtn active={tab === "pilotage"} onClick={() => setTab("pilotage")} icon={BarChart3} label="Pilotage" />
      </div>
      {tab === "scoring" && <ScoringTab />}
      {tab === "kyc" && <KycTab />}
      {tab === "aml" && <AmlTab />}
      {tab === "registre" && <RegistreTab />}
      {tab === "pilotage" && <PilotageTab />}
    </div>
  );
}

// --- Scoring ---------------------------------------------------------------

function ScoringTab() {
  const [f, setF] = useState({
    revenu_mensuel_xaf: "800000",
    charges_mensuelles_xaf: "100000",
    montant_demande_xaf: "1500000",
    duree_mois: 24,
    anciennete_activite_mois: 24,
    incidents_paiement: 0,
    epargne_xaf: "300000",
    garanties_xaf: "1000000",
    type_emploi: "salarie_prive",
  });
  const [client, setClient] = useState("");
  const [res, setRes] = useState<CreditScore | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (v: string) => setF((s) => ({ ...s, [k]: v }));

  async function run() {
    setLoading(true);
    setErr(null);
    setRes(null);
    setSaved(null);
    try {
      setRes(await scoreCredit(f));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Service indisponible.");
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      const rec = await createApplication(client.trim() || "Demandeur", f);
      setSaved(rec.numero);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Enregistrement impossible.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Card className="grid gap-3 sm:grid-cols-2">
        <div className="col-span-full"><Field label="Nom du demandeur"><Inp className="w-full" value={client} onChange={setClient} placeholder="ex : Jean Mabiala" /></Field></div>
        <Field label="Revenu mensuel (XAF)"><Inp className="w-full" value={f.revenu_mensuel_xaf} onChange={set("revenu_mensuel_xaf")} type="number" /></Field>
        <Field label="Charges mensuelles (XAF)"><Inp className="w-full" value={f.charges_mensuelles_xaf} onChange={set("charges_mensuelles_xaf")} type="number" /></Field>
        <Field label="Montant demandé (XAF)"><Inp className="w-full" value={f.montant_demande_xaf} onChange={set("montant_demande_xaf")} type="number" /></Field>
        <Field label="Durée (mois)"><Inp className="w-full" value={String(f.duree_mois)} onChange={(v) => set("duree_mois")(v)} type="number" /></Field>
        <Field label="Ancienneté activité (mois)"><Inp className="w-full" value={String(f.anciennete_activite_mois)} onChange={(v) => set("anciennete_activite_mois")(v)} type="number" /></Field>
        <Field label="Incidents de paiement"><Inp className="w-full" value={String(f.incidents_paiement)} onChange={(v) => set("incidents_paiement")(v)} type="number" /></Field>
        <Field label="Épargne / apport (XAF)"><Inp className="w-full" value={f.epargne_xaf} onChange={set("epargne_xaf")} type="number" /></Field>
        <Field label="Garanties (XAF)"><Inp className="w-full" value={f.garanties_xaf} onChange={set("garanties_xaf")} type="number" /></Field>
        <Field label="Type d'emploi">
          <select value={f.type_emploi} onChange={(e) => set("type_emploi")(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {EMPLOIS.map((x) => <option key={x} value={x}>{x.replace("_", " ")}</option>)}
          </select>
        </Field>
        <div className="col-span-full flex justify-end"><Button onClick={run} disabled={loading}>Évaluer le dossier</Button></div>
      </Card>

      {loading && <Card><Skeleton className="mb-2 h-6 w-1/3" /><Skeleton className="h-4 w-full" /></Card>}
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {res && (
        <Card className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <ScoreDonut score={res.score} grade={res.grade} />
            <div className="flex flex-col gap-1">
              <DecisionBadge decision={res.decision} />
              <div className="text-xs text-muted">Taux d'endettement : <b className="text-ink">{res.taux_endettement_pct} %</b></div>
            </div>
            <div className="ml-auto grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
              <Stat label="Mensualité estimée" value={`${fmt(res.mensualite_estimee_xaf)} XAF`} />
              <Stat label="Montant soutenable" value={`${fmt(res.montant_max_suggere_xaf)} XAF`} />
              <Stat label="Capacité mensuelle" value={`${fmt(res.capacite_remboursement_xaf)} XAF`} />
              <Stat label="Coût du crédit" value={`${fmt(res.cout_total_credit_xaf)} XAF`} />
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Facteurs</div>
            <div className="flex flex-col gap-1.5">
              {res.facteurs.map((x) => (
                <div key={x.code} className="flex items-center gap-3 text-sm">
                  <span className={clsx("h-2 w-2 rounded-full", x.sens === "positif" ? "bg-forest" : x.sens === "negatif" ? "bg-red-500" : "bg-gray-300")} />
                  <span className="w-44 shrink-0 font-medium">{x.libelle}</span>
                  <span className="w-40 shrink-0 text-muted">{x.valeur}</span>
                  <span className="ml-auto tabular-nums font-semibold text-ink">+{x.contribution}</span>
                </div>
              ))}
            </div>
          </div>

          {res.avertissements.length > 0 && (
            <ul className="flex flex-col gap-1 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
              {res.avertissements.map((a, i) => (
                <li key={i} className="flex items-start gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{a}</li>
              ))}
            </ul>
          )}
          {res.bareme_indicatif && (
            <p className="flex items-center gap-1.5 text-xs text-muted"><Info className="h-3.5 w-3.5" /> Barème indicatif paramétrable — aide à la décision, l'octroi reste soumis à l'analyse de l'agent de crédit.</p>
          )}

          <div className="flex items-center gap-3 border-t border-black/5 pt-3">
            <Button onClick={save} disabled={saving}><Save className="h-4 w-4" /> Enregistrer le dossier</Button>
            {saved && <span className="flex items-center gap-1.5 text-sm font-medium text-forest"><CheckCircle2 className="h-4 w-4" /> Enregistré — {saved}</span>}
          </div>
        </Card>
      )}
    </>
  );
}

// --- KYC -------------------------------------------------------------------

function KycTab() {
  const [type, setType] = useState<"particulier" | "entreprise">("particulier");
  const [nom, setNom] = useState("");
  const [pieces, setPieces] = useState<Set<string>>(new Set());
  const [pep, setPep] = useState(false);
  const [sanction, setSanction] = useState(false);
  const [secteur, setSecteur] = useState("");
  const [pays, setPays] = useState("CG");
  const [res, setRes] = useState<KycResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const togglePiece = (id: string) => setPieces((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const profile = () => ({ nom: nom || "Client", type_client: type, pieces_fournies: [...pieces], pep, pays_residence: pays, secteur_activite: secteur || undefined, correspondance_liste: sanction });

  async function run() {
    setLoading(true); setErr(null); setRes(null); setSaved(false);
    try {
      setRes(await evaluateKyc(profile()));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Service indisponible.");
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    setSaving(true); setErr(null);
    try {
      await createKycRecord(profile());
      setSaved(true);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Enregistrement impossible.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Card className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Nom / raison sociale"><Inp className="w-full" value={nom} onChange={setNom} placeholder="ex : Jean Mabiala" /></Field>
          <Field label="Type de client">
            <select value={type} onChange={(e) => { setType(e.target.value as "particulier" | "entreprise"); setPieces(new Set()); }} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              <option value="particulier">Particulier</option>
              <option value="entreprise">Entreprise</option>
            </select>
          </Field>
          <Field label="Secteur d'activité">
            <select value={secteur} onChange={(e) => setSecteur(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              {SECTEURS.map((s) => <option key={s} value={s}>{s ? s.replace(/_/g, " ") : "— standard —"}</option>)}
            </select>
          </Field>
          <Field label="Pays de résidence"><Inp className="w-full" value={pays} onChange={setPays} /></Field>
        </div>
        <div>
          <div className="mb-1 text-sm font-medium">Pièces fournies</div>
          <div className="flex flex-wrap gap-2">
            {PIECES_KYC[type].map((p) => {
              const on = pieces.has(p.id);
              return (
                <button key={p.id} onClick={() => togglePiece(p.id)}
                  className={clsx("flex items-center gap-1.5 rounded-full px-3 py-1 text-sm transition", on ? "bg-forest text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
                  {on && <CheckCircle2 className="h-3.5 w-3.5" />} {p.label}
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={pep} onChange={(e) => setPep(e.target.checked)} /> Personne politiquement exposée (PEP)</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={sanction} onChange={(e) => setSanction(e.target.checked)} /> Concordance liste de sanctions</label>
        </div>
        <div className="flex justify-end"><Button onClick={run} disabled={loading}>Évaluer le KYC</Button></div>
      </Card>

      {loading && <Card><Skeleton className="h-5 w-1/2" /></Card>}
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {res && (
        <Card className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <RiskBadge niveau={res.niveau_risque} />
            <span className={clsx("rounded-full px-2.5 py-1 text-xs font-medium", res.vigilance === "renforcee" ? "bg-amber-100 text-amber-800" : "bg-mint/25 text-forest")}>Vigilance {res.vigilance}</span>
            <span className={clsx("ml-auto flex items-center gap-1.5 text-sm font-semibold", res.peut_entrer_en_relation ? "text-forest" : "text-red-600")}>
              {res.peut_entrer_en_relation ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
              {res.peut_entrer_en_relation ? "Entrée en relation possible" : "Entrée en relation bloquée"}
            </span>
          </div>
          {res.pieces_manquantes.length > 0 && (
            <div className="text-sm"><span className="text-muted">Pièces manquantes : </span>{res.pieces_manquantes.map((p) => <span key={p} className="mr-1 rounded bg-red-50 px-1.5 py-0.5 text-xs text-red-700">{p.replace(/_/g, " ")}</span>)}</div>
          )}
          <ul className="flex flex-col gap-1 text-sm text-ink/80">
            {res.facteurs_risque.map((x, i) => <li key={i} className="flex items-start gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-forest" />{x}</li>)}
          </ul>
          {res.motifs_blocage.length > 0 && (
            <ul className="flex flex-col gap-1 rounded-lg bg-red-50 p-3 text-sm text-red-700">
              {res.motifs_blocage.map((m, i) => <li key={i} className="flex items-start gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{m}</li>)}
            </ul>
          )}
          <p className="text-xs text-muted">{res.reference_cadre}</p>
          <div className="flex items-center gap-3 border-t border-black/5 pt-3">
            <Button onClick={save} disabled={saving}><Save className="h-4 w-4" /> Enregistrer au registre</Button>
            {saved && <span className="flex items-center gap-1.5 text-sm font-medium text-forest"><CheckCircle2 className="h-4 w-4" /> Enregistré</span>}
          </div>
        </Card>
      )}
    </>
  );
}

// --- AML -------------------------------------------------------------------

const NEW_TX: TransactionInput = { date: new Date().toISOString().slice(0, 10), montant_xaf: "", sens: "entree", canal: "virement" };

function AmlTab() {
  const [txs, setTxs] = useState<TransactionInput[]>([
    { date: "2026-07-01", montant_xaf: "4800000", sens: "entree", canal: "virement" },
    { date: "2026-07-02", montant_xaf: "4900000", sens: "entree", canal: "especes" },
  ]);
  const [res, setRes] = useState<AmlResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const upd = (i: number, k: keyof TransactionInput, v: string) => setTxs((s) => s.map((t, j) => (j === i ? { ...t, [k]: v } : t)));

  async function run() {
    setLoading(true); setErr(null); setRes(null);
    try {
      setRes(await evaluateAml(txs.filter((t) => t.montant_xaf)));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Service indisponible.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Card className="flex flex-col gap-2">
        {txs.map((t, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <Inp className="w-36" value={t.date} onChange={(v) => upd(i, "date", v)} type="date" />
            <Inp className="w-36" value={t.montant_xaf} onChange={(v) => upd(i, "montant_xaf", v)} type="number" placeholder="Montant XAF" />
            <select value={t.canal} onChange={(e) => upd(i, "canal", e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1.5 text-sm">
              <option value="virement">Virement</option>
              <option value="especes">Espèces</option>
              <option value="mobile_money">Mobile Money</option>
            </select>
            <button onClick={() => setTxs((s) => s.filter((_, j) => j !== i))} className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-black/5 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
        <div className="flex items-center justify-between">
          <button onClick={() => setTxs((s) => [...s, { ...NEW_TX }])} className="flex items-center gap-1.5 text-sm text-forest hover:underline"><Plus className="h-4 w-4" /> Ajouter une opération</button>
          <Button onClick={run} disabled={loading}>Analyser</Button>
        </div>
      </Card>

      {loading && <Card><Skeleton className="h-5 w-1/2" /></Card>}
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {res && (
        <Card className="flex flex-col gap-3">
          <div className="flex gap-6 text-sm">
            <Stat label="Opérations" value={String(res.nb_operations)} />
            <Stat label="Volume total" value={`${fmt(res.volume_total_xaf)} XAF`} />
            <Stat label="Dont espèces" value={`${fmt(res.volume_especes_xaf)} XAF`} />
          </div>
          <div className="flex flex-col gap-2">
            {res.alertes.map((a, i) => (
              <div key={i} className={clsx("flex items-start gap-2 rounded-lg p-3 text-sm",
                a.niveau === "alerte" ? "bg-red-50 text-red-700" : a.niveau === "attention" ? "bg-amber-50 text-amber-800" : "bg-mint/15 text-forest")}>
                {a.niveau === "info" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />}
                <div><div className="font-semibold">{a.titre}</div><div className="opacity-90">{a.detail}</div></div>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted">{res.reference_cadre}</p>
        </Card>
      )}
    </>
  );
}

// --- Registre --------------------------------------------------------------

function RegistreTab() {
  const [apps, setApps] = useState<CreditApplication[]>([]);
  const [kyc, setKyc] = useState<KycRecordItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [a, k] = await Promise.all([listApplications(), listKycRecords()]);
      setApps(a);
      setKyc(k);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  const appDecide = async (id: string, statut: string) => { await decideApplication(id, statut); await refresh(); };
  const appDelete = async (id: string) => { await deleteApplication(id); await refresh(); };
  const kycDecide = async (id: string, statut: string) => { await decideKycRecord(id, statut); await refresh(); };
  const kycDelete = async (id: string) => { await deleteKycRecord(id); await refresh(); };

  if (loading) return <Card><Skeleton className="mb-2 h-5 w-1/3" /><Skeleton className="h-4 w-full" /></Card>;

  return (
    <div className="flex flex-col gap-4">
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      <Card className="flex flex-col gap-2">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold"><Gauge className="h-4 w-4 text-forest" /> Dossiers de crédit ({apps.length})</div>
        {apps.length === 0 && <p className="text-sm text-muted">Aucun dossier enregistré.</p>}
        {apps.map((a) => (
          <div key={a.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-black/5 p-2.5 text-sm">
            <div className="min-w-40">
              <div className="font-medium">{a.client}</div>
              <div className="text-xs text-muted">{a.numero} · {fmt(a.montant_demande_xaf)} XAF · {a.duree_mois} mois</div>
            </div>
            <span className="rounded-full bg-black/5 px-2 py-0.5 text-xs font-semibold">Score {a.score} · {a.grade}</span>
            <StatutBadge statut={a.statut} />
            <div className="ml-auto flex items-center gap-1.5">
              {a.statut === "evaluee" && (
                <>
                  <MiniBtn onClick={() => appDecide(a.id, "accordee")} tone="forest">Accorder</MiniBtn>
                  <MiniBtn onClick={() => appDecide(a.id, "refusee")} tone="red">Refuser</MiniBtn>
                </>
              )}
              {a.statut === "accordee" && <MiniBtn onClick={() => appDecide(a.id, "decaissee")} tone="forest">Décaisser</MiniBtn>}
              <button onClick={() => appDelete(a.id)} className="grid h-7 w-7 place-items-center rounded-lg text-muted hover:bg-black/5 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        ))}
      </Card>

      <Card className="flex flex-col gap-2">
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="h-4 w-4 text-forest" /> Registre KYC ({kyc.length})</div>
        {kyc.length === 0 && <p className="text-sm text-muted">Aucun dossier KYC enregistré.</p>}
        {kyc.map((k) => (
          <div key={k.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-black/5 p-2.5 text-sm">
            <div className="min-w-40">
              <div className="font-medium">{k.nom}</div>
              <div className="text-xs text-muted">{k.type_client} · risque {k.niveau_risque} · vigilance {k.vigilance}</div>
            </div>
            <StatutBadge statut={k.statut} />
            <div className="ml-auto flex items-center gap-1.5">
              {k.statut === "a_valider" && (
                <>
                  <MiniBtn onClick={() => kycDecide(k.id, "valide")} tone="forest">Valider</MiniBtn>
                  <MiniBtn onClick={() => kycDecide(k.id, "refuse")} tone="red">Refuser</MiniBtn>
                </>
              )}
              <button onClick={() => kycDelete(k.id)} className="grid h-7 w-7 place-items-center rounded-lg text-muted hover:bg-black/5 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}

const STATUT_MAP: Record<string, { c: string; t: string }> = {
  evaluee: { c: "bg-black/5 text-ink/70", t: "Évaluée" },
  accordee: { c: "bg-forest text-white", t: "Accordée" },
  decaissee: { c: "bg-mint/30 text-forest", t: "Décaissée" },
  refusee: { c: "bg-red-100 text-red-700", t: "Refusée" },
  cloturee: { c: "bg-black/5 text-ink/50", t: "Clôturée" },
  a_valider: { c: "bg-amber-100 text-amber-800", t: "À valider" },
  valide: { c: "bg-forest text-white", t: "Validé" },
  refuse: { c: "bg-red-100 text-red-700", t: "Refusé" },
};

function StatutBadge({ statut }: { statut: string }) {
  const m = STATUT_MAP[statut] ?? { c: "bg-black/5 text-ink/70", t: statut };
  return <span className={clsx("rounded-full px-2.5 py-0.5 text-xs font-semibold", m.c)}>{m.t}</span>;
}

function MiniBtn({ onClick, tone, children }: { onClick: () => void; tone: "forest" | "red"; children: React.ReactNode }) {
  return (
    <button onClick={onClick} className={clsx("rounded-lg px-2.5 py-1 text-xs font-medium transition", tone === "forest" ? "bg-forest/10 text-forest hover:bg-forest/20" : "bg-red-50 text-red-600 hover:bg-red-100")}>
      {children}
    </button>
  );
}

// --- Pilotage --------------------------------------------------------------

function PilotageTab() {
  const [p, setP] = useState<PortfolioStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setP(await getPortfolio());
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : "Chargement impossible.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Card><Skeleton className="mb-2 h-6 w-1/3" /><Skeleton className="h-4 w-full" /></Card>;
  if (err) return <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>;
  if (!p) return null;
  const maxGrade = Math.max(1, ...Object.values(p.repartition_grade));

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Kpi label="Dossiers" value={String(p.nb_dossiers)} />
        <Kpi label="Encours décaissé" value={`${fmt(p.encours_decaisse_xaf)} XAF`} />
        <Kpi label="Montant accordé" value={`${fmt(p.montant_accorde_xaf)} XAF`} />
        <Kpi label="Taux d'acceptation" value={`${p.taux_acceptation_pct} %`} />
        <Kpi label="Service dette / mois" value={`${fmt(p.service_dette_mensuel_xaf)} XAF`} />
        <Kpi label="Score moyen" value={String(p.score_moyen)} />
      </div>

      <Card>
        <div className="mb-2 text-sm font-semibold">Répartition du portefeuille par grade</div>
        <div className="flex flex-col gap-1.5">
          {["A", "B", "C", "D", "E"].map((g) => (
            <div key={g} className="flex items-center gap-2 text-sm">
              <span className="w-4 font-semibold">{g}</span>
              <div className="h-3 flex-1 rounded bg-black/5">
                <div className="h-3 rounded bg-forest" style={{ width: `${((p.repartition_grade[g] || 0) / maxGrade) * 100}%` }} />
              </div>
              <span className="w-6 text-right tabular-nums text-muted">{p.repartition_grade[g] || 0}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card className="flex flex-col gap-2">
        <div className="text-sm font-semibold">Conformité KYC ({p.nb_kyc})</div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Chip label={`À valider ${p.kyc_par_statut.a_valider || 0}`} tone="amber" />
          <Chip label={`Validés ${p.kyc_par_statut.valide || 0}`} tone="forest" />
          <Chip label={`Refusés ${p.kyc_par_statut.refuse || 0}`} tone="red" />
          <Chip label={`Risque élevé ${p.kyc_par_risque.eleve || 0}`} tone="red" />
          <Chip label={`Vigilance renforcée ${p.nb_vigilance_renforcee}`} tone="amber" />
        </div>
      </Card>

      {p.signaux.length > 0 && (
        <Card className="flex flex-col gap-1.5">
          <div className="text-sm font-semibold">Signaux de pilotage</div>
          {p.signaux.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-ink/80"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-forest" />{s}</div>
          ))}
        </Card>
      )}

      <p className="flex items-start gap-1.5 text-xs text-muted"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {p.note}</p>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card className="py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-lg font-bold tabular-nums text-ink">{value}</div>
    </Card>
  );
}

function Chip({ label, tone }: { label: string; tone: "forest" | "amber" | "red" }) {
  const c = tone === "forest" ? "bg-mint/25 text-forest" : tone === "amber" ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-700";
  return <span className={"rounded-full px-2.5 py-1 font-medium " + c}>{label}</span>;
}

// --- primitives ------------------------------------------------------------

function TabBtn({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof Gauge; label: string }) {
  return (
    <button onClick={onClick} className={clsx("flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm transition", active ? "bg-forest text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-sm"><span className="mb-1 block font-medium">{label}</span>{children}</label>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div><div className="text-xs text-muted">{label}</div><div className="font-semibold tabular-nums text-ink">{value}</div></div>;
}

function DecisionBadge({ decision }: { decision: string }) {
  const map: Record<string, { c: string; t: string }> = {
    accorde: { c: "bg-forest text-white", t: "Accordé" },
    a_etudier: { c: "bg-amber-100 text-amber-800", t: "À étudier" },
    refuse: { c: "bg-red-100 text-red-700", t: "Refusé" },
  };
  const m = map[decision] ?? map.refuse;
  return <span className={clsx("rounded-full px-3 py-1 text-sm font-semibold", m.c)}>{m.t}</span>;
}

function RiskBadge({ niveau }: { niveau: string }) {
  const map: Record<string, { c: string; t: string }> = {
    faible: { c: "bg-mint/25 text-forest", t: "Risque faible" },
    moyen: { c: "bg-amber-100 text-amber-800", t: "Risque moyen" },
    eleve: { c: "bg-red-100 text-red-700", t: "Risque élevé" },
  };
  const m = map[niveau] ?? map.moyen;
  return <span className={clsx("rounded-full px-3 py-1 text-sm font-semibold", m.c)}>{m.t}</span>;
}

function ScoreDonut({ score, grade }: { score: number; grade: string }) {
  const color = score >= 70 ? "#1E6B4F" : score >= 50 ? "#D9822B" : "#DC2626";
  return (
    <div className="relative grid h-24 w-24 place-items-center rounded-full"
      style={{ background: `conic-gradient(${color} ${score * 3.6}deg, #E9ECF1 0deg)` }}>
      <div className="grid h-[76px] w-[76px] place-items-center rounded-full bg-white">
        <div className="text-2xl font-bold leading-none text-ink">{score}</div>
        <div className="text-xs font-semibold" style={{ color }}>Grade {grade}</div>
      </div>
    </div>
  );
}
