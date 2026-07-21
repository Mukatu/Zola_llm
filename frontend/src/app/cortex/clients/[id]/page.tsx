"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Building2, Server, KeyRound, ShieldOff, Copy, Check, Loader2, AlertTriangle } from "lucide-react";
import { Card, Button, Skeleton } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useZola, hasScope } from "@/components/ConfigProvider";
import {
  getClient,
  updateClient,
  issueBoxCredential,
  revokeBoxCredential,
  type ClientDetail,
} from "@/lib/cortex-clients";

// Couleurs alignées sur /cortex/missions (même vocabulaire de statut).
const STATUS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700", revoked: "bg-red-100 text-red-700",
  expired: "bg-gray-100 text-gray-600", completed: "bg-blue-100 text-blue-700",
};

// Traduit les codes d'erreur backend en messages FR (même schéma que /cortex/clients).
function messageFromError(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  if (e.status === 404) return "Client introuvable.";
  if (e.status === 403) return "Accès réservé aux administrateurs du cabinet.";
  if (e.status === 500 && e.detail.includes("api_key_pepper_not_configured")) return "Configuration serveur incomplète (pepper de credential manquant).";
  return fallback;
}

export default function ClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { config, user } = useZola();
  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [boxUrl, setBoxUrl] = useState("");
  const [boxUrlBusy, setBoxUrlBusy] = useState(false);
  const [boxUrlErr, setBoxUrlErr] = useState<string | null>(null);

  const [credBusy, setCredBusy] = useState(false);
  const [credErr, setCredErr] = useState<string | null>(null);
  const [issuedCred, setIssuedCred] = useState<{ credential: string; prefix: string } | null>(null);
  const [copied, setCopied] = useState(false);

  async function reload() {
    try {
      const d = await getClient(id);
      setDetail(d);
      setBoxUrl(d.tenant.box_url ?? "");
      setErr(null);
    } catch (e) {
      setErr(messageFromError(e, "Cortex injoignable / authentification requise."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (config.profil === "cortex" && hasScope(user, "admin:users")) reload();
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.profil, user, id]);

  async function saveBoxUrl() {
    setBoxUrlBusy(true);
    setBoxUrlErr(null);
    try {
      await updateClient(id, { box_url: boxUrl.trim() });
      await reload();
    } catch (e) {
      setBoxUrlErr(messageFromError(e, "Échec de l'enregistrement de l'adresse."));
    } finally {
      setBoxUrlBusy(false);
    }
  }

  async function issueCredential() {
    setCredBusy(true);
    setCredErr(null);
    setIssuedCred(null);
    setCopied(false);
    try {
      const res = await issueBoxCredential(id);
      setIssuedCred({ credential: res.credential, prefix: res.prefix });
      await reload();
    } catch (e) {
      setCredErr(messageFromError(e, "Échec de l'émission du credential."));
    } finally {
      setCredBusy(false);
    }
  }

  async function revokeCredential() {
    if (!window.confirm("Révoquer le credential de cette box ? Elle sera immédiatement déconnectée et ne pourra plus se reconnecter tant qu'un nouveau credential ne lui sera pas donné.")) return;
    setCredBusy(true);
    setCredErr(null);
    try {
      await revokeBoxCredential(id);
      setIssuedCred(null);
      await reload();
    } catch (e) {
      setCredErr(messageFromError(e, "Échec de la révocation du credential."));
    } finally {
      setCredBusy(false);
    }
  }

  function copyCredential() {
    if (!issuedCred) return;
    navigator.clipboard.writeText(issuedCred.credential).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (config.profil !== "cortex") {
    return (
      <div className="mx-auto max-w-2xl">
        <Card><p className="text-sm text-muted">Réservé au cockpit cabinet.</p></Card>
      </div>
    );
  }

  if (!hasScope(user, "admin:users")) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card><p className="text-sm text-muted">Accès réservé aux administrateurs du cabinet.</p></Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Link href="/cortex/clients" className="flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" /> Clients</Link>

      {loading && <Card><Skeleton className="mb-2 h-5 w-1/3" /><Skeleton className="h-4 w-2/3" /></Card>}
      {err && <Card className="ring-amber-200"><p className="text-sm text-amber-700">{err}</p></Card>}

      {detail && (
        <>
          <Card className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><Building2 className="h-5 w-5" /></span>
            <div className="flex-1">
              <h1 className="text-lg font-semibold">{detail.tenant.name}</h1>
              <p className="text-xs text-muted">
                {detail.tenant.country.toUpperCase()} · {detail.tenant.tenant_type === "cabinet" ? "Cabinet" : "Client"} · {detail.tenant.is_active ? "actif" : "désactivé"}
              </p>
            </div>
          </Card>

          <Card className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-mint/25 text-forest"><Server className="h-5 w-5" /></span>
              <div className="flex-1">
                <div className="font-semibold">Zolabox</div>
                <div className="text-xs text-muted">Déploiement hybride : corpus et données du client hébergés chez lui, interrogés à distance pendant les missions.</div>
              </div>
              {detail.tenant.box_credential_prefix ? (
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                  Box provisionnée ({detail.tenant.box_credential_prefix}…)
                </span>
              ) : (
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600">Aucune box provisionnée</span>
              )}
            </div>

            <label className="text-sm">
              <span className="mb-1 block font-medium">Adresse de la box (box_url)</span>
              <div className="flex gap-2">
                <input
                  value={boxUrl}
                  onChange={(e) => setBoxUrl(e.target.value)}
                  placeholder="https://box-client.exemple.cg"
                  disabled={boxUrlBusy}
                  className="w-full rounded-lg border border-black/10 bg-white px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-primary/40"
                />
                <Button variant="ghost" onClick={saveBoxUrl} disabled={boxUrlBusy}>
                  {boxUrlBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Enregistrer
                </Button>
              </div>
            </label>
            {boxUrlErr && (
              <div className="flex items-start gap-2 rounded-xl p-3 text-sm text-red-700 ring-1 ring-red-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> <span>{boxUrlErr}</span>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={issueCredential} disabled={credBusy}>
                {credBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
                {detail.tenant.box_credential_prefix ? "Faire tourner le credential" : "Provisionner"}
              </Button>
              {detail.tenant.box_credential_prefix && (
                <button
                  onClick={revokeCredential}
                  disabled={credBusy}
                  className="flex items-center gap-1 text-sm text-red-600 hover:underline disabled:opacity-50"
                >
                  <ShieldOff className="h-4 w-4" /> Révoquer
                </button>
              )}
            </div>

            {credErr && (
              <div className="flex items-start gap-2 rounded-xl p-3 text-sm text-red-700 ring-1 ring-red-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> <span>{credErr}</span>
              </div>
            )}

            {issuedCred && (
              <div className="flex flex-col gap-2 rounded-xl p-3 text-sm ring-1 ring-amber-200">
                <span className="font-medium text-amber-700">Credential émis — à copier maintenant</span>
                <code className="break-all rounded-lg bg-black/5 p-2 text-xs">{issuedCred.credential}</code>
                <div className="flex items-center gap-3">
                  <Button variant="ghost" onClick={copyCredential}>
                    {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
                    {copied ? "Copié" : "Copier"}
                  </Button>
                  <span className="text-xs text-amber-700">Notez-le : il ne sera plus affiché. À placer dans ZOLAOS_BOX_CREDENTIAL de la box.</span>
                </div>
              </div>
            )}
          </Card>

          <Card>
            <h2 className="mb-2 text-sm font-semibold">Missions liées</h2>
            {detail.missions.length === 0 && <p className="text-sm text-muted">Aucune mission liée à ce tenant.</p>}
            {detail.missions.map((m) => (
              <div key={m.id} className="flex items-center justify-between border-b border-black/5 py-2 text-sm last:border-0">
                <div>
                  <div className="font-medium">{m.offre}</div>
                  <div className="text-xs text-muted">
                    rôle {m.role === "cabinet" ? "cabinet" : "client"} · débutée {new Date(m.started_at).toLocaleDateString("fr-FR")}
                    {m.expires_at ? " · expire " + new Date(m.expires_at).toLocaleDateString("fr-FR") : ""}
                  </div>
                </div>
                <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + (STATUS[m.status] ?? "bg-gray-100 text-gray-600")}>{m.status}</span>
              </div>
            ))}
          </Card>
        </>
      )}
    </div>
  );
}
