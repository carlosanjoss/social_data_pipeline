import json
from pathlib import Path
from typing import Iterator

from config import settings, get_logger
from .base import BaseConnector

logger = get_logger(__name__)


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").replace(".", "").strip())
    except (ValueError, TypeError):
        return None


class YouTubeConnector(BaseConnector):
    """
    Walks the directory tree:
        youtube_data_path/channels/<channel_id>/
            channel.json
            videos/<video_id>/
                video.json
                comments.json
    """

    def __init__(self, data_path: Path | None = None):
        self.data_path = Path(data_path or settings.youtube_data_path)

    def _channel_dirs(self) -> list[Path]:
        channels_root = self.data_path / "channels"
        if not channels_root.exists():
            logger.warning("youtube_channels_dir_not_found", path=str(channels_root))
            return []
        return [d for d in channels_root.iterdir() if d.is_dir()]

    def _load_json(self, path: Path) -> dict | list | None:
        if not path.exists():
            return None
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("youtube_json_parse_error", path=str(path), error=str(exc))
            return None

    def iter_posts(self) -> Iterator[dict]:
        for channel_dir in self._channel_dirs():
            channel_id = channel_dir.name
            channel_data = self._load_json(channel_dir / "channel.json") or {}
            channel_title = channel_data.get("channel_title") or channel_data.get("title")

            videos_root = channel_dir / "videos"
            if not videos_root.exists():
                continue

            for video_dir in videos_root.iterdir():
                if not video_dir.is_dir():
                    continue

                video_id = video_dir.name
                raw = self._load_json(video_dir / "video.json")
                if not raw:
                    continue

                yield {
                    "platform":     "youtube",
                    "external_id":  video_id,
                    "content_type": "video",
                    "source_system": "youtube_scraper",
                    "collected_at":  raw.get("collected_at"),
                    "raw":          raw,
                    "normalized": {
                        # scraper uses video_title / video_description
                        "title":         raw.get("video_title") or raw.get("title"),
                        "description":   raw.get("video_description") or raw.get("description"),
                        # description becomes text so NLP can operate on it
                        "text":          raw.get("video_description") or raw.get("description"),
                        # channel is the author for a video
                        "author":        channel_title or raw.get("channel_title"),
                        "channel_id":    channel_id,
                        "channel_title": channel_title or raw.get("channel_title"),
                        "view_count":    _to_int(raw.get("view_count") or raw.get("viewCount")),
                        "like_count":    _to_int(raw.get("like_count") or raw.get("likeCount")),
                        "comment_count": _to_int(raw.get("comment_count") or raw.get("commentCount")),
                        "tags":          raw.get("tags") or [],
                        "language":      raw.get("defaultLanguage") or raw.get("language"),
                        "published_at":  raw.get("published_at") or raw.get("publishedAt"),
                        "duration":      raw.get("duration"),
                        "thumbnail_url": raw.get("thumbnail_url") or raw.get("thumbnailUrl"),
                    },
                }

    def iter_comments(self) -> Iterator[dict]:
        for channel_dir in self._channel_dirs():
            videos_root = channel_dir / "videos"
            if not videos_root.exists():
                continue

            for video_dir in videos_root.iterdir():
                if not video_dir.is_dir():
                    continue

                video_id = video_dir.name
                video_data = self._load_json(video_dir / "video.json") or {}
                comments_data = self._load_json(video_dir / "comments.json")
                if not comments_data:
                    continue

                items = comments_data if isinstance(comments_data, list) else comments_data.get("comments", [])
                for raw in items:
                    comment_id = str(raw.get("comment_id") or raw.get("id") or "")
                    if not comment_id:
                        continue

                    is_reply = bool(raw.get("is_reply"))
                    parent_id = raw.get("parent_id")  # set for replies, None for top-level
                    content_type = "reply" if is_reply else "comment"

                    yield {
                        "platform":     "youtube",
                        "external_id":  comment_id,
                        "content_type": content_type,
                        "source_system": "youtube_scraper",
                        "collected_at":  raw.get("collected_at") or video_data.get("collected_at"),
                        "raw":          raw,
                        "normalized": {
                            "text":         raw.get("text") or raw.get("textDisplay"),
                            "author":       raw.get("author") or raw.get("authorDisplayName"),
                            "author_id":    raw.get("author_id") or raw.get("authorChannelId"),
                            "like_count":   _to_int(raw.get("like_count") or raw.get("likeCount")),
                            "reply_count":  _to_int(raw.get("reply_count") or raw.get("totalReplyCount")),
                            "post_id":      video_id,
                            "parent_id":    parent_id,
                            "is_reply":     is_reply,
                            "published_at": raw.get("published_at") or raw.get("publishedAt"),
                        },
                    }
