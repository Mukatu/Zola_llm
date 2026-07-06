"use client";

import { useState } from "react";
import { Languages, FileText, Loader2, Copy, Check } from "lucide-react";
import { Card, Button } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { translateContract, type TranslateResult } from "@/lib/legal";

const CIBLES = ["français", "anglais", "portugais"];

/**
 * Traduction de contrats étrangers — capacité du pôle juridique.
 * Coller un texte ou téléverser un fichier → traduction fidèle → assimilation
 * optionnelle dans « Mes documents » (le contrat traduit devient interrogeable).
 */
export function ContractTranslator({ module = "ohada" }: { module?: string }) {
  const [mode, setMode] = useState<"texte" | "fichier">("texte");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [target, setTarget] = useState("français");
  const [assimilate, setAssimilate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<TranslateResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function run() {
    if (busy) return;
    if (mode === "texte" && !text.trim()) return;
    if (mode === "fichier" && !file) return;
    setBusy(true);
    setErr(null);
    setRes(null);
    try {
      const r = await translateContract({
        text: mode === "texte" ? text : undefined,
        file: mode === "fichier" ? (file ?? undefined) : undefined,
        targetLang: target,
        assimilate,
        module,
      });
      setRes(r);
    } catch (e) {
      setErr(
        e instanceof ApiError
          ? `Traduction indisponible (le LLM doit tourner) — ${e.message}`
          : "Traduction indisponible",
      );
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!res) return;
    await navigator.clipboard.writeText(res.translation);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-2">
        <Languages className="h-5 w-5 text-primary" />
        <div>
          <h3 className="text-sm font-semibold">Traduction de contrats étrangers</h3>
          <p className="text-xs text-muted">
            Traduction juridique fidèle · langue source détectée automatiquement.
          </p>
        </div>
      </div>

      <div className="mb-2 flex gap-1">
        {(["texte", "fichier"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={
              "rounded-md px-2.5 py-1 text-xs " +
              (mode === m ? "bg-primary text-white" : "bg-black/5 hover:bg-black/10")
            }
          >
            {m === "texte" ? "Coller un texte" : "Téléverser un fichier"}
          </button>
        ))}
      </div>

      {mode === "texte" ? (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          placeholder="Collez le contrat en langue étrangère…"
          className="w-full resize-y rounded-lg border border-black/10 bg-white p-2 text-sm outline-none focus:ring-2 focus:ring-primary/40"
        />
      ) : (
        <input
          type="file"
          accept=".pdf,.docx,.txt,.md,.html"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm file:mr-2 file:rounded-md file:border-0 file:bg-black/5 file:px-2 file:py-1"
        />
      )}

      <div className="mt-2 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-1 text-sm">
          Vers
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
          >
            {CIBLES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-sm text-muted">
          <input
            type="checkbox"
            checked={assimilate}
            onChange={(e) => setAssimilate(e.target.checked)}
          />
          Enregistrer dans « Mes documents »
        </label>
        <Button onClick={run} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Languages className="h-4 w-4" />}
          Traduire
        </Button>
      </div>

      {err && <div className="mt-2 text-sm text-red-600">{err}</div>}

      {res && (
        <div className="mt-3">
          <div className="mb-1 flex items-center justify-between text-xs text-muted">
            <span>
              {res.source_lang} → {res.target_lang} · {res.caracteres} car.
              {res.assimilated ? " · enregistré ✓" : ""}
            </span>
            <button onClick={copy} className="inline-flex items-center gap-1 text-primary">
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copié" : "Copier"}
            </button>
          </div>
          <pre className="max-h-[40vh] overflow-y-auto whitespace-pre-wrap rounded-lg bg-black/5 p-3 font-sans text-sm leading-relaxed">
            {res.translation}
          </pre>
          {res.assimilated && (
            <p className="mt-1 flex items-center gap-1 text-xs text-emerald-700">
              <FileText className="h-3.5 w-3.5" /> Le contrat traduit est désormais interrogeable
              par l'assistant.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
