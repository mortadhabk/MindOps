"""Convertisseur ADF (Atlassian Document Format, Jira Cloud) → texte brut.

Jira Cloud renvoie `description` et le corps des commentaires comme un arbre JSON structuré (pas
une chaîne) — voir https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/.
Jira Server/Data Center ne produit jamais ce format : sa description est déjà une chaîne, utilisée
telle quelle par `connector.py`, qui n'appelle ce module que pour un déploiement "cloud".
"""

from typing import Any

# Nœuds "bloc" : un saut de ligne les sépare du contenu suivant, pour que le texte reste lisible
# (paragraphes, titres, cellules de tableau...) plutôt qu'une bouillie sans ponctuation.
_BLOCK_TYPES = {"paragraph", "heading", "blockquote", "panel", "tableCell", "tableHeader"}


def adf_to_text(node: dict[str, Any] | None) -> str:
    """Convertit un document ADF (ou un fragment) en texte brut lisible."""
    if not node:
        return ""
    return _walk(node).strip()


def _walk(node: dict[str, Any]) -> str:
    node_type = node.get("type")

    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"
    if node_type == "mention":
        return node.get("attrs", {}).get("text", "")
    if node_type == "emoji":
        return node.get("attrs", {}).get("shortName", "")
    if node_type == "rule":
        return "\n---\n"

    children = node.get("content", [])
    inner = "".join(_walk(child) for child in children)

    if node_type == "listItem":
        return f"- {inner.strip()}\n"
    if node_type in _BLOCK_TYPES or node_type == "codeBlock":
        return f"{inner}\n\n"
    # bulletList/orderedList/table/tableRow/doc/nœud inconnu : pas de saut de ligne propre à eux,
    # celui de leurs enfants (listItem, paragraph, ...) suffit déjà.
    return inner
