"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Sparkles, X, Send } from "lucide-react";
import { streamQuery, type Citation, type Grounding } from "@/lib/query";
import { FeedbackBar } from "@/components/FeedbackBar";
import { GroundingBadge } from "@/components/GroundingBadge";
import { Prose } from "@/components/Prose";
import { ApiError } from "@/lib/api";

// Pré-scoping par module (dérivé de la route /c/<pole>.<module>). Le préfixe
// biaise le routeur vers le bon agent ; le label habille le dock.
const CONTEXT: Record<string, { label: string; prefix: string }> = {
  compta: { label: "Comptabilité", prefix: "En comptabilité OHADA (AUDCIF/SYSCOHADA) au Congo" },
  ohada: { label: "Droit OHADA", prefix: "En droit des affaires OHADA" },
  travail_cg: {
    label: "Droit du travail",
    prefix: "En droit du travail congolais (Code du travail + conventions collectives)",
  },
  paie: { label: "Paie", prefix: "En paie et droit du travail congolais" },
  fiscal_cg: { label: "Droit fiscal", prefix: "En droit fiscal congolais (CGI)" },
  admin_cg: {
    label: "Droit administratif",
    prefix: "En droit administratif congolais (marchés publics)",
  },
  rh: { label: "RH", prefix: "En gestion RH et droit du travail congolais" },
  pharmacology: { label: "Santé", prefix: "En pharmacologie et santé (CIM / LNME)" },
  projets_ong: { label: "Projets ONG", prefix: "En gestion de projets ONG (SYCEBNL, bailleurs)" },
};

function contextFromPath(path: string | null): { label: string; prefix: string } | undefined {
  const m = path?.match(/^\/c\/[a-z_]+\.([a-z0-9_]+)/);
  return m ? CONTEXT[m[1]] : undefined;
}

function sourceLabel(c: Citation): string {
  return c.source_id || c.source_uri.split("/").pop() || c.source_uri;
}

interface Msg {
  role: "user" | "assistant";
  content: string;
  query?: string;
  pole?: string;
  requestId?: string;
  citations?: Citation[];
  error?: boolean;
  streaming?: boolean; // réponse encore en cours d'écriture
  grounding?: Grounding; // "unsourced" → avertissement affiché
}

/** Assistant contextuel réutilisable, docké sur chaque écran métier. */
export function AssistantDock() {
  const path = usePathname();
  const ctx = contextFromPath(path);
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  // Redondant sur l'assistant plein écran et la Bibliothèque.
  if (path === "/assistant" || path === "/kb") return null;

  async function send() {
    const q = input.trim();
    if (!q || busy) return;
    // Bulle assistant poussée vide : elle se remplit au fil du flux.
    setMsgs((m) => [
      ...m,
      { role: "user", content: q },
      { role: "assistant", content: "", query: q, streaming: true },
    ]);
    setInput("");
    setBusy(true);

    const patchLast = (patch: Partial<Msg>) =>
      setMsgs((m) => m.map((msg, i) => (i === m.length - 1 ? { ...msg, ...patch } : msg)));

    try {
      const r = await streamQuery(ctx ? `${ctx.prefix} : ${q}` : q, {
        onRouting: (pole) => patchLast({ pole }),
        onCitations: (citations) => patchLast({ citations }),
        onToken: (text) =>
          setMsgs((m) =>
            m.map((msg, i) => (i === m.length - 1 ? { ...msg, content: msg.content + text } : msg)),
          ),
      });
      patchLast({
        content: r.content,
        pole: r.pole,
        requestId: r.requestId,
        citations: r.citations,
        grounding: r.grounding,
        streaming: false,
      });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Service indisponible (LLM requis).";
      patchLast({ content: "⚠️ " + msg, error: true, streaming: false });
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-white shadow-lg hover:opacity-90"
      >
        <Sparkles className="h-4 w-4" /> Assistant{ctx ? ` · ${ctx.label}` : ""}
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-40 flex h-[72vh] max-h-[640px] w-[92vw] max-w-[400px] flex-col rounded-2xl bg-surface shadow-2xl ring-1 ring-black/10">
      <div className="flex items-center justify-between border-b border-black/5 px-4 py-2.5">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles className="h-4 w-4 text-primary" /> Assistant{ctx ? ` · ${ctx.label}` : ""}
        </div>
        <button onClick={() => setOpen(false)} className="rounded p-1 text-muted hover:bg-black/5">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {msgs.length === 0 && (
          <p className="text-xs text-muted">
            Posez une question{ctx ? ` sur ${ctx.label.toLowerCase()}` : ""} — la réponse cite ses
            sources.
          </p>
        )}
        {msgs.map((m, i) => (
          <div
            key={i}
            className={m.role === "user" ? "flex justify-end" : "flex flex-col items-start gap-1"}
          >
            <div
              className={
                "max-w-[90%] rounded-xl px-3 py-1.5 text-sm " +
                (m.role === "user" ? "bg-primary text-white" : "bg-black/5")
              }
            >
              {m.role === "user" ? (
                <p className="whitespace-pre-wrap">{m.content}</p>
              ) : m.streaming && !m.content ? (
                // Le routage tourne : rien à afficher encore, mais on montre que ça vit.
                <span className="flex items-center gap-1 py-1 text-muted">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-forest" />
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-forest [animation-delay:150ms]" />
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-forest [animation-delay:300ms]" />
                </span>
              ) : (
                <Prose text={m.content} compact />
              )}
            </div>
            {m.role === "assistant" && !m.streaming && !m.error && (
              <GroundingBadge grounding={m.grounding} />
            )}
            {m.role === "assistant" && m.citations && m.citations.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 text-xs text-muted">
                <span className="font-medium">Sources :</span>
                {m.citations.map((c) =>
                  c.schema_rag ? (
                    <Link
                      key={c.index}
                      href={`/kb?schema=${encodeURIComponent(c.schema_rag)}&source_uri=${encodeURIComponent(c.source_uri)}`}
                      className="rounded bg-primary/10 px-1.5 py-0.5 text-primary hover:bg-primary/20"
                    >
                      [{c.index}] {sourceLabel(c)}
                    </Link>
                  ) : (
                    <span key={c.index} className="rounded bg-black/5 px-1.5 py-0.5">
                      [{c.index}] {sourceLabel(c)}
                    </span>
                  ),
                )}
              </div>
            )}
            {m.role === "assistant" && !m.error && !m.streaming && (
              <FeedbackBar
                agent={m.pole ?? "general"}
                query={m.query ?? ""}
                response={m.content}
                requestId={m.requestId}
              />
            )}
          </div>
        ))}
      </div>

      <div className="flex items-end gap-2 border-t border-black/5 p-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={1}
          placeholder="Votre question…"
          className="flex-1 resize-none rounded-lg border border-black/10 bg-white p-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
        />
        <button
          onClick={send}
          disabled={busy || !input.trim()}
          className="inline-flex items-center rounded-lg bg-primary p-2 text-white disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
