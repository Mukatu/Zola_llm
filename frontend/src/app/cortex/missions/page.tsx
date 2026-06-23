"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, Plus, Ban, ShieldCheck } from "lucide-react";
import { Card, Button } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { listMissions, createMission, revokeMission, type MissionSummary, type CreateMissionInput } from "@/lib/cortex";

const OFFRES = ["conformite_rh", "fiscal_ohada", "tresorerie", "audit_sante", "audit_commercial", "audit_hse_gouvernance"];

const STATUS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700", revoked: "bg-red-100 text-red-700",
  expired: "bg-gray-100 text-gray-600", completed: "bg-blue-100 text-blue-700",
};

export default function MissionsPage() {
  const [missions, setMissions] = useState<MissionSummary[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState<CreateMissionInput>({ client_tenant_id: "", offre: OFFRES[0], scope_tags: ["country:cg"], ttl_hours: 2 });
  const [scopeText, setScopeText] = useState("country:cg, module:travail_cg");
  const [busy, setBusy] = useState(false);

  async function reload() {
    try { setMissions(await listMissions()); setErr(null); }
    catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) setErr("Authentification cabinet requise (configurez NEXT_PUBLIC_API_TOKEN).");
      else setErr("Cortex injoignable (backend cortex requis).");
    }
  }
  useEffect(() => { reload(); }, []);

  async function create() {
    setBusy(true); setErr(null);
    const body: CreateMissionInput = { ...form, scope_tags: scopeText.split(",").map((s) => s.trim()).filter(Boolean) };
    try { await createMission(body); await reload(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Échec de création."); }
    finally { setBusy(false); }
  }

  async function revoke(id: string) {
    try { await revokeMission(id); await reload(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Échec de révocation."); }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><Briefcase className="h-5 w-5" /></span>
        <div><h1 className="text-lg font-semibold">Missions</h1><p className="text-sm text-muted">Accès éphémère et scopé aux Zolabox clientes (Zero Trust).</p></div>
      </div>

      <Card className="grid gap-3 sm:grid-cols-[1fr_180px_1fr_90px_auto]">
        <label className="text-sm"><span className="mb-1 block font-medium">Client (tenant UUID)</span>
          <input value={form.client_tenant_id} onChange={(e) => setForm({ ...form, client_tenant_id: e.target.value })} placeholder="uuid du client" className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Offre</span>
          <select value={form.offre} onChange={(e) => setForm({ ...form, offre: e.target.value })} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {OFFRES.map((o) => <option key={o}>{o}</option>)}
          </select>
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Scope (tags)</span>
          <input value={scopeText} onChange={(e) => setScopeText(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">TTL (h)</span>
          <input type="number" min={1} max={6} value={form.ttl_hours} onChange={(e) => setForm({ ...form, ttl_hours: Number(e.target.value) })} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <div className="flex items-end"><Button onClick={create} disabled={busy || !form.client_tenant_id}><Plus className="h-4 w-4" /> Créer</Button></div>
      </Card>

      {err && <Card className="ring-amber-200"><div className="flex items-center gap-2 text-sm text-amber-700"><ShieldCheck className="h-4 w-4" /> {err}</div></Card>}

      <Card>
        {missions.length === 0 && !err && <p className="text-sm text-muted">Aucune mission.</p>}
        {missions.map((m) => (
          <div key={m.mission_id} className="flex items-center justify-between border-b border-black/5 py-2 text-sm last:border-0">
            <div>
              <Link href={"/cortex/mission/" + m.mission_id} className="font-medium text-primary hover:underline">{m.offre}</Link>
              <div className="text-xs text-muted">client {m.client_tenant_id.slice(0, 8)}… · expire {new Date(m.expires_at).toLocaleString("fr-FR")}</div>
            </div>
            <div className="flex items-center gap-3">
              <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + (STATUS[m.status] ?? "bg-gray-100")}>{m.status}</span>
              {m.status === "active" && (
                <button onClick={() => revoke(m.mission_id)} className="flex items-center gap-1 text-xs text-red-600 hover:underline"><Ban className="h-3.5 w-3.5" /> Révoquer</button>
              )}
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}
