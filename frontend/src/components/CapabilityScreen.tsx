"use client";

import { useState } from "react";
import { Sparkles, AlertCircle } from "lucide-react";
import { Card, Button, Skeleton } from "./ui";
import { useZola } from "./ConfigProvider";
import { api, ApiError } from "@/lib/api";
import type { Capability } from "@/lib/capabilities";

interface QueryResult {
  content?: string;
  agent?: string;
  citations?: { index: number; source_uri: string }[];
}

/** Écran de capacité générique : entrée libre → orchestrateur/agent → rendu. */
export function CapabilityScreen({ capability }: { capability: Capability }) {
  const { t } = useZola();
  const [input, setInput] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!input.trim()) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const r = await api<QueryResult>("/v1/query", {
        body: { query: input, pole: capability.pole, module: capability.code.split(".")[1] },
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Service indisponible (hors-ligne ?).");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
          <capability.icon className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-lg font-semibold">{capability.label}</h1>
          <p className="text-sm text-muted">Capacité ZolaOS — {capability.pole}</p>
        </div>
      </div>

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

      {loading && (
        <Card><Skeleton className="mb-2 h-4 w-1/2" /><Skeleton className="mb-2 h-4 w-full" /><Skeleton className="h-4 w-5/6" /></Card>
      )}

      {error && (
        <Card className="ring-amber-200">
          <div className="flex items-start gap-2 text-amber-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <p className="text-sm">{error}</p>
          </div>
        </Card>
      )}

      {result && (
        <Card>
          <pre className="whitespace-pre-wrap text-sm leading-relaxed">{result.content ?? JSON.stringify(result, null, 2)}</pre>
          {result.citations?.length ? (
            <div className="mt-3 border-t border-black/5 pt-2 text-xs text-muted">
              Sources : {result.citations.map((c) => `[${c.index}] ${c.source_uri}`).join("  ")}
            </div>
          ) : null}
        </Card>
      )}
    </div>
  );
}
