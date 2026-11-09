from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from config import get_logger, settings
from .base import BaseConnector

logger = get_logger(__name__)


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _user(raw: dict) -> tuple[str | None, str | None]:
    user = raw.get("user") or {}
    if not isinstance(user, dict):
        return None, None
    username = user.get("username")
    user_id = user.get("pk") or user.get("id")
    return username, str(user_id) if user_id is not None else None


class InstagramConnector(BaseConnector):
    """Lê o layout ``data/users/<user_id>/media/<media_id>`` do scraper."""

    def __init__(self, data_path: Path | None = None):
        self.data_path = Path(data_path or settings.instagram_data_path)

    def _media_dirs(self) -> Iterator[Path]:
        users_root = self.data_path / "users"
        if not users_root.exists():
            logger.warning("instagram_users_dir_not_found", path=str(users_root))
            return
        for media_file in sorted(users_root.glob("*/media/*/media.json")):
            yield media_file.parent

    @staticmethod
    def _load(path: Path, default):
        if not path.exists():
            return default
        try:
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            logger.error("instagram_json_parse_error", path=str(path), error=str(exc))
            return default

    def iter_posts(self) -> Iterator[dict]:
        for media_dir in self._media_dirs():
            raw = self._load(media_dir / "media.json", {})
            if not isinstance(raw, dict) or not raw:
                continue
            media_id = str(raw.get("pk") or raw.get("id") or media_dir.name)
            username, author_id = _user(raw)
            code = raw.get("code")
            product_type = str(raw.get("product_type") or "").lower()
            is_reel = product_type in {"clips", "reel", "reels"}
            url = (
                f"https://www.instagram.com/{'reel' if is_reel else 'p'}/{code}/"
                if code else None
            )
            collected_at = raw.get("collected_at")

            yield {
                "platform": "instagram",
                "external_id": media_id,
                "content_type": "reel" if is_reel else "post",
                "source_system": "instagram_scrapper",
                "collected_at": collected_at,
                "raw": raw,
                "normalized": {
                    "title": raw.get("title"),
                    "text": raw.get("caption_text") or raw.get("description"),
                    "url": url,
                    "author": username,
                    "author_id": author_id,
                    "published_at": raw.get("taken_at"),
                    "like_count": _to_int(raw.get("like_count")),
                    "comment_count": _to_int(raw.get("comment_count")),
                    "view_count": _to_int(raw.get("view_count") or raw.get("play_count")),
                },
            }

    def iter_comments(self) -> Iterator[dict]:
        for media_dir in self._media_dirs():
            media = self._load(media_dir / "media.json", {})
            media_id = str(
                media.get("pk") or media.get("id") or media_dir.name
            ) if isinstance(media, dict) else media_dir.name
            comments = self._load(media_dir / "comments.json", [])
            if not isinstance(comments, list):
                continue

            for raw in comments:
                if not isinstance(raw, dict):
                    continue
                comment_id = raw.get("pk") or raw.get("id")
                if comment_id is None:
                    continue
                parent_id = raw.get("replied_to_comment_id")
                username, author_id = _user(raw)
                is_reply = parent_id is not None

                yield {
                    "platform": "instagram",
                    "external_id": str(comment_id),
                    "content_type": "reply" if is_reply else "comment",
                    "source_system": "instagram_scrapper",
                    "collected_at": raw.get("collected_at") or (
                        media.get("collected_at") if isinstance(media, dict) else None
                    ),
                    "raw": raw,
                    "normalized": {
                        "text": raw.get("text"),
                        "author": username,
                        "author_id": author_id,
                        "post_id": media_id,
                        "parent_id": str(parent_id) if parent_id is not None else None,
                        "is_reply": is_reply,
                        "depth": 1 if is_reply else 0,
                        "like_count": _to_int(raw.get("like_count")),
                        "published_at": raw.get("created_at_utc") or raw.get("created_at"),
                    },
                }
