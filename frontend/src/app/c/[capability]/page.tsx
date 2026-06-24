"use client";

import { useParams } from "next/navigation";
import { CapabilityScreen } from "@/components/CapabilityScreen";
import { PaieScreen } from "@/components/flagship/PaieScreen";
import { ComptaScreen } from "@/components/flagship/ComptaScreen";
import { SupplyScreen } from "@/components/flagship/SupplyScreen";
import { AchatsScreen } from "@/components/flagship/AchatsScreen";
import { HseScreen } from "@/components/flagship/HseScreen";
import { FacilityScreen } from "@/components/flagship/FacilityScreen";
import { CrmScreen } from "@/components/flagship/CrmScreen";
import { BiScreen } from "@/components/flagship/BiScreen";
import { FinanceScreen } from "@/components/flagship/FinanceScreen";
import { CodeScreen } from "@/components/flagship/CodeScreen";
import { DroitScreen } from "@/components/flagship/DroitScreen";
import { MarketingScreen } from "@/components/flagship/MarketingScreen";
import { RegistreScreen } from "@/components/flagship/RegistreScreen";
import { RHScreen } from "@/components/flagship/RHScreen";
import { ReferentielsScreen } from "@/components/flagship/ReferentielsScreen";
import { RecrutementScreen } from "@/components/flagship/RecrutementScreen";
import { DeveloppementScreen } from "@/components/flagship/DeveloppementScreen";
import { getCapability } from "@/lib/capabilities";
import { Card } from "@/components/ui";
import type { ComponentType } from "react";

// Écrans phares (UX dédiée câblée sur les moteurs déterministes /v1/erp/*).
// Les autres capacités utilisent l'écran générique (CapabilityScreen).
const FLAGSHIPS: Record<string, ComponentType> = {
  "erp.paie": PaieScreen,
  "erp.compta": ComptaScreen,
  "erp.supply_chain": SupplyScreen,
  "erp.achats": AchatsScreen,
  "erp.hse": HseScreen,
  "erp.moyens_generaux": FacilityScreen,
  "commercial.crm": CrmScreen,
  "bi.pilotage": BiScreen,
  "erp.finance": FinanceScreen,
  "erp.registre": RegistreScreen,
  "erp.rh": RHScreen,
  "erp.referentiels": ReferentielsScreen,
  "erp.recrutement": RecrutementScreen,
  "erp.developpement": DeveloppementScreen,
  "engineering.code": CodeScreen,
  "droit.ohada": DroitScreen,
  "droit.travail_cg": DroitScreen,
  "droit.fiscal_cg": DroitScreen,
  "droit.admin_cg": DroitScreen,
  "marketing.campagnes": MarketingScreen,
};

export default function CapabilityPage() {
  const params = useParams<{ capability: string }>();
  const code = decodeURIComponent(params.capability);
  const capability = getCapability(code);

  if (!capability) {
    return (
      <Card className="mx-auto max-w-2xl ring-amber-200">
        <p className="text-sm text-amber-700">Capacité inconnue : <code>{code}</code></p>
      </Card>
    );
  }

  const Flagship = FLAGSHIPS[code];
  if (Flagship) return <Flagship />;
  return <CapabilityScreen capability={capability} />;
}
