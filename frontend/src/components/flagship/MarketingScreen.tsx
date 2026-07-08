"use client";

import { useCallback, useEffect, useState } from "react";
import { Megaphone, ShieldCheck, Plus, Trash2, Send, AlertCircle } from "lucide-react";
import { Card, Button } from "../ui";
import { FlagshipHeader, Inp } from "./_shared";
import { ApiError } from "@/lib/api";
import {
  listContacts,
  createContact,
  patchContact,
  deleteContact,
  listCampaigns,
  createCampaign,
  sendCampaign,
  deleteCampaign,
  audienceStore,
  type ContactRec,
  type CampaignRec,
  type AudienceStore,
} from "@/lib/marketing";

const FINALITES = ["promotions", "newsletter"];
const STATUT_COLOR: Record<string, string> = {
  brouillon: "bg-gray-100 text-gray-600",
  validee: "bg-amber-100 text-amber-700",
  envoyee: "bg-emerald-100 text-emerald-700",
};
const DEMO_CONTACTS = [
  { id_externe: "C1", nom: "Awa", email: "awa@ex.cg", type: "client", consentement_marketing: true, finalites: ["newsletter", "promotions"], source: "web" },
  { id_externe: "C2", nom: "Paul", email: "paul@ex.cg", type: "client", consentement_marketing: false, finalites: [], source: "salon" },
  { id_externe: "C3", nom: "Sylvie", email: "sylvie@ex.cg", type: "prospect", consentement_marketing: true, finalites: ["newsletter"], source: "referral" },
  { id_externe: "C4", nom: "Jean", email: "jean@ex.cg", type: "client", consentement_marketing: true, finalites: ["promotions"], source: "web" },
];

