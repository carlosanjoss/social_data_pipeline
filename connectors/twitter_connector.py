import json
from pathlib import Path
from typing import Iterator

from config import settings, get_logger
from .base import BaseConnector

logger = get_logger(__name__)


class TwitterConnector(BaseConnector):
    """
    Reads tweet-harvest output: JSON files whose root is an envelope with a
    `tweets` array. Each file lives at:
        twitter_data_path/posts/<query>_<timestamp>.json
    """

    def __init__(self, data_path: Path | None = None):
        self.data_path = Path(data_path or settings.twitter_data_path)

    def _iter_raw_tweets(self) -> Iterator[dict]:
        posts_dir = self.data_path / "posts"
        if not posts_dir.exists():
            logger.warning("twitter_posts_dir_not_found", path=str(posts_dir))
            return

        for json_file in sorted(posts_dir.glob("*.json")):
            try:
                with json_file.open(encoding="utf-8") as f:
                    envelope = json.load(f)
            except Exception as exc:
                logger.error("twitter_json_parse_error", file=json_file.name, error=str(exc))
                continue

            tweets = envelope if isinstance(envelope, list) else envelope.get("tweets", [])
            collected_at = envelope.get("collected_at") if isinstance(envelope, dict) else None
            envelope_group = envelope.get("group") if isinstance(envelope, dict) else None
            for tweet in tweets:
                yield tweet, json_file.name, collected_at, envelope_group

    def iter_posts(self) -> Iterator[dict]:
        for raw, source_file, collected_at, envelope_group in self._iter_raw_tweets():
            tweet_id = str(raw.get("tweet_id") or raw.get("id") or raw.get("id_str") or "")
            if not tweet_id:
                logger.warning("twitter_no_id", source=source_file)
                continue

            # tweet-harvest does not export in_reply_to_status_id; use group_name
            # "post_especifico" = replies scraped from a specific post thread
            group = raw.get("group_name") or envelope_group or ""
            is_reply = group == "post_especifico"
            content_type = "reply" if is_reply else "tweet"

            yield {
                "platform":      "twitter",
                "external_id":   tweet_id,
                "content_type":  content_type,
                "source_system": "twitter_scraper_project",
                "source_file":   source_file,
                "collected_at":  collected_at,
                "raw":           raw,
                "normalized": {
                    # tweet-harvest uses 'content', not 'full_text'/'text'
                    "text":            raw.get("content") or raw.get("full_text") or raw.get("text"),
                    "author":          raw.get("username") or raw.get("user", {}).get("screen_name"),
                    "author_id":       str(raw.get("twitter_user_id") or raw.get("user_id") or raw.get("author_id") or ""),
                    "like_count":      _to_int(raw.get("like_count") or raw.get("likes_count") or raw.get("favorite_count")),
                    "retweet_count":   _to_int(raw.get("retweet_count") or raw.get("retweets_count")),
                    "reply_count":     _to_int(raw.get("reply_count") or raw.get("replies_count")),
                    "quote_count":     _to_int(raw.get("quote_count") or raw.get("quotes_count")),
                    "hashtags":        raw.get("hashtags") or [],
                    # conversation_id groups all tweets in the same thread
                    "conversation_id": str(raw.get("conversation_id") or ""),
                    "group_name":      group,
                    "language":        raw.get("language") or raw.get("lang"),
                    # tweet-harvest uses 'posted_at', not 'created_at'/'date'
                    "published_at":    raw.get("posted_at") or raw.get("created_at") or raw.get("date"),
                },
            }

    def iter_comments(self) -> Iterator[dict]:
        replies_dir = self.data_path / "replies"
        if not replies_dir.exists():
            logger.warning("twitter_replies_dir_not_found", path=str(replies_dir))
            return

        for json_file in sorted(replies_dir.glob("*.json")):
            try:
                with json_file.open(encoding="utf-8") as f:
                    envelope = json.load(f)
            except Exception as exc:
                logger.error("twitter_replies_parse_error", file=json_file.name, error=str(exc))
                continue

            replies = envelope if isinstance(envelope, list) else envelope.get("replies", [])
            parent_tweet_id = envelope.get("parent_tweet_id") if isinstance(envelope, dict) else None
            collected_at = envelope.get("collected_at") if isinstance(envelope, dict) else None

            for raw in replies:
                tweet_id = str(raw.get("tweet_id") or raw.get("id") or "")
                if not tweet_id:
                    continue

                post_id = str(raw.get("parent_tweet_id") or parent_tweet_id or "")

                yield {
                    "platform":     "twitter",
                    "external_id":  tweet_id,
                    "content_type": "reply",
                    "source_system": "twitter_scraper_project",
                    "source_file":  json_file.name,
                    "collected_at": collected_at,
                    "raw":          raw,
                    "normalized": {
                        "text":            raw.get("content") or raw.get("full_text") or raw.get("text"),
                        "author":          raw.get("username") or raw.get("user", {}).get("screen_name"),
                        "author_id":       str(raw.get("twitter_user_id") or raw.get("user_id") or ""),
                        "post_id":         post_id,
                        "like_count":      _to_int(raw.get("like_count") or raw.get("favorite_count")),
                        "reply_count":     _to_int(raw.get("reply_count")),
                        "retweet_count":   _to_int(raw.get("retweet_count")),
                        "quote_count":     _to_int(raw.get("quote_count")),
                        "conversation_id": str(raw.get("parent_conversation_id") or raw.get("conversation_id") or ""),
                        "language":        raw.get("language") or raw.get("lang"),
                        "published_at":    raw.get("posted_at") or raw.get("created_at") or raw.get("date"),
                    },
                }


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
