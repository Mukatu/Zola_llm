"use client";

import { useCallback, useEffect, useState } from "react";
import { BookText, Download, Archive } from "lucide-react";
import { Card, Button } from "../ui";
import { ApiError } from "@/lib/api";
import { fmt } from "@/lib/data";
import {
  payrollJournal,
  downloadJournal,
  listArchives,
  downloadArchive,
  type Journal,
  type Archive as ArchiveT,
} from "@/lib/payroll";

const PERIODE_DEFAUT = new Date().toISOString().slice(0, 7);

export function JournalPaiePanel() {
  const [periode, setPeriode] = useState(PERIODE_DEFAUT);
  const [journal, setJournal] = useState<Journal | null>(null);
  const [archives, setArchives] = useState<ArchiveT[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [j, a] = await Promise.all([payrollJournal(periode), listArchives(periode)]);
      setJournal(j);
      setArchives(a.archives);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Erreur");
    }
  }, [periode]);

  useEffect(() => {
    void load();
  }, [load]);

  const t = journal?.totaux;

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 font-semibold">
          <BookText className="h-5 w-5" /> Journal de paie & coffre-fort
        </h3>
        <div className="flex items-center gap-2">
          <input
            className="rounded border border-black/15 px-2 py-1 text-sm"
            type="month"
            value={periode}
            onChange={(e) => setPeriode(e.target.value)}
          />
          <Button variant="ghost" onClick={() => downloadJournal(periode)}>
            <Download className="h-4 w-4" /> Exporter
          </Button>
        </div>
      </div>

      {journal && journal.nb_bulletins > 0 ? (
        <>
          <div className="mb-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <Mini label="Bulletins" value={String(journal.nb_bulletins)} />
            <Mini label="Brut total" value={fmt(t?.brut ?? "0")} />
            <Mini label="Net total" value={fmt(t?.net ?? "0")} />
            <Mini label="Coût employeur" value={fmt(t?.cout ?? "0")} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th className="py-1 pr-2">Matricule</th>
                  <th className="pr-2">Nom</th>
                  <th className="pr-2 text-right">Brut</th>
                  <th className="pr-2 text-right">Cotis.</th>
                  <th className="pr-2 text-right">IRPP</th>
                  <th className="pr-2 text-right">Net</th>
                  <th className="pr-2">Archivé ?</th>
                </tr>
              </thead>
              <tbody>
                {journal.lignes.map((l) => (
                  <tr key={l.matricule} className="border-t border-black/5">
                    <td className="py-1 pr-2 font-medium">{l.matricule}</td>
                    <td className="pr-2">{l.nom || "—"}</td>
                    <td className="pr-2 text-right">{fmt(l.brut_xaf)}</td>
                    <td className="pr-2 text-right text-muted">{fmt(l.cotisations_salariales_xaf)}</td>
                    <td className="pr-2 text-right text-muted">{fmt(l.irpp_xaf)}</td>
                    <td className="pr-2 text-right font-semibold">{fmt(l.net_a_payer_xaf)}</td>
                    <td className="pr-2">
                      {archives.some((a) => a.employee_matricule === l.matricule) ? "✓" : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="text-sm text-muted">Aucun bulletin pour cette période.</div>
      )}

      {archives.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 flex items-center gap-1 text-xs font-medium text-muted">
            <Archive className="h-3 w-3" /> Bulletins archivés ({archives.length})
          </div>
          <ul className="space-y-1 text-sm">
            {archives.map((a) => (
              <li key={a.id} className="flex items-center justify-between">
                <span>
                  {a.employee_matricule} · {a.periode} · net {fmt(a.net_a_payer_xaf ?? "0")}
                </span>
                <button
                  className="inline-flex items-center gap-1 text-primary hover:text-primary/80"
                  onClick={() => downloadArchive(a.id, `${a.employee_matricule}_${a.periode}`)}
                >
                  <Download className="h-4 w-4" /> Télécharger
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
    </Card>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-black/5 px-3 py-2">
      <div className="text-xs text-muted">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}
