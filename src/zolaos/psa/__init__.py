"""PSA (Professional Services Automation) — outillage cabinet.

Socle : feuilles de temps → économie de la mission (honoraires/coût/marge/WIP) →
taux d'occupation. Calcul **déterministe** (le moteur calcule, le LLM narre) ; les
tarifs viennent de la config (`PSA_RATE_CARD_JSON`), jamais inventés.
"""

from zolaos.psa.economics import compute_engagement_economics, compute_utilization, entry_amounts
from zolaos.psa.expenses import EXPENSE_CATEGORIES, summarize_expenses
from zolaos.psa.rates import GRADES, load_rate_card, resolve_rates

__all__ = [
    "EXPENSE_CATEGORIES",
    "GRADES",
    "compute_engagement_economics",
    "compute_utilization",
    "entry_amounts",
    "load_rate_card",
    "resolve_rates",
    "summarize_expenses",
]
