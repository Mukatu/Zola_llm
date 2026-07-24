"use client";

import type { LucideIcon } from "lucide-react";

export function FlagshipHeader({ icon: Icon, title, subtitle }: { icon: LucideIcon; title: string; subtitle: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><Icon className="h-5 w-5" /></span>
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

/** Point d'une série de tendance : `date` déjà formatée pour l'affichage (ex : "24/07"). */
export interface TrendPoint {
  date: string;
  value: number;
}

/**
 * Ligne de tendance SVG autoportée (sans lib de graphes, CSP-safe).
 * Modèle : `TrajectoireTreso` de BiScreen — viewBox + polyline min/max + libellés de dates.
 */
export function LineTrend({
  points,
  tone = "primary",
  height = 96,
  ariaLabel,
}: {
  points: TrendPoint[];
  tone?: "primary" | "danger";
  height?: number;
  ariaLabel: string;
}) {
  if (points.length === 0) {
    return <p className="text-sm text-muted">Aucune donnée.</p>;
  }
  const W = 320, H = height, PAD = 8;
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const x = (i: number) => PAD + (i * (W - 2 * PAD)) / Math.max(1, points.length - 1);
  const y = (v: number) => PAD + ((max - v) / span) * (H - 2 * PAD);
  const pts = points.map((p, i) => `${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const stroke = tone === "danger" ? "rgb(220 38 38)" : "rgb(13 148 136)";
  const lastIdx = points.length - 1;
  const last = points[lastIdx];
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none" role="img" aria-label={ariaLabel}>
        <polyline points={pts} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(lastIdx)} cy={y(last.value)} r="3.5" fill={stroke} />
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-muted">
        <span>{points[0].date}</span>
        <span>{last.date}</span>
      </div>
    </div>
  );
}
