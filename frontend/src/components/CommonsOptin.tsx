"use client";

import { useEffect, useState } from "react";
import { Share2, Check, Shield, Loader2 } from "lucide-react";
import { Card, Button } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { getOptin, setOptin, runExtraction } from "@/lib/commons";

// Périmètres contribuables (valeur = préfixe d'agent côté moteur).
const SCOPES = [
  { value: "legal", label: "Juridique" },
  { value: "erp", label: "Comptabilité / ERP" },
  { value: "achats", label: "Achats" },
  { value: "rh", label: "RH / Paie" },
  { value: "sante", label: "Santé" },
];

/**
 * Consentement à contribuer au moteur commun (niveau 3).
 * Désactivé par défaut, par périmètre, révocable. Seul un savoir dérivé et
 * anonymisé quitte votre espace — jamais vos documents.
 */
export function CommonsOptin() {
  const [enabled, setEnabled] = useState(false);
  const [scopes, setScopes] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [extract, setExtract] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getOptin()
      .then((o) => {
        setEnabled(o.enabled);
        setScopes(new Set(o.scopes));
      })
      .catch(() => setErr("Consentement indisponible (connexion requise)."))
      .finally(() => setLoading(false));
  }, []);

  const toggleScope = (v: string) =>
    setScopes((s) => {
      const n = new Set(s);
      n.has(v) ? n.delete(v) : n.add(v);
      return n;
    });

  async function onSave() {
    setSaving(true);
    setErr(null);
    setSaved(false);
    try {
      await setOptin(enabled, [...scopes]);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      setErr(e instanceof ApiError ? `Échec — ${e.message}` : "Échec de l'enregistrement.");
    } finally {
      setSaving(false);
    }
  }

  async function onExtract() {
    setExtract(null);
    setErr(null);
    try {
      const r = await runExtraction();
      setExtract(
        r.raison
          ? r.raison
          : `${r.scanned} retour(s) analysé(s) · ${r.nouveaux} candidat(s) en quarantaine · ${r.corrobores} corroboré(s).`,
      );
    } catch (e) {
      setErr(e instanceof ApiError ? `Échec — ${e.message}` : "Extraction indisponible.");
    }
  }

  return (
    <Card>
      <div className="mb-2 flex items-center gap-2">
        <Share2 className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">Contribution au moteur commun</h2>
      </div>
      <p className="mb-3 flex items-start gap-2 rounded-lg bg-black/[0.03] p-2.5 text-xs text-muted">
        <Shield className="mt-0.5 h-3.5 w-3.5 flex-none text-emerald-600" />
        <span>
          Facultatif. Vos documents ne quittent <b>jamais</b> votre espace. Seul un savoir{" "}
          <b>dérivé et anonymisé</b> (une règle, jamais un dossier) peut aider à améliorer le moteur
          partagé — après validation humaine. Révocable à tout moment.
        </span>
      </p>

      {loading ? (
        <div className="text-sm text-muted">Chargement…</div>
      ) : (
        <>
          <label className="flex items-center gap-2 text-sm font-medium">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            J&apos;autorise la contribution anonymisée
          </label>

          <div className={"mt-3 " + (enabled ? "" : "pointer-events-none opacity-40")}>
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">
              Périmètres autorisés
            </div>
            <div className="flex flex-wrap gap-2">
              {SCOPES.map((s) => {
                const on = scopes.has(s.value);
                return (
                  <button
                    key={s.value}
                    onClick={() => toggleScope(s.value)}
                    className={
                      "flex items-center gap-1.5 rounded-full px-3 py-1 text-sm transition " +
                      (on ? "bg-primary text-white" : "bg-black/5 text-ink/60 hover:bg-black/10")
                    }
                  >
                    {on && <Check className="h-3.5 w-3.5" />} {s.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button onClick={onSave} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Enregistrer
            </Button>
            {enabled && (
              <button onClick={onExtract} className="text-sm text-primary hover:underline">
                Préparer mes contributions (quarantaine)
              </button>
            )}
            {saved && (
              <span className="flex items-center gap-1 text-sm text-emerald-600">
                <Check className="h-4 w-4" /> Enregistré
              </span>
            )}
          </div>

          {extract && <p className="mt-2 text-xs text-muted">{extract}</p>}
          {err && <p className="mt-2 text-sm text-amber-700">{err}</p>}
        </>
      )}
    </Card>
  );
}
