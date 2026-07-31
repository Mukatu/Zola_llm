"use client";

// PSA (cockpit cabinet Zolacortex) : feuilles de temps. Tout consultant saisit et
// soumet son temps sur les missions ; le cabinet (admin:users) suit en plus
// l'économie de mission (honoraires/coût/marge/WIP) et le taux d'occupation.
import { useEffect, useMemo, useState } from "react";
import { Clock, Timer, TrendingUp, Info, Send, Sparkles, Plus } from "lucide-react";
import { Card, Button, Badge, Skeleton, type BadgeTone } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import { listMissions, type MissionSummary } from "@/lib/cortex";
import {
  logTime,
  listTimeEntries,
  updateTimeEntry,
  getEngagement,
  getUtilization,
  getRateCard,
  assistTimeEntries,
  type TimeEntry,
  type TimeEntryStatus,
  type Economics,
  type UtilizationRow,
  type RateCard,
} from "@/lib/cortex-psa";

interface DraftRow {
  key: string;
  entry_date: string;
  hours: string;
  mission_id: string;
  activity: string;
  billable: boolean;
}

const STATUS_TONE: Record<TimeEntryStatus, BadgeTone> = {
  draft: "grey",
  submitted: "amber",
  approved: "green",
  rejected: "red",
};

const STATUS_LABEL: Record<TimeEntryStatus, string> = {
  draft: "brouillon",
  submitted: "soumis",
  approved: "approuvé",
  rejected: "rejeté",
};

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return "Accès réservé aux administrateurs.";
  return fallback;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { year: "numeric", month: "short", day: "numeric" });
}

function fmtHours(minutes: number): string {
  return (minutes / 60).toFixed(1) + " h";
}

