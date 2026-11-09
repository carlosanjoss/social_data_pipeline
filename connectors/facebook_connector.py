import json
import re
from pathlib import Path
from typing import Iterator
from datetime import datetime, timedelta, timezone

from config import settings, get_logger
from .base import BaseConnector

logger = get_logger(__name__)

_RELATIVE_DATE_RE = re.compile(
    r"(\d+)\s*(minuto|hora|dia|semana|mês|mes|ano)s?",
    re.IGNORECASE,
)
_UNIT_MAP = {
    "minuto": "minutes", "hora": "hours", "dia": "days",
    "semana": "weeks",   "mês": "days",   "mes": "days",
    "ano":    "days",
}
_UNIT_MULTIPLIER = {
    "minuto": 1, "hora": 1, "dia": 1, "semana": 7, "mês": 30, "mes": 30, "ano": 365,
}

# "12 de março de 2026 às 15:30" or "12 de mar. de 2026, 15:30"
_PT_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}
_PT_ABS_RE = re.compile(
    r"(\d{1,2})\s+de\s+([a-záéíóúâêôãõç\.]+)\s+de\s+(\d{4})"
    r"(?:\s+(?:às|as|,)?\s*(\d{1,2}):(\d{2}))?",
    re.IGNORECASE,
)
# "March 12, 2026 at 3:30 PM" or "March 12, 2026"
_EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_EN_ABS_RE = re.compile(
    r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})"
    r"(?:\s+at\s+(\d{1,2}):(\d{2})\s*(AM|PM)?)?",
    re.IGNORECASE,
)


def _fb_date(value: str | None) -> str | None:
    """
    Returns ISO-8601 from Facebook date fields, handling:
    - ISO strings → return as-is
    - Portuguese absolute: "12 de março de 2026 às 15:30"
    - English absolute: "March 12, 2026 at 3:30 PM"
    - Relative Portuguese: "3 horas atrás", "2 semanas atrás"
    """
    if not value:
        return None
    s = str(value).strip()

    # Already ISO
    if "T" in s and (s.endswith("Z") or "+" in s[10:] or s.count("-") >= 3):
        return s

    # Portuguese absolute date
    m = _PT_ABS_RE.search(s)
    if m:
        day, month_str, year = int(m.group(1)), m.group(2).lower().rstrip("."), int(m.group(3))
        month = _PT_MONTHS.get(month_str)
        if month:
            hour = int(m.group(4)) if m.group(4) else 0
            minute = int(m.group(5)) if m.group(5) else 0
            try:
                return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass

    # English absolute date
    m = _EN_ABS_RE.search(s)
    if m:
        month_str, day, year = m.group(1).lower(), int(m.group(2)), int(m.group(3))
        month = _EN_MONTHS.get(month_str)
        if month:
            hour = int(m.group(4)) if m.group(4) else 0
            minute = int(m.group(5)) if m.group(5) else 0
            if m.group(6) and m.group(6).upper() == "PM" and hour < 12:
                hour += 12
            try:
                return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass

    # Relative date in Portuguese or English
    m = _RELATIVE_DATE_RE.search(s)
    if m:
        amount = int(m.group(1))
        unit   = m.group(2).lower()
        days_or_unit = _UNIT_MAP.get(unit, "days")
        multiplier   = _UNIT_MULTIPLIER.get(unit, 1)
        delta = timedelta(**{days_or_unit: amount * multiplier})
        return (datetime.now(timezone.utc) - delta).isoformat()

    return None


