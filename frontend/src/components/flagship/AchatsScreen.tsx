"use client";

import { useState } from "react";
import { ShoppingCart, Plus, Trash2, Trophy } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { achatsCompare, fmtXaf, type OffreInput, type ComparatifLigne } from "@/lib/erp";
import { ApiError } from "@/lib/api";

const DEFAULT: OffreInput[] = [
  { id_externe: "O1", fournisseur: "Alpha SARL", objet: "Consommables", montant_ttc_xaf: "1000000", montant_ht_xaf: "1000000", delai_livraison_jours: 10 },
  { id_externe: "O2", fournisseur: "Beta Distrib", objet: "Consommables", montant_ttc_xaf: "800000", montant_ht_xaf: "800000", delai_livraison_jours: 5 },
  { id_externe: "O3", fournisseur: "Gamma", objet: "Consommables", montant_ttc_xaf: "900000", montant_ht_xaf: "900000", delai_livraison_jours: 7 },
];

export function AchatsScreen() {
  const [offres, setOffres] = useState<OffreInput[]>(DEFAULT);
  const [res, setRes] = useState<ComparatifLigne[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const set = (i: number, k: keyof OffreInput, v: string) =>
    setOffres((l) => l.map((row, j) => (j === i ? { ...row, [k]: k === "delai_livraison_jours" ? Number(v) : v, montant_ht_xaf: k === "montant_ttc_xaf" ? v : row.montant_ht_xaf } : row)));
  const add = () => setOffres((l) => [...l, { id_externe: `O${l.length + 1}`, fournisseur: "", objet: "", montant_ttc_xaf: "0", montant_ht_xaf: "0", delai_livraison_jours: 7 }]);
  const del = (i: number) => setOffres((l) => l.filter((_, j) => j !== i));

  async function run() {
    setErr(null); setRes(null);
    try { setRes((await achatsCompare(offres)).classement); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible."); }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={ShoppingCart} title="Achats — Comparaison de devis" subtitle="Classement prix/délai (déterministe), anti-surfacturation." />
      <Card>
        <div className="grid grid-cols-[1fr_130px_70px_32px] gap-2 text-xs font-medium text-muted">
          <span>Fournisseur</span><span>Montant TTC</span><span>Délai</span><span />
        </div>
        {offres.map((row, i) => (
          <div key={i} className="mt-1 grid grid-cols-[1fr_130px_70px_32px] gap-2">
            <Inp value={row.fournisseur} onChange={(v) => set(i, "fournisseur", v)} />
            <Inp value={row.montant_ttc_xaf} type="number" onChange={(v) => set(i, "montant_ttc_xaf", v)} />
            <Inp value={row.delai_livraison_jours} type="number" onChange={(v) => set(i, "delai_livraison_jours", v)} />
            <button onClick={() => del(i)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
        ))}
        <div className="mt-3 flex justify-between">
          <Button variant="ghost" onClick={add}><Plus className="h-4 w-4" /> Devis</Button>
          <Button onClick={run}>Comparer</Button>
        </div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {res && (
        <Card>
          {res.map((c) => (
            <div key={c.offre_id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span className="flex items-center gap-2">
                {c.rang === 1 ? <Trophy className="h-4 w-4 text-amber-500" /> : <span className="w-4 text-center text-muted">{c.rang}</span>}
                {c.fournisseur}
              </span>
              <span className="text-muted">{fmtXaf(c.montant_ttc_xaf)} · {c.delai_livraison_jours} j · <b className="text-ink">score {c.score}</b></span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
