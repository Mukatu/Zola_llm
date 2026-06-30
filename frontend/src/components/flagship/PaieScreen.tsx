"use client";

import { useCallback, useEffect, useState } from "react";
import { Wallet, AlertCircle, CheckCircle2, Trash2, FileSpreadsheet, Download, FileText, Archive } from "lucide-react";
import { Card, Button } from "../ui";
import { BaremePanel } from "./BaremePanel";
import { EmployeeRubriquesPanel } from "./EmployeeRubriquesPanel";
import { VariablesMoisPanel } from "./VariablesMoisPanel";
import { BulletinModelePanel } from "./BulletinModelePanel";
import { JournalPaiePanel } from "./JournalPaiePanel";
import { ApiError } from "@/lib/api";
import { fmt } from "@/lib/data";
import {
  createPayslip,
  listPayslips,
  patchPayslip,
  deletePayslip,
  payrollDashboard,
  payrollDas1,
  downloadDas1,
  downloadBulletin,
  downloadBulletinHtml,
  archiverBulletin,
  getBulletinModele,
  type PayslipRec,
  type PayrollDashboard,
  type Das1,
} from "@/lib/payroll";

const PERIODE_DEFAUT = new Date().toISOString().slice(0, 7); // AAAA-MM

export function PaieScreen() {
  const [periode, setPeriode] = useState(PERIODE_DEFAUT);
  const [payslips, setPayslips] = useState<PayslipRec[]>([]);
  const [dash, setDash] = useState<PayrollDashboard | null>(null);
  const [form, setForm] = useState({ matricule: "", brut: "450000", sim: true });
  const [das1, setDas1] = useState<Das1 | null>(null);
  const [gabaritActif, setGabaritActif] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const annee = periode.slice(0, 4);

  useEffect(() => {
    getBulletinModele()
      .then((mo) => setGabaritActif(mo.mode === "gabarit" && !!mo.gabarit_html.trim()))
      .catch(() => {});
  }, [payslips]);

  const refresh = useCallback(async () => {
    try {
      const [p, d] = await Promise.all([listPayslips(periode), payrollDashboard(periode)]);
      setPayslips(p.payslips);
      setDash(d);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, [periode]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function emit() {
    if (!form.matricule || !form.brut) return;
    try {
      await createPayslip({
        employee_matricule: form.matricule,
        periode,
        brut_mensuel_xaf: form.brut,
        allow_unvalidated: form.sim,
      });
      setForm({ ...form, matricule: "" });
      await refresh();
    } catch (e) {
      setErr(
        e instanceof ApiError && e.status === 409
          ? "Barème non validé : activez la simulation pour émettre un bulletin indicatif."
          : "Émission impossible (backend/DB).",
      );
    }
  }
  async function pay(id: string) {
    try {
      await patchPayslip(id, { statut: "valide", date_paiement: new Date().toISOString().slice(0, 10) });
      await refresh();
    } catch {
      setErr("Action impossible.");
    }
  }
  async function loadDas1() {
    try {
      setDas1(await payrollDas1(annee));
      setErr(null);
    } catch {
      setErr("Génération DAS 1 impossible (backend/DB).");
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><Wallet className="h-5 w-5" /></span>
          <div>
            <h1 className="text-lg font-semibold">Paie</h1>
            <p className="text-sm text-muted">Bulletins historisés (CNSS/IRPP) + masse salariale — registre vivant.</p>
          </div>
        </div>
        <input type="month" value={periode} onChange={(e) => setPeriode(e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
      </div>

      {err && (
        <Card className="ring-amber-200">
          <div className="flex items-start gap-2 text-amber-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><p className="text-sm">{err}</p></div>
        </Card>
      )}

      {dash && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Bulletins" value={String(dash.nb_bulletins)} />
          <Kpi label="Masse salariale brute" value={fmt(dash.masse_salariale_brute_xaf) + " XAF"} />
          <Kpi label="Net à payer" value={fmt(dash.total_net_a_payer_xaf) + " XAF"} />
          <Kpi label="Coût employeur" value={fmt(dash.cout_employeur_total_xaf) + " XAF"} />
        </div>
      )}

      {/* Émission */}
      <Card>
        <h2 className="mb-2 text-sm font-semibold">Émettre un bulletin · {periode}</h2>
        <div className="grid grid-cols-[110px_1fr_auto_120px] items-center gap-2">
          <input value={form.matricule} onChange={(e) => setForm({ ...form, matricule: e.target.value })} placeholder="Matricule" className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
          <input type="number" value={form.brut} onChange={(e) => setForm({ ...form, brut: e.target.value })} placeholder="Brut mensuel XAF" className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm" />
          <label className="flex items-center gap-1 text-xs text-muted">
            <input type="checkbox" checked={form.sim} onChange={(e) => setForm({ ...form, sim: e.target.checked })} /> simulation
          </label>
          <Button onClick={emit}><FileSpreadsheet className="h-4 w-4" /> Émettre</Button>
        </div>
      </Card>

      {/* Bulletins */}
      <Card>
        <h2 className="mb-2 text-sm font-semibold">Bulletins ({payslips.length})</h2>
        {payslips.length === 0 && <p className="text-sm text-muted">Aucun bulletin pour cette période.</p>}
        <div className="overflow-x-auto">
          {payslips.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th className="py-1 pr-2">Matricule</th>
                  <th className="pr-2 text-right">Brut</th>
                  <th className="pr-2 text-right">Cotis.</th>
                  <th className="pr-2 text-right">IRPP</th>
                  <th className="pr-2 text-right">Net</th>
                  <th className="pr-2">Statut</th>
                  <th className="pr-2" />
                </tr>
              </thead>
              <tbody>
                {payslips.map((p) => (
                  <tr key={p.id} className="border-t border-black/5">
                    <td className="py-1 pr-2 font-medium">{p.employee_matricule}</td>
                    <td className="pr-2 text-right">{fmt(p.brut_xaf)}</td>
                    <td className="pr-2 text-right text-muted">{fmt(p.total_cotisations_salariales_xaf)}</td>
                    <td className="pr-2 text-right text-muted">{fmt(p.irpp_xaf)}</td>
                    <td className="pr-2 text-right font-semibold">{fmt(p.net_a_payer_xaf)}</td>
                    <td className="pr-2">
                      <span className={"rounded-full px-2 py-0.5 text-[10px] font-semibold " + (p.statut === "valide" ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-600")}>{p.statut}</span>
                    </td>
                    <td className="pr-2">
                      <span className="flex items-center gap-2">
                        <button onClick={() => downloadBulletin(p.id, `${p.employee_matricule}_${p.periode}`)} title="Bulletin Excel" className="text-primary hover:text-primary/80"><Download className="h-4 w-4" /></button>
                        {gabaritActif && (
                          <button onClick={() => downloadBulletinHtml(p.id, `${p.employee_matricule}_${p.periode}`)} title="Bulletin HTML (gabarit)" className="text-xs font-semibold text-primary hover:text-primary/80">HTML</button>
                        )}
                        <button onClick={() => archiverBulletin(p.id)} title="Archiver (coffre-fort)" className="text-muted hover:text-primary"><Archive className="h-4 w-4" /></button>
                        {p.statut !== "valide" && (
                          <button onClick={() => pay(p.id)} title="Valider/payer" className="text-emerald-600 hover:text-emerald-800"><CheckCircle2 className="h-4 w-4" /></button>
                        )}
                        <button onClick={() => deletePayslip(p.id).then(refresh)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      {/* Déclarations annuelles — DAS 1 */}
      <Card>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <FileText className="h-4 w-4 text-primary" /> Déclarations · DAS 1 {annee}
          </h2>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={loadDas1}>Aperçu</Button>
            <Button variant="ghost" onClick={() => downloadDas1(annee)}><Download className="h-4 w-4" /> Exporter</Button>
          </div>
        </div>
        <p className="mb-2 text-xs text-muted">
          Consolide les bulletins de l&apos;exercice {annee} : état annuel (brut × 12 mois) +
          DAS 1 / CNSS 1 (brut, salaire plafonné, base imposable 80 %, IRPP).
        </p>
        {das1 && (
          <>
            <div className="mb-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <Mini label="Salariés" value={String(das1.nb_salaries)} />
              <Mini label="Brut annuel" value={fmt(das1.totaux.brut_xaf) + " XAF"} />
              <Mini label="Base imposable" value={fmt(das1.totaux.base_imposable_xaf) + " XAF"} />
              <Mini label="IRPP" value={fmt(das1.totaux.irpp_xaf) + " XAF"} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted">
                    <th className="py-1 pr-2">Matricule</th>
                    <th className="pr-2">Nom</th>
                    <th className="pr-2 text-right">Brut</th>
                    <th className="pr-2 text-right">Plafonné</th>
                    <th className="pr-2 text-right">Av. nature</th>
                    <th className="pr-2 text-right">Base imp.</th>
                    <th className="pr-2 text-right">IRPP</th>
                    <th className="pr-2 text-right">Indem.</th>
                  </tr>
                </thead>
                <tbody>
                  {das1.lignes.map((l) => (
                    <tr key={l.matricule} className="border-t border-black/5">
                      <td className="py-1 pr-2 font-medium">{l.matricule}</td>
                      <td className="pr-2">{l.nom || "—"}</td>
                      <td className="pr-2 text-right">{fmt(l.brut_annuel_xaf)}</td>
                      <td className="pr-2 text-right text-muted">{fmt(l.salaire_plafonne_xaf)}</td>
                      <td className="pr-2 text-right text-muted">{fmt(l.avantages_nature_xaf)}</td>
                      <td className="pr-2 text-right text-muted">{fmt(l.base_imposable_xaf)}</td>
                      <td className="pr-2 text-right">{fmt(l.irpp_xaf)}</td>
                      <td className="pr-2 text-right text-muted">{fmt(l.indemnites_non_imposables_xaf)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <JournalPaiePanel />
      <BaremePanel />
      <EmployeeRubriquesPanel />
      <VariablesMoisPanel />
      <BulletinModelePanel />
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-black/[0.03] p-2">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-0.5 font-semibold">{value}</div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </Card>
  );
}
