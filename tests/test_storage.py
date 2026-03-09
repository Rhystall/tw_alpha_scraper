import json

from tw_alpha_scraper.models import FollowEvent
from tw_alpha_scraper.storage import AppDatabase, utcnow_iso


def test_follow_event_dedupes_by_target_and_followed_user(tmp_path):
    db = AppDatabase(str(tmp_path / "app.db"))
    db.initialize()

    event = FollowEvent(
        target_user_id="1",
        target_username="alpha",
        target_display_name="Alpha",
        followed_user_id="2",
        followed_username="beta",
        followed_display_name="Beta",
        followed_bio="bio",
        followed_profile_image_url=None,
        observed_at=utcnow_iso(),
        payload_json=json.dumps({"target_user_id": "1", "followed_user_id": "2"}),
    )

    first_id = db.record_follow_event(event)
    second_id = db.record_follow_event(event)

    assert first_id is not None
    assert second_id is None
