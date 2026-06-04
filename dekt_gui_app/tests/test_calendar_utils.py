from __future__ import annotations

from datetime import datetime

from dekt_gui.calendar_utils import (
    CalendarEvent,
    calculate_event_time,
    build_display_location,
    build_export_location,
    extract_time_place_fields,
    is_event_ended,
    normalize_display_text,
    parse_event_from_list_my_courses,
    parse_datetime,
    summarize_event_day_completion,
)


def test_parse_datetime_supports_chinese_datetime_with_trailing_punctuation() -> None:
    dt = parse_datetime("2026年4月17日18:30;")

    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 17
    assert dt.hour == 18
    assert dt.minute == 30


def test_calculate_event_time_prefers_activity_start_time_over_checkin_midpoint() -> None:
    data = {
        "activity_start_time": "2026年4月17日18:30;",
        "activity_end_time": "2026年4月17日19:30",
        "sign_in_start_time": "2026-04-17 18:25:00",
        "sign_in_end_time": "2026-04-17 18:40:00",
    }

    start_time, end_time = calculate_event_time(data)

    assert start_time is not None
    assert end_time is not None
    assert start_time.hour == 18
    assert start_time.minute == 30
    assert end_time.hour == 19
    assert end_time.minute == 30


def test_extract_time_place_fields_parses_multiline_live_api_text() -> None:
    time_text, place_text = extract_time_place_fields("时间：2026年4月17日18:30；\n地点：综教B203")

    assert time_text == "2026年4月17日18:30"
    assert place_text == "综教B203"


def test_parse_datetime_supports_chinese_meridiem_time() -> None:
    dt = parse_datetime("2026年4月11日上午9：30")

    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 11
    assert dt.hour == 9
    assert dt.minute == 30


def test_parse_datetime_supports_no_year_chinese_range_with_weekday() -> None:
    dt = parse_datetime("4月19日（周日）15：00-17：00~")

    assert dt is not None
    assert dt.month == 4
    assert dt.day == 19
    assert dt.hour == 15
    assert dt.minute == 0


def test_calculate_event_time_uses_time_place_when_activity_start_missing() -> None:
    data = {
        "time_place": "时间：2026年4月17日18:30；\n地点：综教B203",
        "sign_in_start_time": "2026-04-17 18:25:00",
        "sign_in_end_time": "2026-04-17 18:40:00",
        "sign_out_start_time": "2026-04-17 19:30:00",
    }

    start_time, end_time = calculate_event_time(data)

    assert start_time is not None
    assert end_time is not None
    assert start_time.hour == 18
    assert start_time.minute == 30
    assert end_time.hour == 19
    assert end_time.minute == 30


def test_normalize_display_text_collapses_newlines_to_one_line() -> None:
    assert normalize_display_text("综教B303\n北京理工大学") == "综教B303 北京理工大学"


def test_build_display_location_uses_first_line_only() -> None:
    assert build_display_location("时间：2026年4月11日上午9：30\n地点：综教B303") == "综教B303"


def test_build_export_location_appends_campus_line() -> None:
    location = build_export_location(
        "综教B303",
        "时间：2026年4月11日上午9：30\n地点：综教B303",
        "北京理工大学(良乡校区)(东区)",
    )

    assert location == "综教B303\n北京理工大学"


def test_extract_time_place_fields_supports_unlabeled_two_line_text() -> None:
    time_text, place_text = extract_time_place_fields("2026年4月19日13:00\n良乡校区北校区北湖西侧长廊与主舞台")

    assert time_text == "2026年4月19日13:00"
    assert place_text == "良乡校区北校区北湖西侧长廊与主舞台"


def test_build_display_location_prefers_unlabeled_time_place_location() -> None:
    display = build_display_location(
        "2026年4月19日13:00\n良乡校区北校区北湖西侧长廊与主舞台",
        "北京理工大学人工湖休闲公园",
    )

    assert display == "北湖西侧长廊与主舞台"


def test_build_display_location_keeps_zhongguancun_prefix() -> None:
    display = build_display_location("2026年4月19日13:00\n中关村校区体育馆")

    assert display == "中关村校区体育馆"


def test_extract_time_place_fields_unlabeled_range_does_not_pollute_location() -> None:
    time_text, place_text = extract_time_place_fields(
        "2026年4月9日19:00-20:30 北京理工大学良乡校区体育馆二层武术教室"
    )

    assert time_text == "2026年4月9日19:00"
    assert place_text == "北京理工大学良乡校区体育馆二层武术教室"


def test_build_display_location_compresses_zonghejiaoxuelou() -> None:
    display = build_display_location("2026年4月19日13:00\n综合教学楼B203")

    assert display == "综教B203"


def test_calculate_event_time_prefers_time_place_range_without_year() -> None:
    data = {
        "time_place": "时间：4月19日（周日）15：00-17：00~\n地点：良乡北校区北湖北侧篮球场",
        "sign_in_start_time": "2026-04-19 14:57:00",
        "sign_in_end_time": "2026-04-19 15:03:00",
        "sign_out_start_time": "2026-04-19 17:05:00",
    }

    start_time, end_time = calculate_event_time(data)

    assert start_time is not None
    assert end_time is not None
    assert start_time.hour == 15
    assert start_time.minute == 0
    assert end_time.hour == 17
    assert end_time.minute == 5


def test_build_display_location_removes_liangxiang_and_north_south_campus() -> None:
    display = build_display_location(
        "时间：4月19日（周日）15：00-17：00~\n地点：良乡北校区北湖北侧篮球场"
    )

    assert display == "北湖北侧篮球场"


