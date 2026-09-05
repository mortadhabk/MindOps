from enum import StrEnum

from app.config import get_settings


class Decision(StrEnum):
    SUGGEST_ONLY = "suggest_only"
    REQUIRE_VALIDATION = "require_validation"
    AUTO_EXECUTE = "auto_execute"


def evaluate(action_type: str, confidence: float) -> Decision:
    """Politique de confiance : configurable par type d'action, sans redéploiement (US-402, US-406).

    Fonction pure : ne lit que la configuration en mémoire, aucun accès base de données ni réseau.
    """
    settings = get_settings()
    configured = settings.gating_policy.get(action_type, Decision.REQUIRE_VALIDATION.value)
    decision = Decision(configured)

    # Garde-fou : même autorisé en auto_execute, un appel sous le seuil de confiance configuré
    # retombe en validation humaine plutôt que de s'exécuter à l'aveugle.
    if decision is Decision.AUTO_EXECUTE and confidence < settings.gating_min_confidence:
        return Decision.REQUIRE_VALIDATION
    return decision
