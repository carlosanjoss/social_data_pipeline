from services.language import PT_BR, detect_language, is_pt_br


def test_detects_portuguese_and_rejects_english():
    assert detect_language("Este é um texto escrito em português do Brasil.") == "pt"
    assert is_pt_br("A pesquisa analisa comentários publicados nas redes sociais.")
    assert not is_pt_br("This text is written entirely in English.")


def test_rejects_empty_or_undetectable_content():
    assert detect_language(None, "", "   ") is None
    assert not is_pt_br("😀 🎯")


def test_canonical_database_code_is_pt_br():
    assert PT_BR == "pt-BR"
