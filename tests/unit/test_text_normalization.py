"""Regras de normalização/anonimização do Radar Ódio v0.1."""
from services.text_normalization import (
    normalize_text,
    anonymize_text,
    normalize_document,
)


# ── Normalização textual ──────────────────────────────────────────────────────

def test_collapses_crlf_cr_and_tabs_and_spaces():
    assert normalize_text("a\r\nb\rc\td") == "a\nb\nc d"
    assert normalize_text("muitos    espaços") == "muitos espaços"
    # tabulação vira espaço e participa do colapso
    assert normalize_text("a\t\tb") == "a b"


def test_preserves_newlines_case_punctuation_emoji_hashtag():
    src = "OLÁ!!! 😀 #Bolsonaro17  não   sei\nsegunda linha"
    out = normalize_text(src)
    assert out == "OLÁ!!! 😀 #Bolsonaro17 não sei\nsegunda linha"


def test_applies_unicode_nfc():
    decomposed = "cafe\u0301"          # e + acento combinante
    assert normalize_text(decomposed) == "café"


def test_preserves_replacement_char():
    assert normalize_text("texto � aqui") == "texto � aqui"


def test_no_lowercase_stemming_or_stopword_removal():
    src = "Ele NÃO foi à casa, viu?!"
    assert normalize_text(src) == src


# ── Anonimização ─────────────────────────────────────────────────────────────

def test_legacy_markers_are_canonicalized():
    assert anonymize_text("[URL] e [EMAIL] e [PHONE] e [USER]") == \
        "<URL> e <EMAIL> e <PHONE> e <USER>"


def test_urls_replaced():
    assert anonymize_text("veja https://exemplo.com/p/a?x=1 ok") == "veja <URL> ok"
    assert anonymize_text("acesse www.teste.com.br agora") == "acesse <URL> agora"


def test_emails_replaced():
    assert anonymize_text("manda para fulano@exemplo.com.br hoje") == \
        "manda para <EMAIL> hoje"


def test_valid_cpf_replaced_invalid_kept():
    # 529.982.247-25 é CPF formalmente válido
    assert anonymize_text("CPF 529.982.247-25 consta") == "CPF <ID> consta"
    assert anonymize_text("numero 111.111.111-11 invalido") == "numero 111.111.111-11 invalido"


def test_mobile_phone_replaced():
    assert anonymize_text("liga (11) 91234-5678 agora") == "liga <PHONE> agora"
    assert anonymize_text("tel 11912345678 hoje") == "tel <PHONE> hoje"


def test_phone_without_valid_ddd_kept():
    # 23 não é DDD válido
    assert anonymize_text("codigo 23912345678 aqui") == "codigo 23912345678 aqui"


def test_landline_requires_structural_evidence():
    assert anonymize_text("fixo (11) 2345-6789 hoje") == "fixo <PHONE> hoje"
    # 8 dígitos sem separador/parênteses/país não é telefone
    assert anonymize_text("serie 1123456789 aqui") == "serie 1123456789 aqui"


def test_country_code_is_structural_evidence():
    assert anonymize_text("chama +55 11 2345 6789 agora") == "chama <PHONE> agora"


def test_mentions_replaced_but_email_survives_as_email():
    assert anonymize_text("oi @joao_silva tudo bem") == "oi <USER> tudo bem"
    assert anonymize_text("email a@b.com aqui") == "email <EMAIL> aqui"


def test_numbers_years_and_ranges_not_converted():
    assert anonymize_text("em 2026 e paginas 100-200 e 3.14") == \
        "em 2026 e paginas 100-200 e 3.14"


def test_mention_followed_by_sentence_period_is_replaced():
    assert anonymize_text("preside a @fugnacional. por isso") == \
        "preside a <USER>. por isso"


def test_mention_with_internal_dot_is_replaced():
    assert anonymize_text("oi @joao.silva!") == "oi <USER>!"


def test_does_not_touch_numbers_inside_usernames():
    # A menção inteira vira <USER>; o telefone NÃO deve "vazar" de dentro dela.
    out = anonymize_text("@user11912345678")
    assert out == "<USER>"
    assert "<PHONE>" not in out


# ── Função única ─────────────────────────────────────────────────────────────

def test_normalize_document_applies_both_in_order():
    src = "OLÁ\r\n\t veja  https://x.com/a   e fale com @maria 😀"
    out = normalize_document(src)
    assert out == "OLÁ\n veja <URL> e fale com <USER> 😀"


def test_removed_reports_only_replaced_spans():
    removed: list[str] = []
    out = normalize_document("veja https://x.com/a#tag e @maria 😀", removed)
    assert out == "veja <URL> e <USER> 😀"
    assert removed == ["https://x.com/a#tag", "@maria"]


def test_emoji_outside_anonymized_span_is_preserved():
    removed: list[str] = []
    out = normalize_document("bom dia 😀 https://x.com/a 😀", removed)
    assert out.count("😀") == 2
    assert "😀" not in "".join(removed)
