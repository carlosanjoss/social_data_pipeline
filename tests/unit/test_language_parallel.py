"""Paridade entre a decisão de idioma sequencial e a paralelizada, e limpeza de NUL."""
from services.language import decide_target, decide_target_payload, decide_batch
from normalizers.posts import normalize_post, _clean
from normalizers.comments import normalize_comment


def _payloads():
    return [
        ("pt", True, (None, "ok")),
        ("en", False, ("This is English.",)),
        ("", False, ("Este comentário está em português do Brasil.",)),
        (None, False, ("Camiseta promoção frete grátis",)),
        ("pt-BR", False, ("", "Texto curto em português.")),
        ("es", False, ("Este texto es en español.",)),
    ]


def test_wrappers_match_sequential_decisions():
    payloads = _payloads()
    seq = [decide_target(*p) for p in payloads]
    assert [decide_target_payload(p) for p in payloads] == seq
    assert decide_batch(payloads) == seq


def test_clean_removes_nul_bytes_recursively():
    assert _clean("a\x00b") == "ab"
    assert _clean(["x\x00", {"k": "v\x00v"}]) == ["x", {"k": "vv"}]


def test_normalize_post_strips_nul_from_text():
    doc = {
        "platform": "youtube",
        "external_id": "1",
        "content_type": "video",
        "normalized": {"title": "t\x00itulo", "text": "comentário\x00", "tags": ["a\x00b"]},
    }
    base, ext = normalize_post(doc)
    assert "\x00" not in base["title"]
    assert "\x00" not in base["text"]
    assert ext["tags"] == ["ab"]


def test_normalize_comment_strips_nul_from_text():
    doc = {
        "platform": "youtube",
        "external_id": "2",
        "content_type": "comment",
        "normalized": {"text": "olá\x00mundo", "post_id": "p1"},
    }
    base, _ = normalize_comment(doc)
    assert base["text"] == "olámundo"
    assert "\x00" not in base["text"]
