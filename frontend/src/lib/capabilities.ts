// Manifeste des capacités : pilote la navigation ET le contenu de chaque écran.
// Chaque capacité a un écran (route /c/<code>) rendu depuis ces métadonnées
// (description + intents). Pas de page bespoke par métier → pas de dispersion,
// mais un écran tailored par capacité.

import {
  BarChart3, Boxes, Calculator, Code2, FileSignature, HardHat, Handshake,
  Landmark, Megaphone, Receipt, ScrollText, ShieldCheck, ShoppingCart, Stethoscope,
  Users, Wallet, Wrench, type LucideIcon,
} from "lucide-react";

export const POLE_LABELS: Record<string, string> = {
  sante: "Santé", droit: "Droit", erp: "ERP & Opérations", bi: "Pilotage",
  commercial: "Commercial", marketing: "Marketing", grc: "GRC",
  fintech: "Fintech", cyber: "Cyber", engineering: "Engineering",
};

export interface Intent { id: string; label: string }

export interface Capability {
  code: string;
  label: string;
  pole: string;
  kind: "generic" | "flagship";
  route: string;
  icon: LucideIcon;
  description: string;
  intents: Intent[];
}

function intents(...pairs: [string, string][]): Intent[] {
  return pairs.map(([id, label]) => ({ id, label }));
}

function cap(
  code: string, label: string, icon: LucideIcon, description: string,
  ints: Intent[] = [], kind: "generic" | "flagship" = "generic",
): Capability {
  return { code, label, pole: code.split(".")[0], icon, description, intents: ints, kind, route: `/c/${code}` };
}

