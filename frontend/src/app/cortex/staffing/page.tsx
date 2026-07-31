"use client";

// Plan de charge (staffing) du cockpit cabinet Zolacortex : affectation des
// consultants aux missions par semaine, et vue agrégée charge vs capacité.
// Acte de gestion prospectif → réservé au profil cortex + rôle admin.
import { useEffect, useState } from "react";
import { CalendarDays, Users, AlertTriangle, RefreshCw, Trash2 } from "lucide-react";
import { Card, Button, Badge, Skeleton, type BadgeTone } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import { listAccounts, type Account } from "@/lib/cortex-accounts";
import { listMissions, type MissionSummary } from "@/lib/cortex";
import {
  upsertAssignment,
  listAssignments,
  deleteAssignment,
  getLoadPlan,
  type Assignment,
  type LoadPlan,
  type WeekLoad,
} from "@/lib/cortex-staffing";

const DEFAULT_CAPACITY_MINUTES = 2400; // repli : 5 j × 480 min (8 h/j)
const STAFF_ROLES = ["consultant", "admin"];

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return "Accès réservé aux administrateurs.";
  return fallback;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function fmtWeek(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  return "sem. du " + d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", timeZone: "UTC" });
}

function fmtDays(minutes: number, capacityMinutes: number): string {
  const perDay = capacityMinutes / 5 || 480 / 1;
  return (minutes / perDay).toFixed(1) + " j";
}

function pct(n: number | null): string {
  return n === null ? "—" : n + " %";
}

function accountLabel(accounts: Account[], userId: string): string {
  const a = accounts.find((x) => x.id === userId);
  if (!a) return userId.slice(0, 8) + "…";
  return a.display_name || a.email;
}

function missionLabel(missions: MissionSummary[], missionId: string): string {
  const m = missions.find((x) => x.mission_id === missionId);
  if (!m) return missionId.slice(0, 8) + "…";
  return m.offre;
}

function cellClasses(week: WeekLoad): string {
  if (week.over_allocated) return "bg-red-100 text-red-700";
  if (!week.allocated_minutes || week.load_pct === 0) return "bg-black/5 text-muted";
  if (week.load_pct !== null && week.load_pct >= 80) return "bg-amber-100 text-amber-800";
  return "bg-green-100 text-green-700";
}

function avgTone(avg: number | null): BadgeTone {
  if (avg === null) return "grey";
  if (avg > 100) return "red";
  if (avg >= 80) return "amber";
  return "green";
}

