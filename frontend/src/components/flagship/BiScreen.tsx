"use client";

import { useEffect, useState } from "react";
import { BarChart3, Sparkles, AlertTriangle, CalendarClock, Send, Loader2 } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader } from "./_shared";
import { biCockpit, biBrief, biAsk, fmt, type Cockpit, type Signal, type Kpi } from "@/lib/data";
import { ApiError } from "@/lib/api";

const DOMAINE: Record<string, string> = {
  commercial: "Commercial",
  finance: "Finance",
  achats: "Achats",
  supply: "Supply Chain",
  rh: "RH",
};
const ORDRE = ["commercial", "finance", "achats", "supply", "rh"];

const NIVEAU: Record<string, string> = {
  alerte: "border-red-200 bg-red-50 text-red-800",
  attention: "border-amber-200 bg-amber-50 text-amber-800",
  info: "border-black/10 bg-black/[0.03] text-ink/70",
};

export function BiScreen() {
  const [cockpit, setCockpit] = useState<Cockpit | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [brief, setBrief] = useState<string | null>(null);
  const [briefBusy, setBriefBusy] = useState(false);
  const [briefErr, setBriefErr] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [askBusy, setAskBusy] = useState(false);

  useEffect(() => {
    biCockpit()
      .then(setCockpit)
      .catch(() => setErr("Backend indisponible (DB requise)."));
  }, []);

  async function genererBrief() {
    if (briefBusy) return;
    setBriefBusy(true);
    setBriefErr(null);
    setBrief(null);
    try {
      setBrief((await biBrief()).brief);
    } catch (e) {
      setBriefErr(e instanceof ApiError ? `Brief indisponible (LLM requis) — ${e.message}` : "Brief indisponible");
    } finally {
      setBriefBusy(false);
    }
  }

  async function poser() {
    if (askBusy || !q.trim()) return;
    setAskBusy(true);
    setAnswer(null);
    try {
      setAnswer((await biAsk(q)).answer);
    } catch (e) {
      setAnswer(e instanceof ApiError ? `Indisponible (LLM requis) — ${e.message}` : "Indisponible");
    } finally {
      setAskBusy(false);
    }
  }

  const kpis = cockpit?.kpis ?? [];
  const signals = cockpit?.signals ?? [];
  const echeances = cockpit?.echeances ?? [];
  const alertes = signals.filter((s) => s.niveau !== "info");
  const byDomaine = kpis.reduce<Record<string, Kpi[]>>((acc, k) => {
    (acc[k.domaine] ??= []).push(k);
    return acc;
  }, {});
  const allZero = kpis.length > 0 && kpis.every((k) => Number(k.valeur) === 0);

  return (
    <div className="flex flex-col gap-4">
      <FlagshipHeader
        icon={BarChart3}
        title="Pilotage / BI"
        subtitle="Cockpit décisionnel : chiffres agrégés, signaux dérivés, échéances et brief narré. Le LLM interprète, ne calcule jamais."
      />
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {/* Brief IA narré */}
      <Card>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-sm font-semibold">Brief de pilotage</h2>
          </div>
          <Button onClick={genererBrief} disabled={briefBusy}>
            {briefBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Générer le brief IA
          </Button>
        </div>
        {briefErr && <p className="mt-2 text-sm text-amber-700">{briefErr}</p>}
        {brief ? (
          <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-relaxed">{brief}</pre>
        ) : (
          !briefErr && <p className="mt-2 text-sm text-muted">Synthèse écrite des KPIs et signaux, en un clic.</p>
        )}
      </Card>

      {/* Signaux déterministes */}
      {alertes.length > 0 && (
        <section>
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted">
            <AlertTriangle className="h-4 w-4" /> Signaux ({alertes.length})
          </h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {alertes.map((s: Signal) => (
              <div key={s.code} className={"rounded-xl border p-3 " + (NIVEAU[s.niveau] ?? NIVEAU.info)}>
                <div className="text-sm font-semibold">{s.titre}</div>
                <div className="mt-0.5 text-xs opacity-80">{s.detail}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Échéances indicatives */}
      {echeances.length > 0 && (
        <section>
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted">
            <CalendarClock className="h-4 w-4" /> Échéances à venir
          </h2>
          <Card className="divide-y divide-black/5 p-0">
            {echeances.map((e) => (
              <div key={e.code} className="flex items-center justify-between px-3 py-2 text-sm">
                <div>
                  <span className="font-medium">{e.libelle}</span>
                  <span className="ml-2 rounded-full bg-black/5 px-1.5 py-0.5 text-[10px] uppercase text-muted">
                    indicatif
                  </span>
                </div>
                <div className="text-right">
                  <div className="tabular-nums">{e.date_limite}</div>
                  <div className="text-xs text-muted">dans {e.jours_restants} j</div>
                </div>
              </div>
            ))}
          </Card>
          <p className="mt-1 text-xs text-muted">
            Rappels indicatifs — confirmez les dates auprès de l&apos;administration ou de votre conseil.
          </p>
        </section>
      )}

      {allZero && (
        <Card>
          <p className="text-sm text-muted">
            Indicateurs à zéro : alimentez les registres (factures, trésorerie, stock, CRM, achats, RH) — le cockpit s&apos;actualise automatiquement.
          </p>
        </Card>
      )}

      {/* KPIs par domaine */}
      {ORDRE.filter((dom) => byDomaine[dom]).map((dom) => (
        <section key={dom}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">{DOMAINE[dom] ?? dom}</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {byDomaine[dom].map((k) => (
              <Card key={k.code}>
                <div className="text-xs text-muted">{k.libelle}</div>
                <div className="mt-1 text-xl font-semibold">
                  {fmt(k.valeur)} <span className="text-sm font-normal text-muted">{k.unite === "XAF" ? "XAF" : k.unite}</span>
                </div>
              </Card>
            ))}
          </div>
        </section>
      ))}

      {/* Question libre sur les KPIs */}
      {kpis.length > 0 && (
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Interroger le cockpit</h2>
          <div className="flex gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && poser()}
              placeholder="ex : quel domaine pèse le plus sur la trésorerie ?"
              className="flex-1 rounded-lg border border-black/10 bg-white px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/40"
            />
            <Button onClick={poser} disabled={askBusy || !q.trim()}>
              {askBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
          {answer && <pre className="mt-3 whitespace-pre-wrap font-sans text-sm leading-relaxed">{answer}</pre>}
        </Card>
      )}
    </div>
  );
}