function fmtMoney(n: number, currency: string): string {
  return new Intl.NumberFormat("fr-FR").format(n) + " " + currency;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function currentPeriod(): string {
  return new Date().toISOString().slice(0, 7);
}

function missionLabel(missions: MissionSummary[], missionId: string): string {
  return missions.find((m) => m.mission_id === missionId)?.offre ?? missionId;
}

function occupationTone(pct: number | null): BadgeTone {
  if (pct === null) return "grey";
  if (pct < 60) return "amber";
  if (pct >= 80) return "green";
  return "blue";
}

export default function TempsPage() {
  const { config, user } = useZola();
  const cabinetAllowed = hasScope(user, "admin:users");

  const [missions, setMissions] = useState<MissionSummary[]>([]);

  // --- Ma feuille de temps -------------------------------------------------
  const [missionId, setMissionId] = useState("");
  const [entryDate, setEntryDate] = useState(todayIso());
  const [hours, setHours] = useState("");
  const [billable, setBillable] = useState(true);
  const [activity, setActivity] = useState("");
  const [saving, setSaving] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);

  const [myEntries, setMyEntries] = useState<TimeEntry[]>([]);
  const [myLoading, setMyLoading] = useState(true);
  const [myErr, setMyErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function reloadMine() {
    setMyLoading(true);
    try {
      const rows = await listTimeEntries({ mine: true });
      setMyEntries(rows);
      setMyErr(null);
    } catch (e) {
      setMyErr(messageFromError(e, "Feuille de temps indisponible (backend cortex requis)."));
    } finally {
      setMyLoading(false);
    }
  }

  useEffect(() => {
    if (config.profil !== "cortex") {
      setMyLoading(false);
      return;
    }
    reloadMine();
    listMissions()
      .then(setMissions)
      .catch(() => setMissions([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.profil]);

  useEffect(() => {
    if (!missionId && missions.length > 0) setMissionId(missions[0].mission_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [missions]);

  async function submitEntry() {
    if (!missionId) {
      setFormErr("Sélectionnez une mission.");
      return;
    }
    const h = Number(hours);
    if (!h || h <= 0) {
      setFormErr("Durée invalide.");
      return;
    }
    setSaving(true);
    setFormErr(null);
    try {
      await logTime({
        mission_id: missionId,
        entry_date: entryDate,
        minutes: Math.round(h * 60),
        billable,
        activity,
      });
      setHours("");
      setActivity("");
      await reloadMine();
    } catch (e) {
      setFormErr(messageFromError(e, "Échec de l'enregistrement."));
    } finally {
      setSaving(false);
    }
  }

  async function submitDraft(id: string) {
    setBusyId(id);
    try {
      await updateTimeEntry(id, { action: "submit" });
      await reloadMine();
    } catch (e) {
      setMyErr(messageFromError(e, "Échec de la soumission."));
    } finally {
      setBusyId(null);
    }
  }

  // --- Saisie assistée (IA) — propositions à valider, rien n'est créé ------
  const [narrative, setNarrative] = useState("");
  const [weekStart, setWeekStart] = useState("");
  const [assisting, setAssisting] = useState(false);
  const [assistErr, setAssistErr] = useState<string | null>(null);
  const [assistStatus, setAssistStatus] = useState<"idle" | "suggested" | "unavailable">("idle");
  const [drafts, setDrafts] = useState<DraftRow[]>([]);
  const [draftBusy, setDraftBusy] = useState<string | null>(null);

  async function proposeEntries() {
    if (!narrative.trim()) return;
    setAssisting(true);
    setAssistErr(null);
    try {
      const result = await assistTimeEntries({ narrative, week_start: weekStart || undefined });
      setAssistStatus(result.status);
      if (result.status === "suggested") {
        setDrafts(
          result.suggestions.map((s, i) => ({
            key: `sug-${Date.now()}-${i}`,
            entry_date: s.entry_date ?? todayIso(),
            hours: String(s.hours),
            mission_id: s.mission_id ?? "",
            activity: s.activity,
            billable: s.billable,
          })),
        );
      } else {
        setDrafts([]);
      }
    } catch (e) {
      setAssistErr(messageFromError(e, "Échec de la suggestion de saisie."));
    } finally {
      setAssisting(false);
    }
  }

  function updateDraft(key: string, patch: Partial<DraftRow>) {
    setDrafts((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  function dismissDraft(key: string) {
    setDrafts((rows) => rows.filter((r) => r.key !== key));
  }

  async function addDraft(row: DraftRow) {
    const h = Number(row.hours);
    if (!row.mission_id || !h || h <= 0) {
      setAssistErr("Sélectionnez une mission et une durée valide avant d'ajouter.");
      return;
    }
    setDraftBusy(row.key);
    setAssistErr(null);
    try {
      await logTime({
        mission_id: row.mission_id,
        entry_date: row.entry_date,
        minutes: Math.round(h * 60),
        billable: row.billable,
        activity: row.activity,
      });
      dismissDraft(row.key);
      await reloadMine();
    } catch (e) {
      setAssistErr(messageFromError(e, "Échec de l'ajout de la ligne."));
    } finally {
      setDraftBusy(null);
    }
  }

  // --- Vue cabinet (admin:users) ------------------------------------------
  const [econMissionId, setEconMissionId] = useState("");
  const [econ, setEcon] = useState<Economics | null>(null);
  const [econLoading, setEconLoading] = useState(false);
  const [econErr, setEconErr] = useState<string | null>(null);

  const [period, setPeriod] = useState(currentPeriod());
  const [util, setUtil] = useState<UtilizationRow[]>([]);
  const [utilLoading, setUtilLoading] = useState(false);
  const [utilErr, setUtilErr] = useState<string | null>(null);

  const [rateCard, setRateCard] = useState<RateCard | null>(null);

  useEffect(() => {
    if (!cabinetAllowed || config.profil !== "cortex") return;
    getRateCard()
      .then(setRateCard)
      .catch(() => setRateCard(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cabinetAllowed, config.profil]);

  useEffect(() => {
    if (!econMissionId && missions.length > 0) setEconMissionId(missions[0].mission_id);
  }, [missions, econMissionId]);

  useEffect(() => {
    if (!cabinetAllowed || !econMissionId) {
      setEcon(null);
      return;
    }
    let alive = true;
    setEconLoading(true);
    getEngagement(econMissionId)
      .then((e) => {
        if (alive) {
          setEcon(e);
          setEconErr(null);
        }
      })
      .catch((e) => {
        if (alive) setEconErr(messageFromError(e, "Économie de la mission indisponible."));
      })
      .finally(() => {
        if (alive) setEconLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [cabinetAllowed, econMissionId]);

  useEffect(() => {
    if (!cabinetAllowed) return;
    let alive = true;
    setUtilLoading(true);
    getUtilization(period)
      .then((rows) => {
        if (alive) {
          setUtil(rows);
          setUtilErr(null);
        }
      })
      .catch((e) => {
        if (alive) setUtilErr(messageFromError(e, "Taux d'occupation indisponible."));
      })
      .finally(() => {
        if (alive) setUtilLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [cabinetAllowed, period]);

  const rateCardEmpty = useMemo(() => {
    if (!rateCard) return false;
    const rates = Object.values(rateCard);
    return rates.length > 0 && rates.every((r) => r.bill_rate === 0 && r.cost_rate === 0);
  }, [rateCard]);

  if (config.profil !== "cortex") {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <p className="text-sm text-muted">Réservé au cockpit cabinet.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest">
          <Clock className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-lg font-semibold">Feuilles de temps</h1>
          <p className="text-sm text-muted">Saisie du temps sur les missions — PSA du cabinet.</p>
        </div>
      </div>

      {/* --- Ma feuille de temps --- */}
      <Card className="flex flex-col gap-4">
        <div className="text-sm font-semibold">Ma feuille de temps</div>

        {formErr && <p className="text-sm text-amber-700">{formErr}</p>}

        <div className="grid gap-3 sm:grid-cols-5">
          <label className="text-sm sm:col-span-2">
            <span className="mb-1 block font-medium">Mission</span>
            {missions.length > 0 ? (
              <select
                value={missionId}
                onChange={(e) => setMissionId(e.target.value)}
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              >
                {missions.map((m) => (
                  <option key={m.mission_id} value={m.mission_id}>
                    {m.offre}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={missionId}
                onChange={(e) => setMissionId(e.target.value)}
                placeholder="id de la mission"
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              />
            )}
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Date</span>
            <input
              type="date"
              value={entryDate}
              onChange={(e) => setEntryDate(e.target.value)}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Durée (h)</span>
            <input
              type="number"
              min={0}
              step={0.25}
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              placeholder="ex. 2.5"
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
          <label className="flex items-end gap-1.5 text-sm">
            <input
              type="checkbox"
              checked={billable}
              onChange={(e) => setBillable(e.target.checked)}
              className="h-3.5 w-3.5 accent-primary"
            />
            <span>Facturable</span>
          </label>
        </div>

        <label className="text-sm">
          <span className="mb-1 block font-medium">Activité</span>
          <input
            type="text"
            value={activity}
            onChange={(e) => setActivity(e.target.value)}
            placeholder="ex. revue de dossier, entretien client…"
            className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          />
        </label>

        <div>
          <Button onClick={submitEntry} disabled={saving}>
            <Clock className="h-4 w-4" /> Enregistrer
          </Button>
        </div>

        <div className="border-t border-black/5 pt-3">
          {myErr && <p className="mb-2 text-sm text-amber-700">{myErr}</p>}
          {myLoading && !myEntries.length && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          )}
          {!myLoading && myEntries.length === 0 && !myErr && (
            <p className="text-sm text-muted">Aucune saisie pour le moment.</p>
          )}
          {myEntries.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-black/5 text-left text-xs text-muted">
                    <th className="py-2 pr-3 font-medium">Date</th>
                    <th className="py-2 pr-3 font-medium">Mission</th>
                    <th className="py-2 pr-3 font-medium">Durée</th>
                    <th className="py-2 pr-3 font-medium">Statut</th>
                    <th className="py-2 pr-3 font-medium">Honoraires</th>
                    <th className="py-2 pr-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {myEntries.map((entry) => (
                    <tr key={entry.id} className="border-b border-black/5 last:border-0">
                      <td className="py-2 pr-3">{fmtDate(entry.entry_date)}</td>
                      <td className="py-2 pr-3">{missionLabel(missions, entry.mission_id)}</td>
                      <td className="py-2 pr-3">{fmtHours(entry.minutes)}</td>
                      <td className="py-2 pr-3">
                        <Badge tone={STATUS_TONE[entry.status]}>{STATUS_LABEL[entry.status]}</Badge>
                      </td>
                      <td className="py-2 pr-3">
                        {entry.billable ? fmtMoney(entry.honoraires, "XAF") : "—"}
                      </td>
                      <td className="py-2 pr-3 text-right">
                        {entry.status === "draft" && (
                          <Button variant="ghost" onClick={() => submitDraft(entry.id)} disabled={busyId === entry.id}>
                            <Send className="h-3.5 w-3.5" /> Soumettre
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      {/* --- Saisie assistée (IA) --- */}
      <Card className="flex flex-col gap-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles className="h-4 w-4" /> Saisie assistée (IA)
        </div>
        <p className="text-xs text-muted">
          Décrivez votre semaine en langage libre : l&apos;assistant propose des lignes de temps à
          partir de votre récit. <strong>Rien n&apos;est enregistré</strong> — chaque ligne reste une
          proposition que vous relisez, corrigez si besoin, puis validez une à une avec « Ajouter ».
        </p>

        <label className="text-sm">
          <span className="mb-1 block font-medium">Récit de la semaine</span>
          <textarea
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            rows={4}
            placeholder="ex. Lundi 3h sur l'audit ACME, mardi 2h de cadrage…"
            className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          />
        </label>

        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block font-medium">Lundi de référence (optionnel)</span>
            <input
              type="date"
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
          <Button onClick={proposeEntries} disabled={assisting || !narrative.trim()}>
            <Sparkles className="h-4 w-4" /> {assisting ? "Analyse en cours…" : "Proposer des lignes"}
          </Button>
        </div>

        {assistErr && <p className="text-sm text-amber-700">{assistErr}</p>}
        {assistStatus === "unavailable" && (
          <p className="text-sm text-amber-700">Assistant de saisie indisponible pour le moment.</p>
        )}
        {assistStatus === "suggested" && drafts.length === 0 && (
          <p className="text-sm text-muted">Aucune ligne détectée dans le récit.</p>
        )}

        {drafts.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-amber-700">
              Propositions à valider — aucune ligne n&apos;est enregistrée avant votre clic sur « Ajouter ».
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-black/5 text-left text-xs text-muted">
                    <th className="py-2 pr-3 font-medium">Date</th>
                    <th className="py-2 pr-3 font-medium">Durée (h)</th>
                    <th className="py-2 pr-3 font-medium">Mission</th>
                    <th className="py-2 pr-3 font-medium">Activité</th>
                    <th className="py-2 pr-3 font-medium">Facturable</th>
                    <th className="py-2 pr-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {drafts.map((row) => (
                    <tr key={row.key} className="border-b border-black/5 last:border-0">
                      <td className="py-2 pr-3">
                        <input
                          type="date"
                          value={row.entry_date}
                          onChange={(e) => updateDraft(row.key, { entry_date: e.target.value })}
                          className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
                        />
                      </td>
                      <td className="py-2 pr-3">
                        <input
                          type="number"
                          min={0}
                          step={0.25}
                          value={row.hours}
                          onChange={(e) => updateDraft(row.key, { hours: e.target.value })}
                          className="w-20 rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
                        />
                      </td>
                      <td className="py-2 pr-3">
                        {missions.length > 0 ? (
                          <select
                            value={row.mission_id}
                            onChange={(e) => updateDraft(row.key, { mission_id: e.target.value })}
                            className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
                          >
                            <option value="">—</option>
                            {missions.map((m) => (
                              <option key={m.mission_id} value={m.mission_id}>
                                {m.offre}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input
                            type="text"
                            value={row.mission_id}
                            onChange={(e) => updateDraft(row.key, { mission_id: e.target.value })}
                            placeholder="id de la mission"
                            className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
                          />
                        )}
                      </td>
                      <td className="py-2 pr-3">
                        <input
                          type="text"
                          value={row.activity}
                          onChange={(e) => updateDraft(row.key, { activity: e.target.value })}
                          className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
                        />
                      </td>
                      <td className="py-2 pr-3">
                        <input
                          type="checkbox"
                          checked={row.billable}
                          onChange={(e) => updateDraft(row.key, { billable: e.target.checked })}
                          className="h-3.5 w-3.5 accent-primary"
                        />
                      </td>
                      <td className="py-2 pr-3 text-right">
                        <div className="flex justify-end gap-1.5">
                          <Button onClick={() => addDraft(row)} disabled={draftBusy === row.key}>
                            <Plus className="h-3.5 w-3.5" /> Ajouter
                          </Button>
                          <Button variant="ghost" onClick={() => dismissDraft(row.key)} disabled={draftBusy === row.key}>
                            Ignorer
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>

      {/* --- Vue cabinet --- */}
      {cabinetAllowed && (
        <div className="flex flex-col gap-4">
          <div className="text-sm font-semibold text-muted">Vue cabinet</div>

          {rateCardEmpty && (
            <Card className="ring-amber-200">
              <p className="flex items-center gap-2 text-sm text-amber-700">
                <Info className="h-4 w-4 shrink-0" />
                Barème d&apos;honoraires non configuré (PSA_RATE_CARD_JSON) — honoraires, coût et marge
                restent à zéro tant que le cabinet n&apos;a pas fixé ses taux.
              </p>
            </Card>
          )}

          <Card className="flex flex-col gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Timer className="h-4 w-4" /> Économie de la mission
            </div>
            <label className="text-sm sm:max-w-xs">
              <span className="mb-1 block font-medium">Mission</span>
              {missions.length > 0 ? (
                <select
                  value={econMissionId}
                  onChange={(e) => setEconMissionId(e.target.value)}
                  className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                >
                  {missions.map((m) => (
                    <option key={m.mission_id} value={m.mission_id}>
                      {m.offre}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={econMissionId}
                  onChange={(e) => setEconMissionId(e.target.value)}
                  placeholder="id de la mission"
                  className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                />
              )}
            </label>

            {econErr && <p className="text-sm text-amber-700">{econErr}</p>}
            {econLoading && !econ && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            )}
            {econ && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
                  <div className="text-xs text-muted">Honoraires</div>
                  <div className="text-lg font-semibold text-ink">{fmtMoney(econ.honoraires, econ.currency)}</div>
                </div>
                <div className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
                  <div className="text-xs text-muted">Coût</div>
                  <div className="text-lg font-semibold text-ink">{fmtMoney(econ.cost, econ.currency)}</div>
                </div>
                <div className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
                  <div className="text-xs text-muted">Marge</div>
                  <div className={"text-lg font-semibold " + (econ.margin >= 0 ? "text-emerald-700" : "text-red-700")}>
                    {fmtMoney(econ.margin, econ.currency)}
                    {econ.margin_pct !== null && <span className="ml-1 text-xs font-normal text-muted">({econ.margin_pct}%)</span>}
                  </div>
                </div>
                <div className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
                  <div className="text-xs text-muted">WIP (encours)</div>
                  <div className="text-lg font-semibold text-ink">{fmtMoney(econ.honoraires_wip, econ.currency)}</div>
                </div>
              </div>
            )}
          </Card>

          <Card className="flex flex-col gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <TrendingUp className="h-4 w-4" /> Taux d&apos;occupation
            </div>
            <label className="text-sm sm:max-w-xs">
              <span className="mb-1 block font-medium">Mois</span>
              <input
                type="month"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              />
            </label>

            {utilErr && <p className="text-sm text-amber-700">{utilErr}</p>}
            {utilLoading && !util.length && (
              <div className="flex flex-col gap-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            )}
            {!utilLoading && util.length === 0 && !utilErr && (
              <p className="text-sm text-muted">Aucune saisie sur ce mois.</p>
            )}
            {util.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-black/5 text-left text-xs text-muted">
                      <th className="py-2 pr-3 font-medium">Consultant</th>
                      <th className="py-2 pr-3 font-medium">Travaillé</th>
                      <th className="py-2 pr-3 font-medium">Facturable</th>
                      <th className="py-2 pr-3 font-medium">Occupation</th>
                      <th className="py-2 pr-3 font-medium">Activité</th>
                    </tr>
                  </thead>
                  <tbody>
                    {util.map((row) => (
                      <tr key={row.consultant_user_id} className="border-b border-black/5 last:border-0">
                        <td className="py-2 pr-3 font-mono text-xs">{row.consultant_user_id.slice(0, 8)}</td>
                        <td className="py-2 pr-3">{fmtHours(row.worked_minutes)}</td>
                        <td className="py-2 pr-3">{fmtHours(row.billable_minutes)}</td>
                        <td className="py-2 pr-3">
                          <Badge tone={occupationTone(row.occupation_pct)}>
                            {row.occupation_pct === null ? "—" : row.occupation_pct + " %"}
                          </Badge>
                        </td>
                        <td className="py-2 pr-3 text-muted">
                          {row.activity_pct === null ? "—" : row.activity_pct + " %"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
