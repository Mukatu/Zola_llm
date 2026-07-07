"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { LayoutDashboard, MessagesSquare, FolderOpen, BookOpen, Settings, Briefcase, FileSpreadsheet } from "lucide-react";
import { useZola } from "./ConfigProvider";
import { navGroupsFromModules } from "@/lib/capabilities";

const TRANSVERSES = [
  { href: "/", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/assistant", label: "Assistant", icon: MessagesSquare },
  { href: "/documents", label: "Documents", icon: FolderOpen },
  { href: "/kb", label: "Consultation", icon: BookOpen },
  { href: "/import", label: "Import / Export", icon: FileSpreadsheet },
];

function PolarisSignature() {
  return (
    <div className="mt-3 flex flex-col items-center gap-1 border-t border-white/10 pt-3">
      <span className="text-[10px] uppercase tracking-wide text-white/40">Propulsé par</span>
      <span className="rounded-lg bg-white px-2.5 py-1.5">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/polaris.png" alt="Polaris — Ingénierie de performance" className="h-5 w-auto" />
      </span>
    </div>
  );
}

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
          active
            ? "bg-primary font-semibold text-white shadow-sm shadow-primary/30"
            : "text-white/70 hover:bg-white/[0.08] hover:text-white",
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
      <aside className="hidden w-64 shrink-0 flex-col gap-2 overflow-y-auto bg-navy px-3 py-4 text-white md:flex">
        <nav className="flex flex-col gap-1">
          {item("/", "Tableau de bord", LayoutDashboard)}
          {item("/cortex/missions", "Missions", Briefcase)}
        </nav>
        <div className="mt-auto rounded-xl bg-white/[0.06] p-3 text-xs text-white/60">
          Accès client uniquement via mission (anonymisé, éphémère, audité).
        </div>
        <PolarisSignature />
      </aside>
    );
  }

  return (
    <aside className="hidden w-64 shrink-0 flex-col gap-6 overflow-y-auto bg-navy px-3 py-4 text-white md:flex">
      <nav className="flex flex-col gap-1">
        {TRANSVERSES.map((t) => item(t.href, t.label, t.icon))}
      </nav>

      {groups.map((g) => (
        <div key={g.pole}>
          <div className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-white/40">{g.label}</div>
          <nav className="flex flex-col gap-1">
            {g.items.map((c) => item(c.route, c.label, c.icon))}
          </nav>
        </div>
      ))}

      <div className="mt-auto pt-2">
        {item("/parametres", "Paramètres", Settings)}
        <PolarisSignature />
      </div>
    </aside>
  );
}
