"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Building2, Users, Ban, CheckCircle2 } from "lucide-react";
import { Card, Button, Skeleton } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import {
  listClients,
  createClient,
  updateClient,
  type Tenant,
  type CreateClientInput,
} from "@/lib/cortex-clients";

const TYPE_LABEL: Record<string, string> = { client: "Client", cabinet: "Cabinet" };

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
  if (detail.includes("invalid_tenant_type")) return "Type de tenant invalide.";
  if (detail.includes("parent_not_found")) return "Cabinet parent introuvable.";
  if (detail.includes("parent_not_a_cabinet")) return "Le cabinet parent doit être un tenant de type cabinet.";
  if (e.status === 403) return "Accès réservé aux administrateurs du cabinet.";
  return fallback;
}

const EMPTY_FORM: CreateClientInput = { name: "", tenant_type: "client", country: "cg", parent_tenant_id: "" };

export default function ClientsPage() {
  const { config, user } = useZola();
  const [clients, setClients] = useState<Tenant[]>([]);
  const [cabinets, setCabinets] = useState<Tenant[]>([]);
  const [filter, setFilter] = useState<"" | "client" | "cabinet">("client");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState<CreateClientInput>(EMPTY_FORM);
  const [busy, setBusy] = useState(false);

  async function reload() {
    try {
      const [all, cabs] = await Promise.all([
        listClients(filter || undefined),
        listClients("cabinet"),
      ]);
      setClients(all);
      setCabinets(cabs);
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Annuaire indisponible (backend cortex requis)."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (config.profil === "cortex" && hasScope(user, "admin:users")) reload();
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.profil, user, filter]);

  async function create() {
    setBusy(true);
    setErr(null);
    const body: CreateClientInput = {
      ...form,
      country: form.country || undefined,
      parent_tenant_id: form.parent_tenant_id || undefined,
    };
    try {
      await createClient(body);
      setForm(EMPTY_FORM);
      await reload();
    } catch (e) {
      setErr(messageFromError(e, "Échec de création du tenant."));
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(t: Tenant) {
    try {
      await updateClient(t.id, { is_active: !t.is_active });
      await reload();
    } catch (e) {
      setErr(messageFromError(e, "Échec de la mise à jour du statut."));
    }
  }

  function parentName(t: Tenant): string | null {
    if (!t.parent_tenant_id) return null;
    return cabinets.find((c) => c.id === t.parent_tenant_id)?.name ?? null;
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
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><Building2 className="h-5 w-5" /></span>
        <div>
          <h1 className="text-lg font-semibold">Clients</h1>
          <p className="text-sm text-muted">Annuaire des clients et cabinets rattachés au cockpit Zolacortex.</p>
        </div>
      </div>

      <Card className="grid gap-3 sm:grid-cols-[1fr_110px_140px_1fr_auto]">
        <label className="text-sm"><span className="mb-1 block font-medium">Nom</span>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Pays</span>
          <input value={form.country ?? ""} onChange={(e) => setForm({ ...form, country: e.target.value })} maxLength={2} placeholder="cg" className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Type</span>
          <select value={form.tenant_type} onChange={(e) => setForm({ ...form, tenant_type: e.target.value as "client" | "cabinet" })} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            <option value="client">Client</option>
            <option value="cabinet">Cabinet</option>
          </select>
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Cabinet parent (optionnel)</span>
          <select value={form.parent_tenant_id ?? ""} onChange={(e) => setForm({ ...form, parent_tenant_id: e.target.value })} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            <option value="">—</option>
            {cabinets.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <div className="flex items-end">
          <Button onClick={create} disabled={busy || !form.name}><Building2 className="h-4 w-4" /> Créer</Button>
        </div>
      </Card>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted">Filtre :</span>
        {(["client", "cabinet", ""] as const).map((f) => (
          <button
            key={f || "tous"}
            onClick={() => setFilter(f)}
            className={"rounded-full px-3 py-1 text-xs font-semibold " + (filter === f ? "bg-primary text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}
          >
            {f ? TYPE_LABEL[f] : "Tous"}
          </button>
        ))}
      </div>

      <Card>
        {loading && <div className="flex flex-col gap-2"><Skeleton className="h-8 w-full" /><Skeleton className="h-8 w-full" /></div>}
        {!loading && clients.length === 0 && !err && <p className="text-sm text-muted">Aucun tenant.</p>}
        {!loading && clients.map((t) => (
          <div key={t.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-black/5 py-2 text-sm last:border-0">
            <div className="min-w-[220px]">
              <Link href={"/cortex/clients/" + t.id} className="flex items-center gap-1 font-medium text-primary hover:underline">
                <Users className="h-3.5 w-3.5" /> {t.name}
              </Link>
              <div className="text-xs text-muted">
                {t.country.toUpperCase()} · {TYPE_LABEL[t.tenant_type] ?? t.tenant_type}
                {parentName(t) ? " · rattaché à " + parentName(t) : ""}
                {" · créé " + new Date(t.created_at).toLocaleDateString("fr-FR")}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + (t.is_active ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500")}>
                {t.is_active ? "actif" : "désactivé"}
              </span>
              <button onClick={() => toggleActive(t)} className={"flex items-center gap-1 text-xs hover:underline " + (t.is_active ? "text-red-600" : "text-emerald-600")}>
                {t.is_active ? <><Ban className="h-3.5 w-3.5" /> Désactiver</> : <><CheckCircle2 className="h-3.5 w-3.5" /> Réactiver</>}
              </button>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}
