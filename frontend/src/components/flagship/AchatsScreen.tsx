"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ShoppingCart,
  Plus,
  Trash2,
  Trophy,
  ShieldAlert,
  FileCheck2,
  Star,
  GitBranch,
  AlertTriangle,
  Wallet,
  BarChart3,
  Download,
} from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { fmt } from "@/lib/data";
import { ApiError } from "@/lib/api";
import {
  listSuppliers,
  createSupplier,
  supplierScores,
  deleteSupplier,
  listPurchaseOrders,
  createPurchaseOrder,
  comparePurchaseOrders,
  receiptPurchaseOrder,
  deletePurchaseOrder,
  listEngagements,
  createEngagement,
  engagementStats,
  listPurchaseBudgets,
  setPurchaseBudget,
  engagementPilotage,
  downloadPilotage,
  type SupplierRec,
  type SupplierScore,
  type PurchaseOrderRec,
  type ComparatifLigne,
  type EngagementRec,
  type EngagementStats,
  type EngagementAlerte,
  type PurchaseBudgetRec,
  type PilotageBudgetaire,
} from "@/lib/achats";

const GRADE: Record<string, string> = {
  A: "bg-emerald-100 text-emerald-700",
  B: "bg-amber-100 text-amber-700",
  C: "bg-orange-100 text-orange-700",
  D: "bg-gray-100 text-gray-600",
};
const DOCS = ["rccm", "niu", "attestation_fiscale"];
const TODAY = new Date().toISOString().slice(0, 10);

const DEMO_SUPPLIERS = [
  { id_externe: "F1", nom: "Alpha SARL", secteur: "Consommables", note_qualite: "4.5", delai_moyen_jours: 8, documents_conformite: ["rccm", "niu", "attestation_fiscale"] },
  { id_externe: "F2", nom: "Beta Distrib", secteur: "Consommables", note_qualite: "3.0", delai_moyen_jours: 15, documents_conformite: ["rccm", "niu"] },
  { id_externe: "F3", nom: "Gamma", secteur: "Consommables", note_qualite: "2.0", delai_moyen_jours: 30, documents_conformite: ["rccm"] },
];
const DEMO_POS = [
  { id_externe: "BC1", numero: "BC-001", fournisseur: "Alpha SARL", objet: "Consommables", date_emission: TODAY, statut: "confirme", montant_ht_xaf: "1000000", montant_ttc_xaf: "1180000", delai_livraison_jours: 8 },
  { id_externe: "BC2", numero: "BC-002", fournisseur: "Beta Distrib", objet: "Consommables", date_emission: TODAY, statut: "envoye", montant_ht_xaf: "800000", montant_ttc_xaf: "944000", delai_livraison_jours: 15 },
  { id_externe: "BC3", numero: "BC-003", fournisseur: "Gamma", objet: "Consommables", date_emission: TODAY, statut: "envoye", montant_ht_xaf: "900000", montant_ttc_xaf: "1062000", delai_livraison_jours: 7 },
];
const DEMO_ENGAGEMENTS = [
  { numero_eb: "0319/26", numero_da: "0313/26", numero_bc: "0172/26", date_eb: "2026-04-13", date_da: "2026-04-28", date_bc: "2026-04-30", direction: "DIP", service: "SIPT", demandeur: "BELO D.", acheteur: "Ferlez", fournisseur: "HBM Services", estimation_xaf: "200000", montant_xaf: "225910", statut_ebda: "OK / Traitée", statut_bc: "Traité" },
  { numero_eb: "0368/26", numero_da: "0332/26", date_eb: "2026-04-20", date_da: "2026-04-30", direction: "DFC", service: "Logistique", demandeur: "MAVOUNGOU R.", acheteur: "Ferlez", estimation_xaf: "1400000", statut_ebda: "OK / En cours CDG", statut_bc: "En Cours CDG" },
  { numero_eb: "0401/26", date_eb: "2026-05-02", direction: "DOM", service: "Production", demandeur: "NGOMA P.", acheteur: "Leroy", estimation_xaf: "750000", statut_ebda: "OK / En cours ACH", statut_bc: "N/C" },
  { numero_eb: "0410/26", numero_da: "0345/26", numero_bc: "0181/26", date_eb: "2026-05-04", date_da: "2026-05-10", date_bc: "2026-05-18", direction: "DARH", service: "Moyens généraux", demandeur: "OKEMBA J.", acheteur: "Judith", fournisseur: "Beta Distrib", estimation_xaf: "600000", montant_xaf: "850000", statut_ebda: "OK / Traitée", statut_bc: "En cours F/sseur" },
];

