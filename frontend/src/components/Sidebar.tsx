"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { LayoutDashboard, MessagesSquare, FolderOpen, BookOpen, Settings, Briefcase } from "lucide-react";
import { useZola } from "./ConfigProvider";
import { navGroupsFromModules } from "@/lib/capabilities";

const TRANSVERSES = [
  { href: "/", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/assistant", label: "Assistant", icon: MessagesSquare },
  { href: "/documents", label: "Documents", icon: FolderOpen },
  { href: "/kb", label: "Consultation", icon: BookOpen },
];

export function Sidebar() {
  const { config } = useZola();
  const pathname = usePathname();
  const groups = navGroupsFromModules(config.modules_actifs);

  const item = (href: string, label: string, Icon: React.ElementType) => {
    const active = pathname === href;
    return (
      <Link
        key={href}
        href={href}
        className={clsx(
          "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition",
          active ? "bg-primary/10 font-semibold text-primary" : "text-ink/80 hover:bg-black/5",
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
        <span className="truncate">{label}</span>
      </Link>
    );
  };

  // Surface cabinet (Zolacortex) : navigation par missions, isolée (Zero Trust).
  if (config.profil === "cortex") {
    return (
      <aside className="hidden w-64 shrink-0 flex-col gap-2 overflow-y-auto border-r border-black/5 bg-surface px-3 py-4 md:flex">
        <nav className="flex flex-col gap-1">
          {item("/", "Tableau de bord", LayoutDashboard)}
          {item("/cortex/missions", "Missions", Briefcase)}
        </nav>
        <div className="mt-auto rounded-xl bg-black/[0.03] p-3 text-xs text-muted">
          Accès client uniquement via mission (anonymisé, éphémère, audité).
        </div>
      </aside>
    );
  }

  return (
    <aside className="hidden w-64 shrink-0 flex-col gap-6 overflow-y-auto border-r border-black/5 bg-surface px-3 py-4 md:flex">
      <nav className="flex flex-col gap-1">
        {TRANSVERSES.map((t) => item(t.href, t.label, t.icon))}
      </nav>

      {groups.map((g) => (
        <div key={g.pole}>
          <div className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted">{g.label}</div>
          <nav className="flex flex-col gap-1">
            {g.items.map((c) => item(c.route, c.label, c.icon))}
          </nav>
        </div>
      ))}

      <div className="mt-auto px-3 pt-2">
        {item("/parametres", "Paramètres", Settings)}
      </div>
    </aside>
  );
}
