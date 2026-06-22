// Manifeste des capacités : pilote la navigation et les écrans de capacité.
// Une capacité = un module (code "pole.module"). Écran générique par défaut,
// quelques "phares" avec route dédiée.

import {
  BarChart3, Boxes, Calculator, Code2, FileSignature, HardHat, Handshake,
  Landmark, Megaphone, ScrollText, ShieldCheck, ShoppingCart, Stethoscope,
  Truck, Users, Wallet, Wrench, type LucideIcon,
} from "lucide-react";

export const POLE_LABELS: Record<string, string> = {
  sante: "Santé", droit: "Droit", erp: "ERP & Opérations", bi: "Pilotage",
  commercial: "Commercial", marketing: "Marketing", grc: "GRC",
  fintech: "Fintech", cyber: "Cyber", engineering: "Engineering",
};

export interface Capability {
  code: string;
  label: string;
  pole: string;
  kind: "generic" | "flagship";
  route: string;
  icon: LucideIcon;
}

function cap(code: string, label: string, icon: LucideIcon, kind: "generic" | "flagship" = "generic", route?: string): Capability {
  const pole = code.split(".")[0];
  return { code, label, pole, icon, kind, route: route ?? `/c/${code}` };
}

export const CAPABILITIES: Record<string, Capability> = Object.fromEntries(
  [
    cap("sante.pharmacology", "Pharmacologie", Stethoscope),
    cap("droit.ohada", "Droit OHADA", ScrollText),
    cap("droit.travail_cg", "Droit du travail", ScrollText),
    cap("droit.fiscal_cg", "Droit fiscal", ScrollText),
    cap("droit.admin_cg", "Droit administratif", ScrollText),
    cap("engineering.code", "Code", Code2),
    cap("erp.rh", "RH", Users),
    cap("erp.paie", "Paie", Wallet, "flagship", "/paie"),
    cap("erp.finance", "Finance / Trésorerie", Wallet, "flagship", "/finance"),
    cap("erp.compta", "Comptabilité", Calculator, "flagship", "/compta"),
    cap("erp.projets_ong", "Projets ONG", Handshake),
    cap("erp.supply_chain", "Supply Chain & Stocks", Boxes),
    cap("erp.achats", "Achats", ShoppingCart),
    cap("erp.moyens_generaux", "Moyens Généraux", Wrench),
    cap("erp.secretariat_societaire", "Secrétariat sociétaire", FileSignature),
    cap("erp.hse", "HSE / RSE", HardHat),
    cap("bi.pilotage", "Pilotage / BI", BarChart3, "flagship", "/pilotage"),
    cap("commercial.crm", "Commercial / CRM", Handshake, "flagship", "/crm"),
    cap("marketing.campagnes", "Marketing", Megaphone),
    cap("grc.conformite", "Conformité GRC", ShieldCheck),
    cap("grc.reporting_bailleurs", "Reporting bailleurs", ShieldCheck),
    cap("fintech.scoring", "Scoring crédit", Landmark),
    cap("fintech.kyc", "KYC", Landmark),
    cap("cyber.defense", "Cyber-défense", ShieldCheck),
  ].map((c) => [c.code, c]),
);

export function getCapability(code: string): Capability | undefined {
  return CAPABILITIES[code];
}

export interface NavGroup {
  pole: string;
  label: string;
  items: Capability[];
}

/** Construit les groupes de navigation depuis les modules activés (config). */
export function navGroupsFromModules(modules: string[]): NavGroup[] {
  const groups = new Map<string, Capability[]>();
  for (const code of modules) {
    const c = CAPABILITIES[code];
    if (!c) continue;
    if (!groups.has(c.pole)) groups.set(c.pole, []);
    groups.get(c.pole)!.push(c);
  }
  return [...groups.entries()].map(([pole, items]) => ({
    pole, label: POLE_LABELS[pole] ?? pole, items,
  }));
}
