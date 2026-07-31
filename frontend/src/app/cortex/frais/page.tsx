"use client";

// PSA (cockpit cabinet Zolacortex) : notes de frais. Tout consultant saisit et
// soumet ses dépenses de mission ; le cabinet (admin:users) suit en plus la
// synthèse par mission — dont la part refacturable déjà approuvée, prête à
// porter sur facture.
import { useEffect, useState } from "react";
import { Wallet, Receipt, Send } from "lucide-react";
import { Card, Button, Badge, Skeleton, type BadgeTone } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import { listMissions, type MissionSummary } from "@/lib/cortex";
import {
  logExpense,
  listExpenses,
  updateExpense,
  getExpensesSummary,
  type Expense,
  type ExpenseStatus,
  type ExpenseSummary,
} from "@/lib/cortex-expenses";

const STATUS_TONE: Record<ExpenseStatus, BadgeTone> = {
  draft: "grey",
  submitted: "amber",
  approved: "green",
  rejected: "red",
};

const STATUS_LABEL: Record<ExpenseStatus, string> = {
  draft: "brouillon",
  submitted: "soumis",
  approved: "approuvé",
  rejected: "rejeté",
};

const CATEGORIES: { value: string; label: string }[] = [
  { value: "transport", label: "Transport" },
  { value: "hebergement", label: "Hébergement" },
  { value: "repas", label: "Repas" },
  { value: "fournitures", label: "Fournitures" },
  { value: "honoraires_tiers", label: "Honoraires tiers" },
  { value: "autre", label: "Autre" },
];

const CATEGORY_LABEL: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.value, c.label]),
);

function categoryLabel(value: string): string {
  return CATEGORY_LABEL[value] ?? value;
}

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 403) return "Accès réservé aux administrateurs.";
  return fallback;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { year: "numeric", month: "short", day: "numeric" });
}

