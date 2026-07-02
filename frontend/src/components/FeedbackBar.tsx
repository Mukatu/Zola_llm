"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Check, Pencil } from "lucide-react";
import clsx from "clsx";
import { sendFeedback, type FeedbackVerdict } from "@/lib/feedback";
import { ApiError } from "@/lib/api";

/**
 * Contrôle de feedback sous une réponse d'agent : 👍 / 👎 + correction experte.
 * POST vers /v1/feedback (boucle d'auto-amélioration du moteur ZolaOS).
 */
export function FeedbackBar({
  agent,
  query,
  response,
  requestId,
}: {
  agent: string;
  query: string;
  response: string;
  requestId?: string;
}) {
  const [state, setState] = useState<"idle" | "correcting" | "sending" | "done">("idle");
  const [verdictEnvoye, setVerdictEnvoye] = useState<FeedbackVerdict | null>(null);
  const [correction, setCorrection] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function envoyer(verdict: FeedbackVerdict, corr?: string) {
    setState("sending");
    setErr(null);
    try {
      await sendFeedback({
        agent,
        query,
        response,
        verdict,
        request_id: requestId,
        correction: corr?.trim() || undefined,
      });
      setVerdictEnvoye(verdict);
      setState("done");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Envoi impossible");
      setState("idle");
    }
  }

  if (state === "done") {
    return (
      <div className="flex items-center gap-1 pl-1 text-xs text-muted">
        <Check className="h-3.5 w-3.5 text-emerald-600" />
        Merci — retour {verdictEnvoye === "up" ? "positif" : "négatif"} enregistré.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 pl-1">
      <div className="flex items-center gap-1 text-muted">
        <span className="text-xs">Cette réponse vous a-t-elle aidé ?</span>
        <IconBtn label="Utile" disabled={state === "sending"} onClick={() => envoyer("up")}>
          <ThumbsUp className="h-3.5 w-3.5" />
        </IconBtn>
        <IconBtn
          label="À corriger"
          active={state === "correcting"}
          disabled={state === "sending"}
          onClick={() => setState((s) => (s === "correcting" ? "idle" : "correcting"))}
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </IconBtn>
      </div>

      {state === "correcting" && (
        <div className="flex flex-col gap-1">
          <textarea
            value={correction}
            onChange={(e) => setCorrection(e.target.value)}
            rows={2}
            placeholder="Correction ou précision (optionnel) — aide le moteur à s'améliorer."
            className="w-full max-w-md resize-none rounded-lg border border-black/10 bg-white p-2 text-xs outline-none focus:ring-2 focus:ring-primary/40"
          />
          <button
            type="button"
            onClick={() => envoyer("down", correction)}
            className="inline-flex w-fit items-center gap-1 rounded-lg bg-primary px-2.5 py-1 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
          >
            <Pencil className="h-3 w-3" /> Envoyer la correction
          </button>
        </div>
      )}

      {err && <div className="text-xs text-red-600">{err}</div>}
    </div>
  );
}

function IconBtn({
  children,
  label,
  onClick,
  active,
  disabled,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "inline-flex items-center justify-center rounded-md p-1 transition hover:bg-black/5 disabled:opacity-40",
        active && "bg-black/5 text-primary",
      )}
    >
      {children}
    </button>
  );
}
