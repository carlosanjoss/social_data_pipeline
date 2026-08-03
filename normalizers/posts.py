from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from psycopg.types.json import Jsonb


def normalize_post(doc: dict) -> tuple[dict, dict]:
    """
    Flatten a MongoDB raw_posts document into (base_row, ext_row).

    base_row → INSERT INTO posts (...)
    ext_row  → INSERT INTO {platform}_posts/tweets/videos (...)
    """
    n = doc.get("normalized") or {}
    platform = doc["platform"]
    quality = n.get("quality") or {}

    base: dict[str, Any] = {
        "platform":      platform,
        "external_id":   doc["external_id"],
        "content_type":  doc.get("content_type", "post"),
        "title":         _str(n.get("title")),
        "text":          _str(n.get("text")),
        "url":           _str(n.get("url")),
        "author":        _str(n.get("author")),
        "author_id":     _str(n.get("author_id")),
        "language":      _str(n.get("language")),
        "language_verified": bool(n.get("language_verified")),
        "published_at":  _dt(n.get("published_at")),
        "like_count":    _int(n.get("like_count")),
        "share_count":   _int(n.get("share_count")),
        "comment_count": _int(n.get("comment_count")),
        "retweet_count": _int(n.get("retweet_count")),
        "reply_count":   _int(n.get("reply_count")),
        "quote_count":   _int(n.get("quote_count")),
        "view_count":    _int(n.get("view_count")),
        "quality_score": quality.get("score"),
        "quality_flags": quality.get("flags") or [],
        "is_usable":     quality.get("is_usable"),
        "source_system": _str(doc.get("source_system")),
        "mongo_id":      str(doc.get("_id", "")),
        "collected_at":  _dt(doc.get("collected_at")),
    }

    ext = _ext_row(platform, n)
    return base, ext


def _ext_row(platform: str, n: dict) -> dict:
    if platform == "reddit":
        return {
            "score":        _int(n.get("score")),
            "num_comments": _int(n.get("num_comments")),
            "subreddit":    _str(n.get("subreddit")),
        }
    if platform == "twitter":
        return {
            "conversation_id": _str(n.get("conversation_id")),
            "group_name":      _str(n.get("group_name")),
            "hashtags":        n.get("hashtags") or [],
        }
    if platform == "youtube":
        return {
            "channel_id":    _str(n.get("channel_id")),
            "channel_title": _str(n.get("channel_title")),
            "description":   _str(n.get("description")),
            "duration":      _str(n.get("duration")),
            "thumbnail_url": _str(n.get("thumbnail_url")),
            "tags":          n.get("tags") or [],
        }
    if platform == "facebook":
        return {
            "page_id":    _str(n.get("page_id")),
            "page_slug":  _str(n.get("page_slug")),
            "reactions":  Jsonb(n.get("reactions") or {}),
            "media_types": n.get("media_types") or [],
        }
    if platform == "tiktok":
        return {
            "video_url": _str(n.get("video_url")),
        }
    if platform in {"whatsapp", "telegram"}:
        return {
            "group_id":             _str(n.get("group_id")),
            "member_id":            _str(n.get("member_id")),
            "score_sentiment":      _float(n.get("score_sentiment")),
            "score_misinformation": _float(n.get("score_misinformation")),
            "matched_terms":        _str_list(n.get("matched_terms")),
            "collection_periods":   _str_list(n.get("collection_periods")),
        }
    return {}


def _str(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _str_list(v) -> list[str]:
    if not isinstance(v, (list, tuple, set)):
        return []
    return [text for item in v if (text := _str(item))]


def _dt(v) -> datetime | None:
    if not v:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

    s = str(v).strip().replace("Z", "+00:00")
    try:
        # APIs como TikTok e Reddit também podem fornecer epoch como string.
        if s.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(s), tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
