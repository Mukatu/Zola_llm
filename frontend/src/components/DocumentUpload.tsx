"use client";

import { useRef, useState } from "react";
import { Upload, Check, Loader2 } from "lucide-react";
import { ApiError } from "@/lib/api";
import { kbUpload } from "@/lib/kb";

/**
 * Téléversement contextuel réutilisable : le client dépose ses documents
 * (règlement intérieur, accords, chartes, contrats…) → assimilés dans son
 * corpus privé (rag_tenant, cloisonné par tenant) pour enrichir l'assistance.
 */
export function DocumentUpload({
  module,
  doctypes,
  titre = "Téléverser un document",
  onUploaded,
}: {
  module: string;
  doctypes: string[];
  titre?: string;
  onUploaded?: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [doctype, setDoctype] = useState(doctypes[0] ?? "document");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function upload() {
    if (!file || busy) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await kbUpload({ file, module, doctype });
      setMsg(`« ${r.titre} » assimilé (${r.chunks} sections).`);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      onUploaded?.();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec du téléversement");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-dashed border-black/15 p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium">
        <Upload className="h-4 w-4 text-primary" /> {titre}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={doctype}
          onChange={(e) => setDoctype(e.target.value)}
          className="rounded-lg border border-black/10 bg-white px-2 py-1.5 text-sm"
        >
          {doctypes.map((d) => (
            <option key={d} value={d}>
              {d.replaceAll("_", " ")}
            </option>
          ))}
        </select>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md,.html,.csv,.xlsx"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="flex-1 text-sm file:mr-2 file:rounded-md file:border-0 file:bg-black/5 file:px-2 file:py-1 file:text-sm"
        />
        <button
          onClick={upload}
          disabled={busy || !file}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
          Téléverser
        </button>
      </div>
      <p className="mt-2 text-xs text-muted">
        PDF (OCR auto pour les scans), Word, texte… Le document reste privé à votre organisation et
        vient enrichir les réponses de l'assistant.
      </p>
      {msg && (
        <div className="mt-2 flex items-center gap-1 text-xs text-emerald-700">
          <Check className="h-3.5 w-3.5" /> {msg}
        </div>
      )}
      {err && <div className="mt-2 text-xs text-red-600">{err}</div>}
    </div>
  );
}
