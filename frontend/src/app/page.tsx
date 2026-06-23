"use client";

import Link from "next/link";
import { MessagesSquare, ArrowRight, Briefcase, ShieldCheck } from "lucide-react";
import { useZola } from "@/components/ConfigProvider";
import { Card, Skeleton } from "@/components/ui";
import { navGroupsFromModules } from "@/lib/capabilities";

export default function Dashboard() {
  const { config, loading } = useZola();
  const groups = navGroupsFromModules(config.modules_actifs);

  if (config.profil === "cortex") {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold">Cockpit cabinet — Polaris</h1>
          <p className="text-muted">Conduisez vos missions d'audit augmentées par ZolaOS.</p>
        </div>
        <Link href="/cortex/missions">
          <Card className="flex items-center gap-4 transition hover:shadow-md">
            <span className="grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary"><Briefcase className="h-6 w-6" /></span>
            <div className="flex-1"><div className="font-semibold">Missions</div><div className="text-sm text-muted">Créer, suivre et révoquer les missions d'audit.</div></div>
            <ArrowRight className="h-5 w-5 text-muted" />
          </Card>
        </Link>
        <Card className="flex items-start gap-3 text-sm text-muted">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
          <span><b className="text-ink">Zero Trust.</b> Le cabinet n'accède jamais aux données du client en direct : seuls des extraits anonymisés transitent pendant une mission active, scopés et audités côté client. Les méthodologies et prompts cabinet restent chez Polaris.</span>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Bonjour 👋</h1>
        <p className="text-muted">
          {config.branding.nom_affichage} — votre hub de pilotage. {config.modules_actifs.length} capacités activées.
        </p>
      </div>

      <Link href="/assistant">
        <Card className="flex items-center gap-4 transition hover:shadow-md">
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary">
            <MessagesSquare className="h-6 w-6" />
          </span>
          <div className="flex-1">
            <div className="font-semibold">Assistant</div>
            <div className="text-sm text-muted">Posez une question — l'orchestrateur route vers le bon agent.</div>
          </div>
          <ArrowRight className="h-5 w-5 text-muted" />
        </Card>
      </Link>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Card key={i}><Skeleton className="h-16" /></Card>)}
        </div>
      ) : (
        groups.map((g) => (
          <section key={g.pole}>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">{g.label}</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {g.items.map((c) => (
                <Link key={c.code} href={c.route}>
                  <Card className="flex items-center gap-3 transition hover:shadow-md">
                    <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
                      <c.icon className="h-5 w-5" />
                    </span>
                    <span className="font-medium">{c.label}</span>
                  </Card>
                </Link>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
