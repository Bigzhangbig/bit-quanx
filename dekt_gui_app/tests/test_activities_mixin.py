from __future__ import annotations

from dekt_gui.activities_mixin import ActivitiesMixin


class _DummyActivities(ActivitiesMixin):
    pass


_DUMMY = _DummyActivities()


def _is_done(course: dict) -> bool:
    return ActivitiesMixin._is_course_completed(None, course)


def _is_in_progress(course: dict) -> bool:
    return ActivitiesMixin._is_course_in_progress(None, course)


def _sorted(items: list[dict]) -> list[dict]:
    return _DUMMY._sort_activities_items(items)


def test_completed_by_sign_status() -> None:
    assert _is_done({"sign_status": 3})


def test_completed_by_label() -> None:
    assert _is_done({"sign_status_label": "已结束"})
    assert _is_done({"sign_status_label": "已完成"})


def test_not_completed_when_in_progress() -> None:
    assert not _is_done({"sign_status": 2, "sign_status_label": "进行中"})


def test_completed_by_complete_time() -> None:
    assert _is_done({"complate_time": "2026-04-17 10:00:00"})


def test_in_progress_by_sign_status() -> None:
    assert _is_in_progress({"sign_status": 2})


def test_in_progress_by_label() -> None:
    assert _is_in_progress({"sign_status_label": "进行中"})
    assert _is_in_progress({"checkin_status_label": "待签到"})


def test_not_in_progress_when_completed() -> None:
    assert not _is_in_progress({"sign_status": 3, "sign_status_label": "已结束"})


def test_sort_unfinished_first_then_sign_in_time_asc() -> None:
    items = [
        {"id": 200, "sign_status": 3, "sign_status_label": "已结束", "sign_in_start_time": "2026-04-17 12:00:00"},
        {"id": 101, "sign_status": 2, "sign_status_label": "进行中", "sign_in_start_time": "2026-04-17 10:00:00"},
        {"id": 102, "sign_status": 2, "sign_status_label": "进行中", "sign_in_start_time": "2026-04-17 09:00:00"},
    ]

    sorted_items = _sorted(items)

    assert [item["id"] for item in sorted_items] == [102, 101, 200]


def test_sort_completed_by_id_desc() -> None:
    items = [
        {"id": 10, "sign_status": 3, "sign_status_label": "已结束"},
        {"id": 30, "sign_status": 3, "sign_status_label": "已结束"},
        {"id": 20, "sign_status": 3, "sign_status_label": "已结束"},
    ]

    sorted_items = _sorted(items)

    assert [item["id"] for item in sorted_items] == [30, 20, 10]
