"use client";

import { useEffect, useState } from "react";
import { Users, UserCog, KeyRound, Ban, CheckCircle2 } from "lucide-react";
import { Card, Button, Skeleton } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import {
  listAccounts,
  createAccount,
  updateAccount,
  resetPassword,
  type Account,
  type CreateAccountInput,
} from "@/lib/cortex-accounts";

const ROLES = ["admin", "consultant", "client"];

const ROLE_LABEL: Record<string, string> = {
  admin: "Administrateur",
  consultant: "Consultant",
  client: "Client",
};

const ROLE_BADGE: Record<string, string> = {
  admin: "bg-primary/15 text-primary",
  consultant: "bg-mint/25 text-forest",
  client: "bg-gray-100 text-gray-600",
};

// Traduit les codes d'erreur backend (detail JSON `{"detail": "..."}`) en messages FR.
function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  let detail = e.detail;
  try {
    const parsed = JSON.parse(e.detail) as { detail?: string };
    if (parsed?.detail) detail = parsed.detail;
  } catch {
    /* detail n'est pas du JSON — on garde le texte brut */
  }
  if (detail.includes("email_already_exists")) return "Cet email existe déjà.";
  if (detail.includes("cannot_deactivate_self")) return "Vous ne pouvez pas vous désactiver vous-même.";
  if (detail.includes("cannot_demote_self")) return "Vous ne pouvez pas retirer votre propre rôle admin.";
  if (detail.includes("invalid_role")) return "Rôle invalide.";
  if (e.status === 403) return "Accès réservé aux administrateurs du cabinet.";
  return fallback;
}

const EMPTY_FORM: CreateAccountInput = { email: "", display_name: "", role: "consultant", tenant_id: "", password: "" };

export default function ComptesPage() {
  const { config, user } = useZola();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [reveal, setReveal] = useState<{ email: string; password: string } | null>(null);
  const [form, setForm] = useState<CreateAccountInput>(EMPTY_FORM);
  const [busy, setBusy] = useState(false);

  async function reload() {
    try {
      setAccounts(await listAccounts());
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Comptes indisponibles (backend cortex requis)."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (config.profil === "cortex" && hasScope(user, "admin:users")) reload();
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.profil, user]);

  async function create() {
    setBusy(true);
    setErr(null);
    const body: CreateAccountInput = { ...form, tenant_id: form.tenant_id || undefined, password: form.password || undefined };
    try {
      const res = await createAccount(body);
      if (res.temp_password) setReveal({ email: res.account.email, password: res.temp_password });
      setForm(EMPTY_FORM);
      await reload();
    } catch (e) {
      setErr(messageFromError(e, "Échec de création du compte."));
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(a: Account) {
    try {
      await updateAccount(a.id, { is_active: !a.is_active });
      await reload();
    } catch (e) {
      setErr(messageFromError(e, "Échec de la mise à jour du statut."));
    }
  }

  async function changeRole(a: Account, role: string) {
    if (role === a.role) return;
    try {
      await updateAccount(a.id, { role });
      await reload();
    } catch (e) {
      setErr(messageFromError(e, "Échec du changement de rôle."));
    }
  }

  async function reset(a: Account) {
    try {
      const res = await resetPassword(a.id);
      setReveal({ email: a.email, password: res.password });
    } catch (e) {
      setErr(messageFromError(e, "Échec de la réinitialisation."));
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
          <p className="text-sm text-muted">Accès réservé aux administrateurs du cabinet.</p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><Users className="h-5 w-5" /></span>
        <div>
          <h1 className="text-lg font-semibold">Comptes</h1>
          <p className="text-sm text-muted">Gestion des comptes du cabinet (rôles, activation, mots de passe).</p>
        </div>
      </div>

      <Card className="grid gap-3 sm:grid-cols-[1fr_1fr_150px_1fr_1fr_auto]">
        <label className="text-sm"><span className="mb-1 block font-medium">Email</span>
          <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="nom@cabinet.cg" className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Nom</span>
          <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Rôle</span>
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
          </select>
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Tenant (optionnel)</span>
          <input value={form.tenant_id ?? ""} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })} placeholder="uuid client" className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Mot de passe (optionnel)</span>
          <input type="password" value={form.password ?? ""} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="généré si vide" className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <div className="flex items-end">
          <Button onClick={create} disabled={busy || !form.email || !form.display_name}><UserCog className="h-4 w-4" /> Créer</Button>
        </div>
      </Card>

      {reveal && (
        <Card className="ring-amber-200">
          <div className="flex items-center justify-between gap-3 text-sm">
            <div>
              <p className="font-medium text-amber-700">Mot de passe pour {reveal.email}</p>
              <p className="text-xs text-muted">Notez-le, il ne sera plus affiché.</p>
              <code className="mt-1 inline-block rounded-lg bg-amber-50 px-2 py-1 font-mono text-sm text-amber-900">{reveal.password}</code>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={() => navigator.clipboard.writeText(reveal.password)}>Copier</Button>
              <Button variant="ghost" onClick={() => setReveal(null)}>Fermer</Button>
            </div>
          </div>
        </Card>
      )}

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      <Card>
        {loading && <div className="flex flex-col gap-2"><Skeleton className="h-8 w-full" /><Skeleton className="h-8 w-full" /></div>}
        {!loading && accounts.length === 0 && !err && <p className="text-sm text-muted">Aucun compte.</p>}
        {!loading && accounts.map((a) => (
          <div key={a.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-black/5 py-2 text-sm last:border-0">
            <div className="min-w-[220px]">
              <div className="font-medium">{a.display_name}</div>
              <div className="text-xs text-muted">{a.email}{a.tenant_id ? " · tenant " + a.tenant_id.slice(0, 8) + "…" : ""} · créé {new Date(a.created_at).toLocaleDateString("fr-FR")}</div>
            </div>
            <div className="flex items-center gap-3">
              <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + (a.is_active ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500")}>
                {a.is_active ? "actif" : "désactivé"}
              </span>
              <select
                value={a.role}
                onChange={(e) => changeRole(a, e.target.value)}
                className={"rounded-full border-0 px-2 py-0.5 text-xs font-semibold " + (ROLE_BADGE[a.role] ?? "bg-gray-100 text-gray-600")}
              >
                {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
              </select>
              <button onClick={() => reset(a)} className="flex items-center gap-1 text-xs text-primary hover:underline">
                <KeyRound className="h-3.5 w-3.5" /> Réinitialiser
              </button>
              <button onClick={() => toggleActive(a)} className={"flex items-center gap-1 text-xs hover:underline " + (a.is_active ? "text-red-600" : "text-emerald-600")}>
                {a.is_active ? <><Ban className="h-3.5 w-3.5" /> Désactiver</> : <><CheckCircle2 className="h-3.5 w-3.5" /> Réactiver</>}
              </button>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}
