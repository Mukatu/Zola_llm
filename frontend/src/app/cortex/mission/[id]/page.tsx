"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ShieldCheck, FileText, Gavel } from "lucide-react";
import { Card, Button } from "@/components/ui";
import { listMissions, type MissionSummary } from "@/lib/cortex";

export default function MissionCockpit() {
  const { id } = useParams<{ id: string }>();
  const [mission, setMission] = useState<MissionSummary | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listMissions().then((all) => { setMission(all.find((m) => m.mission_id === id) ?? null); })
      .catch(() => setErr("Cortex injoignable / authentification requise."));
  }, [id]);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Link href="/cortex/missions" className="flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" /> Missions</Link>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {mission && (
        <>
          <Card>
            <h1 className="text-lg font-semibold">{mission.offre}</h1>
            <div className="mt-1 grid gap-1 text-sm text-muted">
              <span>Client : {mission.client_tenant_id}</span>
              <span>Statut : {mission.status} · expire {new Date(mission.expires_at).toLocaleString("fr-FR")}</span>
              <span>Scope : {mission.scope_tags.join(", ")}</span>
            </div>
          </Card>

          <Card className="flex items-start gap-3 text-sm text-muted">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            <span>Pendant cette mission, les méthodologies cabinet s'exécutent <b className="text-ink">chez Polaris</b> ; seuls des extraits <b className="text-ink">anonymisés</b> de la Zolabox du client transitent (scopés, audités). Aucune donnée brute client ne quitte ses murs.</span>
          </Card>

          <div className="grid gap-3 sm:grid-cols-2">
            <Card className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><Gavel className="h-5 w-5" /></span>
              <div className="flex-1"><div className="font-semibold">Audit</div><div className="text-xs text-muted">Lancer une méthodologie d'audit (overlays cabinet).</div></div>
              <Button variant="ghost" onClick={() => {}}>Ouvrir</Button>
            </Card>
            <Card className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><FileText className="h-5 w-5" /></span>
              <div className="flex-1"><div className="font-semibold">Rapport</div><div className="text-xs text-muted">Générer le livrable .docx de la mission.</div></div>
              <Button variant="ghost" onClick={() => {}}>Générer</Button>
            </Card>
          </div>
          <p className="text-xs text-muted">Les méthodologies d'audit (overlays) et la génération de rapports sont servies par le déploiement Cortex (composants cabinet, non publics).</p>
        </>
      )}
    </div>
  );
}
