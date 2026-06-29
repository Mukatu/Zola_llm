"use client";

import { useState } from "react";
import { UserCog, Plus, Trash2 } from "lucide-react";
import { Card, Button } from "../ui";
import { ApiError } from "@/lib/api";
import {
  getEmployeeRubriques,
  setEmployeeRubrique,
  deleteEmployeeRubrique,
  type EmployeeRubriques,
} from "@/lib/bareme";

const I = "rounded border border-black/15 px-2 py-1 text-sm";

export function EmployeeRubriquesPanel() {
  const [mat, setMat] = useState("");
  const [data, setData] = useState<EmployeeRubriques | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load(m: string) {
    if (!m.trim()) return;
    setBusy(true);
    try {
      setData(await getEmployeeRubriques(m.trim()));
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Erreur de chargement");
    } finally {
      setBusy(false);
    }
  }

  async function assign(code: string, valeur?: string) {
    if (!data) return;
    setBusy(true);
    try {
      await setEmployeeRubrique(data.matricule, code, valeur && valeur !== "" ? valeur : null);
      await load(data.matricule);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec");
    } finally {
      setBusy(false);
    }
  }

  async function remove(code: string) {
    if (!data) return;
    setBusy(true);
    try {
      await deleteEmployeeRubrique(data.matricule, code);
      await load(data.matricule);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Échec");
    } finally {
      setBusy(false);
    }
  }

  const affectees = new Map((data?.affectations ?? []).map((a) => [a.code, a.valeur]));

  return (
    <Card className="p-4">
      <h3 className="mb-3 flex items-center gap-2 font-semibold">
        <UserCog className="h-5 w-5" /> Rubriques par employé
      </h3>

      <div className="mb-3 flex items-center gap-2">
        <input
          className={`w-48 ${I}`}
          placeholder="Matricule employé"
          value={mat}
          onChange={(e) => setMat(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(mat)}
        />
        <Button disabled={busy || !mat.trim()} onClick={() => load(mat)}>
          Charger
        </Button>
      </div>

      {data && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th className="py-1 pr-2">Rubrique</th>
                <th className="pr-2">Type</th>
                <th className="pr-2">Portée</th>
                <th className="pr-2 text-right">Montant appliqué</th>
                <th className="pr-2" />
              </tr>
            </thead>
            <tbody>
              {data.catalogue.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-2 text-muted">
                    Aucune rubrique au barème. Ajoutez-en dans « Barème de paie ».
                  </td>
                </tr>
              )}
              {data.catalogue.map((c) => {
                const isAff = affectees.has(c.code);
                const applied = c.applicable_a_tous || isAff;
                return (
                  <RubRow
                    key={c.code}
                    code={c.code}
                    libelle={c.libelle || c.code}
                    type={c.type}
                    global={c.applicable_a_tous}
                    affecte={isAff}
                    applied={applied}
                    valeurDefaut={c.valeur}
                    valeurAffectee={affectees.get(c.code) ?? null}
                    busy={busy}
                    onAssign={assign}
                    onRemove={remove}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {err && <div className="mt-2 text-sm text-red-600">{err}</div>}
    </Card>
  );
}

function RubRow({
  code,
  libelle,
  type,
  global,
  affecte,
  applied,
  valeurDefaut,
  valeurAffectee,
  busy,
  onAssign,
  onRemove,
}: {
  code: string;
  libelle: string;
  type: string;
  global: boolean;
  affecte: boolean;
  applied: boolean;
  valeurDefaut: string;
  valeurAffectee: string | null;
  busy: boolean;
  onAssign: (code: string, valeur?: string) => void;
  onRemove: (code: string) => void;
}) {
  const [val, setVal] = useState(valeurAffectee ?? "");
  return (
    <tr className="border-t border-black/5">
      <td className="py-1 pr-2 font-medium">{libelle}</td>
      <td className="pr-2">{type}</td>
      <td className="pr-2">
        {global ? (
          <span className="text-xs text-muted">tous</span>
        ) : applied ? (
          <span className="rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">affectée</span>
        ) : (
          <span className="text-xs text-muted">non affectée</span>
        )}
      </td>
      <td className="pr-2 text-right text-muted">
        {global ? (
          valeurDefaut
        ) : (
          <input
            className={`w-24 ${I}`}
            placeholder={valeurDefaut}
            value={val}
            onChange={(e) => setVal(e.target.value)}
            title="Vide = montant du barème"
          />
        )}
      </td>
      <td className="pr-2 text-right">
        {!global &&
          (affecte ? (
            <div className="flex items-center justify-end gap-1">
              <Button variant="ghost" disabled={busy} onClick={() => onAssign(code, val)}>
                Maj
              </Button>
              <button
                className="rounded p-1 text-red-600 hover:bg-red-50"
                title="Retirer"
                onClick={() => onRemove(code)}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <Button variant="ghost" disabled={busy} onClick={() => onAssign(code, val)}>
              <Plus className="h-4 w-4" /> Affecter
            </Button>
          ))}
      </td>
    </tr>
  );
}
