"use client";

import { useCallback, useEffect, useState } from "react";
import { ShoppingCart, Plus, Trash2, Trophy, ShieldAlert, FileCheck2, Star } from "lucide-react";
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
  type SupplierRec,
  type SupplierScore,
  type PurchaseOrderRec,
  type ComparatifLigne,
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

export function AchatsScreen() {
  const [suppliers, setSuppliers] = useState<SupplierRec[]>([]);
  const [scores, setScores] = useState<Record<string, SupplierScore>>({});
  const [pos, setPos] = useState<PurchaseOrderRec[]>([]);
  const [classement, setClassement] = useState<ComparatifLigne[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [supForm, setSupForm] = useState({ nom: "", note_qualite: "3.0" });
  const [poForm, setPoForm] = useState({ fournisseur: "", objet: "Consommables", montant: "", delai: "7" });

  const refresh = useCallback(async () => {
    try {
      const [s, sc, p] = await Promise.all([listSuppliers(), supplierScores(), listPurchaseOrders()]);
      setSuppliers(s.suppliers);
      setScores(Object.fromEntries(sc.scores.map((x) => [x.id, x])));
      setPos(p.purchase_orders);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

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

  const isEmpty = suppliers.length === 0 && pos.length === 0;
  const objets = Array.from(new Set(pos.map((p) => p.objet).filter(Boolean)));

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader
        icon={ShoppingCart}
        title="Achats / Procurement"
        subtitle="Registre fournisseurs noté, comparatif des BC et réception → facture d'achat (anti-surfacturation tracée)."
      />

      {err && (
        <Card className="ring-amber-200">
          <p className="text-sm text-amber-700">{err}</p>
        </Card>
      )}

      {isEmpty && (
        <Card>
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-muted">
              Aucune donnée achat. Le registre est <b>persistant</b> : chargez un jeu de démo ou
              créez un fournisseur.
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
    </div>
  );
}
