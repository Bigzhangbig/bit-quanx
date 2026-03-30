from dekt_backend.filtering import matches_whitelist, normalize_grade


def test_normalize_grade_accepts_suffix() -> None:
    assert normalize_grade("2024级") == "2024"


def test_matches_whitelist_pass_when_course_has_no_limits() -> None:
    course = {"id": 1, "grade": [], "college": []}
    assert matches_whitelist(course, ["2024"], ["计算机学院"])


def test_matches_whitelist_blocks_non_matching_grade() -> None:
    course = {"id": 1, "grade": ["2023"], "college": ["计算机学院"]}
    assert not matches_whitelist(course, ["2024"], [])


def test_matches_whitelist_blocks_non_matching_academy() -> None:
    course = {"id": 1, "grade": ["2024"], "college": ["外国语学院"]}
    assert not matches_whitelist(course, [], ["计算机学院"])
