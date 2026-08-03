from datetime import datetime, timezone

from connectors.tiktok_connector import _published_at_from_aweme_id
from normalizers.posts import _dt


def test_normalizer_accepts_epoch_number_and_string():
    expected = datetime(2026, 3, 1, tzinfo=timezone.utc)
    epoch = expected.timestamp()
    assert _dt(epoch) == expected
    assert _dt(str(int(epoch))) == expected


def test_tiktok_video_date_is_derived_from_aweme_id():
    assert _published_at_from_aweme_id("7626827891782798614").startswith(
        "2026-04-09T18:27:27"
    )
