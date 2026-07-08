// Typographie de lecture réutilisable : texte long (réponses IA, contrats, textes
// juridiques) rendu en serif justifié avec césure, articles/sections détachés.

// Structure un texte souvent extrait/généré « au fil de l'eau » : nettoie les
// artefacts OCR et insère un saut avant chaque marqueur (Titre, Chapitre, Section,
// Article/Art.) pour détacher visuellement articles et sections.
export function structureText(texte: string): string[] {
  const t = (texte || "")
    .replace(/\.{3,}/g, " · ")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\s*\n\s*/g, "\n")
    .replace(/\s+(TITRE\s)/g, "\n\n$1")
    .replace(/\s+(Titre\s+[0-9IVXLC])/g, "\n\n$1")
    .replace(/\s+(Chapitre\s)/gi, "\n\n$1")
    .replace(/\s+(Section\s+[0-9IVXLC])/g, "\n\n$1")
    .replace(/\s+(Art(?:icle)?\.?\s*\d+)/g, "\n\n$1");
  return t
    .split(/\n{2,}/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// Détection légère de titres pour la mise en page.
export function headingKind(bloc: string): "major" | "article" | null {
  const t = bloc.trim();
  if (/^(titre|chapitre|livre|section|préambule|partie|annexe)\b/i.test(t) && t.length <= 120)
    return "major";
  const lettres = t.replace(/[^A-Za-zÀ-ÿ]/g, "");
  if (lettres.length >= 4 && lettres === lettres.toUpperCase() && t.length <= 90) return "major";
  if (/\bart(?:icle)?\.?\s*\d+/i.test(t) && t.length <= 70) return "article";
  return null;
}

/**
 * Rend un texte long avec une vraie typographie de lecture (serif justifié,
 * césure, sections en vert forêt, articles détachés).
 */
export function Prose({
  text,
  className = "",
  compact = false,
}: {
  text: string;
  className?: string;
  compact?: boolean;
}) {
  const body = compact ? "text-[13px] leading-[1.6]" : "text-[15px] leading-[1.7]";
  return (
    <div lang="fr" className={(compact ? "space-y-2 " : "space-y-3.5 ") + className}>
      {structureText(text).map((b, i) => {
        const kind = headingKind(b);
        if (kind === "major")
          return (
            <h3
              key={i}
              className="mt-6 border-l-2 border-forest pl-3 text-sm font-bold uppercase tracking-wide text-forest first:mt-0"
            >
              {b}
            </h3>
          );
        if (kind === "article")
          return (
            <h4 key={i} className="mt-5 text-[15px] font-semibold text-ink first:mt-0">
              {b}
            </h4>
          );
        return (
          <p key={i} className={"hyphens-auto text-justify font-serif text-ink/90 " + body}>
            {b}
          </p>
        );
      })}
    </div>
  );
}
