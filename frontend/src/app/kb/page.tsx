"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Search, FileText, Loader2, Trash2 } from "lucide-react";
import { Card, Button } from "@/components/ui";
import { DocumentUpload } from "@/components/DocumentUpload";
import { ApiError } from "@/lib/api";
import {
  kbCatalog,
  kbDocuments,
  kbDocument,
  kbSearch,
  kbDelete,
  type KbCatalog,
  type KbDoc,
  type KbDocument,
  type KbSearchResult,
} from "@/lib/kb";

const SCHEMAS: { id: string; label: string }[] = [
  { id: "rag_legal", label: "Droit & OHADA" },
  { id: "rag_erp", label: "Comptable / ERP" },
  { id: "rag_health", label: "Santé" },
  { id: "rag_tenant", label: "Mes documents" },
];

// Modules proposés au téléversement depuis la Bibliothèque (contexte non deviné).
const UPLOAD_MODULES: { id: string; label: string; doctypes: string[] }[] = [
  { id: "travail_cg", label: "RH / Droit du travail", doctypes: ["reglement_interieur", "accord_entreprise", "grille_salariale", "procedure_rh", "organigramme"] },
  { id: "compta", label: "Comptabilité", doctypes: ["manuel_procedures", "plan_comptes", "politique_engagement"] },
  { id: "ohada", label: "Juridique", doctypes: ["charte", "statuts", "pacte_actionnaires", "contrat_type", "pv_ag"] },
  { id: "fiscal_cg", label: "Fiscal", doctypes: ["convention_fiscale", "attestation", "procedure"] },
  { id: "projets_ong", label: "Projets ONG", doctypes: ["convention_financement", "manuel_procedures", "cadre_logique", "rapport"] },
];

interface Filter {
  kind: "module" | "secteur" | "acte";
  valeur: string;
}

