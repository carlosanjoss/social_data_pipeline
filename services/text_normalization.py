"""
Normalização e anonimização de texto — Radar Ódio v0.1.

Aplica exatamente o pré-processamento do Radar Ódio v0.1: normalização Unicode
NFC, unificação de quebras de linha, tabulações → espaço, colapso de espaços
ASCII consecutivos e anonimização de URLs, e-mails, CPFs, telefones e menções.

Preserva caixa, pontuação, emojis, hashtags, erros ortográficos, abreviações e
grafias intencionais. Não faz lowercase, stemming, lematização, remoção de
stopwords/pontuação/emojis/hashtags, correção ortográfica nem tradução.

`normalize_document(text)` é a função única usada em todos os dados: ela executa
normalização + anonimização na ordem exigida.
"""
from __future__ import annotations

import re
import unicodedata

# ── Normalização ──────────────────────────────────────────────────────────────

_MULTI_SPACE = re.compile(r" {2,}")


def normalize_text(text: str | None) -> str | None:
    """Normalização textual pura (sem anonimização)."""
    if text is None:
        return None

    # 3. Unicode NFC
    out = unicodedata.normalize("NFC", text)
    # 4. \r\n e \r → \n  (a ordem importa: CRLF antes de CR solto)
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    # 5. tabulações → espaço ASCII
    out = out.replace("\t", " ")
    # 6. colapsa 2+ espaços ASCII consecutivos (preserva \n)
    out = _MULTI_SPACE.sub(" ", out)
    return out


# ── Anonimização ──────────────────────────────────────────────────────────────

# 1. Marcadores legados → canônicos
_LEGACY_MARKERS = {
    "[USER]": "<USER>",
    "[EMAIL]": "<EMAIL>",
    "[PHONE]": "<PHONE>",
    "[URL]": "<URL>",
    "[user]": "<USER>",
    "[email]": "<EMAIL>",
    "[phone]": "<PHONE>",
    "[url]": "<URL>",
}

# 2. URLs (esquema, www. ou domínio nu com TLD conhecido)
_URL_RE = re.compile(
    r"""(?xi)
    (?<![\w@.])
    (?:
        (?:https?|ftp)://[^\s<>"'\)\]]+
      | www\.[^\s<>"'\)\]]+
      | [a-z0-9][a-z0-9.\-]*\.(?:
            com\.br|net\.br|org\.br|gov\.br|edu\.br|jus\.br|leg\.br
          | com|net|org|gov|edu|mil|int|io|br|info|biz|me|tv|xyz
          | online|site|blog|app|dev|link|cc|us|uk|pt
        )(?:/[^\s<>"'\)\]]*)?
    )(?![\w])
    """
)

# 3. E-mails (aceita marcador já canonicalizado como primeiro caractere)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# 4. CPF (com ou sem máscara) — validado por dígitos verificadores
_CPF_RE = re.compile(r"(?<![\d.])(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?![\d.])")

# 5. Telefone (regra conservadora). Separadores permitidos: espaço, ponto, hífen.
_SEP = r"[ .\-]*"
_PHONE_RE = re.compile(
    r"(?<![\w@.])"
    r"(?:(?P<pais>\+?55)" + _SEP + r")?"
    r"(?:(?P<paren>\(\s*(?P<ddd1>\d{2})\s*\))|(?P<ddd2>\d{2}))"
    + _SEP +
    r"(?P<num>\d{4,5})"
    + _SEP +
    r"(?P<fim>\d{4})"
    r"(?![\w@.])"
)

# 6. Menções de usuário (permite ponto interno, não consome pontuação final)
_MENTION_RE = re.compile(
    r"(?<![\w@.])@(?P<user>[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)(?![\w@])"
)

# DDDs brasileiros oficialmente atribuídos.
_DDD_VALIDOS = frozenset(
    [11, 12, 13, 14, 15, 16, 17, 18, 19,
     21, 22, 24, 27, 28,
     31, 32, 33, 34, 35, 37, 38,
     41, 42, 43, 44, 45, 46, 47, 48, 49,
     51, 53, 54, 55,
     61, 62, 63, 64, 65, 66, 67, 68, 69,
     71, 73, 74, 75, 77, 79,
     81, 82, 83, 84, 85, 86, 87, 88, 89,
     91, 92, 93, 94, 95, 96, 97, 98, 99]
)


def _cpf_valido(digitos: str) -> bool:
    """Valida CPF pelos dígitos verificadores (módulo 11)."""
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False

    def dv(parcial: str) -> str:
        peso = len(parcial) + 1
        soma = sum(int(d) * (peso - i) for i, d in enumerate(parcial))
        resto = (soma * 10) % 11
        return "0" if resto == 10 else str(resto)

    return dv(digitos[:9]) == digitos[9] and dv(digitos[:10]) == digitos[10]


def _telefone_aceito(m: re.Match) -> bool:
    """Aplica a regra conservadora de telefone sobre um match do regex."""
    ddd = int(m.group("ddd1") or m.group("ddd2"))
    if ddd not in _DDD_VALIDOS:
        return False

    numero = m.group("num") + m.group("fim")
    tem_pais = m.group("pais") is not None
    tem_parenteses = m.group("paren") is not None
    tem_separador = bool(re.search(r"[ .\-]", m.group(0)))

    if len(numero) == 9:
        # Celular: nove dígitos começando por 9.
        return numero[0] == "9"
    if len(numero) == 8:
        # Fixo: só com evidência estrutural (país, parênteses ou separadores).
        return tem_pais or tem_parenteses or tem_separador
    return False


def anonymize_text(text: str | None, removed: list[str] | None = None) -> str | None:
    """Aplica as substituições de anonimização na ordem especificada.

    ``removed`` (opcional) recebe os trechos efetivamente substituídos, para
    auditoria: emojis/hashtags que viviam dentro de uma URL desaparecem junto
    com ela, e isso precisa ser distinguido de remoção indevida.
    """
    if text is None:
        return None

    out = text

    def _aplica(pattern: re.Pattern, repl, s: str) -> str:
        def _r(m: re.Match) -> str:
            novo = repl(m)
            if novo != m.group(0) and removed is not None:
                removed.append(m.group(0))
            return novo

        return pattern.sub(_r, s)

    # 1. Canonicaliza marcadores legados (antes de tudo, para não competir com URL/email).
    for legacy, canonical in _LEGACY_MARKERS.items():
        out = out.replace(legacy, canonical)

    # 2. URLs
    out = _aplica(_URL_RE, lambda m: "<URL>", out)

    # 3. E-mails
    out = _aplica(_EMAIL_RE, lambda m: "<EMAIL>", out)

    # 4. CPF (antes de telefone)
    out = _aplica(
        _CPF_RE,
        lambda m: "<ID>" if _cpf_valido(re.sub(r"\D", "", m.group(1))) else m.group(1),
        out,
    )

    # 5. Telefones validados
    out = _aplica(
        _PHONE_RE,
        lambda m: "<PHONE>" if _telefone_aceito(m) else m.group(0),
        out,
    )

    # 6. Menções
    out = _aplica(_MENTION_RE, lambda m: "<USER>", out)

    return out


def normalize_document(text: str | None, removed: list[str] | None = None) -> str | None:
    """Função única de pré-processamento: normalização + anonimização.

    ``removed`` (opcional) acumula os trechos substituídos na anonimização.
    """
    return anonymize_text(normalize_text(text), removed)