function fmtMoney(n: number, currency: string): string {
  return new Intl.NumberFormat("fr-FR").format(n) + " " + currency;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function missionLabel(missions: MissionSummary[], missionId: string): string {
  return missions.find((m) => m.mission_id === missionId)?.offre ?? missionId;
}

export default function FraisPage() {
  const { config, user } = useZola();
  const cabinetAllowed = hasScope(user, "admin:users");

  const [missions, setMissions] = useState<MissionSummary[]>([]);

  // --- Mes notes de frais ---------------------------------------------------
  const [missionId, setMissionId] = useState("");
  const [expenseDate, setExpenseDate] = useState(todayIso());
  const [category, setCategory] = useState(CATEGORIES[0].value);
  const [amount, setAmount] = useState("");
  const [billable, setBillable] = useState(true);
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);

  const [myExpenses, setMyExpenses] = useState<Expense[]>([]);
  const [myLoading, setMyLoading] = useState(true);
  const [myErr, setMyErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function reloadMine() {
    setMyLoading(true);
    try {
      const rows = await listExpenses({ mine: true });
      setMyExpenses(rows);
      setMyErr(null);
    } catch (e) {
      setMyErr(messageFromError(e, "Notes de frais indisponibles (backend cortex requis)."));
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

  async function submitExpense() {
    if (!missionId) {
      setFormErr("Sélectionnez une mission.");
      return;
    }
    const a = Number(amount);
    if (!a || a <= 0) {
      setFormErr("Montant invalide.");
      return;
    }
    setSaving(true);
    setFormErr(null);
    try {
      await logExpense({
        mission_id: missionId,
        expense_date: expenseDate,
        category,
        amount: a,
        billable,
        description,
      });
      setAmount("");
      setDescription("");
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
      await updateExpense(id, { action: "submit" });
      await reloadMine();
    } catch (e) {
      setMyErr(messageFromError(e, "Échec de la soumission."));
    } finally {
      setBusyId(null);
    }
  }

  // --- Vue cabinet (admin:users) -------------------------------------------
  const [summaryMissionId, setSummaryMissionId] = useState("");
  const [summary, setSummary] = useState<ExpenseSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryErr, setSummaryErr] = useState<string | null>(null);

  useEffect(() => {
    if (!summaryMissionId && missions.length > 0) setSummaryMissionId(missions[0].mission_id);
  }, [missions, summaryMissionId]);

  useEffect(() => {
    if (!cabinetAllowed || !summaryMissionId) {
      setSummary(null);
      return;
    }
    let alive = true;
    setSummaryLoading(true);
    getExpensesSummary(summaryMissionId)
      .then((s) => {
        if (alive) {
          setSummary(s);
          setSummaryErr(null);
        }
      })
      .catch((e) => {
        if (alive) setSummaryErr(messageFromError(e, "Synthèse de la mission indisponible."));
      })
      .finally(() => {
        if (alive) setSummaryLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [cabinetAllowed, summaryMissionId]);

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
          <Wallet className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-lg font-semibold">Notes de frais</h1>
          <p className="text-sm text-muted">Saisie des dépenses de mission — PSA du cabinet.</p>
        </div>
      </div>

      {/* --- Mes notes de frais --- */}
      <Card className="flex flex-col gap-4">
        <div className="text-sm font-semibold">Mes notes de frais</div>

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
              value={expenseDate}
              onChange={(e) => setExpenseDate(e.target.value)}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Catégorie</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Montant (XAF)</span>
            <input
              type="number"
              min={0}
              step={1}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="ex. 50000"
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm">
            <span className="mb-1 block font-medium">Description</span>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="ex. taxi aéroport, hôtel client…"
              className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            />
          </label>
          <label className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              checked={billable}
              onChange={(e) => setBillable(e.target.checked)}
              className="h-3.5 w-3.5 accent-primary"
            />
            <span>Refacturable au client</span>
          </label>
        </div>

        <div>
          <Button onClick={submitExpense} disabled={saving}>
            <Wallet className="h-4 w-4" /> Enregistrer
          </Button>
        </div>

        <div className="border-t border-black/5 pt-3">
          {myErr && <p className="mb-2 text-sm text-amber-700">{myErr}</p>}
          {myLoading && !myExpenses.length && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          )}
          {!myLoading && myExpenses.length === 0 && !myErr && (
            <p className="text-sm text-muted">Aucune note de frais pour le moment.</p>
          )}
          {myExpenses.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-black/5 text-left text-xs text-muted">
                    <th className="py-2 pr-3 font-medium">Date</th>
                    <th className="py-2 pr-3 font-medium">Mission</th>
                    <th className="py-2 pr-3 font-medium">Catégorie</th>
                    <th className="py-2 pr-3 font-medium">Montant</th>
                    <th className="py-2 pr-3 font-medium">Refacturable</th>
                    <th className="py-2 pr-3 font-medium">Statut</th>
                    <th className="py-2 pr-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {myExpenses.map((exp) => (
                    <tr key={exp.id} className="border-b border-black/5 last:border-0">
                      <td className="py-2 pr-3">{fmtDate(exp.expense_date)}</td>
                      <td className="py-2 pr-3">{missionLabel(missions, exp.mission_id)}</td>
                      <td className="py-2 pr-3">{categoryLabel(exp.category)}</td>
                      <td className="py-2 pr-3">{fmtMoney(exp.amount, "XAF")}</td>
                      <td className="py-2 pr-3">
                        {exp.billable && <Badge tone="mint">refacturable</Badge>}
                      </td>
                      <td className="py-2 pr-3">
                        <Badge tone={STATUS_TONE[exp.status]}>{STATUS_LABEL[exp.status]}</Badge>
                      </td>
                      <td className="py-2 pr-3 text-right">
                        {exp.status === "draft" && (
                          <Button variant="ghost" onClick={() => submitDraft(exp.id)} disabled={busyId === exp.id}>
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

      {/* --- Vue cabinet --- */}
      {cabinetAllowed && (
        <div className="flex flex-col gap-4">
          <div className="text-sm font-semibold text-muted">Vue cabinet</div>

          <Card className="flex flex-col gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Receipt className="h-4 w-4" /> Synthèse de la mission
            </div>
            <label className="text-sm sm:max-w-xs">
              <span className="mb-1 block font-medium">Mission</span>
              {missions.length > 0 ? (
                <select
                  value={summaryMissionId}
                  onChange={(e) => setSummaryMissionId(e.target.value)}
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
                  value={summaryMissionId}
                  onChange={(e) => setSummaryMissionId(e.target.value)}
                  placeholder="id de la mission"
                  className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
                />
              )}
            </label>

            {summaryErr && <p className="text-sm text-amber-700">{summaryErr}</p>}
            {summaryLoading && !summary && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            )}
            {summary && (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <div className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
                    <div className="text-xs text-muted">Total</div>
                    <div className="text-lg font-semibold text-ink">{fmtMoney(summary.total, summary.currency)}</div>
                  </div>
                  <div className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
                    <div className="text-xs text-muted">Facturable</div>
                    <div className="text-lg font-semibold text-ink">
                      {fmtMoney(summary.billable_total, summary.currency)}
                    </div>
                  </div>
                  <div className="rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
                    <div className="text-xs text-muted">Refacturable approuvé</div>
                    <div className="text-lg font-semibold text-emerald-700">
                      {fmtMoney(summary.refacturable_approved, summary.currency)}
                    </div>
                  </div>
                </div>

                {Object.keys(summary.by_category).length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-black/5 text-left text-xs text-muted">
                          <th className="py-2 pr-3 font-medium">Catégorie</th>
                          <th className="py-2 pr-3 font-medium">Montant</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(summary.by_category).map(([cat, total]) => (
                          <tr key={cat} className="border-b border-black/5 last:border-0">
                            <td className="py-2 pr-3">{categoryLabel(cat)}</td>
                            <td className="py-2 pr-3">{fmtMoney(total, summary.currency)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
            {!summaryLoading && summary && summary.count === 0 && (
              <p className="text-sm text-muted">Aucune note de frais sur cette mission.</p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
