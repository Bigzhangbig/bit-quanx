from __future__ import annotations

from typing import Any


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    parts = [part.strip() for part in text.replace("，", ",").split(",")]
    return [part for part in parts if part]


def normalize_grade(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if text.endswith("级"):
        text = text[:-1]
    return text


def matches_whitelist(
    course: dict[str, Any],
    grade_whitelist: list[str],
    academy_whitelist: list[str],
) -> bool:
    if grade_whitelist:
        target_grades = {normalize_grade(item) for item in grade_whitelist if normalize_grade(item)}
        course_grades = {normalize_grade(item) for item in _as_text_list(course.get("grade")) if normalize_grade(item)}
        if course_grades and not course_grades.intersection(target_grades):
            return False

    if academy_whitelist:
        targets = {str(item).strip() for item in academy_whitelist if str(item).strip()}
        course_academies = set(_as_text_list(course.get("academy")))
        if not course_academies:
            course_academies = set(_as_text_list(course.get("college")))
        if course_academies and not course_academies.intersection(targets):
            return False

    return True
