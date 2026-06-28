// Client typé — Opérations persistées : Facility (/v1/erp/assets|echeances) + HSE (/risques|incidents).
import { api } from "./api";

// ----- Facility -----
export interface AssetRec {
  id: string;
  id_externe: string;
  libelle: string;
  type_actif: string;
  maintenance_intervalle_jours: number;
  derniere_maintenance: string | null;
}
export interface EcheanceRec {
  id: string;
  id_externe: string;
  asset_id: string | null;
  type_echeance: string;
  libelle: string;
  date_echeance: string | null;
}
export interface FacilityAlerte {
  categorie: string;
  reference: string;
  libelle: string;
  date_cible: string;
  jours_restants: number;
  urgence: string;
}

export function listAssets(): Promise<{ assets: AssetRec[] }> {
  return api("/v1/erp/assets");
}
export function createAsset(b: {
  id_externe: string;
  libelle: string;
  type_actif?: string;
  maintenance_intervalle_jours?: number;
  derniere_maintenance?: string | null;
}): Promise<AssetRec> {
  return api("/v1/erp/assets", { body: b });
}
export function deleteAsset(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/assets/${id}`, { method: "DELETE" });
}
export function listEcheances(): Promise<{ echeances: EcheanceRec[] }> {
  return api("/v1/erp/echeances");
}
export function createEcheance(b: {
  id_externe: string;
  type_echeance: string;
  libelle: string;
  date_echeance: string;
}): Promise<EcheanceRec> {
  return api("/v1/erp/echeances", { body: b });
}
export function deleteEcheance(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/echeances/${id}`, { method: "DELETE" });
}
export function facilityEcheancier(
  horizonJours = 30,
): Promise<{ maintenances: FacilityAlerte[]; echeances: FacilityAlerte[] }> {
  return api(`/v1/erp/facility/echeancier?horizon_jours=${horizonJours}`);
}

// ----- HSE -----
export interface RisqueRec {
  id: string;
  id_externe: string;
  libelle: string;
  probabilite: number;
  gravite: number;
}
export interface RisqueEvalue {
  reference: string;
  libelle: string;
  criticite: number;
  niveau: string;
}
export interface IncidentRec {
  id: string;
  id_externe: string;
  date_incident: string | null;
  type_incident: string;
  gravite: string;
  description: string;
  jours_arret: number;
}
export interface HseIndicators {
  statistiques: Record<string, number>;
  taux_frequence: string;
  taux_gravite: string;
}

export function listRisques(): Promise<{ risques: RisqueRec[] }> {
  return api("/v1/erp/risques");
}
export function createRisque(b: {
  id_externe: string;
  libelle: string;
  probabilite: number;
  gravite: number;
}): Promise<RisqueRec> {
  return api("/v1/erp/risques", { body: b });
}
export function deleteRisque(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/risques/${id}`, { method: "DELETE" });
}
export function hseCartographie(): Promise<{ risques: RisqueEvalue[] }> {
  return api("/v1/erp/hse/cartographie");
}
export function listIncidents(): Promise<{ incidents: IncidentRec[] }> {
  return api("/v1/erp/incidents");
}
export function createIncident(b: {
  id_externe: string;
  date_incident: string;
  type_incident?: string;
  gravite?: string;
  jours_arret?: number;
}): Promise<IncidentRec> {
  return api("/v1/erp/incidents", { body: b });
}
export function deleteIncident(id: string): Promise<{ deleted: string }> {
  return api(`/v1/erp/incidents/${id}`, { method: "DELETE" });
}
export function hseIndicators(heuresTravaillees = 200000): Promise<HseIndicators> {
  return api(`/v1/erp/hse/indicators?heures_travaillees=${heuresTravaillees}`);
}
