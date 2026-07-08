// Client API du pôle Fintech (/v1/fintech) — scoring crédit + KYC/AML.
// Les montants XAF sont sérialisés en chaînes (Decimal) côté backend.
import { api } from "./api";

export interface Facteur {
  code: string;
  libelle: string;
  sens: "positif" | "negatif" | "neutre";
  valeur: string;
  contribution: number;
  commentaire: string;
}

export interface CreditScore {
  score: number;
  grade: string;
  decision: "accorde" | "a_etudier" | "refuse";
  taux_endettement_pct: string;
  capacite_remboursement_xaf: string;
  mensualite_estimee_xaf: string;
  montant_max_suggere_xaf: string;
  cout_total_credit_xaf: string;
  facteurs: Facteur[];
  avertissements: string[];
  bareme_indicatif: boolean;
}

export interface CreditInput {
  revenu_mensuel_xaf: string;
  charges_mensuelles_xaf: string;
  montant_demande_xaf: string;
  duree_mois: number;
  anciennete_activite_mois: number;
  incidents_paiement: number;
  epargne_xaf: string;
  garanties_xaf: string;
  type_emploi: string;
}

export async function scoreCredit(dossier: CreditInput): Promise<CreditScore> {
  return api<CreditScore>("/v1/fintech/score", { body: { dossier } });
}

export interface KycInput {
  nom: string;
  type_client: "particulier" | "entreprise";
  pieces_fournies: string[];
  pep: boolean;
  pays_residence: string;
  secteur_activite?: string;
  correspondance_liste: boolean;
}

export interface KycResult {
  complet: boolean;
  pieces_manquantes: string[];
  niveau_risque: "faible" | "moyen" | "eleve";
  score_risque: number;
  facteurs_risque: string[];
  vigilance: "standard" | "renforcee";
  peut_entrer_en_relation: boolean;
  motifs_blocage: string[];
  reference_cadre: string;
}

export async function evaluateKyc(profile: KycInput): Promise<KycResult> {
  return api<KycResult>("/v1/fintech/kyc", { body: profile });
}

export interface TransactionInput {
  date: string;
  montant_xaf: string;
  sens: "entree" | "sortie";
  canal: "especes" | "virement" | "mobile_money";
  contrepartie?: string;
}

export interface AmlAlert {
  code: string;
  niveau: "info" | "attention" | "alerte";
  titre: string;
  detail: string;
}

export interface AmlResult {
  nb_operations: number;
  volume_total_xaf: string;
  volume_especes_xaf: string;
  alertes: AmlAlert[];
  bareme_indicatif: boolean;
  reference_cadre: string;
}

export async function evaluateAml(transactions: TransactionInput[]): Promise<AmlResult> {
  return api<AmlResult>("/v1/fintech/aml", { body: { transactions } });
}

// --- Persistance (FINTECH-3/4) --------------------------------------------

export interface CreditApplication {
  id: string;
  numero: string;
  client: string;
  montant_demande_xaf: string;
  duree_mois: number;
  score: number;
  grade: string;
  decision: string;
  statut: string;
  taux_endettement_pct: string;
  mensualite_xaf: string;
  montant_max_xaf: string;
  commentaire: string | null;
  created_at: string | null;
}

export async function createApplication(
  client: string,
  dossier: CreditInput,
): Promise<CreditApplication> {
  return api<CreditApplication>("/v1/fintech/applications", { body: { client, dossier } });
}

export async function listApplications(): Promise<CreditApplication[]> {
  return (await api<{ applications: CreditApplication[] }>("/v1/fintech/applications")).applications;
}

export async function decideApplication(
  id: string,
  statut: string,
  commentaire?: string,
): Promise<CreditApplication> {
  return api<CreditApplication>(`/v1/fintech/applications/${id}/decision`, {
    body: { statut, commentaire },
  });
}

export async function deleteApplication(id: string): Promise<void> {
  await api(`/v1/fintech/applications/${id}`, { method: "DELETE" });
}