def test_calculate_event_time_prefers_time_place_over_activity_start_time_when_range_present() -> None:
    data = {
        "activity_start_time": "2026-04-19 14:57:00",
        "time_place": "时间：4月19日（周日）15：00-17：00~\n地点：良乡北校区北湖北侧篮球场",
        "sign_out_start_time": "2026-04-19 17:05:00",
    }

    start_time, end_time = calculate_event_time(data)

    assert start_time is not None
    assert end_time is not None
    assert start_time.hour == 15
    assert start_time.minute == 0
    assert end_time.hour == 17
    assert end_time.minute == 5


def test_calculate_event_time_parses_year_range_with_weekday() -> None:
    data = {
        "time_place": "时间:2026年3月28日(周六)14:30-17:00\n地点:良乡校区文萃楼圆形报告厅一层",
        "activity_start_time": "2026-03-28 14:22:00",
        "sign_out_start_time": "2026-03-28 16:30:00",
    }

    start_time, end_time = calculate_event_time(data)

    assert start_time is not None
    assert end_time is not None
    assert start_time.hour == 14
    assert start_time.minute == 30
    assert end_time.hour == 17
    assert end_time.minute == 0


def test_parse_event_from_list_my_courses_uses_detail_text_when_time_place_missing() -> None:
    courses = [
        {
            "id": 1,
            "title": "2026年北京理工大学志愿服务项目大赛决赛观众",
            "content": (
                "2026年北京理工大学青年志愿服务项目大赛决赛将于3月28日周六举行。\n"
                "时间:2026年3月28日(周六)14:30-17:00\n"
                "地点:良乡校区文萃楼圆形报告厅一层"
            ),
            "activity_start_time": "2026-03-28 14:22:00",
            "sign_out_start_time": "2026-03-28 16:30:00",
            "sign_in_address": [{"address": "(良乡校区)(东区)"}],
            "duration": 150,
        }
    ]

    events = parse_event_from_list_my_courses(courses)

    assert len(events) == 1
    assert events[0].start_time is not None
    assert events[0].end_time is not None
    assert events[0].start_time.hour == 14
    assert events[0].start_time.minute == 30
    assert events[0].end_time.hour == 17
    assert events[0].end_time.minute == 0
    assert events[0].location == "文萃楼圆形报告厅一层"


def test_build_display_location_cleans_bracketed_liangxiang_prefix() -> None:
    display = build_display_location("", "(良乡校区南区)")

    assert display == "(南区)"


def test_calculate_event_time_parses_time_place_with_zao_prefix_and_no_full_date() -> None:
    data = {
        "time_place": "周六（28日）早8：20-9：00\n南操场主席台\n随机就坐即可",
        "sign_in_start_time": "2026-03-28 08:20:00",
        "sign_in_end_time": "2026-03-28 08:40:00",
        "sign_out_start_time": "2026-03-28 09:00:00",
        "sign_out_end_time": "2026-03-28 09:30:00",
    }

    start_time, end_time = calculate_event_time(data)

    assert start_time is not None
    assert end_time is not None
    assert start_time.hour == 8
    assert start_time.minute == 20
    assert end_time.hour == 9
    assert end_time.minute == 0


def test_build_display_location_prefers_second_line_for_weekday_time_range() -> None:
    display = build_display_location(
        "周六（28日）早8：20-9：00\n南操场主席台 \n随机就坐即可",
        "北京理工大学(良乡校区南区)",
    )

    assert display == "南操场主席台"


def test_build_display_location_skips_instruction_line_for_weekday_time_range() -> None:
    display = build_display_location(
        "周六（28日）早8：20-9：00\n随机就坐即可\n南操场主席台",
        "北京理工大学(良乡校区南区)",
    )

    assert display == "南操场主席台"


def test_is_event_ended_by_end_time() -> None:
    event = CalendarEvent(
        id=1,
        title="已结束活动",
        start_time=datetime(2026, 3, 28, 8, 20),
        end_time=datetime(2026, 3, 28, 9, 0),
    )

    assert is_event_ended(event, now=datetime(2026, 3, 28, 9, 1)) is True
    assert is_event_ended(event, now=datetime(2026, 3, 28, 8, 59)) is False


def test_is_event_ended_by_sign_out_end_time() -> None:
    event = CalendarEvent(
        id=2,
        title="有签退窗口活动",
        sign_out_end_time="2026-03-28 09:30:00",
    )

    assert is_event_ended(event, now=datetime(2026, 3, 28, 9, 31)) is True
    assert is_event_ended(event, now=datetime(2026, 3, 28, 9, 29)) is False


def test_summarize_event_day_completion_marks_mixed_day_as_not_completed() -> None:
    events = [
        CalendarEvent(
            id=1,
            title="已结束活动",
            start_time=datetime(2026, 3, 28, 8, 20),
            sign_out_end_time="2026-03-28 09:00:00",
        ),
        CalendarEvent(
            id=2,
            title="未结束活动",
            start_time=datetime(2026, 3, 28, 10, 0),
            sign_out_end_time="2026-03-29 12:00:00",
        ),
        CalendarEvent(
            id=3,
            title="另一日已结束活动",
            start_time=datetime(2026, 3, 29, 8, 20),
            sign_out_end_time="2026-03-29 09:00:00",
        ),
    ]

    completion = summarize_event_day_completion(events, now=datetime(2026, 3, 29, 10, 0))

    assert completion[(2026, 3, 28)] is False
    assert completion[(2026, 3, 29)] is True