const EXERCICE_DEFAUT = String(new Date().getFullYear());

export function AchatsScreen() {
  const [tab, setTab] = useState<"appro" | "engagements" | "pilotage">("appro");
  const [exercice, setExercice] = useState<string>(EXERCICE_DEFAUT);
  const [suppliers, setSuppliers] = useState<SupplierRec[]>([]);
  const [scores, setScores] = useState<Record<string, SupplierScore>>({});
  const [pos, setPos] = useState<PurchaseOrderRec[]>([]);
  const [classement, setClassement] = useState<ComparatifLigne[] | null>(null);
  const [engagements, setEngagements] = useState<EngagementRec[]>([]);
  const [engStats, setEngStats] = useState<EngagementStats | null>(null);
  const [engAlertes, setEngAlertes] = useState<EngagementAlerte[]>([]);
  const [pilotage, setPilotage] = useState<PilotageBudgetaire | null>(null);
  const [budgets, setBudgets] = useState<PurchaseBudgetRec[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [supForm, setSupForm] = useState({ nom: "", note_qualite: "3.0" });
  const [poForm, setPoForm] = useState({ fournisseur: "", objet: "Consommables", montant: "", delai: "7" });

  const refresh = useCallback(async () => {
    try {
      const [s, sc, p, eng, est] = await Promise.all([
        listSuppliers(),
        supplierScores(),
        listPurchaseOrders(),
        listEngagements(),
        engagementStats(),
      ]);
      setSuppliers(s.suppliers);
      setScores(Object.fromEntries(sc.scores.map((x) => [x.id, x])));
      setPos(p.purchase_orders);
      setEngagements(eng.engagements);
      setEngStats(est.stats);
      setEngAlertes(est.alertes);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  const loadPilotage = useCallback(async () => {
    try {
      const [p, b] = await Promise.all([
        engagementPilotage(exercice),
        listPurchaseBudgets(exercice),
      ]);
      setPilotage(p.pilotage);
      setBudgets(b.budgets);
    } catch {
      /* le bandeau d'erreur global suffit */
    }
  }, [exercice]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    loadPilotage();
  }, [loadPilotage]);

  async function saveBudget(direction: string, montant: string) {
    try {
      await setPurchaseBudget({ direction, exercice, budget_xaf: montant });
      await loadPilotage();
    } catch {
      setErr("Enregistrement du budget impossible.");
    }
  }

  // Exercices proposés : ceux présents dans les engagements + l'année courante.
  const exercices = Array.from(
    new Set([
      EXERCICE_DEFAUT,
      exercice,
      ...engagements.flatMap((e) =>
        [e.date_bc, e.date_da, e.date_eb].filter(Boolean).map((d) => (d as string).slice(0, 4)),
      ),
    ]),
  ).sort((a, b) => b.localeCompare(a));

  async function addSupplier() {
    if (!supForm.nom) return;
    try {
      await createSupplier({
        id_externe: `F-${Date.now()}`,
        nom: supForm.nom,
        note_qualite: supForm.note_qualite,
        documents_conformite: [],
      });
      setSupForm({ nom: "", note_qualite: "3.0" });
      await refresh();
    } catch {
      setErr("Création fournisseur impossible (backend/DB).");
    }
  }

  async function addPo() {
    if (!poForm.fournisseur || !poForm.montant) return;
    try {
      await createPurchaseOrder({
        id_externe: `BC-${Date.now()}`,
        numero: `BC-${Date.now()}`,
        fournisseur: poForm.fournisseur,
        objet: poForm.objet,
        date_emission: TODAY,
        statut: "envoye",
        montant_ht_xaf: poForm.montant,
        montant_ttc_xaf: poForm.montant,
        delai_livraison_jours: Number(poForm.delai) || 0,
      });
      setPoForm({ ...poForm, fournisseur: "", montant: "" });
      await refresh();
    } catch {
      setErr("Création BC impossible (backend/DB).");
    }
  }

  async function compare(objet: string) {
    try {
      setClassement((await comparePurchaseOrders(objet)).classement);
    } catch {
      setErr("Comparatif impossible.");
    }
  }

  async function receipt(id: string) {
    try {
      await receiptPurchaseOrder(id);
      await refresh();
    } catch (e) {
      setErr(
        e instanceof ApiError && e.status === 422
          ? "BC encore en brouillon : émettez-le avant réception."
          : e instanceof ApiError && e.status === 409
            ? "BC déjà réceptionné (facturé)."
            : "Réception impossible.",
      );
    }
  }

  async function seedDemo() {
    try {
      for (const s of DEMO_SUPPLIERS) await createSupplier(s);
      for (const p of DEMO_POS) await createPurchaseOrder(p);
      await refresh();
    } catch {
      setErr("Initialisation du jeu de démo impossible (backend/DB).");
    }
  }

  async function seedEngagements() {
    try {
      for (const e of DEMO_ENGAGEMENTS) await createEngagement(e);
      await refresh();
    } catch {
      setErr("Initialisation des engagements de démo impossible (backend/DB).");
    }
  }

  const isEmpty = suppliers.length === 0 && pos.length === 0;
  const objets = Array.from(new Set(pos.map((p) => p.objet).filter(Boolean)));

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader
        icon={ShoppingCart}
        title="Achats / Procurement"
        subtitle="Approvisionnement (fournisseurs, BC, réception→facture) et pilotage des engagements EB→DA→BC."
      />

      {/* Onglets */}
      <div className="flex gap-1 rounded-xl bg-black/[0.04] p-1 text-sm">
        {([
          ["appro", "Approvisionnement"],
          ["engagements", "Engagements"],
          ["pilotage", "Pilotage"],
        ] as const).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={
              "rounded-lg px-3 py-1.5 font-medium transition " +
              (tab === k ? "bg-surface shadow-sm" : "text-muted hover:text-ink")
            }
          >
            {label}
          </button>
        ))}
      </div>

      {err && (
        <Card className="ring-amber-200">
          <p className="text-sm text-amber-700">{err}</p>
        </Card>
      )}

      {tab === "pilotage" ? (
        <PilotagePanel
          exercice={exercice}
          exercices={exercices}
          onExercice={setExercice}
          pilotage={pilotage}
          budgets={budgets}
          onSaveBudget={saveBudget}
        />
      ) : tab === "engagements" ? (
        <EngagementsPanel
          engagements={engagements}
          stats={engStats}
          alertes={engAlertes}
          onSeed={seedEngagements}
        />
      ) : (
        <>
          {isEmpty && (
            <Card>
              <div className="flex flex-col items-start gap-2">
                <p className="text-sm text-muted">
                  Aucune donnée achat. Le registre est <b>persistant</b> : chargez un jeu de démo
                  ou créez un fournisseur.
                </p>
                <Button onClick={seedDemo}>
                  <Plus className="h-4 w-4" /> Charger un jeu de démo
                </Button>
              </div>
            </Card>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
        {/* Registre fournisseurs noté/gradé */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Fournisseurs (notés &amp; gradés)</h2>
          <div className="mb-3 grid grid-cols-[1fr_90px_36px] gap-2">
            <Inp value={supForm.nom} onChange={(v) => setSupForm({ ...supForm, nom: v })} placeholder="Nom" />
            <Inp value={supForm.note_qualite} type="number" onChange={(v) => setSupForm({ ...supForm, note_qualite: v })} placeholder="Note /5" />
            <button onClick={addSupplier} className="grid place-items-center rounded-lg bg-primary text-white">
              <Plus className="h-4 w-4" />
            </button>
          </div>
          {suppliers.length === 0 && <p className="text-sm text-muted">Aucun fournisseur.</p>}
          {suppliers.map((s) => {
            const sc = scores[s.id];
            return (
              <div key={s.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
                <span className="flex items-center gap-2">
                  <Star className="h-3.5 w-3.5 text-amber-400" />
                  <b>{s.nom}</b>
                  <span className="text-xs text-muted">{s.note_qualite}/5</span>
                </span>
                <span className="flex items-center gap-2">
                  {sc && sc.conformite_manquante.length > 0 && (
                    <span className="flex items-center gap-1 text-xs text-amber-700" title={"Manque : " + sc.conformite_manquante.join(", ")}>
                      <ShieldAlert className="h-3.5 w-3.5" /> {sc.conformite_manquante.length}/{DOCS.length}
                    </span>
                  )}
                  {sc && <span className={"rounded px-1.5 text-[10px] font-bold " + (GRADE[sc.grade] ?? "")}>{sc.grade} · {sc.score}</span>}
                  <button onClick={() => deleteSupplier(s.id).then(refresh)} className="text-muted hover:text-red-600">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </span>
              </div>
            );
          })}
        </Card>

        {/* Bons de commande + réception → facture d'achat */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Bons de commande</h2>
          <div className="mb-3 grid grid-cols-[1fr_110px_60px_36px] gap-2">
            <Inp value={poForm.fournisseur} onChange={(v) => setPoForm({ ...poForm, fournisseur: v })} placeholder="Fournisseur" />
            <Inp value={poForm.montant} type="number" onChange={(v) => setPoForm({ ...poForm, montant: v })} placeholder="Montant" />
            <Inp value={poForm.delai} type="number" onChange={(v) => setPoForm({ ...poForm, delai: v })} placeholder="Délai" />
            <button onClick={addPo} className="grid place-items-center rounded-lg bg-primary text-white">
              <Plus className="h-4 w-4" />
            </button>
          </div>
          {pos.length === 0 && <p className="text-sm text-muted">Aucun bon de commande.</p>}
          {pos.map((p) => (
            <div key={p.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span>
                <b>{p.numero}</b> · {p.fournisseur} · {fmt(p.montant_ttc_xaf)} XAF
                <span className="ml-2 rounded-full bg-black/5 px-2 py-0.5 text-xs">{p.statut}</span>
              </span>
              <span className="flex items-center gap-2">
                <span className="text-xs text-muted">{p.delai_livraison_jours} j</span>
                {p.invoice_id ? (
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">facturé</span>
                ) : (
                  <button onClick={() => receipt(p.id)} disabled={p.statut === "brouillon"} title="Réceptionner → facture d'achat" className="text-primary hover:opacity-80 disabled:opacity-40">
                    <FileCheck2 className="h-4 w-4" />
                  </button>
                )}
                <button onClick={() => deletePurchaseOrder(p.id).then(refresh)} className="text-muted hover:text-red-600">
                  <Trash2 className="h-4 w-4" />
                </button>
              </span>
            </div>
          ))}
        </Card>
      </div>

      {/* Comparatif des BC (anti-surfacturation) */}
      {objets.length > 0 && (
        <Card>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Comparatif des BC (prix / délai)</h2>
            <div className="flex flex-wrap gap-2">
              {objets.map((o) => (
                <Button key={o} variant="ghost" onClick={() => compare(o)}>
                  {o}
                </Button>
              ))}
            </div>
          </div>
          {!classement && <p className="text-sm text-muted">Choisissez un objet à comparer.</p>}
          {classement?.map((c) => (
            <div key={c.offre_id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span className="flex items-center gap-2">
                {c.rang === 1 ? <Trophy className="h-4 w-4 text-amber-500" /> : <span className="w-4 text-center text-muted">{c.rang}</span>}
                {c.fournisseur}
              </span>
              <span className="text-muted">
                {fmt(c.montant_ttc_xaf)} XAF · {c.delai_livraison_jours} j · <b className="text-ink">score {c.score}</b>
              </span>
            </div>
          ))}
        </Card>
          )}
        </>
      )}
    </div>
  );
}

const PHASE_LABEL: Record<string, string> = {
  besoin: "Besoin (EB)",
  demande: "Demande (DA)",
  commande: "Commande (BC)",
  traite: "Traité",
  annulee: "Annulé",
};
const PHASE_COLOR: Record<string, string> = {
  besoin: "bg-gray-100 text-gray-600",
  demande: "bg-blue-100 text-blue-700",
  commande: "bg-indigo-100 text-indigo-700",
  traite: "bg-emerald-100 text-emerald-700",
  annulee: "bg-red-100 text-red-600",
};

function EngagementsPanel({
  engagements,
  stats,
  alertes,
  onSeed,
}: {
  engagements: EngagementRec[];
  stats: EngagementStats | null;
  alertes: EngagementAlerte[];
  onSeed: () => void;
}) {
  if (engagements.length === 0) {
    return (
      <Card>
        <div className="flex flex-col items-start gap-2">
          <p className="text-sm text-muted">
            Aucun engagement. Le suivi <b>EB → DA → BC</b> (estimation vs engagé, par direction et
            acheteur) s&apos;alimente par import Excel ou par le jeu de démo.
          </p>
          <Button onClick={onSeed}>
            <Plus className="h-4 w-4" /> Charger des engagements de démo
          </Button>
        </div>
      </Card>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {stats && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi label="Engagements" value={String(stats.nb_total)} />
            <Kpi label="Estimé" value={fmt(stats.estimation_totale_xaf) + " XAF"} />
            <Kpi label="Engagé" value={fmt(stats.engage_total_xaf) + " XAF"} />
            <Kpi
              label="Écart (engagé − estimé)"
              value={(stats.ecart_xaf >= 0 ? "+" : "") + fmt(stats.ecart_xaf) + " XAF"}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {/* Transformation EB→DA→BC */}
            <Card>
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <GitBranch className="h-4 w-4 text-indigo-600" /> Transformation
              </div>
              <Funnel label="EB" value={stats.nb_eb} pct={100} />
              <Funnel label="DA" value={stats.nb_da} pct={Number(stats.taux_eb_vers_da_pct)} />
              <Funnel label="BC" value={stats.nb_bc} pct={Number(stats.taux_eb_vers_bc_pct)} />
              <div className="mt-2 flex justify-between text-xs text-muted">
                <span>Taux EB→BC : {stats.taux_eb_vers_bc_pct}%</span>
                <span>
                  Cycle moy. : {stats.delai_moyen_eb_da_jours ?? "—"} j (EB→DA) ·{" "}
                  {stats.delai_moyen_da_bc_jours ?? "—"} j (DA→BC)
                </span>
              </div>
            </Card>

            {/* Funnel des statuts BC */}
            <Card>
              <div className="mb-2 text-sm font-semibold">En-cours par statut BC</div>
              {Object.keys(stats.funnel_statut_bc).length === 0 && (
                <p className="text-sm text-muted">Aucun BC émis.</p>
              )}
              {Object.entries(stats.funnel_statut_bc).map(([s, n]) => (
                <div key={s} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
                  <span>{s}</span>
                  <span className="font-semibold">{n}</span>
                </div>
              ))}
            </Card>

            {/* Par direction */}
            <Card>
              <div className="mb-2 text-sm font-semibold">Engagé par direction</div>
              {stats.par_direction.map((d) => (
                <div key={d.cle} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
                  <span>{d.cle} <span className="text-xs text-muted">({d.nb})</span></span>
                  <span className="text-muted">{fmt(d.engage_xaf)} XAF</span>
                </div>
              ))}
            </Card>

            {/* Par acheteur */}
            <Card>
              <div className="mb-2 text-sm font-semibold">Charge par acheteur</div>
              {stats.par_acheteur.map((a) => (
                <div key={a.cle} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
                  <span>{a.cle} <span className="text-xs text-muted">({a.nb})</span></span>
                  <span className="text-muted">{fmt(a.engage_xaf)} XAF</span>
                </div>
              ))}
            </Card>
          </div>

          {alertes.length > 0 && (
            <Card className="ring-amber-200">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <AlertTriangle className="h-4 w-4 text-amber-600" /> Alertes ({alertes.length})
                {stats.nb_depassements > 0 && (
                  <span className="text-xs font-normal text-muted">
                    · {stats.nb_depassements} dépassement(s) d&apos;estimation
                  </span>
                )}
              </div>
              {alertes.map((a, i) => (
                <div key={i} className="flex items-start justify-between gap-2 border-b border-black/5 py-1 text-sm last:border-0">
                  <span>{a.libelle}</span>
                  <span className={"shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold " + (a.priorite === "high" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700")}>
                    {a.type}
                  </span>
                </div>
              ))}
            </Card>
          )}
        </>
      )}

      {/* Registre des engagements */}
      <Card>
        <div className="mb-2 text-sm font-semibold">Registre des engagements (EB → DA → BC)</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th className="py-1 pr-2">N° EB</th>
                <th className="pr-2">Direction</th>
                <th className="pr-2">Acheteur</th>
                <th className="pr-2">Fournisseur</th>
                <th className="pr-2 text-right">Estimé</th>
                <th className="pr-2 text-right">Engagé</th>
                <th className="pr-2">Phase</th>
              </tr>
            </thead>
            <tbody>
              {engagements.map((e) => {
                const ph = computePhase(e);
                return (
                  <tr key={e.id} className="border-t border-black/5">
                    <td className="py-1 pr-2 font-medium">{e.numero_eb}</td>
                    <td className="pr-2">{e.direction ?? "—"}</td>
                    <td className="pr-2">{e.acheteur ?? "—"}</td>
                    <td className="pr-2">{e.fournisseur ?? "—"}</td>
                    <td className="pr-2 text-right text-muted">{fmt(e.estimation_xaf)}</td>
                    <td className="pr-2 text-right">{fmt(e.montant_xaf)}</td>
                    <td className="pr-2">
                      <span className={"rounded px-1.5 py-0.5 text-[10px] font-semibold " + (PHASE_COLOR[ph] ?? "")}>
                        {PHASE_LABEL[ph] ?? ph}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// Reflet déterministe de la phase calculée côté moteur (pour l'affichage du registre).
function computePhase(e: EngagementRec): string {
  const s = (e.statut_ebda + " " + e.statut_bc).toLowerCase();
  if (s.includes("annul")) return "annulee";
  if (e.statut_bc.trim().toLowerCase().startsWith("trait")) return "traite";
  if (e.numero_bc) return "commande";
  if (e.numero_da) return "demande";
  return "besoin";
}

const NIVEAU_COLOR: Record<string, string> = {
  ok: "bg-emerald-500",
  vigilance: "bg-amber-500",
  depassement: "bg-red-500",
  hors_budget: "bg-gray-400",
};
const NIVEAU_LABEL: Record<string, string> = {
  ok: "OK",
  vigilance: "Vigilance",
  depassement: "Dépassement",
  hors_budget: "Hors budget",
};

function PilotagePanel({
  exercice,
  exercices,
  onExercice,
  pilotage,
  budgets,
  onSaveBudget,
}: {
  exercice: string;
  exercices: string[];
  onExercice: (e: string) => void;
  pilotage: PilotageBudgetaire | null;
  budgets: PurchaseBudgetRec[];
  onSaveBudget: (direction: string, montant: string) => void;
}) {
  const [budForm, setBudForm] = useState({ direction: "", montant: "" });
  const budgetMap = Object.fromEntries(budgets.map((b) => [b.direction, b.budget_xaf]));

  const selecteur = (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted">Exercice</span>
      <select
        value={exercice}
        onChange={(e) => onExercice(e.target.value)}
        className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
      >
        {exercices.map((ex) => (
          <option key={ex} value={ex}>
            {ex}
          </option>
        ))}
      </select>
      <Button variant="ghost" onClick={() => downloadPilotage(exercice)}>
        <Download className="h-4 w-4" /> Exporter
      </Button>
    </div>
  );

  if (!pilotage) {
    return (
      <Card>
        <div className="mb-2 flex justify-end">{selecteur}</div>
        <p className="text-sm text-muted">Chargement du pilotage…</p>
      </Card>
    );
  }
  const maxSerie = Math.max(1, ...pilotage.serie_mensuelle.map((s) => s.engage_xaf));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">{selecteur}</div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi label={`Budget ${exercice}`} value={fmt(pilotage.budget_total_xaf) + " XAF"} />
        <Kpi label="Engagé" value={fmt(pilotage.engage_total_xaf) + " XAF"} />
        <Kpi label="Reste" value={fmt(pilotage.reste_total_xaf) + " XAF"} />
        <Kpi label="Consommation" value={pilotage.consommation_pct + " %"} />
      </div>

      {/* Engagé vs budget par direction */}
      <Card>
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <Wallet className="h-4 w-4 text-indigo-600" /> Engagé vs budget par direction ({exercice})
        </div>
        {pilotage.par_direction.length === 0 && (
          <p className="text-sm text-muted">Aucune donnée. Définissez un budget et importez des engagements.</p>
        )}
        {pilotage.par_direction.map((d) => {
          const pct = Math.min(100, d.consommation_pct);
          return (
            <div key={d.direction} className="mb-2.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">
                  {d.direction} <span className="text-xs text-muted">({d.nb})</span>
                </span>
                <span className="text-muted">
                  {fmt(d.engage_xaf)} / {fmt(d.budget_xaf)} XAF · {d.consommation_pct}%
                  <span className={"ml-2 rounded-full px-2 py-0.5 text-[10px] font-semibold text-white " + (NIVEAU_COLOR[d.niveau] ?? "bg-gray-400")}>
                    {NIVEAU_LABEL[d.niveau] ?? d.niveau}
                  </span>
                </span>
              </div>
              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-black/10">
                <div className={"h-full rounded-full transition-all " + (NIVEAU_COLOR[d.niveau] ?? "bg-gray-400")} style={{ width: `${Math.max(2, pct)}%` }} />
              </div>
            </div>
          );
        })}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Tendance mensuelle des engagements */}
        <Card>
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
            <BarChart3 className="h-4 w-4 text-indigo-600" /> Engagé par mois
          </div>
          {pilotage.serie_mensuelle.length === 0 && (
            <p className="text-sm text-muted">Aucun engagement daté.</p>
          )}
          <div className="flex items-end gap-2 pt-2" style={{ height: 120 }}>
            {pilotage.serie_mensuelle.map((s) => (
              <div key={s.mois} className="flex flex-1 flex-col items-center justify-end gap-1">
                <div
                  className="w-full rounded-t bg-indigo-400"
                  style={{ height: `${(s.engage_xaf / maxSerie) * 90}%` }}
                  title={fmt(s.engage_xaf) + " XAF"}
                />
                <span className="text-[10px] text-muted">{s.mois.slice(5)}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Concentration fournisseurs */}
        <Card>
          <div className="mb-2 text-sm font-semibold">Top fournisseurs (engagé)</div>
          {pilotage.top_fournisseurs.length === 0 && (
            <p className="text-sm text-muted">Aucun fournisseur engagé.</p>
          )}
          {pilotage.top_fournisseurs.slice(0, 6).map((f) => (
            <div key={f.fournisseur} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
              <span>{f.fournisseur} <span className="text-xs text-muted">({f.nb})</span></span>
              <span className="text-muted">{fmt(f.engage_xaf)} XAF</span>
            </div>
          ))}
        </Card>
      </div>

      {/* Définition des budgets */}
      <Card>
        <div className="mb-2 text-sm font-semibold">Budgets par direction ({exercice})</div>
        <div className="mb-3 grid grid-cols-[1fr_140px_36px] gap-2">
          <Inp value={budForm.direction} onChange={(v) => setBudForm({ ...budForm, direction: v })} placeholder="Direction (ex. DFC)" />
          <Inp value={budForm.montant} type="number" onChange={(v) => setBudForm({ ...budForm, montant: v })} placeholder="Budget XAF" />
          <button
            onClick={() => {
              if (budForm.direction && budForm.montant) {
                onSaveBudget(budForm.direction.trim(), budForm.montant);
                setBudForm({ direction: "", montant: "" });
              }
            }}
            className="grid place-items-center rounded-lg bg-primary text-white"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
        {Object.keys(budgetMap).length === 0 && (
          <p className="text-sm text-muted">Aucun budget défini. Ajoutez-en (ou importez le pôle Achats).</p>
        )}
        {Object.entries(budgetMap).map(([dir, montant]) => (
          <div key={dir} className="flex items-center justify-between border-b border-black/5 py-1 text-sm last:border-0">
            <span className="font-medium">{dir}</span>
            <span className="text-muted">{fmt(montant)} XAF</span>
          </div>
        ))}
      </Card>
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

function Funnel({ label, value, pct }: { label: string; value: number; pct: number }) {
  return (
    <div className="mb-1.5">
      <div className="flex justify-between text-xs">
        <span className="font-medium">{label}</span>
        <span className="text-muted">{value}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-black/10">
        <div className="h-full rounded-full bg-indigo-500 transition-all" style={{ width: `${Math.max(2, Math.min(100, pct))}%` }} />
      </div>
    </div>
  );
}
