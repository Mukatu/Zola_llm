"use client";

import { useState } from "react";
import clsx from "clsx";
import { ScrollText, FileText, Scale, Info } from "lucide-react";
import { Card, Button, Skeleton } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { runQuery } from "@/lib/query";
import { ApiError } from "@/lib/api";

const TYPES = ["CDI", "CDD", "Bail commercial OHADA", "Cession de parts", "NDA / Confidentialité", "Contrat de prestation"];
const CLAUSES = ["Confidentialité", "Non-concurrence", "Pénalités de retard", "Résiliation", "Règlement des litiges (OHADA)"];

export function DroitScreen() {
  const [mode, setMode] = useState<"rediger" | "analyser">("rediger");
  const [type, setType] = useState(TYPES[0]);
  const [partieA, setPartieA] = useState("");
  const [partieB, setPartieB] = useState("");
  const [objet, setObjet] = useState("");
  const [montant, setMontant] = useState("");
  const [clauses, setClauses] = useState<string[]>(["Résiliation", "Règlement des litiges (OHADA)"]);
  const [situation, setSituation] = useState("");
  const [out, setOut] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const toggle = (c: string) => setClauses((l) => (l.includes(c) ? l.filter((x) => x !== c) : [...l, c]));

  async function run() {
    setLoading(true); setErr(null); setOut(null);
    const q = mode === "rediger"
      ? `Rédige un projet de "${type}" conforme au droit OHADA / République du Congo.\n`
        + `Parties : ${partieA || "Partie A"} et ${partieB || "Partie B"}.\n`
        + `Objet : ${objet || "(à préciser)"}.${montant ? ` Montant/rémunération : ${montant} XAF.` : ""}\n`
        + `Clauses à inclure : ${clauses.join(", ") || "usuelles"}.\n`
        + `Cite les articles applicables et signale les clauses à risque (sécurisation).`
      : `Analyse juridique (droit OHADA / CG) de la situation suivante, avec base légale, jurisprudence si pertinente, et évaluation du risque :\n\n${situation}`;
    try { setOut((await runQuery(q)).content); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Service indisponible (LLM/auth requis ou hors-ligne)."); }
    finally { setLoading(false); }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <FlagshipHeader icon={ScrollText} title="Droit" subtitle="Rédaction de contrats (OHADA) et analyse de contentieux — avec citations." />

      <div className="flex gap-2">
        <Tab active={mode === "rediger"} onClick={() => setMode("rediger")} icon={FileText} label="Rédiger un contrat" />
        <Tab active={mode === "analyser"} onClick={() => setMode("analyser")} icon={Scale} label="Analyser (contentieux)" />
      </div>

      {mode === "rediger" ? (
        <Card className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Type de contrat">
              <select value={type} onChange={(e) => setType(e.target.value)} className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
                {TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Montant / rémunération (XAF)"><Inp className="w-full" value={montant} onChange={setMontant} type="number" /></Field>
            <Field label="Partie A"><Inp className="w-full" value={partieA} onChange={setPartieA} placeholder="ex: Employeur SARL" /></Field>
            <Field label="Partie B"><Inp className="w-full" value={partieB} onChange={setPartieB} placeholder="ex: M. X" /></Field>
          </div>
          <Field label="Objet"><Inp className="w-full" value={objet} onChange={setObjet} placeholder="ex: poste de comptable" /></Field>
          <div>
            <div className="mb-1 text-sm font-medium">Clauses</div>
            <div className="flex flex-wrap gap-2">
              {CLAUSES.map((c) => (
                <button key={c} onClick={() => toggle(c)}
                  className={clsx("rounded-full px-3 py-1 text-xs transition", clauses.includes(c) ? "bg-primary text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
                  {c}
                </button>
              ))}
            </div>
          </div>
          <div className="flex justify-end"><Button onClick={run} disabled={loading}>Générer le projet</Button></div>
        </Card>
      ) : (
        <Card>
          <textarea value={situation} onChange={(e) => setSituation(e.target.value)} rows={5}
            placeholder="Décrivez la situation litigieuse…"
            className="w-full resize-y rounded-xl border border-black/10 bg-white p-3 text-sm outline-none focus:ring-2 focus:ring-primary/40" />
          <div className="mt-3 flex justify-end"><Button onClick={run} disabled={loading || !situation.trim()}>Analyser</Button></div>
        </Card>
      )}

      {loading && <Card><Skeleton className="mb-2 h-4 w-1/3" /><Skeleton className="mb-2 h-4 w-full" /><Skeleton className="h-4 w-5/6" /></Card>}
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}
      {out && (
        <Card>
          <div className="mb-3 flex items-center gap-2 rounded-lg bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800">
            <Info className="h-4 w-4" /> Projet — à faire valider par un juriste avant signature.
          </div>
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{out}</pre>
        </Card>
      )}
    </div>
  );
}

function Tab({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: typeof FileText; label: string }) {
  return (
    <button onClick={onClick} className={clsx("flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm transition", active ? "bg-primary text-white" : "bg-black/5 text-ink/70 hover:bg-black/10")}>
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-sm"><span className="mb-1 block font-medium">{label}</span>{children}</label>;
}
