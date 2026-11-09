import json

from connectors import CONNECTORS
from connectors.instagram_connector import InstagramConnector
from connectors.tiktok_connector import TikTokConnector
from connectors.twitter_connector import TwitterConnector


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_instagram_current_layout_yields_media_and_comments(tmp_path):
    media_dir = tmp_path / "users" / "42" / "media" / "9001"
    _write(media_dir / "media.json", {
        "pk": "9001",
        "code": "ABC123",
        "product_type": "clips",
        "caption_text": "Legenda em português",
        "taken_at": "2026-09-30T12:00:00+00:00",
        "collected_at": "2026-10-01T12:00:00+00:00",
        "user": {"pk": "42", "username": "perfil"},
        "like_count": 10,
        "comment_count": 1,
    })
    _write(media_dir / "comments.json", [{
        "pk": "c1",
        "text": "Comentário",
        "created_at_utc": "2026-09-30T13:00:00+00:00",
        "collected_at": "2026-10-01T12:00:00+00:00",
        "user": {"pk": "7", "username": "autora"},
        "like_count": 2,
        "replied_to_comment_id": None,
    }])

    connector = InstagramConnector(data_path=tmp_path)
    post = next(connector.iter_posts())
    comment = next(connector.iter_comments())

    assert post["external_id"] == "9001"
    assert post["content_type"] == "reel"
    assert post["normalized"]["url"] == "https://www.instagram.com/reel/ABC123/"
    assert post["collected_at"] == "2026-10-01T12:00:00+00:00"
    assert comment["external_id"] == "c1"
    assert comment["normalized"]["post_id"] == "9001"


def test_tiktok_reads_profile_layout_and_ignores_profile_metadata(tmp_path):
    profile = tmp_path / "profiles" / "perfil"
    _write(profile / "_profile.json", {"username": "perfil"})
    _write(profile / "123.json", {
        "aweme_id": "123",
        "scraped_at": "2026-10-01T12:00:00Z",
        "caption": "Vídeo",
        "comments": [{
            "comment_id": "c1", "comment": "Texto", "username": "u",
            "create_time": "2026-10-01T11:00:00Z", "replies": [],
        }],
    })

    connector = TikTokConnector(data_path=tmp_path)

    assert [p["external_id"] for p in connector.iter_posts()] == ["123"]
    assert [c["external_id"] for c in connector.iter_comments()] == ["c1"]


def test_twitter_uses_envelope_group_and_collection_time(tmp_path):
    _write(tmp_path / "posts" / "batch.json", {
        "group": "Perfil Exemplo",
        "collected_at": "2026-10-01T12:00:00",
        "tweets": [{"tweet_id": "t1", "content": "Texto", "username": "u"}],
    })

    post = next(TwitterConnector(data_path=tmp_path).iter_posts())

    assert post["normalized"]["group_name"] == "Perfil Exemplo"
    assert post["collected_at"] == "2026-10-01T12:00:00"


def test_instagram_is_registered():
    assert CONNECTORS["instagram"] is InstagramConnector
