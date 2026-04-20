from __future__ import annotations


def apply_enrollment_delta(current_ids: set[int], course_id: int, enrolled: bool) -> set[int]:
    """基于报名/取消报名动作更新已报名活动 ID 集合。"""
    updated = set(current_ids)
    if enrolled:
        updated.add(course_id)
    else:
        updated.discard(course_id)
    return updated
