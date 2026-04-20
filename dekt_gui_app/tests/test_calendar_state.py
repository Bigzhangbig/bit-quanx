from __future__ import annotations

from dekt_gui.calendar_state import apply_enrollment_delta


def test_apply_enrollment_delta_removes_course_for_cancel() -> None:
    current = {101, 202, 303}

    updated = apply_enrollment_delta(current, 202, enrolled=False)

    assert updated == {101, 303}


def test_apply_enrollment_delta_adds_course_for_signup() -> None:
    current = {101, 303}

    updated = apply_enrollment_delta(current, 202, enrolled=True)

    assert updated == {101, 202, 303}
