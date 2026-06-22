"use client";

import { useParams } from "next/navigation";
import { CapabilityScreen } from "@/components/CapabilityScreen";
import { getCapability } from "@/lib/capabilities";
import { Card } from "@/components/ui";

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
  return <CapabilityScreen capability={capability} />;
}