class FacebookConnector(BaseConnector):
    """
    Walks the directory tree:
        facebook_data_path/<page_slug>/posts/<pfbid>.json
    """

    def __init__(self, data_path: Path | None = None):
        self.data_path = Path(data_path or settings.facebook_data_path)

    def _post_files(self) -> Iterator[tuple[str, Path]]:
        if not self.data_path.exists():
            logger.warning("facebook_data_dir_not_found", path=str(self.data_path))
            return
        for page_dir in self.data_path.iterdir():
            if not page_dir.is_dir():
                continue
            posts_dir = page_dir / "posts"
            if not posts_dir.exists():
                continue
            for json_file in posts_dir.glob("*.json"):
                yield page_dir.name, json_file

    def _load(self, path: Path) -> dict | None:
        try:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("facebook_json_parse_error", path=str(path), error=str(exc))
            return None

    def iter_posts(self) -> Iterator[dict]:
        for page_slug, json_file in self._post_files():
            raw = self._load(json_file)
            if not raw:
                continue

            post_id = str(
                raw.get("post_id") or raw.get("id") or json_file.stem
            )

            # Extract numeric reaction counts
            reactions = raw.get("reactions") or {}
            if isinstance(reactions, str):
                try:
                    reactions = json.loads(reactions)
                except Exception:
                    reactions = {}

            media = raw.get("media") or []
            media_types = list({m.get("type") for m in media if isinstance(m, dict) and m.get("type")})

            yield {
                "platform":     "facebook",
                "external_id":  post_id,
                "content_type": "post",
                "source_system": "facebook_scrapper",
                "collected_at":  raw.get("collected_at") or raw.get("last_collected_at"),
                "raw":          raw,
                "normalized": {
                    "text":         raw.get("text") or raw.get("content"),
                    # author often null in post-level FB data; fall back to page slug
                    "author":       raw.get("author") or raw.get("page_name") or page_slug,
                    "page_id":      raw.get("page_id") or page_slug,
                    "page_slug":    page_slug,
                    "like_count":   _to_int(
                        reactions.get("like")
                        or (raw.get("reactions_count") if isinstance(raw.get("reactions_count"), dict) else {}).get("like")
                        or raw.get("likes")
                    ),
                    "share_count":  _to_int(raw.get("shares") or raw.get("shares_count")),
                    "comment_count":_to_int(raw.get("comments_count") or raw.get("num_comments")),
                    "reactions":    reactions,
                    "media_types":  media_types,
                    "url":          raw.get("url") or raw.get("post_url"),
                    # Data de coleta não substitui data de publicação ausente.
                    "published_at": _fb_date(
                        raw.get("created_at_absolute")
                        or raw.get("created_at")
                        or raw.get("date")
                        or raw.get("timestamp")
                    ),
                },
            }

    def iter_comments(self) -> Iterator[dict]:
        for page_slug, json_file in self._post_files():
            raw_post = self._load(json_file)
            if not raw_post:
                continue
            post_id = str(raw_post.get("post_id") or raw_post.get("id") or json_file.stem)

            for comment in raw_post.get("comments") or []:
                comment_id = str(comment.get("comment_id") or comment.get("id") or "")
                if not comment_id:
                    continue
                yield {
                    "platform":     "facebook",
                    "external_id":  comment_id,
                    "content_type": "comment",
                    "source_system": "facebook_scrapper",
                    "collected_at":  comment.get("collected_at") or raw_post.get("collected_at"),
                    "raw":          comment,
                    "normalized": {
                        "text":       comment.get("text") or comment.get("body"),
                        "author":     comment.get("author"),
                        "like_count": _to_int(
                            (comment.get("reactions") or {}).get("like")
                            or comment.get("likes")
                        ),
                        "post_id":    post_id,
                        "page_slug":  page_slug,
                        "published_at": _fb_date(
                            comment.get("created_at_absolute")
                            or comment.get("created_at")
                            or comment.get("date")
                        ),
                    },
                }
                # also yield nested replies as separate comment documents
                for reply in comment.get("replies") or []:
                    reply_id = str(reply.get("comment_id") or reply.get("id") or "")
                    if not reply_id:
                        continue
                    yield {
                        "platform":     "facebook",
                        "external_id":  reply_id,
                        "content_type": "reply",
                        "source_system": "facebook_scrapper",
                        "collected_at":  reply.get("collected_at") or raw_post.get("collected_at"),
                        "raw":          reply,
                        "normalized": {
                            "text":       reply.get("text") or reply.get("body"),
                            "author":     reply.get("author"),
                            "like_count": _to_int((reply.get("reactions") or {}).get("like") or reply.get("likes")),
                            "post_id":    post_id,
                            "parent_id":  comment_id,
                            "page_slug":  page_slug,
                            "published_at": _fb_date(
                                reply.get("created_at_absolute")
                                or reply.get("created_at")
                                or reply.get("date")
                            ),
                        },
                    }


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").replace(".", "").strip())
    except (ValueError, TypeError):
        return None
