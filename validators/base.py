from __future__ import annotations
from typing import Any
from pydantic import ValidationError

from models import NormalizedPost, NormalizedComment, QualityReport
from .quality_score import compute_quality


def validate_post(doc: dict[str, Any]) -> tuple[NormalizedPost | None, list[str]]:
    """
    Validates a MongoDB raw_posts document.
    Returns (model_instance, validation_errors).
    Quality score is embedded into the model's .quality field.
    """
    platform = doc.get("platform", "")
    n = doc.get("normalized", {}) or {}

    quality_dict = compute_quality(n, platform, is_comment=False)
    quality = QualityReport(**quality_dict)

    payload = {
        "platform":    platform,
        "external_id": doc.get("external_id", ""),
        "content_type": doc.get("content_type", ""),
        **n,
        "quality": quality,
    }

    try:
        return NormalizedPost.model_validate(payload), []
    except ValidationError as exc:
        errors = [f"{e['loc']}: {e['msg']}" for e in exc.errors()]
        return None, errors


def validate_comment(doc: dict[str, Any]) -> tuple[NormalizedComment | None, list[str]]:
    """
    Validates a MongoDB raw_comments document.
    """
    platform = doc.get("platform", "")
    n = doc.get("normalized", {}) or {}
    is_reply = doc.get("content_type") == "reply" or n.get("is_reply", False)

    quality_dict = compute_quality(n, platform, is_comment=True)
    quality = QualityReport(**quality_dict)

    payload = {
        "platform":    platform,
        "external_id": doc.get("external_id", ""),
        "content_type": doc.get("content_type", "comment"),
        **n,
        "is_reply": is_reply,
        "quality": quality,
    }

    try:
        return NormalizedComment.model_validate(payload), []
    except ValidationError as exc:
        errors = [f"{e['loc']}: {e['msg']}" for e in exc.errors()]
        return None, errors
