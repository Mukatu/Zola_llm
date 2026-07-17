import { AlertTriangle } from "lucide-react";
import type { Grounding } from "@/lib/query";

/**
 * Avertit quand le modèle a répondu SANS aucune source.
 *
 * Le routeur peut se tromper de pôle et envoyer une question de droit vers
 * l'assistance générale, qui n'a pas de corpus : la réponse est alors inventée
 * mais a l'air aussi assurée qu'une réponse sourcée. On ne peut pas garantir un
 * routage parfait — on garantit au moins qu'une réponse non sourcée ne se fasse
 * jamais passer pour une réponse fiable.
 *
 * Rien à afficher pour "sourced" (les citations parlent d'elles-mêmes) ni pour
 * "abstained" (le texte du refus est déjà explicite).
 */
export function GroundingBadge({ grounding }: { grounding?: Grounding }) {
  if (grounding !== "unsourced") return null;
  return (
    <span
      title="Aucune source du corpus ne soutient cette réponse. Le modèle a répondu de mémoire : vérifiez toute règle, tout chiffre ou toute référence avant de vous en servir."
      className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800"
    >
      <AlertTriangle className="h-3 w-3" />
      Réponse non sourcée — à vérifier
    </span>
  );
}