export interface KycRecordItem {
  id: string;
  nom: string;
  type_client: string;
  niveau_risque: string;
  score_risque: number;
  vigilance: string;
  complet: boolean;
  peut_entrer_en_relation: boolean;
  pep: boolean;
  statut: string;
  commentaire: string | null;
  created_at: string | null;
}

export async function createKycRecord(profile: KycInput): Promise<KycRecordItem> {
  return api<KycRecordItem>("/v1/fintech/kyc-records", { body: profile });
}

export async function listKycRecords(): Promise<KycRecordItem[]> {
  return (await api<{ kyc_records: KycRecordItem[] }>("/v1/fintech/kyc-records")).kyc_records;
}

export async function decideKycRecord(id: string, statut: string): Promise<KycRecordItem> {
  return api<KycRecordItem>(`/v1/fintech/kyc-records/${id}/decision`, { body: { statut } });
}

export async function deleteKycRecord(id: string): Promise<void> {
  await api(`/v1/fintech/kyc-records/${id}`, { method: "DELETE" });
}

export interface PortfolioStats {
  nb_dossiers: number;
  par_statut: Record<string, number>;
  montant_demande_total_xaf: string;
  montant_accorde_xaf: string;
  encours_decaisse_xaf: string;
  service_dette_mensuel_xaf: string;
  taux_acceptation_pct: string;
  taux_decaissement_pct: string;
  score_moyen: number;
  repartition_grade: Record<string, number>;
  nb_kyc: number;
  kyc_par_statut: Record<string, number>;
  kyc_par_risque: Record<string, number>;
  nb_vigilance_renforcee: number;
  encours_restant_du_xaf: string;
  montant_en_retard_xaf: string;
  nb_prets_en_retard: number;
  par30_pct: string;
  par90_pct: string;
  echeancier_disponible: boolean;
  signaux: string[];
  note: string;
}

export async function getPortfolio(): Promise<PortfolioStats> {
  return api<PortfolioStats>("/v1/fintech/portfolio");
}

// --- Échéancier de remboursement (FINTECH-6) -------------------------------

export interface Echeance {
  id: string;
  numero: number;
  date_echeance: string;
  principal_xaf: string;
  interet_xaf: string;
  montant_xaf: string;
  montant_paye_xaf: string;
  reste_xaf: string;
  statut: string;
  en_retard: boolean;
  paye_le: string | null;
}

export interface ScheduleResult {
  echeances: Echeance[];
  total_xaf: string;
  paye_xaf: string;
  reste_xaf: string;
}

export async function disburse(id: string, dateDecaissement?: string): Promise<void> {
  await api(`/v1/fintech/applications/${id}/disburse`, {
    body: { date_decaissement: dateDecaissement ?? null },
  });
}

export async function getSchedule(id: string): Promise<ScheduleResult> {
  return api<ScheduleResult>(`/v1/fintech/applications/${id}/schedule`);
}

export async function payInstallment(id: string, montant?: string): Promise<Echeance> {
  return api<Echeance>(`/v1/fintech/installments/${id}/pay`, {
    body: { montant: montant ?? null },
  });
}

export interface CohortStat {
  periode: string;
  nb_prets: number;
  montant_decaisse_xaf: string;
  montant_du_echu_xaf: string;
  montant_rembourse_xaf: string;
  encours_restant_xaf: string;
  montant_en_retard_xaf: string;
  taux_remboursement_pct: string;
  par30_pct: string;
}

export async function getCohortes(): Promise<CohortStat[]> {
  return (await api<{ cohortes: CohortStat[] }>("/v1/fintech/cohortes")).cohortes;
}

// Pièces requises par type de client (miroir du backend, pour l'UI).
export const PIECES_KYC: Record<string, { id: string; label: string }[]> = {
  particulier: [
    { id: "piece_identite", label: "Pièce d'identité" },
    { id: "justificatif_domicile", label: "Justificatif de domicile" },
    { id: "niu", label: "NIU (optionnel)" },
  ],
  entreprise: [
    { id: "rccm", label: "RCCM" },
    { id: "niu", label: "NIU" },
    { id: "statuts", label: "Statuts" },
    { id: "piece_dirigeant", label: "Pièce du dirigeant" },
  ],
};
