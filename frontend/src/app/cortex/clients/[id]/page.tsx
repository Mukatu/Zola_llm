"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Building2 } from "lucide-react";
import { Card } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { getClient, type ClientDetail } from "@/lib/cortex-clients";

// Couleurs alignées sur /cortex/missions (même vocabulaire de statut).
const STATUS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700", revoked: "bg-red-100 text-red-700",
  expired: "bg-gray-100 text-gray-600", completed: "bg-blue-100 text-blue-700",
};

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getClient(id)
      .then(setDetail)
      .catch((e) => setErr(e instanceof ApiError && e.status === 404 ? "Client introuvable." : "Cortex injoignable / authentification requise."));
  }, [id]);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Link href="/cortex/clients" className="flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" /> Clients</Link>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {detail && (
        <>
          <Card className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><Building2 className="h-5 w-5" /></span>
            <div className="flex-1">
              <h1 className="text-lg font-semibold">{detail.tenant.name}</h1>
              <p className="text-xs text-muted">
                {detail.tenant.country.toUpperCase()} · {detail.tenant.tenant_type === "cabinet" ? "Cabinet" : "Client"} · {detail.tenant.is_active ? "actif" : "désactivé"}
              </p>
            </div>
          </Card>

          <Card>
            <h2 className="mb-2 text-sm font-semibold">Missions liées</h2>
            {detail.missions.length === 0 && <p className="text-sm text-muted">Aucune mission liée à ce tenant.</p>}
            {detail.missions.map((m) => (
              <div key={m.id} className="flex items-center justify-between border-b border-black/5 py-2 text-sm last:border-0">
                <div>
                  <div className="font-medium">{m.offre}</div>
                  <div className="text-xs text-muted">
                    rôle {m.role === "cabinet" ? "cabinet" : "client"} · débutée {new Date(m.started_at).toLocaleDateString("fr-FR")}
                    {m.expires_at ? " · expire " + new Date(m.expires_at).toLocaleDateString("fr-FR") : ""}
                  </div>
                </div>
                <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + (STATUS[m.status] ?? "bg-gray-100 text-gray-600")}>{m.status}</span>
              </div>
            ))}
          </Card>
        </>
      )}
    </div>
  );
}
