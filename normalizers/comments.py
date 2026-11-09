from __future__ import annotations

from typing import Any

from .posts import _str, _int, _dt, _clean


def normalize_comment(doc: dict) -> tuple[dict, dict]:
    """
    Flatten a MongoDB raw_comments document into (base_row, ext_row).

    base_row → INSERT INTO comments (...)
    ext_row  → INSERT INTO {platform}_comments (...)
    """
    n = doc.get("normalized") or {}
    platform = doc["platform"]
    quality = n.get("quality") or {}

    base: dict[str, Any] = {
        "platform":           platform,
        "external_id":        doc["external_id"],
        "content_type":       doc.get("content_type", "comment"),
        "text":               _str(n.get("text")),
        "author":             _str(n.get("author")),
        "author_id":          _str(n.get("author_id")),
        "language":           _str(n.get("language")),
        "language_verified":  bool(n.get("language_verified")),
        "post_external_id":   _str(n.get("post_id")),
        "parent_external_id": _str(n.get("parent_id")),
        "is_reply":           bool(n.get("is_reply") or n.get("is_reply_to_comment")),
        "depth":              _int(n.get("depth")),
        "published_at":       _dt(n.get("published_at")),
        "like_count":         _int(n.get("like_count")),
        "reply_count":        _int(n.get("reply_count")),
        "quality_score":      quality.get("score"),
        "quality_flags":      _clean(quality.get("flags") or []),
        "is_usable":          quality.get("is_usable"),
        "source_system":      _str(doc.get("source_system")),
        "mongo_id":           str(doc.get("_id", "")),
        "collected_at":       _dt(doc.get("collected_at")),
    }

    ext = _comment_ext_row(platform, n)
    return base, ext


def _comment_ext_row(platform: str, n: dict) -> dict:
    if platform == "reddit":
        return {
            "score":               _int(n.get("score")),
            "subreddit":           _str(n.get("subreddit")),
            "is_reply_to_comment": bool(n.get("is_reply_to_comment")),
        }
    if platform == "youtube":
        return {
            "video_id": _str(n.get("post_id")),
        }
    if platform == "facebook":
        return {
            "page_slug": _str(n.get("page_slug")),
        }
    if platform == "tiktok":
        return {
            "video_id": _str(n.get("video_id")),
        }
    return {}
