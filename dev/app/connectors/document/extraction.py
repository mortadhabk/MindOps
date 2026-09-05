import io

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.exceptions import ConnectorConfigError

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 Mo : garde-fou simple, largement suffisant pour un POC


def extract_text(*, filename: str, raw_bytes: bytes) -> str:
    """Convertit un fichier déposé dans le Studio en texte brut, prêt pour `content` du
    connecteur `document`. Le format est déduit de l'extension — `.pdf`/`.docx` passent par une
    extraction structurée, tout le reste est traité comme du texte brut (`.txt`, `.md`, ...)."""
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        limit_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise ConnectorConfigError(f"Fichier trop volumineux (> {limit_mb} Mo)")

    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if suffix == "pdf":
        return _extract_pdf(raw_bytes)
    if suffix == "docx":
        return _extract_docx(raw_bytes)

    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConnectorConfigError(
            f"Format de fichier non pris en charge : .{suffix or '?'} "
            "(pris en charge : texte brut, .pdf, .docx)"
        ) from exc


def _extract_pdf(raw_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # fichier corrompu ou chiffré : pypdf lève des exceptions variées
        raise ConnectorConfigError(f"Impossible de lire ce PDF : {exc}") from exc

    text = "\n\n".join(page.strip() for page in pages if page.strip())
    if not text:
        raise ConnectorConfigError(
            "Aucun texte extrait de ce PDF (page scannée/image sans OCR ?)"
        )
    return text


def _extract_docx(raw_bytes: bytes) -> str:
    try:
        document = DocxDocument(io.BytesIO(raw_bytes))
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    except Exception as exc:  # fichier corrompu ou pas un vrai .docx malgré l'extension
        raise ConnectorConfigError(f"Impossible de lire ce document Word : {exc}") from exc

    text = "\n\n".join(paragraphs)
    if not text:
        raise ConnectorConfigError("Aucun texte extrait de ce document Word")
    return text