export default function StaffingPage() {
  const { config, user } = useZola();
  const allowed = config.profil === "cortex" && hasScope(user, "admin:users");

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [missions, setMissions] = useState<MissionSummary[]>([]);
  const [refLoading, setRefLoading] = useState(true);
  const [refErr, setRefErr] = useState<string | null>(null);

  const [plan, setPlan] = useState<LoadPlan | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [planLoading, setPlanLoading] = useState(true);
  const [planErr, setPlanErr] = useState<string | null>(null);

  const [fromWeek, setFromWeek] = useState(todayIso());
  const [weeksCount, setWeeksCount] = useState(6);

  const consultants = accounts.filter((a) => STAFF_ROLES.includes(a.role));

  const [form, setForm] = useState({
    consultant_user_id: "",
    mission_id: "",
    week_start: todayIso(),
    days: "1",
    note: "",
  });
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);

  async function loadRefs() {
    setRefLoading(true);
    try {
      const [accs, miss] = await Promise.all([listAccounts(), listMissions()]);
      setAccounts(accs);
      setMissions(miss);
      setRefErr(null);
    } catch (e) {
      setRefErr(messageFromError(e, "Référentiels indisponibles (backend cortex requis)."));
    } finally {
      setRefLoading(false);
    }
  }

  async function loadPlan() {
    setPlanLoading(true);
    try {
      const to = addDaysIso(fromWeek, weeksCount * 7);
      const [p, a] = await Promise.all([
        getLoadPlan({ from: fromWeek, weeks: weeksCount }),
        listAssignments({ from: fromWeek, to }),
      ]);
      setPlan(p);
      setAssignments(a);
      setPlanErr(null);
    } catch (e) {
      setPlanErr(messageFromError(e, "Plan de charge indisponible (backend cortex requis)."));
    } finally {
      setPlanLoading(false);
    }
  }

  useEffect(() => {
    if (allowed) {
      loadRefs();
      loadPlan();
    } else {
      setRefLoading(false);
      setPlanLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.profil, user]);

  async function submit() {
    const daysNum = Number(form.days);
    if (!form.consultant_user_id || !form.mission_id || !form.week_start || !daysNum || daysNum <= 0) return;
    setBusy(true);
    setFormErr(null);
    try {
      const capacityMinutes = plan?.capacity_minutes ?? DEFAULT_CAPACITY_MINUTES;
      const allocated_minutes = Math.max(1, Math.round(daysNum * (capacityMinutes / 5)));
      await upsertAssignment({
        consultant_user_id: form.consultant_user_id,
        mission_id: form.mission_id,
        week_start: form.week_start,
        allocated_minutes,
        note: form.note || undefined,
      });
      setForm({ ...form, days: "1", note: "" });
      await loadPlan();
    } catch (e) {
      setFormErr(messageFromError(e, "Échec de l'affectation."));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await deleteAssignment(id);
      await loadPlan();
    } catch (e) {
      setPlanErr(messageFromError(e, "Échec de la suppression."));
    }
  }

  if (config.profil !== "cortex") {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <p className="text-sm text-muted">Réservé au cockpit cabinet.</p>
        </Card>
      </div>
    );
  }

  if (!hasScope(user, "admin:users")) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <p className="text-sm text-muted">Accès réservé aux administrateurs.</p>
        </Card>
      </div>
    );
  }

  const loading = refLoading || planLoading;
  const capacityMinutes = plan?.capacity_minutes ?? DEFAULT_CAPACITY_MINUTES;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><CalendarDays className="h-5 w-5" /></span>
        <div>
          <h1 className="text-lg font-semibold">Plan de charge</h1>
          <p className="text-sm text-muted">Affectation des consultants aux missions par semaine — charge vs capacité.</p>
        </div>
      </div>

      {refErr && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{refErr}</p></Card>}

      <Card className="grid gap-3 sm:grid-cols-[1fr_1fr_150px_110px_1fr_auto]">
        <label className="text-sm"><span className="mb-1 block font-medium">Consultant</span>
          <select
            value={form.consultant_user_id}
            onChange={(e) => setForm({ ...form, consultant_user_id: e.target.value })}
            className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          >
            <option value="">—</option>
            {consultants.map((a) => (
              <option key={a.id} value={a.id}>{a.display_name || a.email}</option>
            ))}
          </select>
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Mission</span>
          <select
            value={form.mission_id}
            onChange={(e) => setForm({ ...form, mission_id: e.target.value })}
            className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          >
            <option value="">—</option>
            {missions.map((m) => (
              <option key={m.mission_id} value={m.mission_id}>{m.offre}</option>
            ))}
          </select>
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Semaine</span>
          <input
            type="date"
            value={form.week_start}
            onChange={(e) => setForm({ ...form, week_start: e.target.value })}
            className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Jours</span>
          <input
            type="number"
            min={0.5}
            step={0.5}
            value={form.days}
            onChange={(e) => setForm({ ...form, days: e.target.value })}
            className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Note (optionnel)</span>
          <input
            value={form.note}
            onChange={(e) => setForm({ ...form, note: e.target.value })}
            className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          />
        </label>
        <div className="flex items-end">
          <Button onClick={submit} disabled={busy || !form.consultant_user_id || !form.mission_id}>
            <Users className="h-4 w-4" /> Affecter
          </Button>
        </div>
      </Card>

      {formErr && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{formErr}</p></Card>}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm"><span className="mb-1 block font-medium">Début</span>
            <input
              type="date"
              value={fromWeek}
              onChange={(e) => setFromWeek(e.target.value)}
              className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
          <label className="text-sm"><span className="mb-1 block font-medium">Semaines</span>
            <input
              type="number"
              min={1}
              max={52}
              value={weeksCount}
              onChange={(e) => setWeeksCount(Number(e.target.value) || 1)}
              className="w-20 rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
        </div>
        <Button variant="ghost" onClick={loadPlan} disabled={planLoading}>
          <RefreshCw className={"h-4 w-4" + (planLoading ? " animate-spin" : "")} /> Rafraîchir
        </Button>
      </div>

      {planErr && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{planErr}</p></Card>}

      <Card>
        {loading && !plan && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        )}
        {!loading && plan && plan.consultants.length === 0 && !planErr && (
          <p className="text-sm text-muted">Aucune affectation sur cette période.</p>
        )}
        {plan && plan.consultants.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-black/5 text-left text-xs text-muted">
                  <th className="py-2 pr-3 font-medium">Consultant</th>
                  {plan.consultants[0].weeks.map((w) => (
                    <th key={w.week_start} className="py-2 pr-3 text-center font-medium">{fmtWeek(w.week_start)}</th>
                  ))}
                  <th className="py-2 pr-3 text-center font-medium">Moy.</th>
                  <th className="py-2 pr-3 text-center font-medium">Surcharge</th>
                </tr>
              </thead>
              <tbody>
                {plan.consultants.map((c) => (
                  <tr key={c.consultant_user_id} className="border-b border-black/5 last:border-0">
                    <td className="py-2 pr-3 font-medium text-ink">{accountLabel(accounts, c.consultant_user_id)}</td>
                    {c.weeks.map((w) => (
                      <td key={w.week_start} className="py-2 pr-3 text-center">
                        <span
                          title={fmtDays(w.allocated_minutes, w.capacity_minutes) + " / " + fmtDays(w.capacity_minutes, w.capacity_minutes)}
                          className={"inline-flex min-w-[3.5rem] items-center justify-center rounded-full px-2 py-0.5 text-xs font-semibold " + cellClasses(w)}
                        >
                          {pct(w.load_pct)}
                        </span>
                      </td>
                    ))}
                    <td className="py-2 pr-3 text-center"><Badge tone={avgTone(c.avg_load_pct)}>{pct(c.avg_load_pct)}</Badge></td>
                    <td className="py-2 pr-3 text-center">
                      {c.over_weeks > 0
                        ? <Badge tone="red"><AlertTriangle className="h-3 w-3" /> {c.over_weeks} sem. surchargées</Badge>
                        : <span className="text-xs text-muted">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <h2 className="mb-2 text-sm font-semibold text-ink">Affectations de la période</h2>
        {loading && !assignments.length && <Skeleton className="h-8 w-full" />}
        {!loading && assignments.length === 0 && !planErr && (
          <p className="text-sm text-muted">Aucune affectation sur cette période.</p>
        )}
        {assignments.length > 0 && (
          <div className="flex flex-col gap-1">
            {assignments.map((a) => (
              <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-black/5 py-2 text-sm last:border-0">
                <div>
                  <span className="font-medium">{accountLabel(accounts, a.consultant_user_id)}</span>
                  {" · "}
                  <span className="text-muted">{missionLabel(missions, a.mission_id)}</span>
                  {" · "}
                  <span className="text-muted">{fmtWeek(a.week_start)}</span>
                  {" · "}
                  <span className="text-muted">{fmtDays(a.allocated_minutes, capacityMinutes)}</span>
                  {a.note && <span className="text-muted"> · {a.note}</span>}
                </div>
                <button onClick={() => remove(a.id)} className="flex items-center gap-1 text-xs text-red-600 hover:underline">
                  <Trash2 className="h-3.5 w-3.5" /> Supprimer
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
