"use client";

import { FolderOpen } from "lucide-react";
import { Card } from "@/components/ui";

export default function DocumentsPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><FolderOpen className="h-5 w-5" /></span>
        <div><h1 className="text-lg font-semibold">Documents générés</h1><p className="text-sm text-muted">Contrats, bulletins, rapports et exports.</p></div>
      </div>
      <Card className="text-center text-sm text-muted">
        <FolderOpen className="mx-auto mb-2 h-8 w-8 opacity-40" />
        Aucun document pour l'instant. Les documents générés (contrats, PV, rapports, bons de commande) apparaîtront ici.
      </Card>
    </div>
  );
}
