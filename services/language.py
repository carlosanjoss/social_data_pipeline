"""Detecção de idioma usada na fronteira do PostgreSQL final."""
from __future__ import annotations

from langdetect import DetectorFactory, LangDetectException, detect

# O algoritmo do langdetect é probabilístico. Fixar a semente deixa cargas e
# testes reprodutíveis para o mesmo texto.
DetectorFactory.seed = 0

PORTUGUESE = "pt"
PT_BR = "pt-BR"
MAX_DETECTION_CHARS = 2_000


def detect_language(*parts: object) -> str | None:
    """Retorna o código ISO 639-1 detectado para as partes textuais."""
    text = " ".join(str(part).strip() for part in parts if part and str(part).strip())
    if not text:
        return None
    text = text[:MAX_DETECTION_CHARS]

    try:
        return detect(text)
    except LangDetectException:
        return None


def is_pt_br(*parts: object) -> bool:
    """Aceita apenas texto detectado como português.

    ``langdetect`` identifica o idioma como ``pt`` e não separa as variantes
    regionais. Como o corpus-alvo desta pesquisa é brasileiro, todo texto
    português aceito é persistido com o código canônico ``pt-BR``.
    """
    return detect_language(*parts) == PORTUGUESE
