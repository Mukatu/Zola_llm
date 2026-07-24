import clsx from "clsx";

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={clsx("rounded-2xl bg-surface p-5 shadow-sm ring-1 ring-black/5 animate-fade-in", className)}>
      {children}
    </div>
  );
}

export function Button({
  children, onClick, variant = "primary", type = "button", disabled,
}: {
  children: React.ReactNode; onClick?: () => void;
  variant?: "primary" | "ghost"; type?: "button" | "submit"; disabled?: boolean;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition active:scale-[0.98] disabled:opacity-50",
        variant === "primary" &&
          "bg-gradient-to-b from-primary to-primary/85 text-white shadow-sm shadow-primary/30 hover:brightness-[1.05]",
        variant === "ghost" && "text-ink hover:bg-black/5",
      )}
    >
      {children}
    </button>
  );
}

export type BadgeTone = "red" | "amber" | "green" | "grey" | "blue" | "mint";

const TONE_CLASSES: Record<BadgeTone, string> = {
  red: "bg-red-100 text-red-700",
  amber: "bg-amber-100 text-amber-800",
  green: "bg-green-100 text-green-700",
  grey: "bg-black/5 text-muted",
  blue: "bg-blue-100 text-blue-700",
  mint: "bg-mint/25 text-forest",
};

/** Pastille colorée générique — la correspondance valeur→tone reste locale à chaque écran. */
export function Badge({
  tone = "grey", className = "", children,
}: {
  tone?: BadgeTone; className?: string; children: React.ReactNode;
}) {
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold", TONE_CLASSES[tone], className)}>
      {children}
    </span>
  );
}

// Sévérité des contrôles de durcissement (Cyber) — "high" (orange) et "low" (emerald) ne
// correspondent pas exactement aux 6 tons partagés : couleur exacte préservée via override.
const SEV_OVERRIDE: Record<string, string> = {
  critical: "!bg-red-100 !text-red-700",
  high: "!bg-orange-100 !text-orange-700",
  medium: "!bg-amber-100 !text-amber-700",
  low: "!bg-emerald-100 !text-emerald-700",
};

export function SeverityBadge({ level }: { level: string }) {
  return <Badge className={SEV_OVERRIDE[level] ?? "!bg-gray-100 !text-gray-600"}>{level}</Badge>;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-lg bg-black/10", className)} />;
}
