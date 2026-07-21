"use client";

import { useEffect, useState } from "react";
import { Lock, Mail } from "lucide-react";
import { Card, Button } from "@/components/ui";
import { login } from "@/lib/auth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [next, setNext] = useState("/");

  useEffect(() => {
    // Lu côté client (pas de useSearchParams) pour rester une page 100% statique.
    const params = new URLSearchParams(window.location.search);
    setNext(params.get("next") || "/");
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      // Rechargement complet (pas de navigation SPA) : les cookies de session
      // doivent être pris en compte par tout l'arbre au prochain rendu.
      window.location.assign(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connexion impossible pour le moment.");
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-navy px-4">
      <Card className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-1 text-center">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary text-lg font-semibold text-white shadow-sm shadow-primary/40">
            Z
          </span>
          <h1 className="mt-2 text-lg font-semibold text-ink">ZolaOS</h1>
          <p className="text-sm text-muted">Espace Polaris</p>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm text-ink">
            Email
            <div className="flex items-center gap-2 rounded-xl bg-black/5 px-3 py-2 ring-1 ring-black/5 focus-within:ring-2 focus-within:ring-primary">
              <Mail className="h-4 w-4 shrink-0 text-muted" />
              <input
                type="email"
                required
                autoFocus
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-muted"
                placeholder="prenom.nom@exemple.com"
              />
            </div>
          </label>

          <label className="flex flex-col gap-1 text-sm text-ink">
            Mot de passe
            <div className="flex items-center gap-2 rounded-xl bg-black/5 px-3 py-2 ring-1 ring-black/5 focus-within:ring-2 focus-within:ring-primary">
              <Lock className="h-4 w-4 shrink-0 text-muted" />
              <input
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-muted"
                placeholder="••••••••"
              />
            </div>
          </label>

          {error && (
            <p role="alert" className="rounded-lg bg-red-100 px-3 py-2 text-xs font-medium text-red-700">
              {error}
            </p>
          )}

          <Button type="submit" disabled={busy}>
            {busy ? "Connexion…" : "Se connecter"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
