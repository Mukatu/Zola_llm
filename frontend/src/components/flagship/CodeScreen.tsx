"use client";

import { useState } from "react";
import clsx from "clsx";
import { Code2, Play, Copy, Check } from "lucide-react";
import { Card, Button, Skeleton } from "../ui";
import { FlagshipHeader } from "./_shared";
import { runQuery } from "@/lib/query";
import { ApiError } from "@/lib/api";

const INTENTS = [
  { id: "generate", label: "Générer" }, { id: "refactor", label: "Refactor" },
  { id: "debug", label: "Debug" }, { id: "explain", label: "Expliquer" },
  { id: "review", label: "Revue" }, { id: "test", label: "Tests" },
];
const LANGS = ["python", "typescript", "javascript", "sql", "bash", "go", "java"];

export function CodeScreen() {
  const [intent, setIntent] = useState("generate");
  const [lang, setLang] = useState("python");
  const [input, setInput] = useState("");
  const [out, setOut] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function run() {
    if (!input.trim()) return;
    setLoading(true); setErr(null); setOut(null);
    const q = `Code Agent — intent: ${intent}, langage: ${lang}.\n\n${input}`;
    try { setOut((await runQuery(q)).content); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible (LLM/auth requis ou hors-ligne)."); }
    finally { setLoading(false); }
  }

  function copy() {
    if (out) { navigator.clipboard?.writeText(out); setCopied(true); setTimeout(() => setCopied(false), 1200); }
  }

  const isPaste = ["refactor", "debug", "review", "test"].includes(intent);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={Code2} title="Code (Engineering)" subtitle="Génération, refactor, debug, revue — assistant développeur." />

      <div className="flex flex-wrap items-center gap-2">
        {INTENTS.map((it) => (
          <button key={it.id} onClick={() => setIntent(it.id)}
            className={clsx("rounded-full px-3 py-1 text-sm transition", intent === it.id ? "bg-primary text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
            {it.label}
          </button>
        ))}
        <select value={lang} onChange={(e) => setLang(e.target.value)} className="ml-auto rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
          {LANGS.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
      </div>

      <Card>
        <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={isPaste ? 8 : 4}
          placeholder={isPaste ? "Collez le code…" : "Décrivez ce que le code doit faire…"}
          className="w-full resize-y rounded-xl border border-black/10 bg-[#0d1117] p-3 font-mono text-sm text-[#e6edf3] outline-none focus:ring-2 focus:ring-primary/40" />
        <div className="mt-3 flex justify-end">
          <Button onClick={run} disabled={loading || !input.trim()}><Play className="h-4 w-4" /> Exécuter</Button>
        </div>
      </Card>

      {loading && <Card><Skeleton className="mb-2 h-4 w-1/3" /><Skeleton className="mb-2 h-4 w-full" /><Skeleton className="h-4 w-5/6" /></Card>}
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {out && (
        <Card className="bg-[#0d1117] ring-black/20">
          <div className="mb-2 flex justify-end">
            <button onClick={copy} className="flex items-center gap-1 rounded-lg bg-white/10 px-2 py-1 text-xs text-[#e6edf3] hover:bg-white/20">
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />} {copied ? "Copié" : "Copier"}
            </button>
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-sm text-[#e6edf3]">{out}</pre>
        </Card>
      )}
    </div>
  );
}
