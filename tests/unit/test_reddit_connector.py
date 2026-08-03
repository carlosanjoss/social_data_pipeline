import json

from connectors.reddit_connector import RedditConnector


def test_json_reddit_ids_and_post_relationship_are_canonicalized(tmp_path):
    posts = [
        {
            "id": "hash-local",
            "reddit_post_id": "t3_abc123",
            "title": "Um título em português",
            "published_at": "2026-03-02T00:00:00+00:00",
        }
    ]
    comments = [
        {
            "id": "hash-comment",
            "comment_id_reddit": "comment123",
            "post_id": "hash-local",
            "body_clean": "Um comentário em português.",
            "collected_at": "2026-03-02T01:00:00+00:00",
        }
    ]
    (tmp_path / "posts.json").write_text(json.dumps(posts), encoding="utf-8")
    (tmp_path / "comments.json").write_text(json.dumps(comments), encoding="utf-8")

    connector = RedditConnector(data_path=tmp_path, pipeline_enabled=False)

    post = next(connector.iter_posts())
    comment = next(connector.iter_comments())

    assert post["external_id"] == "abc123"
    assert post["source_system"] == "reddit_scrapper"
    assert comment["external_id"] == "t1_comment123"
    assert comment["normalized"]["post_id"] == "abc123"
