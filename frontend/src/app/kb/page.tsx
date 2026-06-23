"use client";

import { useState } from "react";
import { BookOpen, Search } from "lucide-react";
import { Card, Button } from "@/components/ui";

export default function KbPage() {
  const [q, setQ] = useState("");
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><BookOpen className="h-5 w-5" /></span>
        <div><h1 className="text-lg font-semibold">Consultation documentaire</h1><p className="text-sm text-muted">Actes Uniformes OHADA, conventions, CGI… (recherche dans votre corpus).</p></div>
      </div>
      <Card>
        <div className="flex gap-2">
          <div className="flex flex-1 items-center gap-2 rounded-xl border border-black/10 bg-white px-3">
            <Search className="h-4 w-4 text-muted" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher un article, une notion…" className="flex-1 bg-transparent py-2 text-sm outline-none" />
          </div>
          <Button disabled>Rechercher</Button>
        </div>
        <p className="mt-3 text-xs text-muted">
          La recherche documentaire s'activera une fois les corpus ingérés (OHADA, CGI, conventions). Voir la feuille de route données.
        </p>
      </Card>
    </div>
  );
}
