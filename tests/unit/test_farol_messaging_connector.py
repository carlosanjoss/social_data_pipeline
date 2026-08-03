import json

from connectors.farol_messaging_connector import TelegramConnector, WhatsAppConnector
from normalizers.posts import normalize_post


def test_whatsapp_snapshots_are_merged_and_deduplicated(tmp_path):
    first = [{
        "id": 10,
        "date_message": "2019-05-01T12:00:00",
        "id_member_anonymous": "member-1",
        "id_group_anonymous": "group-1",
        "text_content_anonymous": "Mensagem em português.",
        "score_sentiment": None,
    }]
    second = [{
        "id": 10,
        "date_message": "2019-05-01T12:00:00",
        "id_member_anonymous": "member-1",
        "id_group_anonymous": "group-1",
        "text_content_clean": "Mensagem limpa em português.",
        "score_sentiment": 0.75,
    }]
    (tmp_path / "fd_whatsapp__tb_messages__001.json").write_text(
        json.dumps(first), encoding="utf-8"
    )
    (tmp_path / "fd_whatsapp__tb_messages__002.json").write_text(
        json.dumps(second), encoding="utf-8"
    )

    docs = list(WhatsAppConnector(data_path=tmp_path).iter_posts())

    assert len(docs) == 1
    assert docs[0]["external_id"] == "10"
    assert docs[0]["content_type"] == "message"
    assert docs[0]["normalized"]["text"] == "Mensagem limpa em português."
    assert docs[0]["normalized"]["score_sentiment"] == 0.75
    assert list(WhatsAppConnector(data_path=tmp_path).iter_comments()) == []


def test_telegram_fields_reach_post_extension(tmp_path):
    rows = [{
        "id": 20,
        "date_message": "2023-01-02T03:04:05",
        "id_member_anonymous": "member-2",
        "id_group_anonymous": "group-2",
        "text_content_anonymous": "Outra mensagem em português.",
        "score_sentiment": -0.25,
        "score_misinformation": 0.8,
        "_farol_collection": {
            "period": "Pós-eleição/8jan",
            "matched_terms": ["incel", "MGTOW"],
        },
    }]
    (tmp_path / "fd_telegram__tb_messages__001.json").write_text(
        json.dumps(rows), encoding="utf-8"
    )

    doc = next(TelegramConnector(data_path=tmp_path).iter_posts())
    base, extension = normalize_post(doc)

    assert base["platform"] == "telegram"
    assert base["published_at"].year == 2023
    assert extension == {
        "group_id": "group-2",
        "member_id": "member-2",
        "score_sentiment": -0.25,
        "score_misinformation": 0.8,
        "matched_terms": ["incel", "MGTOW"],
        "collection_periods": ["Pós-eleição/8jan"],
    }
