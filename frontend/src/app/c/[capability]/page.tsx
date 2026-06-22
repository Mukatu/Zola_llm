"use client";

import { useParams } from "next/navigation";
import { CapabilityScreen } from "@/components/CapabilityScreen";
import { PaieScreen } from "@/components/flagship/PaieScreen";
import { getCapability } from "@/lib/capabilities";
import { Card } from "@/components/ui";
import type { ComponentType } from "react";

// Écrans phares (UX dédiée câblée sur les moteurs déterministes /v1/erp/*).
// Les autres capacités utilisent l'écran générique (CapabilityScreen).
const FLAGSHIPS: Record<string, ComponentType> = {
  "erp.paie": PaieScreen,
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
