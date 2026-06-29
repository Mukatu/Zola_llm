"use client";

import { useEffect, useState } from "react";
import { FileBadge } from "lucide-react";
import { Card, Button } from "../ui";
import { ApiError } from "@/lib/api";
import {
  getBulletinModele,
  saveBulletinModele,
  getBulletinPlaceholders,
  type BulletinModele,
} from "@/lib/payroll";

const I = "rounded border border-black/15 px-2 py-1 text-sm";

export function BulletinModelePanel() {
  const [m, setM] = useState<BulletinModele | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [placeholders, setPlaceholders] = useState<{ token: string; description: string }[]>([]);

  useEffect(() => {
    getBulletinModele()
      .then(setM)
      .catch((e) => setErr(e instanceof ApiError ? e.message : "Erreur"));
    getBulletinPlaceholders()
      .then((r) => setPlaceholders(r.placeholders))
      .catch(() => {});
  }, []);

  async function save() {
    if (!m) return;
    setBusy(true);
    try {
      setM(await saveBulletinModele(m));
      setOk(true);
      setErr(null);
      setTimeout(() => setOk(false), 1500);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec");
    } finally {
      setBusy(false);
    }
  }

  if (!m) return null;
  const set = (p: Partial<BulletinModele>) => setM({ ...m, ...p });

  return (
    <Card className="p-4">
      <h3 className="mb-3 flex items-center gap-2 font-semibold">
        <FileBadge className="h-5 w-5" /> Modèle de bulletin (personnalisation)
      </h3>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="text-xs text-muted">
          Titre
          <input className={`mt-0.5 w-full ${I}`} value={m.titre} onChange={(e) => set({ titre: e.target.value })} />
        </label>
        <label className="text-xs text-muted">
          Logo (texte / raison sociale)
          <input className={`mt-0.5 w-full ${I}`} value={m.logo_texte} onChange={(e) => set({ logo_texte: e.target.value })} />
        </label>
        <label className="text-xs text-muted">
          Couleur (hex)
          <input className={`mt-0.5 w-full ${I}`} value={m.couleur} onChange={(e) => set({ couleur: e.target.value })} />
        </label>
        <label className="text-xs text-muted">
          Devise
          <input className={`mt-0.5 w-full ${I}`} value={m.devise} onChange={(e) => set({ devise: e.target.value })} />
        </label>
        <label className="text-xs text-muted sm:col-span-2">
          Mentions (bas de page)
          <input className={`mt-0.5 w-full ${I}`} value={m.mentions} onChange={(e) => set({ mentions: e.target.value })} />
        </label>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-1 text-sm">
          <input type="checkbox" checked={m.afficher_cout_employeur} onChange={(e) => set({ afficher_cout_employeur: e.target.checked })} />
          Afficher le coût employeur
        </label>
        <label className="flex items-center gap-1 text-sm">
          <input type="checkbox" checked={m.afficher_cotisations_patronales} onChange={(e) => set({ afficher_cotisations_patronales: e.target.checked })} />
          Afficher les charges patronales
        </label>
        <label className="flex items-center gap-1 text-sm">
          Format
          <select className={I} value={m.mode} onChange={(e) => set({ mode: e.target.value as BulletinModele["mode"] })}>
            <option value="structure">Structuré (Excel)</option>
            <option value="gabarit">Gabarit HTML</option>
          </select>
        </label>
      </div>

      {m.mode === "gabarit" && (
        <div className="mt-3">
          <div className="mb-1 text-xs font-medium text-muted">
            Gabarit HTML (les scripts sont neutralisés ; seuls les placeholders ci-dessous sont remplacés)
          </div>
          <textarea
            className={`h-40 w-full font-mono text-xs ${I}`}
            value={m.gabarit_html}
            onChange={(e) => set({ gabarit_html: e.target.value })}
            placeholder="<html>…{{salarie.nom}}…{{bulletin.net}}…</html>"
          />
          <details className="mt-1 text-xs text-muted">
            <summary className="cursor-pointer">Placeholders disponibles ({placeholders.length})</summary>
            <ul className="mt-1 grid grid-cols-1 gap-0.5 sm:grid-cols-2">
              {placeholders.map((p) => (
                <li key={p.token}>
                  <code className="text-primary">{p.token}</code> — {p.description}
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}

      <div className="mt-3 flex items-center gap-2">
        <Button disabled={busy} onClick={save}>
          Enregistrer le modèle
        </Button>
        {ok && <span className="text-sm text-emerald-600">Enregistré.</span>}
      </div>
      <p className="mt-2 text-xs text-muted">
        Le bulletin se télécharge depuis chaque ligne (Excel, et HTML si un gabarit est actif).
      </p>
      {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
    </Card>
  );
}
