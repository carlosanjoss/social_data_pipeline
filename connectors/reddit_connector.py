from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import psycopg
from dotenv import dotenv_values
from psycopg.rows import dict_row

from config import settings, get_logger
from .base import BaseConnector

logger = get_logger(__name__)

_SCORE_RE = re.compile(r"(\d+)")


def _parse_score(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    m = _SCORE_RE.search(str(value))
    return int(m.group(1)) if m else None


def _post_external_id(raw: dict) -> str | None:
    value = raw.get("reddit_post_id") or raw.get("id") or raw.get("sha256_id")
    if not value:
        return None
    value = str(value)
    return value[3:] if value.startswith("t3_") else value


def _comment_external_id(value) -> str | None:
    """Usa o fullname t1_ para deduplicar as duas fontes Reddit."""
    if not value:
        return None
    value = str(value)
    return value if value.startswith("t1_") else f"t1_{value}"


def _epoch_iso(value) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


class RedditConnector(BaseConnector):
    """Lê tanto os JSONs do reddit_scrapper quanto o BD do reddit_pipeline."""

    def __init__(
        self,
        data_path: Path | None = None,
        pipeline_enabled: bool | None = None,
    ):
        self.data_path = Path(data_path or settings.reddit_data_path)
        self.pipeline_enabled = (
            settings.reddit_pipeline_enabled
            if pipeline_enabled is None
            else pipeline_enabled
        )
        self._json_post_id_map: dict[str, str] | None = None

    def _load(self, filename: str) -> list:
        path = self.data_path / filename
        if not path.exists():
            logger.warning("reddit_file_not_found", path=str(path))
            return []
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    def _get_json_post_id_map(self) -> dict[str, str]:
        if self._json_post_id_map is None:
            mapping: dict[str, str] = {}
            for raw in self._load("posts.json"):
                external_id = _post_external_id(raw)
                if not external_id:
                    continue
                for key in ("id", "sha256_id", "reddit_post_id"):
                    if raw.get(key):
                        mapping[str(raw[key])] = external_id
            self._json_post_id_map = mapping
        return self._json_post_id_map

    def _pipeline_connection(self) -> psycopg.Connection:
        if settings.reddit_pipeline_uri:
            return psycopg.connect(settings.reddit_pipeline_uri)

        env_path = Path(settings.reddit_pipeline_env_path)
        if not env_path.exists():
            raise FileNotFoundError(
                "Fonte reddit_pipeline habilitada, mas o arquivo de configuração "
                f"não existe: {env_path.resolve()}"
            )

        source = dotenv_values(env_path)
        keys = {
            "host": "DB_HOST",
            "port": "DB_PORT",
            "dbname": "DB_NAME",
            "user": "DB_USER",
            "password": "DB_PASSWORD",
        }
        missing = [env_key for env_key in keys.values() if not source.get(env_key)]
        if missing:
            raise ValueError(
                "Configuração incompleta do reddit_pipeline; faltam: "
                + ", ".join(missing)
            )
        kwargs = {arg: source[env_key] for arg, env_key in keys.items()}
        return psycopg.connect(**kwargs)

    def iter_posts(self) -> Iterator[dict]:
        for raw in self._load("posts.json"):
            external_id = _post_external_id(raw)
            if not external_id:
                logger.warning("reddit_post_no_id", raw=raw)
                continue
            yield {
                "platform": "reddit",
                "external_id": external_id,
                "content_type": "post",
                "source_system": "reddit_scrapper",
                "collected_at": raw.get("collected_at"),
                "raw": raw,
                "normalized": {
                    "title": raw.get("title"),
                    "text": (
                        raw.get("post_text_clean")
                        or raw.get("post_text_original")
                        or raw.get("content")
                        or raw.get("text")
                    ),
                    "url": raw.get("url") or raw.get("old_reddit_url"),
                    "author": raw.get("author"),
                    "score": _parse_score(raw.get("score")),
                    "num_comments": raw.get("num_comments") or raw.get("more_comments_count"),
                    "subreddit": raw.get("subreddit"),
                    "published_at": (
                        raw.get("published_at")
                        or raw.get("created_at")
                        or raw.get("created_utc")
                    ),
                },
            }

        if self.pipeline_enabled:
            yield from self._iter_pipeline_posts()

    def _iter_pipeline_posts(self) -> Iterator[dict]:
        sql = """
            SELECT id, subreddit, title, author, score, num_comments,
                   created_utc, permalink, url, selftext, topics,
                   upvote_ratio, collected_at, raw_json
            FROM reddit_posts
            ORDER BY created_utc, id
        """
        with self._pipeline_connection() as conn:
            with conn.cursor(
                name="social_pipeline_reddit_posts",
                row_factory=dict_row,
            ) as cur:
                cur.execute(sql)
                for raw in cur:
                    external_id = _post_external_id(raw)
                    if not external_id:
                        continue
                    yield {
                        "platform": "reddit",
                        "external_id": external_id,
                        "content_type": "post",
                        "source_system": "reddit_pipeline",
                        "collected_at": raw.get("collected_at"),
                        "raw": raw.get("raw_json") or dict(raw),
                        "normalized": {
                            "title": raw.get("title"),
                            "text": raw.get("selftext"),
                            "url": raw.get("url") or _permalink_url(raw.get("permalink")),
                            "author": raw.get("author"),
                            "score": raw.get("score"),
                            "num_comments": raw.get("num_comments"),
                            "subreddit": raw.get("subreddit"),
                            "published_at": _epoch_iso(raw.get("created_utc")),
                            "tags": raw.get("topics") or [],
                        },
                    }

    def iter_comments(self) -> Iterator[dict]:
        post_id_map = self._get_json_post_id_map()
        for raw in self._load("comments.json"):
            external_id = _comment_external_id(
                raw.get("comment_id_reddit") or raw.get("id") or raw.get("sha256_id")
            )
            if not external_id:
                continue

            parent_id = raw.get("parent_id")
            is_reply_to_comment = bool(parent_id and str(parent_id).startswith("t1_"))
            raw_post_id = raw.get("post_id") or raw.get("link_id")
            post_id = post_id_map.get(str(raw_post_id), raw_post_id) if raw_post_id else None

            yield {
                "platform": "reddit",
                "external_id": external_id,
                "content_type": "comment",
                "source_system": "reddit_scrapper",
                "collected_at": raw.get("collected_at"),
                "raw": raw,
                "normalized": {
                    "text": (
                        raw.get("body_clean")
                        or raw.get("body_original")
                        or raw.get("body")
                        or raw.get("text")
                    ),
                    "author": raw.get("author"),
                    "score": _parse_score(raw.get("score")),
                    "post_id": post_id,
                    "parent_id": parent_id,
                    "is_reply_to_comment": is_reply_to_comment,
                    "depth": raw.get("depth"),
                    "subreddit": raw.get("subreddit"),
                    "published_at": (
                        raw.get("created_utc")
                    ),
                },
            }

        if self.pipeline_enabled:
            yield from self._iter_pipeline_comments()

    def _iter_pipeline_comments(self) -> Iterator[dict]:
        # reddit_clean_comments já foi filtrada como português pelo projeto de
        # origem. A carga final ainda repete a detecção como barreira de defesa.
        sql = """
            SELECT comment_id, post_id, parent_id, subreddit, author,
                   original_body, cleaned_body, score, created_utc,
                   permalink, replies_count, collected_at
            FROM reddit_clean_comments
            ORDER BY created_utc, comment_id
        """
        with self._pipeline_connection() as conn:
            with conn.cursor(
                name="social_pipeline_reddit_comments",
                row_factory=dict_row,
            ) as cur:
                cur.execute(sql)
                for raw in cur:
                    external_id = _comment_external_id(raw.get("comment_id"))
                    if not external_id:
                        continue
                    parent_id = _comment_external_id(raw.get("parent_id"))
                    yield {
                        "platform": "reddit",
                        "external_id": external_id,
                        "content_type": "reply" if parent_id else "comment",
                        "source_system": "reddit_pipeline",
                        "collected_at": raw.get("collected_at"),
                        "raw": dict(raw),
                        "normalized": {
                            "text": raw.get("cleaned_body") or raw.get("original_body"),
                            "language": "pt-BR",
                            "language_verified": True,
                            "author": raw.get("author"),
                            "score": raw.get("score"),
                            "post_id": _post_external_id({"id": raw.get("post_id")}),
                            "parent_id": parent_id,
                            "is_reply": bool(parent_id),
                            "is_reply_to_comment": bool(parent_id),
                            "subreddit": raw.get("subreddit"),
                            "reply_count": raw.get("replies_count"),
                            "published_at": _epoch_iso(raw.get("created_utc")),
                        },
                    }


def _permalink_url(value) -> str | None:
    if not value:
        return None
    value = str(value)
    return value if value.startswith("http") else f"https://www.reddit.com{value}"
