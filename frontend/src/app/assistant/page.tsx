"use client";

import { useState } from "react";
import Link from "next/link";
import { Send, Sparkles } from "lucide-react";
import { useZola } from "@/components/ConfigProvider";
import { Card, Button } from "@/components/ui";
import { FeedbackBar } from "@/components/FeedbackBar";
import { GroundingBadge } from "@/components/GroundingBadge";
import { Prose } from "@/components/Prose";
import { ApiError } from "@/lib/api";
import { streamQuery, type Citation, type Grounding } from "@/lib/query";

interface Msg {
  role: "user" | "assistant";
  content: string;
  query?: string; // (assistant) requête ayant produit la réponse
  pole?: string; // (assistant) agent/pôle ayant répondu
  requestId?: string; // (assistant) identifiant de la requête
  citations?: Citation[]; // (assistant) sources RAG citées
  error?: boolean; // (assistant) réponse d'erreur → pas de feedback
  streaming?: boolean; // (assistant) réponse encore en cours d'écriture
  grounding?: Grounding; // (assistant) "unsourced" → avertissement affiché
}

function sourceLabel(c: Citation): string {
  return c.source_id || c.source_uri.split("/").pop() || c.source_uri;
}

export default function AssistantPage() {
  const { t } = useZola();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const q = input.trim();
    if (!q || busy) return;
    // On pousse la bulle assistant vide tout de suite : elle se remplit au fil du
    // flux (citations d'abord, puis le texte token par token).
    setMsgs((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "", query: q, streaming: true }]);
    setInput(""); setBusy(true);

    const patchLast = (patch: Partial<Msg>) =>
      setMsgs((m) => m.map((msg, i) => (i === m.length - 1 ? { ...msg, ...patch } : msg)));

    try {
      const r = await streamQuery(q, {
        onRouting: (pole) => patchLast({ pole }),
        onCitations: (citations) => patchLast({ citations }),
        onToken: (text) =>
          setMsgs((m) =>
            m.map((msg, i) => (i === m.length - 1 ? { ...msg, content: msg.content + text } : msg)),
          ),
      });
      patchLast({ content: r.content, pole: r.pole, requestId: r.requestId, citations: r.citations, grounding: r.grounding, streaming: false });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Service indisponible (LLM/auth requis ou hors-ligne).";
      patchLast({ content: "⚠️ " + msg, error: true, streaming: false });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-4">
      <div className="flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-primary" />
        <h1 className="text-lg font-semibold">{t("nav.assistant")}</h1>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto">
        {msgs.length === 0 && (
          <Card className="text-sm text-muted">{t("assistant.placeholder")}</Card>
        )}
        {msgs.map((m, i) => (
          <div
            key={i}
            className={m.role === "user" ? "flex justify-end" : "flex flex-col items-start gap-1.5"}
          >
            <div className={
              "max-w-[85%] rounded-2xl px-4 py-2 text-sm " +
              (m.role === "user" ? "bg-primary text-white" : "bg-surface ring-1 ring-black/5")
            }>
              {m.role === "user" ? (
                <p className="whitespace-pre-wrap">{m.content}</p>
              ) : m.streaming && !m.content ? (
                // Le routage tourne : rien à afficher encore, mais on montre que ça vit.
                <span className="flex items-center gap-1.5 py-1 text-muted">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-forest" />
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-forest [animation-delay:150ms]" />
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-forest [animation-delay:300ms]" />
                </span>
              ) : (
                <Prose text={m.content} />
              )}
            </div>
            {m.role === "assistant" && !m.streaming && !m.error && (
              <GroundingBadge grounding={m.grounding} />
            )}
            {m.role === "assistant" && m.citations && m.citations.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 pl-1 text-xs text-muted">
                <span className="font-medium">Sources :</span>
                {m.citations.map((c) =>
                  c.schema_rag ? (
                    <Link
                      key={c.index}
                      href={`/kb?schema=${encodeURIComponent(c.schema_rag)}&source_uri=${encodeURIComponent(c.source_uri)}`}
                      title={`Ouvrir dans la Bibliothèque · similarité ${c.similarity.toFixed(2)}`}
                      className="rounded bg-primary/10 px-1.5 py-0.5 text-primary hover:bg-primary/20"
                    >
                      [{c.index}] {sourceLabel(c)}
                    </Link>
                  ) : (
                    <span
                      key={c.index}
                      title={`${sourceLabel(c)} · similarité ${c.similarity.toFixed(2)}`}
                      className="rounded bg-black/5 px-1.5 py-0.5"
                    >
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

      <div className="flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          rows={2}
          placeholder={t("assistant.placeholder")}
          className="flex-1 resize-none rounded-xl border border-black/10 bg-white p-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
        />
        <Button onClick={send} disabled={busy || !input.trim()}>
          <Send className="h-4 w-4" /> {t("assistant.send")}
        </Button>
      </div>
    </div>
  );
}
