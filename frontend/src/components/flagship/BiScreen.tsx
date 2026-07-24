"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart3, Sparkles, AlertTriangle, CalendarClock, Send, Loader2, TrendingDown, TrendingUp, Camera } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, LineTrend, type TrendPoint } from "./_shared";
import { Prose } from "../Prose";
import {
  biCockpit, biBrief, biAsk, treasuryPilotage, biSnapshot, biSnapshots, fmt,
  type Cockpit, type Signal, type Kpi, type TreasuryPilotage, type BiSnapshot,
} from "@/lib/data";
import { ApiError } from "@/lib/api";

const jm = (s: string) => `${s.slice(8, 10)}/${s.slice(5, 7)}`;

/** Trajectoire du solde projeté — sparkline SVG autoporté (sans lib). */
function TrajectoireTreso({ pilotage }: { pilotage: TreasuryPilotage }) {
  const { previsionnel } = pilotage;
  const serie = [Number(previsionnel.position_initiale_xaf), ...previsionnel.periodes.map((p) => Number(p.solde_projete_xaf))];
  const W = 320, H = 96, PAD = 8;
  const min = Math.min(...serie, 0);
  const max = Math.max(...serie, 0);
  const span = max - min || 1;
  const x = (i: number) => PAD + (i * (W - 2 * PAD)) / Math.max(1, serie.length - 1);
  const y = (v: number) => PAD + ((max - v) / span) * (H - 2 * PAD);
  const pts = serie.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const zeroY = y(0);
  const aire = `${x(0)},${zeroY} ${pts} ${x(serie.length - 1)},${zeroY}`;
  const decouvert = previsionnel.decouvert_periode !== null;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none" role="img" aria-label="Trajectoire du solde de trésorerie projeté">
      <polygon points={aire} fill={decouvert ? "rgb(239 68 68 / 0.10)" : "rgb(20 184 166 / 0.10)"} />
      <line x1={PAD} y1={zeroY} x2={W - PAD} y2={zeroY} stroke="rgb(0 0 0 / 0.25)" strokeWidth="1" strokeDasharray="3 3" />
      <polyline points={pts} fill="none" stroke={decouvert ? "rgb(220 38 38)" : "rgb(13 148 136)"} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/** Pilotage de trésorerie : solde projeté daté + indicateurs de rotation (moteur canonique). */
function PilotageCard({ pilotage }: { pilotage: TreasuryPilotage }) {
  const { previsionnel: prev, indicateurs: ind } = pilotage;
  const decouvert = prev.decouvert_periode !== null;
  const decDate = decouvert ? prev.periodes.find((p) => p.libelle === prev.decouvert_periode)?.debut : null;
  const p0 = prev.periodes[0]?.debut;
  const pN = prev.periodes[prev.periodes.length - 1]?.debut;
  return (
    <Card className={decouvert ? "ring-red-200" : undefined}>
      <div className="flex items-center gap-2">
        <TrendingDown className="h-5 w-5 text-primary" />
        <h2 className="text-sm font-semibold">Pilotage de trésorerie (90 j)</h2>
      </div>
      <p className="mt-0.5 text-xs text-muted">
        Projection déterministe du solde à partir des flux prévus du registre. Le moteur calcule, aucune valeur n&apos;est inventée.
      </p>

      {decouvert && (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <span className="font-semibold">Découvert prévu{decDate ? ` — semaine du ${jm(decDate)}` : ""}.</span>{" "}
          Solde projeté {fmt(prev.decouvert_xaf ?? "0")} XAF. Anticipez un financement ou décalez des décaissements.
        </div>
      )}

      <div className="mt-3 grid grid-cols-3 gap-3">
        <div>
          <div className="text-xs text-muted">Position actuelle</div>
          <div className="mt-0.5 text-lg font-semibold tabular-nums">{fmt(prev.position_initiale_xaf)}</div>
        </div>
        <div>
          <div className="text-xs text-muted">Flux prévus (enc. / déc.)</div>
          <div className="mt-0.5 text-sm font-semibold tabular-nums">
            <span className="text-emerald-600">+{fmt(prev.encaissements_total_xaf)}</span>
            {" / "}
            <span className="text-red-600">−{fmt(prev.decaissements_total_xaf)}</span>
          </div>
        </div>
        <div>
          <div className="text-xs text-muted">Position projetée (90 j)</div>
          <div className={"mt-0.5 text-lg font-semibold tabular-nums " + (Number(prev.position_finale_xaf) < 0 ? "text-red-600" : "")}>
            {fmt(prev.position_finale_xaf)}
          </div>
        </div>
      </div>

      <div className="mt-3">
        <TrajectoireTreso pilotage={pilotage} />
        <div className="mt-1 flex justify-between text-[10px] text-muted">
          <span>{p0 ? jm(p0) : ""}</span>
          <span>{pN ? jm(pN) : ""}</span>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div className="rounded-xl border border-black/10 bg-black/[0.02] p-2">
          <div className="text-[11px] text-muted">DSO (encaissement)</div>
          <div className="text-sm font-semibold tabular-nums">{ind.dso_jours} j</div>
        </div>
        <div className="rounded-xl border border-black/10 bg-black/[0.02] p-2">
          <div className="text-[11px] text-muted">DPO (paiement)</div>
          <div className="text-sm font-semibold tabular-nums">{ind.dpo_jours} j</div>
        </div>
        <div className="rounded-xl border border-black/10 bg-black/[0.02] p-2">
          <div className="text-[11px] text-muted">BFR</div>
          <div className="text-sm font-semibold tabular-nums">{fmt(ind.bfr_xaf)}</div>
        </div>
        <div className="rounded-xl border border-black/10 bg-black/[0.02] p-2">
          <div className="text-[11px] text-muted">Runway</div>
          <div className="text-sm font-semibold tabular-nums">{ind.runway_mois !== null ? `${fmt(ind.runway_mois)} mois` : "—"}</div>
        </div>
      </div>
    </Card>
  );
}

/** Tendances des KPIs du cockpit — instantanés manuels, historisation via LineTrend. */
function TendancesCard() {
  const [snaps, setSnaps] = useState<BiSnapshot[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");

  const refresh = useCallback(async () => {
    try {
      const r = await biSnapshots(60);
      setSnaps(r.snapshots);
    } catch {
      setSnaps([]);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const dernier = snaps[snaps.length - 1];
  const kpisDernier = dernier?.kpis ?? [];
  useEffect(() => {
    if (!code && dernier && dernier.kpis.length > 0) setCode(dernier.kpis[0].code);
  }, [code, dernier]);

  async function capturer() {
    if (busy) return;
    setBusy(true);
    try {
      await biSnapshot();
      await refresh();
    } catch {
      // ignoré — le bouton reste disponible pour réessayer
    } finally {
      setBusy(false);
    }
  }

  const libelle = kpisDernier.find((k) => k.code === code)?.libelle ?? code;
  const points: TrendPoint[] = snaps
    .map((s) => {
      const k = s.kpis.find((x) => x.code === code);
      return k ? { date: jm(s.captured_at), value: Number(k.valeur) } : null;
    })
    .filter((p): p is TrendPoint => p !== null);

  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-primary" />
          <h2 className="text-sm font-semibold">Tendances</h2>
        </div>
        <Button onClick={capturer} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
          Capturer un instantané
        </Button>
      </div>
      {loaded && kpisDernier.length === 0 && (
        <p className="mt-2 text-sm text-muted">Aucun instantané pour le moment. Capturez-en un pour démarrer l&apos;historisation.</p>
      )}
      {kpisDernier.length > 0 && (
        <>
          <div className="mt-3 flex items-center gap-2">
            <label className="text-xs text-muted" htmlFor="tendance-kpi">Indicateur</label>
            <select
              id="tendance-kpi"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            >
              {kpisDernier.map((k) => (
                <option key={k.code} value={k.code}>{k.libelle}</option>
              ))}
            </select>
          </div>
          {snaps.length < 2 ? (
            <p className="mt-3 text-sm text-muted">Capturez des instantanés régulièrement pour voir la tendance.</p>
          ) : (
            <div className="mt-3">
              <LineTrend points={points} ariaLabel={`Tendance ${libelle}`} />
            </div>
          )}
        </>
      )}
    </Card>
  );
}

const DOMAINE: Record<string, string> = {
  commercial: "Commercial",
  finance: "Finance",
  achats: "Achats",
  supply: "Supply Chain",
  rh: "RH",
  projets: "Projets / Bailleurs",
};
const ORDRE = ["commercial", "finance", "achats", "supply", "rh", "projets"];

const NIVEAU: Record<string, string> = {
  alerte: "border-red-200 bg-red-50 text-red-800",
  attention: "border-amber-200 bg-amber-50 text-amber-800",
  info: "border-black/10 bg-black/[0.03] text-ink/70",
};

export function BiScreen() {
  const [cockpit, setCockpit] = useState<Cockpit | null>(null);
  const [pilotage, setPilotage] = useState<TreasuryPilotage | null>(null);
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
    treasuryPilotage().then(setPilotage).catch(() => setPilotage(null));
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
          <Prose text={brief} className="mt-3" />
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

      {/* Pilotage de trésorerie — prévisionnel + indicateurs (moteur canonique) */}
      {pilotage && pilotage.previsionnel.periodes.length > 0 && <PilotageCard pilotage={pilotage} />}

      {/* Tendances des KPIs — instantanés manuels du cockpit */}
      <TendancesCard />

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
          {answer && <Prose text={answer} className="mt-3" />}
        </Card>
      )}
    </div>
  );
}
