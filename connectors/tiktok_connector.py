from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from config import settings, get_logger
from .base import BaseConnector

logger = get_logger(__name__)


def _published_at_from_aweme_id(aweme_id: str) -> str | None:
    """TikTok codifica o timestamp Unix nos 32 bits altos do ID do vídeo."""
    try:
        timestamp = int(aweme_id) >> 32
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


class TikTokConnector(BaseConnector):
    """
    Walks the TikTok scraper output directory:
        tiktok_data_path/<aweme_id>.json

    Each file contains one video with its top-level comments and nested replies.
    iter_posts()    → yields each video as a post document
    iter_comments() → yields all comments and replies (flattened, depth-tagged)
    """

    def __init__(self, data_path: Path | None = None):
        self.data_path = Path(data_path or settings.tiktok_data_path)

    def _video_files(self) -> list[Path]:
        if not self.data_path.exists():
            logger.warning("tiktok_data_dir_not_found", path=str(self.data_path))
            return []
        return sorted(self.data_path.glob("*.json"))

    def _load_json(self, path: Path) -> dict | None:
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("tiktok_json_parse_error", path=str(path), error=str(exc))
            return None

    def iter_posts(self) -> Iterator[dict]:
        for path in self._video_files():
            raw = self._load_json(path)
            if not raw:
                continue

            aweme_id = str(raw.get("aweme_id") or path.stem)
            caption = raw.get("caption") or ""

            yield {
                "platform":     "tiktok",
                "external_id":  aweme_id,
                "content_type": "video",
                "source_system": "tiktok_scrapper",
                "raw":          raw,
                "normalized": {
                    "title":         caption,
                    "text":          caption,
                    "url":           raw.get("video_url"),
                    "video_url":     raw.get("video_url"),
                    "comment_count": raw.get("total_comments_with_replies"),
                    "published_at":  _published_at_from_aweme_id(aweme_id),
                    "collected_at":  raw.get("scraped_at"),
                },
            }

    def iter_comments(self) -> Iterator[dict]:
        for path in self._video_files():
            raw = self._load_json(path)
            if not raw:
                continue

            aweme_id = str(raw.get("aweme_id") or path.stem)
            collected_at = raw.get("scraped_at")

            yield from self._flatten(
                raw.get("comments") or [],
                aweme_id=aweme_id,
                collected_at=collected_at,
                parent_id=None,
                depth=0,
            )

    def _flatten(
        self,
        comments: list[dict],
        aweme_id: str,
        collected_at: str | None,
        parent_id: str | None,
        depth: int,
    ) -> Iterator[dict]:
        for c in comments:
            comment_id = str(c.get("comment_id") or "")
            if not comment_id:
                continue

            is_reply = depth > 0
            content_type = "reply" if is_reply else "comment"

            yield {
                "platform":     "tiktok",
                "external_id":  comment_id,
                "content_type": content_type,
                "source_system": "tiktok_scrapper",
                "raw":          c,
                "normalized": {
                    "text":         c.get("comment"),
                    "author":       c.get("username"),
                    "author_id":    c.get("username"),
                    "post_id":      aweme_id,
                    "parent_id":    parent_id,
                    "is_reply":     is_reply,
                    "depth":        depth,
                    "like_count":   c.get("like_count", 0),
                    "reply_count":  c.get("total_reply", 0),
                    "published_at": c.get("create_time"),
                    "collected_at": collected_at,
                    "video_id":     aweme_id,
                },
            }

            replies = c.get("replies") or []
            if replies:
                yield from self._flatten(
                    replies,
                    aweme_id=aweme_id,
                    collected_at=collected_at,
                    parent_id=comment_id,
                    depth=depth + 1,
                )
