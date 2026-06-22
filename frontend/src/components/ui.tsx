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
        variant === "primary" && "bg-primary text-white hover:opacity-90",
        variant === "ghost" && "text-ink hover:bg-black/5",
      )}
    >
      {children}
    </button>
  );
}

const SEV: Record<string, string> = {
  critical: "bg-red-100 text-red-700", high: "bg-orange-100 text-orange-700",
  medium: "bg-amber-100 text-amber-700", low: "bg-emerald-100 text-emerald-700",
};

export function SeverityBadge({ level }: { level: string }) {
  return (
    <span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", SEV[level] ?? "bg-gray-100 text-gray-600")}>
      {level}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-lg bg-black/10", className)} />;
}
