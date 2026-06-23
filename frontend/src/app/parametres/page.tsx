"use client";

import { useState } from "react";
import { Settings, Check } from "lucide-react";
import { useZola } from "@/components/ConfigProvider";
import { Card, Button } from "@/components/ui";
import { CAPABILITIES, POLE_LABELS, type Capability } from "@/lib/capabilities";

export default function ParametresPage() {
  const { config, save } = useZola();
  const [nom, setNom] = useState(config.branding.nom_affichage);
  const [couleur, setCouleur] = useState(config.branding.couleur_primaire);
  const [locale, setLocale] = useState(config.locale);
  const [modules, setModules] = useState<Set<string>>(new Set(config.modules_actifs));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const toggle = (code: string) => setModules((s) => { const n = new Set(s); n.has(code) ? n.delete(code) : n.add(code); return n; });

  // Capacités regroupées par pôle (catalogue complet).
  const byPole = Object.values(CAPABILITIES).reduce<Record<string, Capability[]>>((acc, c) => {
    (acc[c.pole] ??= []).push(c); return acc;
  }, {});

  async function onSave() {
    setSaving(true); setErr(null); setSaved(false);
    try {
      await save({ branding: { nom_affichage: nom, couleur_primaire: couleur, logo_uri: config.branding.logo_uri }, locale, modules_actifs: [...modules] });
      setSaved(true); setTimeout(() => setSaved(false), 1500);
    } catch {
      setErr("Échec de l'enregistrement (service indisponible ?).");
    } finally { setSaving(false); }
  }

  if (!config.personnalisable) {
    return (
      <Card className="mx-auto max-w-2xl">
        <div className="flex items-center gap-2 text-sm text-muted"><Settings className="h-4 w-4" /> Cette surface (cabinet) a une configuration uniforme — non personnalisable.</div>
      </Card>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><Settings className="h-5 w-5" /></span>
        <div><h1 className="text-lg font-semibold">Paramètres</h1><p className="text-sm text-muted">Personnalisation de votre espace (branding, langue, modules).</p></div>
      </div>

      <Card className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm"><span className="mb-1 block font-medium">Nom affiché</span>
          <input value={nom} onChange={(e) => setNom(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Couleur primaire</span>
          <input type="color" value={couleur} onChange={(e) => setCouleur(e.target.value)} className="h-8 w-full rounded-lg border border-black/10" />
        </label>
        <label className="text-sm"><span className="mb-1 block font-medium">Langue</span>
          <select value={locale} onChange={(e) => setLocale(e.target.value as typeof locale)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            <option value="fr">Français</option><option value="ln">Lingala</option><option value="kg">Kituba</option>
          </select>
        </label>
      </Card>

      <Card>
        <h2 className="mb-2 text-sm font-semibold">Modules activés</h2>
        <div className="flex flex-col gap-3">
          {Object.entries(byPole).map(([pole, caps]) => (
            <div key={pole}>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{POLE_LABELS[pole] ?? pole}</div>
              <div className="flex flex-wrap gap-2">
                {caps.map((c) => {
                  const on = modules.has(c.code);
                  return (
                    <button key={c.code} onClick={() => toggle(c.code)}
                      className={"flex items-center gap-1.5 rounded-full px-3 py-1 text-sm transition " + (on ? "bg-primary text-white" : "bg-black/5 text-ink/60 hover:bg-black/10")}>
                      {on && <Check className="h-3.5 w-3.5" />} {c.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div className="flex items-center justify-end gap-3">
        {err && <span className="text-sm text-amber-700">{err}</span>}
        {saved && <span className="flex items-center gap-1 text-sm text-emerald-600"><Check className="h-4 w-4" /> Enregistré</span>}
        <Button onClick={onSave} disabled={saving}>{saving ? "Enregistrement…" : "Enregistrer"}</Button>
      </div>
    </div>
  );
}
