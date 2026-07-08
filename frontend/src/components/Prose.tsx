// Typographie de lecture réutilisable : texte long (réponses IA, contrats, textes
// juridiques) en serif justifié avec césure, + rendu Markdown léger (gras, italique,
// code, listes, titres) et détection de titres d'articles/sections.

import type { ReactNode } from "react";

// Nettoie et structure un texte souvent extrait/généré « au fil de l'eau » : trim
// des espaces autour des sauts (SANS fusionner les lignes vides → paragraphes
// markdown préservés), et insère un saut avant chaque marqueur (Titre, Chapitre,
// Section, Article/Art.) pour détacher articles et sections des textes juridiques.
export function structureText(texte: string): string[] {
  const t = (texte || "")
    .replace(/\r\n/g, "\n")
    .replace(/\.{3,}/g, " · ")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/[ \t]*\n[ \t]*/g, "\n") // trim autour des \n, garde les lignes vides
    .replace(/\s+(TITRE\s)/g, "\n\n$1")
    .replace(/([^\n])\n?(Titre\s+[0-9IVXLC])/g, "$1\n\n$2")
    .replace(/([^\n])\n?(Chapitre\s)/gi, "$1\n\n$2")
    .replace(/([^\n])\n?(Section\s+[0-9IVXLC])/g, "$1\n\n$2")
    .replace(/([^\n])\n?(Art(?:icle)?\.?\s*\d+)/g, "$1\n\n$2");
  return t
    .split(/\n{2,}/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function headingKind(bloc: string): "major" | "article" | null {
  const t = bloc.trim();
  if (/^(titre|chapitre|livre|section|préambule|partie|annexe)\b/i.test(t) && t.length <= 120)
    return "major";
  const lettres = t.replace(/[^A-Za-zÀ-ÿ]/g, "");
  if (lettres.length >= 4 && lettres === lettres.toUpperCase() && t.length <= 90) return "major";
  if (/\bart(?:icle)?\.?\s*\d+/i.test(t) && t.length <= 70) return "article";
  return null;
}

// Rendu Markdown inline : **gras**, __gras__, *italique*, _italique_, `code`.
function inline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /(\*\*([^*]+)\*\*|__([^_]+)__|\*([^*\s][^*]*)\*|(?<![A-Za-zÀ-ÿ])_([^_]+)_(?![A-Za-zÀ-ÿ])|`([^`]+)`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[2] ?? m[3]) nodes.push(<strong key={k++}>{m[2] ?? m[3]}</strong>);
    else if (m[4] ?? m[5]) nodes.push(<em key={k++}>{m[4] ?? m[5]}</em>);
    else if (m[6])
      nodes.push(
        <code key={k++} className="rounded bg-black/5 px-1 py-0.5 font-mono text-[0.85em]">
          {m[6]}
        </code>,
      );
    last = re.lastIndex;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Prose({
  text,
  className = "",
  compact = false,
}: {
  text: string;
  className?: string;
  compact?: boolean;
}) {
  const body = compact
    ? "font-serif text-[13px] leading-[1.6] text-ink/90"
    : "font-serif text-[15px] leading-[1.7] text-ink/90";

  return (
    <div lang="fr" className={(compact ? "space-y-2 " : "space-y-3.5 ") + className}>
      {structureText(text).map((block, bi) => {
        // Titres juridiques (Titre/Chapitre/Section, Article).
        const kind = headingKind(block);
        if (kind === "major")
          return (
            <h3
              key={bi}
              className="mt-6 border-l-2 border-forest pl-3 text-sm font-bold uppercase tracking-wide text-forest first:mt-0"
            >
              {block}
            </h3>
          );
        if (kind === "article")
          return (
            <h4 key={bi} className="mt-5 text-[15px] font-semibold text-ink first:mt-0">
              {inline(block)}
            </h4>
          );

        // Titre Markdown mono-ligne (# / ## / ###).
        const md = block.match(/^(#{1,3})\s+(.*)$/);
        if (md && !block.includes("\n"))
          return (
            <h4
              key={bi}
              className={
                "mt-5 text-ink first:mt-0 " +
                (md[1].length <= 1 ? "text-base font-bold" : "text-[15px] font-semibold")
              }
            >
              {inline(md[2])}
            </h4>
          );

        // Bloc mixte : regroupe listes et paragraphes ligne par ligne.
        const lines = block.split("\n");
        const out: ReactNode[] = [];
        let para: string[] = [];
        let list: { ordered: boolean; items: string[] } | null = null;
        const flushPara = () => {
          if (para.length) {
            out.push(
              <p key={out.length} className={"hyphens-auto text-justify " + body}>
                {inline(para.join(" "))}
              </p>,
            );
            para = [];
          }
        };
        const flushList = () => {
          if (list) {
            const items = list.items;
            const cls = "ml-5 space-y-1 " + (list.ordered ? "list-decimal" : "list-disc");
            out.push(
              list.ordered ? (
                <ol key={out.length} className={cls}>
                  {items.map((it, j) => (
                    <li key={j} className={body + " marker:text-forest"}>
                      {inline(it)}
                    </li>
                  ))}
                </ol>
              ) : (
                <ul key={out.length} className={cls}>
                  {items.map((it, j) => (
                    <li key={j} className={body + " marker:font-bold marker:text-forest"}>
                      {inline(it)}
                    </li>
                  ))}
                </ul>
              ),
            );
            list = null;
          }
        };
        for (const raw of lines) {
          const t = raw.trim();
          if (!t) continue;
          const ul = /^[-*]\s+(.*)$/.exec(t);
          const ol = /^\d+[.)]\s+(.*)$/.exec(t);
          if (ul || ol) {
            flushPara();
            const ordered = Boolean(ol);
            if (!list || list.ordered !== ordered) {
              flushList();
              list = { ordered, items: [] };
            }
            list.items.push((ul ? ul[1] : ol![1]).trim());
          } else {
            flushList();
            para.push(t);
          }
        }
        flushList();
        flushPara();
        return (
          <div key={bi} className={compact ? "space-y-1.5" : "space-y-2"}>
            {out}
          </div>
        );
      })}
    </div>
  );
}
