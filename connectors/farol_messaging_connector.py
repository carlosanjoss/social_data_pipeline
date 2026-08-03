from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from config import settings, get_logger
from .base import BaseConnector

logger = get_logger(__name__)


class FarolMessagingConnector(BaseConnector):
    """Base para os exports anonimizados de mensagens do Farol Digital."""

    platform_name: str = ""

    def __init__(self, data_path: Path | None = None):
        self.data_path = Path(data_path or settings.farol_exports_path)

    def _files(self) -> list[Path]:
        if not self.data_path.exists():
            logger.warning("farol_exports_dir_not_found", path=str(self.data_path))
            return []
        pattern = f"fd_{self.platform_name}__tb_messages__*.json"
        return sorted(self.data_path.glob(pattern))

    def _merged_rows(self) -> dict[str, dict]:
        """Mescla snapshots repetidos, preservando o valor não vazio mais rico."""
        merged: dict[str, dict] = {}
        for path in self._files():
            try:
                with path.open(encoding="utf-8") as handle:
                    rows = json.load(handle)
            except Exception as exc:
                logger.error("farol_json_parse_error", path=str(path), error=str(exc))
                continue

            if not isinstance(rows, list):
                logger.warning("farol_json_root_not_list", path=str(path))
                continue

            for raw in rows:
                if not isinstance(raw, dict) or raw.get("id") is None:
                    continue
                external_id = str(raw["id"])
                current = merged.setdefault(external_id, {})
                for key, value in raw.items():
                    if current.get(key) in (None, "") and value not in (None, ""):
                        current[key] = value
        return merged

    def iter_posts(self) -> Iterator[dict]:
        files = self._files()
        collected_at = None
        if files:
            collected_at = datetime.fromtimestamp(
                max(path.stat().st_mtime for path in files),
                tz=timezone.utc,
            )

        for external_id, raw in self._merged_rows().items():
            member_id = raw.get("id_member_anonymous")
            collection = raw.get("_farol_collection") or {}
            collection_period = collection.get("period")
            yield {
                "platform": self.platform_name,
                "external_id": external_id,
                "content_type": "message",
                "source_system": "farol_digital_json_api",
                "collected_at": collected_at,
                "raw": raw,
                "normalized": {
                    "text": (
                        raw.get("text_content_clean")
                        or raw.get("text_content_anonymous")
                    ),
                    "author": member_id,
                    "author_id": member_id,
                    "published_at": raw.get("date_message"),
                    "group_id": raw.get("id_group_anonymous"),
                    "member_id": member_id,
                    "score_sentiment": raw.get("score_sentiment"),
                    "score_misinformation": raw.get("score_misinformation"),
                    "matched_terms": collection.get("matched_terms") or [],
                    "collection_periods": [collection_period] if collection_period else [],
                },
            }

    def iter_comments(self) -> Iterator[dict]:
        return iter(())


class WhatsAppConnector(FarolMessagingConnector):
    platform_name = "whatsapp"


class TelegramConnector(FarolMessagingConnector):
    platform_name = "telegram"
