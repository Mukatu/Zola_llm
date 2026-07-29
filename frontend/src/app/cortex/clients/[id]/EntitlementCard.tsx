"use client";

// Section « Licence de modules » de la fiche client (cockpit cortex).
// Émet / révoque / livre l'entitlement signé du tenant, à côté du provisioning de
// la Zolabox. La licence est PAR client, d'où sa place ici plutôt qu'un écran à part.
import { useEffect, useMemo, useState } from "react";
import {
  ShieldCheck, KeyRound, Copy, Check, Loader2, AlertTriangle, Ban, PackagePlus,
} from "lucide-react";
import { Card, Button, Badge, Skeleton, type BadgeTone } from "@/components/ui";
import { ApiError } from "@/lib/api";
import {
  getCatalogue, getActiveGrant, listGrants, issueGrant, revokeGrant,
  type Catalogue, type Grant, type GrantWithToken, type GrantStatus,
} from "@/lib/cortex-entitlements";

const STATUS_TONE: Record<GrantStatus, BadgeTone> = {
  active: "green", expired: "grey", revoked: "red",
};

function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  let detail = e.detail;
  try {
    const parsed = JSON.parse(e.detail) as { detail?: string };
    if (parsed?.detail) detail = parsed.detail;
  } catch {
    /* detail brut */
  }
  if (detail.includes("signing_key_not_configured"))
    return "Clé d'émission absente côté cortex (ENTITLEMENT_PRIVATE_KEY) — impossible de signer.";
  if (detail.includes("tenant_must_be_client")) return "Une licence ne s'accorde qu'à un tenant de type client.";
  if (detail.includes("unknown_modules")) return "Module hors catalogue.";
  if (detail.includes("invalid_tier")) return "Tier inconnu.";
  if (e.status === 403) return "Accès réservé aux administrateurs du cabinet.";
  return fallback;
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { year: "numeric", month: "short", day: "numeric" });
}

