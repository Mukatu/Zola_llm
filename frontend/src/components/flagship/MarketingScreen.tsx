"use client";

import { useState } from "react";
import { Megaphone, ShieldCheck, AlertCircle } from "lucide-react";
import { Card, Button, Skeleton } from "../ui";
import { FlagshipHeader } from "./_shared";
import { api, ApiError } from "@/lib/api";
import { runQuery } from "@/lib/query";

interface Consent { finalite: string; eligibles: number; exclus: number; total: number }
interface Audience { segments: Record<string, number>; consent: Consent }

// Audience d'exemple (en prod : contacts du client). Consentement par finalité.
const CONTACTS = [
  { id_externe: "C1", nom: "Awa", type: "client", derniere_interaction: "2026-06-10", consentement_marketing: true, finalites: ["newsletter", "promotions"] },
  { id_externe: "C2", nom: "Paul", type: "client", derniere_interaction: "2026-04-01", consentement_marketing: false, finalites: [] },
  { id_externe: "C3", nom: "Sylvie", type: "prospect", derniere_interaction: null, consentement_marketing: true, finalites: ["newsletter"] },
  { id_externe: "C4", nom: "Jean", type: "client", derniere_interaction: "2026-06-18", consentement_marketing: true, finalites: ["promotions"] },
];

export function MarketingScreen() {
  const [finalite, setFinalite] = useState("promotions");
  const [canal, setCanal] = useState("email");
  const [brief, setBrief] = useState("Soldes de fin d'année, -20% sur les consommables.");
  const [aud, setAud] = useState<Audience | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function checkAudience() {
    setErr(null);
    try { setAud(await api<Audience>("/v1/mkt/audience", { body: { contacts: CONTACTS, finalite } })); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible."); }
  }

  async function generate() {
    if (!aud) { await checkAudience(); }
    const consent = aud?.consent;
    if (consent && consent.eligibles === 0) {
      setErr("Aucun contact consentant pour cette finalité — campagne bloquée (Loi 29-2019).");
      return;
    }
    setLoading(true); setErr(null); setContent(null);
    const q = `Rédige un contenu marketing pour le canal "${canal}", finalité "${finalite}". `
      + `Brief : ${brief}. Inclure une mention de désinscription si email. Pas d'allégation trompeuse.`;
    try { setContent((await runQuery(q)).content); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible (LLM/auth requis ou hors-ligne)."); }
    finally { setLoading(false); }
  }

  const consent = aud?.consent;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={Megaphone} title="Marketing" subtitle="Composeur de campagne — ciblage conforme au consentement (Loi 29-2019)." />

      <Card className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm"><span className="mb-1 block font-medium">Finalité</span>
            <select value={finalite} onChange={(e) => { setFinalite(e.target.value); setAud(null); }} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              <option value="promotions">Promotions</option><option value="newsletter">Newsletter</option>
            </select>
          </label>
          <label className="text-sm"><span className="mb-1 block font-medium">Canal</span>
            <select value={canal} onChange={(e) => setCanal(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              <option value="email">Email</option><option value="sms">SMS</option><option value="post">Post</option>
            </select>
          </label>
        </div>
        <label className="text-sm"><span className="mb-1 block font-medium">Brief</span>
          <textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={3} className="w-full resize-y rounded-xl border border-black/10 bg-white p-2 text-sm outline-none focus:ring-2 focus:ring-primary/40" />
        </label>
        <div className="flex justify-between">
          <Button variant="ghost" onClick={checkAudience}><ShieldCheck className="h-4 w-4" /> Vérifier l'audience</Button>
          <Button onClick={generate} disabled={loading}>Générer le contenu</Button>
        </div>
      </Card>

      {consent && (
        <Card className={consent.eligibles === 0 ? "ring-red-200" : "ring-emerald-200"}>
          <div className="flex items-center gap-2 text-sm">
            <ShieldCheck className={"h-4 w-4 " + (consent.eligibles === 0 ? "text-red-600" : "text-emerald-600")} />
            <span><b>{consent.eligibles}</b> contact(s) éligible(s) · <b>{consent.exclus}</b> exclu(s) (non consentants) sur {consent.total} — finalité « {consent.finalite} ».</span>
          </div>
        </Card>
      )}

      {loading && <Card><Skeleton className="mb-2 h-4 w-1/3" /><Skeleton className="h-4 w-full" /></Card>}
      {err && <Card className="ring-amber-200"><div className="flex items-start gap-2 text-amber-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><p className="text-sm">{err}</p></div></Card>}
      {content && <Card><pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{content}</pre></Card>}
    </div>
  );
}
