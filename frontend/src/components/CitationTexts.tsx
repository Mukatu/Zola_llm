import type { Citation } from "@/lib/query";

/**
 * Affiche le TEXTE VERBATIM des articles cités, sous la réponse.
 *
 * Le modèle (8B local) raisonne et structure au-dessus, mais il lui arrive de
 * sous-lire une énumération (ex. ne restituer que la catégorie « cadres » d'un
 * article qui en liste trois). La complétude et la fidélité ne doivent donc pas
 * dépendre de sa prose : on affiche ici le texte réel du chunk cité, exhaustif
 * par construction. Le juriste lit un raisonnement adossé à la source, jamais un
 * résumé qui ampute. Replié par défaut pour laisser le raisonnement au premier plan.
 */
export function CitationTexts({ citations }: { citations?: Citation[] }) {
  const avecTexte = (citations ?? []).filter((c) => c.extrait && c.extrait.trim());
  if (avecTexte.length === 0) return null;

  const libelle = (c: Citation) =>
    c.source_id || c.source_uri.split("/").pop() || c.source_uri;

  return (
    <details className="mt-1 w-full rounded-lg border border-black/5 bg-black/[0.02]">
      <summary className="cursor-pointer select-none px-3 py-1.5 text-xs font-medium text-forest">
        Textes cités — lire le texte intégral ({avecTexte.length})
      </summary>
      <div className="flex flex-col gap-3 px-3 pb-3">
        {avecTexte.map((c) => (
          <div key={c.index}>
            <div className="mb-0.5 text-xs font-semibold text-forest">
              [{c.index}] {libelle(c)}
            </div>
            <blockquote className="max-h-72 overflow-y-auto whitespace-pre-wrap border-l-2 border-forest/40 pl-3 font-serif text-[13px] leading-relaxed text-ink/90">
              {c.extrait}
            </blockquote>
          </div>
        ))}
      </div>
    </details>
  );
}
