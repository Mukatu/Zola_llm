// i18n minimal (FR ; Lingala/Kituba viendront en FE-3 / Pôle K).

type Dict = Record<string, string>;

const FR: Dict = {
  "nav.assistant": "Assistant",
  "nav.dashboard": "Tableau de bord",
  "nav.documents": "Documents",
  "nav.kb": "Consultation documentaire",
  "nav.settings": "Paramètres",
  "assistant.placeholder": "Posez une question, l'orchestrateur route vers le bon agent…",
  "assistant.send": "Envoyer",
  "offline.banner": "Mode hors-ligne — les actions seront synchronisées au retour du réseau.",
  "capability.run": "Exécuter",
  "common.loading": "Chargement…",
};

const DICTS: Record<string, Dict> = { fr: FR, ln: FR, kg: FR };

export function makeT(locale: string) {
  const d = DICTS[locale] ?? FR;
  return (key: string) => d[key] ?? key;
}
