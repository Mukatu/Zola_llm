"use client";

import { useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { useZola } from "@/components/ConfigProvider";
import { Card, Button } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { runQuery } from "@/lib/query";

interface Msg { role: "user" | "assistant"; content: string }

export default function AssistantPage() {
  const { t } = useZola();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const q = input.trim();
    if (!q || busy) return;
    setMsgs((m) => [...m, { role: "user", content: q }]);
    setInput(""); setBusy(true);
    try {
      const r = await runQuery(q);
      setMsgs((m) => [...m, { role: "assistant", content: r.content }]);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Service indisponible (LLM/auth requis ou hors-ligne).";
      setMsgs((m) => [...m, { role: "assistant", content: "⚠️ " + msg }]);
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
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div className={
              "max-w-[85%] rounded-2xl px-4 py-2 text-sm " +
              (m.role === "user" ? "bg-primary text-white" : "bg-surface ring-1 ring-black/5")
            }>
              <pre className="whitespace-pre-wrap font-sans">{m.content}</pre>
            </div>
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