export function MarketingScreen() {
  const [contacts, setContacts] = useState<ContactRec[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignRec[]>([]);
  const [finalite, setFinalite] = useState("promotions");
  const [aud, setAud] = useState<AudienceStore | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [cForm, setCForm] = useState({ nom: "", email: "", consent: true });
  const [campForm, setCampForm] = useState({ nom: "", canal: "email", finalite: "promotions" });

  const loadAudience = useCallback(async (f: string) => {
    try {
      setAud(await audienceStore(f));
    } catch {
      setAud(null);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [c, k] = await Promise.all([listContacts(), listCampaigns()]);
      setContacts(c.contacts);
      setCampaigns(k.campaigns);
      setErr(null);
    } catch (e) {
      setErr(e instanceof ApiError ? "Backend indisponible (DB requise)." : "Service indisponible.");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);
  useEffect(() => {
    loadAudience(finalite);
  }, [finalite, loadAudience, contacts]);

  async function addContact() {
    if (!cForm.nom) return;
    try {
      await createContact({
        id_externe: `C-${Date.now()}`,
        nom: cForm.nom,
        email: cForm.email || undefined,
        consentement_marketing: cForm.consent,
        finalites: cForm.consent ? FINALITES : [],
      });
      setCForm({ nom: "", email: "", consent: true });
      await refresh();
    } catch {
      setErr("Création contact impossible (backend/DB).");
    }
  }
  async function toggleConsent(c: ContactRec) {
    try {
      const next = !c.consentement_marketing;
      await patchContact(c.id, { consentement_marketing: next, finalites: next ? FINALITES : [] });
      await refresh();
    } catch {
      setErr("Mise à jour du consentement impossible.");
    }
  }
  async function addCampaign() {
    if (!campForm.nom) return;
    try {
      await createCampaign(campForm);
      setCampForm({ ...campForm, nom: "" });
      await refresh();
    } catch {
      setErr("Création campagne impossible.");
    }
  }
  async function send(id: string) {
    try {
      const r = await sendCampaign(id);
      setErr(null);
      if (r.campaign.nb_cibles === 0) setErr("Aucun contact consentant pour cette finalité — 0 envoi (Loi 29-2019).");
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 409 ? "Campagne déjà envoyée." : "Envoi impossible.");
    }
  }
  async function seedDemo() {
    try {
      for (const c of DEMO_CONTACTS) await createContact(c);
      await refresh();
    } catch {
      setErr("Initialisation de la démo impossible.");
    }
  }

  const consentants = contacts.filter((c) => c.consentement_marketing).length;
  const tauxConsent = contacts.length > 0 ? Math.round((consentants / contacts.length) * 100) : 0;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <FlagshipHeader
        icon={Megaphone}
        title="Marketing"
        subtitle="Base d'audience consentante (Loi 29-2019), segmentation et campagnes — registre vivant."
      />

      {err && (
        <Card className="ring-amber-200">
          <div className="flex items-start gap-2 text-amber-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <p className="text-sm">{err}</p>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi label="Contacts" value={String(contacts.length)} />
        <Kpi label="Taux de consentement" value={tauxConsent + " %"} />
        <Kpi label="Campagnes" value={String(campaigns.length)} />
        <Kpi label={`Éligibles « ${finalite} »`} value={aud ? String(aud.consent.eligibles) : "—"} />
      </div>

      {contacts.length === 0 && (
        <Card>
          <div className="flex flex-col items-start gap-2">
            <p className="text-sm text-muted">Aucun contact. Base <b>persistante</b> avec consentement : chargez une démo ou créez un contact.</p>
            <Button onClick={seedDemo}><Plus className="h-4 w-4" /> Charger une démo</Button>
          </div>
        </Card>
      )}

      {/* Audience consentante par finalité */}
      <Card className={aud && aud.consent.eligibles === 0 ? "ring-red-200" : undefined}>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="h-4 w-4 text-emerald-600" /> Audience consentante</h2>
          <select value={finalite} onChange={(e) => setFinalite(e.target.value)} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
            {FINALITES.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
        {aud && (
          <p className="text-sm">
            <b>{aud.consent.eligibles}</b> éligible(s) · <b>{aud.consent.exclus}</b> exclu(s) sur {aud.consent.total} pour « {aud.consent.finalite} ».
            <span className="ml-2 text-xs text-muted">Segments : {Object.entries(aud.segments).map(([k, v]) => `${k}=${v}`).join(" · ")}</span>
          </p>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Contacts */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Contacts &amp; consentement</h2>
          <div className="mb-2 grid grid-cols-[1fr_1fr_auto_36px] items-center gap-2">
            <Inp value={cForm.nom} onChange={(v) => setCForm({ ...cForm, nom: v })} placeholder="Nom" />
            <Inp value={cForm.email} onChange={(v) => setCForm({ ...cForm, email: v })} placeholder="Email" />
            <label className="flex items-center gap-1 text-xs text-muted">
              <input type="checkbox" checked={cForm.consent} onChange={(e) => setCForm({ ...cForm, consent: e.target.checked })} /> opt-in
            </label>
            <button onClick={addContact} className="grid place-items-center rounded-lg bg-forest text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {contacts.map((c) => (
            <div key={c.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span><b>{c.nom}</b> <span className="text-xs text-muted">{c.email ?? ""}</span></span>
              <span className="flex items-center gap-2">
                <button onClick={() => toggleConsent(c)} className={"rounded-full px-2 py-0.5 text-[10px] font-semibold " + (c.consentement_marketing ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500")}>
                  {c.consentement_marketing ? "consentant" : "non consentant"}
                </button>
                <button onClick={() => deleteContact(c.id).then(refresh)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
              </span>
            </div>
          ))}
        </Card>

        {/* Campagnes */}
        <Card>
          <h2 className="mb-2 text-sm font-semibold">Campagnes</h2>
          <div className="mb-2 grid grid-cols-[1fr_90px_110px_36px] gap-2">
            <Inp value={campForm.nom} onChange={(v) => setCampForm({ ...campForm, nom: v })} placeholder="Nom" />
            <select value={campForm.canal} onChange={(e) => setCampForm({ ...campForm, canal: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              {["email", "sms", "post"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={campForm.finalite} onChange={(e) => setCampForm({ ...campForm, finalite: e.target.value })} className="rounded-lg border border-black/10 bg-white px-2 py-1 text-sm">
              {FINALITES.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
            <button onClick={addCampaign} className="grid place-items-center rounded-lg bg-forest text-white"><Plus className="h-4 w-4" /></button>
          </div>
          {campaigns.length === 0 && <p className="text-sm text-muted">Aucune campagne.</p>}
          {campaigns.map((k) => (
            <div key={k.id} className="flex items-center justify-between border-b border-black/5 py-1.5 text-sm last:border-0">
              <span>
                <b>{k.nom}</b> · {k.canal} · {k.finalite}
                {k.statut === "envoyee" && <span className="ml-1 text-xs text-muted">({k.nb_cibles} ciblés)</span>}
              </span>
              <span className="flex items-center gap-2">
                <span className={"rounded-full px-2 py-0.5 text-[10px] font-semibold " + (STATUT_COLOR[k.statut] ?? "")}>{k.statut}</span>
                {k.statut !== "envoyee" && (
                  <button onClick={() => send(k.id)} title="Envoyer (consentants uniquement)" className="text-emerald-600 hover:text-emerald-800"><Send className="h-4 w-4" /></button>
                )}
                <button onClick={() => deleteCampaign(k.id).then(refresh)} className="text-muted hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
              </span>
            </div>
          ))}
        </Card>
      </div>
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