export const CAPABILITIES: Record<string, Capability> = Object.fromEntries(
  [
    cap("sante.pharmacology", "Pharmacologie", Stethoscope,
      "Conseil posologie, interactions et médicaments essentiels (cite ses sources).",
      intents(["posologie", "Posologie"], ["interactions", "Interactions"], ["info", "Info médicament"])),
    cap("droit.ohada", "Droit OHADA", ScrollText,
      "Droit des affaires OHADA : sociétés, sûretés, contrats.",
      intents(["rediger", "Rédiger"], ["analyser", "Analyser"], ["expliquer", "Expliquer"])),
    cap("droit.travail_cg", "Droit du travail", ScrollText,
      "Contrats, rupture, indemnités — Code du travail CG + conventions.",
      intents(["rediger", "Rédiger"], ["analyser", "Analyser"], ["calcul", "Calcul indemnités"])),
    cap("droit.fiscal_cg", "Droit fiscal", ScrollText,
      "CGI congolais : TVA, IS, IRPP, retenues.",
      intents(["analyser", "Analyser"], ["optimiser", "Optimiser"], ["expliquer", "Expliquer"])),
    cap("droit.admin_cg", "Droit administratif", ScrollText,
      "Marchés publics, ARMP, contentieux administratif (neutralité stricte).",
      intents(["analyser", "Analyser"], ["expliquer", "Expliquer"])),
    cap("engineering.code", "Code", Code2,
      "Génération, refactor, debug et revue de code.",
      intents(["generate", "Générer"], ["refactor", "Refactor"], ["debug", "Debug"], ["explain", "Expliquer"], ["review", "Revue"], ["test", "Tests"])),
    cap("erp.rh", "RH", Users,
      "Documents RH, conformité de contrat, tri de CV.",
      intents(["contrat", "Contrat"], ["lettre", "Lettre"], ["conformite", "Conformité"], ["cv", "Tri CV"])),
    cap("erp.paie", "Paie", Wallet,
      "Bulletin de paie déterministe (CNSS/CIPRES/IRPP).",
      intents(["bulletin", "Simuler bulletin"], ["expliquer", "Expliquer un calcul"]), "flagship"),
    cap("erp.finance", "Finance / Trésorerie", Wallet,
      "Anomalies (doublons/dépassements/échéances) + synthèse trésorerie.",
      intents(["anomalies", "Anomalies"], ["synthese", "Synthèse"]), "flagship"),
    cap("erp.compta", "Comptabilité", Calculator,
      "Validation d'écritures SYSCOHADA + interprétation fiscale.",
      intents(["ecriture", "Valider écriture"], ["interpretation", "Interprétation fiscale"]), "flagship"),
    cap("erp.registre", "Registre & clôture vivante", Receipt,
      "Factures persistées + clôture continue (rapprochement temps réel).",
      intents(["registre", "Registre"], ["cloture", "Clôture vivante"]), "flagship"),
    cap("erp.projets_ong", "Projets ONG", Handshake,
      "Gestion financière ONG, ventilation bailleur/projet.",
      intents(["suivi", "Suivi budget"], ["rapport", "Rapport"])),
    cap("erp.supply_chain", "Supply Chain & Stocks", Boxes,
      "Réapprovisionnement, alertes rupture, bons de commande.",
      intents(["reappro", "Réappro"], ["alertes", "Alertes rupture"], ["bon_commande", "Bon de commande"])),
    cap("erp.achats", "Achats", ShoppingCart,
      "Comparaison de devis, scoring fournisseurs, contrats OHADA.",
      intents(["comparer", "Comparer devis"], ["scoring", "Scoring fournisseur"], ["contrat", "Contrat"])),
    cap("erp.moyens_generaux", "Moyens Généraux", Wrench,
      "Maintenance préventive et échéances (assurances/visites/licences).",
      intents(["echeancier", "Échéancier"], ["ordre_travail", "Ordre de travail"])),
    cap("erp.secretariat_societaire", "Secrétariat sociétaire", FileSignature,
      "PV d'AG/CA, ordres du jour, registre des mandats (AUSCGIE).",
      intents(["pv", "PV"], ["odj", "Ordre du jour"], ["mandats", "Mandats"])),
    cap("erp.hse", "HSE / RSE", HardHat,
      "Cartographie des risques, incidents, plans de prévention, RSE.",
      intents(["cartographie", "Cartographie"], ["plan", "Plan prévention"], ["rse", "Rapport RSE"])),
    cap("bi.pilotage", "Pilotage / BI", BarChart3,
      "KPIs cross-métiers, synthèse et questions en langage naturel.",
      intents(["kpis", "KPIs"], ["synthese", "Synthèse"], ["question", "Question"]), "flagship"),
    cap("commercial.crm", "Commercial / CRM", Handshake,
      "Pipeline, scoring de leads, relances, propositions.",
      intents(["pipeline", "Pipeline"], ["relance", "Relance"], ["proposition", "Proposition"]), "flagship"),
    cap("marketing.campagnes", "Marketing", Megaphone,
      "Segmentation, campagnes, génération de contenu (consentement requis).",
      intents(["contenu", "Contenu"], ["segment", "Segment"])),
    cap("grc.conformite", "Conformité GRC", ShieldCheck,
      "Audit de conformité et contrôle interne.",
      intents(["audit", "Audit"], ["controle", "Contrôle"])),
    cap("grc.reporting_bailleurs", "Reporting bailleurs", ShieldCheck,
      "Rapports bailleurs internationaux (IATI/PRAG).",
      intents(["rapport", "Rapport"], ["conformite", "Conformité"])),
    cap("fintech.scoring", "Scoring crédit", Landmark,
      "Scoring crédit (microfinance).",
      intents(["scorer", "Scorer"], ["expliquer", "Expliquer"])),
    cap("fintech.kyc", "KYC", Landmark,
      "Vérification d'identité et conformité AML/CFT.",
      intents(["verifier", "Vérifier"], ["screening", "Screening"])),
    cap("cyber.defense", "Cyber-défense", ShieldCheck,
      "Audit de configuration et durcissement (défensif).",
      intents(["audit", "Audit config"], ["durcissement", "Durcissement"])),
  ].map((c) => [c.code, c]),
);

export function getCapability(code: string): Capability | undefined {
  return CAPABILITIES[code];
}

export interface NavGroup { pole: string; label: string; items: Capability[] }

export function navGroupsFromModules(modules: string[]): NavGroup[] {
  const groups = new Map<string, Capability[]>();
  for (const code of modules) {
    const c = CAPABILITIES[code];
    if (!c) continue;
    if (!groups.has(c.pole)) groups.set(c.pole, []);
    groups.get(c.pole)!.push(c);
  }
  return [...groups.entries()].map(([pole, items]) => ({ pole, label: POLE_LABELS[pole] ?? pole, items }));
}
