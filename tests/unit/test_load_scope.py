from etl.load_postgres import _is_target_language


def test_declared_non_portuguese_is_rejected():
    base = {"language": "en"}
    assert not _is_target_language(base, "Este texto seria português.")


def test_portuguese_is_confirmed_from_text():
    assert _is_target_language(
        {"language": "pt"},
        "O banco deve conter somente dados em português.",
    )


def test_false_pt_default_does_not_override_english_text():
    assert not _is_target_language(
        {"language": "pt"},
        "The connector used to mark every record as Portuguese.",
    )


def test_verified_curated_portuguese_can_skip_duplicate_detection():
    assert _is_target_language(
        {"language": "pt-BR", "language_verified": True},
        "ok",
    )
