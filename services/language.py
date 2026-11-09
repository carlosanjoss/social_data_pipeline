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


_PT_CODES = {"pt", "pt-br"}


def decide_target(declared: object, verified: bool, parts: tuple) -> bool:
    """Decisão final de fronteira: mantém apenas português.

    Rejeita metadado explicitamente não português e confirma pelo texto quando
    o metadado não é conclusivo. É uma função de topo (picklable) para poder
    rodar em workers paralelos com resultado idêntico ao modo sequencial.
    """
    code = str(declared or "").strip().lower().replace("_", "-")
    if code and code not in _PT_CODES:
        return False
    if verified and code in _PT_CODES:
        return True
    return is_pt_br(*parts)


def decide_target_payload(payload: tuple) -> bool:
    """Wrapper picklable para ``ProcessPoolExecutor.map`` (1 item = 1 arg)."""
    declared, verified, parts = payload
    return decide_target(declared, verified, parts)


def decide_batch(payloads: list) -> list:
    """Decide uma lista inteira num só worker (menos overhead de pickling)."""
    return [decide_target(*payload) for payload in payloads]


# ── Detecção reforçada (apenas para posts-âncora) ─────────────────────────────
# `langdetect` é notoriamente instável em textos curtos: títulos como
# "MAIS UMA DECISÃO COVARDE DE MORAES!" saem como 'de' e "#Bolsonaro17" como
# 'es'. Para rotular o idioma real do post-pai combinamos o detector com um
# escore léxico-ortográfico de português. Não afeta o filtro do corpus, que
# continua usando `is_pt_br`/`decide_target` puros.

_UNDETERMINED = "und"

# Marcas ortográficas praticamente exclusivas do português.
_STRONG_PT_CHARS = set("ãõ")
# Diacríticos comuns em português (também aparecem em francês/italiano).
_WEAK_PT_CHARS = set("âêôàç")
# Marcas tipográficas típicas do espanhol.
_ES_CHARS = set("ñ¿¡")

_PT_WORDS = frozenset("""
que nao não com para uma dos das por mais voce você ele ela isso isto aqui brasil bolsonaro lula
e é sao são esta está vai ser tem foi como mas seu sua ao os as de da do em um na no se ja já tambem também
so só muito bem tudo nada gente cara viu ta tá ne né acho fazer dizer ver todo toda mesmo ainda depois agora hoje
ai aí la lá entao então porque quando onde quem qual quanto todos todas outro outra esse essa este esta aquele aquela
vamos vao vão estão sera será ate até sobre entre sem pelo pela nos nós minhas meus nossa nosso
dia ano anos ontem amanha amanhã tempo povo pais país mundo vida trabalho casa filho filhos mulher homem
governo presidente eleicao eleição deputado senador partido politica política crime justica justiça
pouco grande pequeno novo velho bom ruim melhor pior sempre deles dela dele nele nela aquilo nunca
oi olha veja vejam bora parabéns obrigado obrigada valeu agora mesmo assim pois
""".split())

_WORD_RE = None


def _pt_score(text: str) -> int:
    """Escore heurístico de português: >0 indica texto provavelmente pt."""
    global _WORD_RE
    if _WORD_RE is None:
        import re

        _WORD_RE = re.compile(r"[a-záéíóúâêôãõçà]+")

    lowered = text.lower()
    score = 0
    score += 2 * sum(1 for ch in lowered if ch in _STRONG_PT_CHARS)
    score += sum(1 for ch in lowered if ch in _WEAK_PT_CHARS)
    score -= 3 * sum(1 for ch in lowered if ch in _ES_CHARS)
    score += sum(1 for word in _WORD_RE.findall(lowered) if word in _PT_WORDS)
    return score


def detect_language_robust(*parts: object) -> str:
    """Código do idioma do post-pai, caindo em heurística quando o texto é curto.

    Nunca devolve ``None``: usa ``'und'`` (undetermined) quando não há texto
    utilizável, para que a coluna ``language`` (NOT NULL) sempre tenha valor.
    """
    text = " ".join(str(p).strip() for p in parts if p and str(p).strip())
    if not text:
        return _UNDETERMINED

    code = detect_language(text)
    if code == PORTUGUESE:
        return PORTUGUESE
    if _pt_score(text) >= 2:
        return PORTUGUESE
    return code or _UNDETERMINED
