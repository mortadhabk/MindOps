from typing import Any

from app.connectors.base import Connector
from app.rag.schemas import DocumentIn

FIXED_ITEMS: list[dict[str, Any]] = [
    {
        "id": 1,
        "title": "Le paiement echoue au-dela de 10 000 euros",
        "body": "Le service de paiement rejette les montants superieurs a 10 000 euros "
        "a cause d'un depassement du champ DECIMAL en base de donnees.",
    },
    {
        "id": 2,
        "title": "Timeout sur l'export CSV",
        "body": "L'export CSV des transactions echoue au-dela de 50 000 lignes par timeout HTTP.",
    },
]


class MockConnector(Connector):
    """Connecteur factice, sans appel reseau, pour tester le pipeline connecteur -> RAG."""

    name = "mock"

    async def fetch_items(self, **params: Any) -> list[dict[str, Any]]:
        return FIXED_ITEMS

    def to_document(self, item: dict[str, Any]) -> DocumentIn:
        return DocumentIn(
            source=f"mock#{item['id']}",
            content=f"{item['title']}\n\n{item['body']}",
        )
