// Client typé — Marketing persisté (/v1/mkt/contacts | campaigns | audience-store).
import { api } from "./api";

export interface ContactRec {
  id: string;
  id_externe: string;
  nom: string;
  email: string | null;
  telephone: string | null;
  secteur: string | null;
  type: string;
  derniere_interaction: string | null;
  consentement_marketing: boolean;
  finalites: string[];
  date_consentement: string | null;
  source: string | null;
}

export interface CampaignRec {
  id: string;
  nom: string;
  canal: string;
  finalite: string;
  segment: string | null;
  objet: string | null;
  statut: string;
  date_creation: string | null;
  date_envoi: string | null;
  nb_cibles: number;
  nb_envois: number;
  nb_ouvertures: number;
  nb_clics: number;
}

export interface ConsentSummary {
  finalite: string;
  eligibles: number;
  exclus: number;
  total: number;
}
export interface AudienceStore {
  finalite: string;
  segments: Record<string, number>;
  consent: ConsentSummary;
}

// ----- Contacts -----
export function listContacts(): Promise<{ contacts: ContactRec[] }> {
  return api("/v1/mkt/contacts");
}
export function createContact(b: {
  id_externe: string;
  nom: string;
  email?: string;
  type?: string;
  consentement_marketing?: boolean;
  finalites?: string[];
  source?: string;
}): Promise<ContactRec> {
  return api("/v1/mkt/contacts", { body: b });
}
export function patchContact(
  id: string,
  b: { consentement_marketing?: boolean; finalites?: string[] },
): Promise<ContactRec> {
  return api(`/v1/mkt/contacts/${id}`, { method: "PATCH", body: b });
}
export function deleteContact(id: string): Promise<{ deleted: string }> {
  return api(`/v1/mkt/contacts/${id}`, { method: "DELETE" });
}

// ----- Campagnes -----
export function listCampaigns(): Promise<{ campaigns: CampaignRec[] }> {
  return api("/v1/mkt/campaigns");
}
export function createCampaign(b: {
  nom: string;
  canal: string;
  finalite: string;
  objet?: string;
}): Promise<CampaignRec> {
  return api("/v1/mkt/campaigns", { body: b });
}
export function sendCampaign(
  id: string,
): Promise<{ campaign: CampaignRec; exclus_non_consentants: number }> {
  return api(`/v1/mkt/campaigns/${id}/send`, { method: "POST", body: {} });
}
export function deleteCampaign(id: string): Promise<{ deleted: string }> {
  return api(`/v1/mkt/campaigns/${id}`, { method: "DELETE" });
}

// ----- Audience consentante -----
export function audienceStore(finalite: string): Promise<AudienceStore> {
  return api(`/v1/mkt/audience-store?finalite=${encodeURIComponent(finalite)}`);
}
