"""Detecção reforçada de idioma e recuperação de posts-âncora."""
from services.language import detect_language_robust
from etl.load_postgres import _anchor_row


def test_short_uppercase_portuguese_title_is_recovered():
    # langdetect sozinho devolve 'de' para este título.
    assert detect_language_robust("MAIS UMA DECISÃO COVARDE DE MORAES!") == "pt"
    assert detect_language_robust("NÃO VAMOS JOGAR A TOALHA!") == "pt"
    assert detect_language_robust("PARABÉNS VOVÔ BOLSONARO!") == "pt"


def test_no_text_falls_back_to_undetermined():
    assert detect_language_robust(None, "", "   ") == "und"


def test_real_spanish_is_not_labelled_portuguese():
    assert detect_language_robust(
        "¿El feminismo moderno se trata más de odio hacia los hombres?"
    ) != "pt"


def test_real_english_is_not_labelled_portuguese():
    assert detect_language_robust(
        "This is a long enough sentence written entirely in English for detection."
    ) != "pt"


def test_anchor_row_marks_post_and_sets_real_language():
    doc = {
        "platform": "youtube",
        "external_id": "abc123",
        "content_type": "video",
        "normalized": {"title": "DECISÃO COVARDE DE MORAES!", "text": None},
    }
    base, _ = _anchor_row(doc)
    assert base["is_anchor"] is True
    assert base["language"] == "pt"
    assert base["external_id"] == "abc123"
