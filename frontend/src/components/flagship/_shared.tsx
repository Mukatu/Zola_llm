"use client";

import type { LucideIcon } from "lucide-react";

export function FlagshipHeader({ icon: Icon, title, subtitle }: { icon: LucideIcon; title: string; subtitle: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></span>
      <div>
        <h1 className="text-lg font-semibold">{title}</h1>
        <p className="text-sm text-muted">{subtitle}</p>
      </div>
    </div>
  );
}

export function Inp({ value, onChange, type = "text", className = "", placeholder }: {
  value: string | number; onChange: (v: string) => void; type?: string; className?: string; placeholder?: string;
}) {
  return (
    <input
      type={type}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className={"rounded-lg border border-black/10 bg-white px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-primary/40 " + className}
    />
  );
}

export const URG: Record<string, string> = {
  high: "bg-red-100 text-red-700", critical: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700", low: "bg-emerald-100 text-emerald-700",
  faible: "bg-emerald-100 text-emerald-700", moyen: "bg-amber-100 text-amber-700",
  eleve: "bg-orange-100 text-orange-700",
};

export function Urg({ level }: { level: string }) {
  return <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + (URG[level] ?? "bg-gray-100 text-gray-600")}>{level}</span>;
}
