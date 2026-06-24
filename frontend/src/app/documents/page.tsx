"use client";

import { useCallback, useEffect, useState } from "react";
import { FolderOpen, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import { Card } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { listDocuments, deleteDocument, type DocumentRec } from "@/lib/documents";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentRec[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try { setDocs((await listDocuments()).documents); setErr(null); }
    catch (e) { setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible."); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function del(id: string) { try { await deleteDocument(id); await refresh(); } catch { setErr("Suppression impossible."); } }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><FolderOpen className="h-5 w-5" /></span>
        <div><h1 className="text-lg font-semibold">Documents générés</h1><p className="text-sm text-muted">Fiches de poste, contrats, rapports… (brouillons à valider).</p></div>
      </div>

      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {docs.length === 0 && !err && (
        <Card className="text-center text-sm text-muted">
          <FolderOpen className="mx-auto mb-2 h-8 w-8 opacity-40" />
          Aucun document. Les artefacts générés (fiches de poste, contrats, plans…) apparaîtront ici.
        </Card>
      )}

      {docs.map((d) => (
        <Card key={d.id}>
          <div className="flex items-center justify-between">
            <button onClick={() => setOpen(open === d.id ? null : d.id)} className="flex items-center gap-2 text-left text-sm font-medium">
              {open === d.id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              {d.titre}
              <span className="rounded-full bg-black/5 px-2 py-0.5 text-xs text-muted">{d.type}</span>
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">{d.statut}</span>
            </button>
            <button onClick={() => del(d.id)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
          </div>
          {open === d.id && <pre className="mt-2 whitespace-pre-wrap border-t border-black/5 pt-2 font-sans text-sm leading-relaxed">{d.contenu}</pre>}
        </Card>
      ))}
    </div>
  );
}
