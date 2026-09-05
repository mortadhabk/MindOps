from app.core.logging import logger


async def write_log(event_type: str, payload: dict) -> None:
    """Squelette minimal (Epic 4) : journalise via le logger structuré existant. Remplacé par
    une table `AuditLog` persistante en Epic 5 (US-501, US-502) sans que les appelants
    (`gating`, `agent`) n'aient à changer — c'est le contrat, pas l'implémentation, qui compte."""
    logger.info("audit_event type=%s payload=%s", event_type, payload)