export default function KbPage() {
  const [schema, setSchema] = useState("rag_legal");
  const [cat, setCat] = useState<KbCatalog | null>(null);
  const [filter, setFilter] = useState<Filter | null>(null);
  const [docs, setDocs] = useState<KbDoc[]>([]);
  const [doc, setDoc] = useState<KbDocument | null>(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<KbSearchResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [uploadModule, setUploadModule] = useState(UPLOAD_MODULES[0].id);
  const [refresh, setRefresh] = useState(0);

  const openDoc = useCallback(
    async (sourceUri: string, sc?: string) => {
      setBusy(true);
      setErr(null);
      setResults(null);
      try {
        setDoc(await kbDocument(sc ?? schema, sourceUri));
      } catch (e) {
        setErr(e instanceof ApiError ? e.message : "Document indisponible");
      } finally {
        setBusy(false);
      }
    },
    [schema],
  );

  // Catalogue (facettes) du schéma courant.
  useEffect(() => {
    let ok = true;
    (async () => {
      try {
        setErr(null);
        const c = await kbCatalog(schema);
        if (ok) setCat(c);
      } catch (e) {
        if (ok) setErr(e instanceof ApiError ? e.message : "Chargement impossible");
      }
    })();
    return () => {
      ok = false;
    };
  }, [schema]);

  // Liste des documents selon schéma + filtre.
  useEffect(() => {
    let ok = true;
    (async () => {
      try {
        const r = await kbDocuments({
          schema,
          module: filter?.kind === "module" ? filter.valeur : undefined,
          secteur: filter?.kind === "secteur" ? filter.valeur : undefined,
          acte: filter?.kind === "acte" ? filter.valeur : undefined,
        });
        if (ok) setDocs(r.documents);
      } catch (e) {
        if (ok) setErr(e instanceof ApiError ? e.message : "Erreur");
      }
    })();
    return () => {
      ok = false;
    };
  }, [schema, filter, refresh]);

  async function removeDoc(sourceUri: string) {
    try {
      await kbDelete(sourceUri);
      if (doc?.source_uri === sourceUri) setDoc(null);
      setRefresh((r) => r + 1);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Suppression impossible");
    }
  }

  // Ouverture directe d'un document via l'URL (lien depuis les citations de l'Assistant).
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    const uri = sp.get("source_uri");
    const sc = sp.get("schema");
    if (!uri) return;
    if (sc) setSchema(sc);
    void openDoc(uri, sc ?? undefined);
    // exécuté une seule fois au montage
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectSchema(id: string) {
    setSchema(id);
    setFilter(null);
    setDoc(null);
    setResults(null);
  }

  function pickFilter(f: Filter | null) {
    setFilter(f);
    setDoc(null);
    setResults(null);
  }

  async function runSearch() {
    const query = q.trim();
    if (!query) return;
    setBusy(true);
    setErr(null);
    setDoc(null);
    try {
      const r = await kbSearch({ schema, q: query, k: 10 });
      setResults(r.resultats);
    } catch (e) {
      setErr(
        e instanceof ApiError
          ? `Recherche indisponible (le modèle d'embeddings doit tourner) — ${e.message}`
          : "Recherche indisponible",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/15 text-forest">
          <BookOpen className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-lg font-semibold">Bibliothèque documentaire</h1>
          <p className="text-sm text-muted">
            Actes uniformes OHADA, conventions collectives, CGI, LNME… — consultation directe.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {SCHEMAS.map((s) => (
          <button
            key={s.id}
            onClick={() => selectSchema(s.id)}
            className={
              "rounded-lg px-3 py-1.5 text-sm " +
              (schema === s.id ? "bg-primary text-white" : "bg-black/5 hover:bg-black/10")
            }
          >
            {s.label}
            {cat && schema === s.id ? ` · ${cat.documents}` : ""}
          </button>
        ))}
        <div className="ml-auto flex flex-1 items-center gap-2 sm:max-w-md">
          <div className="flex flex-1 items-center gap-2 rounded-xl border border-black/10 bg-white px-3">
            <Search className="h-4 w-4 text-muted" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
              placeholder="Recherche sémantique…"
              className="flex-1 bg-transparent py-2 text-sm outline-none"
            />
          </div>
          <Button onClick={runSearch} disabled={busy || !q.trim()}>
            Rechercher
          </Button>
        </div>
      </div>

      {err && <div className="text-sm text-red-600">{err}</div>}

      {schema === "rag_tenant" && (
        <Card className="p-3">
          <div className="mb-2 flex items-center gap-2 text-sm">
            <span className="text-muted">Contexte :</span>
            <select
              value={uploadModule}
              onChange={(e) => setUploadModule(e.target.value)}
              className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm"
            >
              {UPLOAD_MODULES.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <DocumentUpload
            module={uploadModule}
            doctypes={UPLOAD_MODULES.find((m) => m.id === uploadModule)?.doctypes ?? ["document"]}
            onUploaded={() => setRefresh((r) => r + 1)}
          />
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[300px_1fr]">
        {/* Colonne gauche : facettes + liste de documents */}
        <div className="flex flex-col gap-3">
          {cat && (
            <Card className="p-3 text-sm">
              <Facets title="Domaines" kind="module" items={cat.facettes.module} filter={filter} onPick={pickFilter} />
              <Facets title="Actes OHADA" kind="acte" items={cat.facettes.acte} filter={filter} onPick={pickFilter} />
              <Facets title="Secteurs (conventions)" kind="secteur" items={cat.facettes.secteur} filter={filter} onPick={pickFilter} />
            </Card>
          )}
          <Card className="p-2">
            <div className="mb-1 px-1 text-xs font-medium text-muted">
              {docs.length} document(s){filter ? ` · ${filter.valeur}` : ""}
            </div>
            <ul className="max-h-[50vh] space-y-0.5 overflow-y-auto">
              {docs.map((d) => (
                <li key={d.source_uri} className="flex items-center">
                  <button
                    onClick={() => openDoc(d.source_uri)}
                    className={
                      "flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-black/5 " +
                      (doc?.source_uri === d.source_uri ? "bg-black/5 font-medium" : "")
                    }
                  >
                    <FileText className="h-3.5 w-3.5 shrink-0 text-muted" />
                    <span className="truncate">{d.titre || d.source_id}</span>
                    <span className="ml-auto shrink-0 text-xs text-muted">{d.nb_chunks}</span>
                  </button>
                  {schema === "rag_tenant" && (
                    <button
                      onClick={() => removeDoc(d.source_uri)}
                      title="Supprimer"
                      className="ml-1 rounded p-1 text-muted hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        </div>

        {/* Colonne droite : lecteur OU résultats de recherche */}
        <Card className="min-h-[50vh] p-4">
          {busy && (
            <div className="flex items-center gap-2 text-sm text-muted">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
            </div>
          )}
          {!busy && results && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">{results.length} résultat(s)</h3>
              {results.map((r) => (
                <button
                  key={`${r.source_uri}-${r.chunk_index}`}
                  onClick={() => openDoc(r.source_uri)}
                  className="block w-full rounded-lg border border-black/5 p-2 text-left hover:bg-black/5"
                >
                  <div className="flex items-center justify-between text-xs text-muted">
                    <span>{r.source_id}</span>
                    <span>sim {r.similarity.toFixed(2)}</span>
                  </div>
                  <p className="mt-1 text-sm">{r.extrait}…</p>
                </button>
              ))}
            </div>
          )}
          {!busy && !results && doc && (
            <article>
              <h2 className="mb-1 font-semibold">{doc.titre || doc.source_id}</h2>
              <div className="mb-3 text-xs text-muted">
                {doc.nb_chunks} section(s) · <span className="break-all">{doc.source_uri}</span>
              </div>
              <pre className="max-h-[62vh] overflow-y-auto whitespace-pre-wrap font-sans text-sm leading-relaxed">
                {doc.texte}
              </pre>
            </article>
          )}
          {!busy && !results && !doc && (
            <div className="text-sm text-muted">
              Sélectionnez un document à gauche, ou lancez une recherche.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Facets({
  title,
  kind,
  items,
  filter,
  onPick,
}: {
  title: string;
  kind: Filter["kind"];
  items: { valeur: string; n: number }[];
  filter: Filter | null;
  onPick: (f: Filter | null) => void;
}) {
  if (items.length === 0) return null;
  return (
    <div className="mb-2">
      <div className="mb-1 text-xs font-semibold text-muted">{title}</div>
      <div className="flex flex-wrap gap-1">
        {items.map((it) => {
          const active = filter?.kind === kind && filter.valeur === it.valeur;
          return (
            <button
              key={it.valeur}
              onClick={() => onPick(active ? null : { kind, valeur: it.valeur })}
              className={
                "rounded px-1.5 py-0.5 text-xs " +
                (active ? "bg-primary text-white" : "bg-black/5 hover:bg-black/10")
              }
            >
              {it.valeur} <span className="opacity-60">{it.n}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
