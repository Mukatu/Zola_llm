// Client typé — Devises / Change : taux gouvernés (validation experte) + conversion
// déterministe (/v1/erp/fx/rates|convert).
import { api } from "./api";

export interface FxRate {
  devise: string;
  taux_vers_xaf: string | null;
  validated: boolean;
  source: string;
  source_donnees: "tenant" | "defaut";
  editable: boolean;
  validated_by: string;
  note: string;
  validated_at: string | null;
}

export interface FxRatesView {
  base: string;
  country: string;
  rates: FxRate[];
}

export interface FxConvertResult {
  montant: string;
  de: string;
  vers: string;
  resultat: string;
  taux_de_vers_xaf: string;
  taux_vers_vers_xaf: string;
}

export function getFxRates(country = "cg"): Promise<FxRatesView> {
  return api(`/v1/erp/fx/rates?country=${encodeURIComponent(country)}`);
}

export function editFxRate(
  devise: string,
  body: { taux_vers_xaf: string; source: string },
  country = "cg",
): Promise<FxRatesView> {
  return api(`/v1/erp/fx/rates/${encodeURIComponent(devise)}?country=${encodeURIComponent(country)}`, {
    method: "PUT",
    body,
  });
}

export function validateFxRate(
  devise: string,
  body: { validated: boolean; validated_by?: string; note?: string },
  country = "cg",
): Promise<FxRatesView> {
  return api(
    `/v1/erp/fx/rates/${encodeURIComponent(devise)}/validate?country=${encodeURIComponent(country)}`,
    { body },
  );
}

export function fxConvert(q: {
  montant: string;
  de: string;
  vers: string;
  country?: string;
}): Promise<FxConvertResult> {
  const params = new URLSearchParams({
    montant: q.montant,
    de: q.de,
    vers: q.vers,
    country: q.country ?? "cg",
  });
  return api(`/v1/erp/fx/convert?${params.toString()}`);
}
