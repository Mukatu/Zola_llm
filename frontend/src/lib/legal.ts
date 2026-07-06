// Client typé — pôle juridique : traduction de contrats étrangers (/v1/legal/translate).
import { api } from "./api";
import { fileToBase64 } from "./kb";

export interface TranslateResult {
  source_lang: string;
  target_lang: string;
  translation: string;
  caracteres: number;
  assimilated: boolean;
  source_uri?: string;
  chunks?: number;
}

export async function translateContract(p: {
  text?: string;
  file?: File;
  targetLang?: string;
  assimilate?: boolean;
  module?: string;
  tenantId?: string;
}): Promise<TranslateResult> {
  const body: Record<string, unknown> = {
    target_lang: p.targetLang ?? "français",
    assimilate: p.assimilate ?? false,
    module: p.module ?? "ohada",
    tenant_id: p.tenantId ?? "local",
  };
  if (p.file) {
    body.filename = p.file.name;
    body.content_b64 = await fileToBase64(p.file);
  } else {
    body.text = p.text ?? "";
  }
  return api("/v1/legal/translate", { body });
}
