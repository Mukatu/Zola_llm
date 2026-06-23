"use client";

import { useState } from "react";
import clsx from "clsx";
import { Sparkles, AlertCircle } from "lucide-react";
import { Card, Button, Skeleton, SeverityBadge } from "./ui";
import { useZola } from "./ConfigProvider";
import { ApiError } from "@/lib/api";
import { runQuery } from "@/lib/query";
import type { Capability, Intent } from "@/lib/capabilities";

interface Finding { [k: string]: unknown; severity?: string; severite?: string }
interface QueryResult {
  content?: string;
  agent?: string;
  synthese?: string;
  findings?: Finding[];
  citations?: { index: number; source_uri: string }[];
  [k: string]: unknown;
}

/** Écran de capacité : intents + entrée → orchestrateur/agent → rendu structuré. */
export function CapabilityScreen({ capability }: { capability: Capability }) {
  const { t } = useZola();
  const [intent, setIntent] = useState<string | null>(capability.intents[0]?.id ?? null);
  const [input, setInput] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!input.trim()) return;
    setLoading(true); setError(null); setResult(null);
    const label = capability.intents.find((it: Intent) => it.id === intent)?.label;
    const q = `[${capability.label}${label ? " · " + label : ""}]\n${input}`;
    try {
      const r = await runQuery(q);
      setResult({ content: r.content });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Service indisponible (LLM/auth requis ou hors-ligne).");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
          <capability.icon className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-lg font-semibold">{capability.label}</h1>
          <p className="text-sm text-muted">{capability.description}</p>
        </div>
      </div>

      {capability.intents.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {capability.intents.map((it) => (
            <button
              key={it.id}
              onClick={() => setIntent(it.id)}
              className={clsx(
                "rounded-full px-3 py-1 text-sm transition",
                intent === it.id ? "bg-primary text-white" : "bg-black/5 text-ink/70 hover:bg-black/10",
              )}
            >
              {it.label}
            </button>
          ))}
        </div>
      )}

      <Card>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("assistant.placeholder")}
          rows={4}
          className="w-full resize-y rounded-xl border border-black/10 bg-white p-3 text-sm outline-none focus:ring-2 focus:ring-primary/40"
        />
        <div className="mt-3 flex justify-end">
          <Button onClick={run} disabled={loading || !input.trim()}>
            <Sparkles className="h-4 w-4" /> {t("capability.run")}
          </Button>
        </div>
      </Card>

      {loading && <Card><Skeleton className="mb-2 h-4 w-1/2" /><Skeleton className="mb-2 h-4 w-full" /><Skeleton className="h-4 w-5/6" /></Card>}

      {error && (
        <Card className="ring-amber-200">
          <div className="flex items-start gap-2 text-amber-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><p className="text-sm">{error}</p>
          </div>
        </Card>
      )}

      {result && <OutputRenderer result={result} />}
    </div>
  );
}

function OutputRenderer({ result }: { result: QueryResult }) {
  const text = result.content ?? result.synthese;
  return (
    <div className="flex flex-col gap-3">
      {text && (
        <Card><pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{text}</pre></Card>
      )}

      {Array.isArray(result.findings) && result.findings.length > 0 && (
        <div className="flex flex-col gap-2">
          {result.findings.map((f, i) => {
            const sev = (f.severity ?? f.severite) as string | undefined;
            return (
              <Card key={i}>
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-sm font-semibold">Constat {i + 1}</span>
                  {sev && <SeverityBadge level={sev} />}
                </div>
                <dl className="grid gap-1 text-sm">
                  {Object.entries(f)
                    .filter(([k]) => k !== "severity" && k !== "severite")
                    .map(([k, v]) => (
                      <div key={k} className="flex gap-2">
                        <dt className="shrink-0 font-medium text-muted">{k}</dt>
                        <dd className="text-ink">{String(v)}</dd>
                      </div>
                    ))}
                </dl>
              </Card>
            );
          })}
        </div>
      )}

      {result.citations?.length ? (
        <Card className="text-xs text-muted">
          Sources : {result.citations.map((c) => `[${c.index}] ${c.source_uri}`).join("   ")}
        </Card>
      ) : null}

      {!text && !result.findings && !result.citations && (
        <Card><pre className="whitespace-pre-wrap text-xs">{JSON.stringify(result, null, 2)}</pre></Card>
      )}
    </div>
  );
}