export default function EntitlementCard({ tenantId }: { tenantId: string }) {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [active, setActive] = useState<GrantWithToken | null>(null);
  const [history, setHistory] = useState<Grant[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [tier, setTier] = useState("starter");
  const [options, setOptions] = useState<Set<string>>(new Set());
  const [days, setDays] = useState(365);
  const [busy, setBusy] = useState(false);
  const [issued, setIssued] = useState<GrantWithToken | null>(null);
  const [copied, setCopied] = useState<"active" | "issued" | null>(null);

  async function reload() {
    try {
      const [cat, act, hist] = await Promise.all([
        getCatalogue(),
        getActiveGrant(tenantId),
        listGrants(tenantId),
      ]);
      setCatalogue(cat);
      setActive(act);
      setHistory(hist);
      if (!(tier in cat.tiers)) setTier(Object.keys(cat.tiers)[0] ?? "starter");
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Cortex injoignable / authentification requise."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId]);

  // Modules inclus d'office par le tier sélectionné (cases cochées + verrouillées).
  const tierBase = useMemo(
    () => new Set(catalogue?.tiers[tier] ?? []),
    [catalogue, tier],
  );
  // Aperçu des modules effectifs = base du tier ∪ options à la carte.
  const effectivePreview = useMemo(() => {
    const s = new Set<string>(tierBase);
    options.forEach((m) => s.add(m));
    return [...s].sort();
  }, [tierBase, options]);

  function toggleOption(mod: string) {
    setOptions((prev) => {
      const next = new Set(prev);
      if (next.has(mod)) next.delete(mod);
      else next.add(mod);
      return next;
    });
  }

  async function issue() {
    setBusy(true);
    setErr(null);
    setIssued(null);
    setCopied(null);
    // On n'envoie que les vraies options (hors base du tier) — le backend fait l'union.
    const extras = [...options].filter((m) => !tierBase.has(m));
    try {
      const g = await issueGrant({ tenant_id: tenantId, tier, modules: extras, days });
      setIssued(g);
      setOptions(new Set());
      await reload();
    } catch (e) {
      setErr(messageFromError(e, "Échec de l'émission de la licence."));
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    if (!active) return;
    if (!window.confirm(
      "Révoquer la licence active de ce client ? La box perdra l'accès aux modules dès qu'elle re-vérifiera. Irréversible.",
    )) return;
    setBusy(true);
    setErr(null);
    try {
      await revokeGrant(active.id);
      await reload();
    } catch (e) {
      setErr(messageFromError(e, "Échec de la révocation."));
    } finally {
      setBusy(false);
    }
  }

  function copy(token: string, which: "active" | "issued") {
    navigator.clipboard.writeText(token).then(() => {
      setCopied(which);
      setTimeout(() => setCopied(null), 2000);
    });
  }

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <div className="flex-1">
          <div className="font-semibold">Licence de modules</div>
          <div className="text-xs text-muted">
            Distribution décidée par Polaris : grant signé (RS256) appliqué au montage sur la box.
            Un module non couvert n&apos;est même pas exposé.
          </div>
        </div>
        {active ? (
          <Badge tone={STATUS_TONE[active.status]}>{active.status}</Badge>
        ) : (
          <Badge tone="grey">aucune licence active</Badge>
        )}
      </div>

      {loading && <Skeleton className="h-16 w-full" />}

      {err && (
        <div className="flex items-start gap-2 rounded-xl p-3 text-sm text-red-700 ring-1 ring-red-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> <span>{err}</span>
        </div>
      )}

      {/* Licence active : récapitulatif + livraison du jeton + révocation */}
      {!loading && active && (
        <div className="flex flex-col gap-2 rounded-xl bg-black/[0.02] p-3 ring-1 ring-black/5">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium capitalize">{active.tier}</span>
            <span className="text-muted">· expire le {fmtDate(active.expires_at)}</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {active.effective_modules.map((m) => (
              <Badge key={m} tone="mint">{m}</Badge>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Button variant="ghost" onClick={() => copy(active.token, "active")}>
              {copied === "active" ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
              {copied === "active" ? "Copié" : "Copier le jeton"}
            </Button>
            <button
              onClick={revoke}
              disabled={busy}
              className="flex items-center gap-1 text-sm text-red-600 hover:underline disabled:opacity-50"
            >
              <Ban className="h-4 w-4" /> Révoquer
            </button>
          </div>
          <p className="text-xs text-muted">
            Jeton à déposer sur la box : <code>ENTITLEMENT_LICENSE_JWT</code> (ou fichier
            <code> ENTITLEMENT_LICENSE_FILE</code>) + <code>ENTITLEMENT_ENFORCED=true</code>.
          </p>
        </div>
      )}

      {/* Formulaire d'émission (renouvellement : remplace la licence active) */}
      {!loading && catalogue && (
        <div className="flex flex-col gap-3 border-t border-black/5 pt-3">
          <div className="text-sm font-medium">
            {active ? "Renouveler / remplacer la licence" : "Émettre une licence"}
          </div>

          <div className="grid gap-3 sm:grid-cols-[160px_120px]">
            <label className="text-sm">
              <span className="mb-1 block font-medium">Tier (bundle)</span>
              <select
                value={tier}
                onChange={(e) => setTier(e.target.value)}
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm capitalize"
              >
                {Object.keys(catalogue.tiers).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium">Validité (jours)</span>
              <input
                type="number"
                min={1}
                value={days}
                onChange={(e) => setDays(Math.max(1, Number(e.target.value) || 0))}
                className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
              />
            </label>
          </div>

          <div className="text-sm">
            <span className="mb-1 block font-medium">Modules</span>
            <div className="flex flex-wrap gap-2">
              {catalogue.modules.map((m) => {
                const inTier = tierBase.has(m);
                const checked = inTier || options.has(m);
                return (
                  <label
                    key={m}
                    className={
                      "flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs ring-1 " +
                      (inTier
                        ? "bg-mint/20 text-forest ring-mint/40 cursor-default"
                        : checked
                          ? "bg-primary/10 text-primary ring-primary/30 cursor-pointer"
                          : "bg-white text-gray-600 ring-black/10 cursor-pointer hover:bg-black/[0.03]")
                    }
                    title={inTier ? "Inclus dans le tier" : "Option à la carte"}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={inTier}
                      onChange={() => toggleOption(m)}
                      className="h-3 w-3 accent-primary"
                    />
                    {m}
                    {inTier && <span className="text-[10px] opacity-70">(tier)</span>}
                  </label>
                );
              })}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={issue} disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <PackagePlus className="h-4 w-4" />}
              {active ? "Renouveler" : "Émettre"}
            </Button>
            <span className="text-xs text-muted">
              Effectif : {effectivePreview.length ? effectivePreview.join(", ") : "—"}
            </span>
          </div>
        </div>
      )}

      {/* Jeton fraîchement émis — à copier maintenant */}
      {issued && (
        <div className="flex flex-col gap-2 rounded-xl p-3 text-sm ring-1 ring-amber-200">
          <span className="font-medium text-amber-800">Licence émise — jeton à livrer sur la box</span>
          <code className="max-h-24 overflow-y-auto break-all rounded-lg bg-black/5 p-2 text-xs">{issued.token}</code>
          <div className="flex items-center gap-3">
            <Button variant="ghost" onClick={() => copy(issued.token, "issued")}>
              {copied === "issued" ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
              {copied === "issued" ? "Copié" : "Copier"}
            </Button>
            <span className="text-xs text-amber-800">
              La licence précédente (si présente) a été révoquée. Le jeton reste récupérable ci-dessus.
            </span>
          </div>
        </div>
      )}

      {/* Historique des licences du tenant */}
      {!loading && history.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer font-medium text-muted">Historique ({history.length})</summary>
          <div className="mt-2 flex flex-col gap-1">
            {history.map((g) => (
              <div key={g.id} className="flex items-center justify-between border-b border-black/5 py-1 last:border-0">
                <span className="text-xs">
                  <span className="capitalize">{g.tier}</span>
                  {g.modules.length ? " + " + g.modules.join(", ") : ""}
                  <span className="text-muted"> · émise {fmtDate(g.issued_at)} · expire {fmtDate(g.expires_at)}</span>
                </span>
                <Badge tone={STATUS_TONE[g.status]}>{g.status}</Badge>
              </div>
            ))}
          </div>
        </details>
      )}
    </Card>
  );
}
