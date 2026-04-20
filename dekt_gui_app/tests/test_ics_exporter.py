from __future__ import annotations

from datetime import datetime

from dekt_gui.calendar_utils import CalendarEvent
from dekt_gui.ics_exporter import export_events_to_ics


def test_export_ics_strips_html_tags_to_plain_text() -> None:
    event = CalendarEvent(
        id=1,
        title="<b>21 天学涯习惯养成计划</b>",
        start_time=datetime(2026, 4, 16, 10, 0, 0),
        end_time=datetime(2026, 4, 16, 11, 0, 0),
        location='<p>主楼 <span style="color:red">101</span></p>',
        category='<span style="font-weight:700">自律体系搭建</span>',
        score='&lt;strong&gt;2 分&lt;/strong&gt;',
    )

    content = export_events_to_ics([event], title="测试日历")

    assert "<b>" not in content
    assert "<span" not in content
    assert "SUMMARY:21 天学涯习惯养成计划" in content
    assert "LOCATION:主楼 101" in content
    assert "DESCRIPTION:类别: 自律体系搭建\\n积分: 2 分" in content


def test_export_ics_appends_beijing_tech_line_to_location() -> None:
    event = CalendarEvent(
        id=2,
        title="测试活动",
        start_time=datetime(2026, 4, 11, 9, 30, 0),
        end_time=datetime(2026, 4, 11, 11, 0, 0),
        location="综教B303",
        address="北京理工大学(良乡校区)(东区)",
        time_place="时间：2026年4月11日上午9：30\n地点：综教B303",
    )

    content = export_events_to_ics([event], title="测试日历")

    assert "LOCATION:综教B303\\n北京理工大学" in content


def test_export_ics_compresses_zonghejiaoxuelou_location() -> None:
    event = CalendarEvent(
        id=3,
        title="测试活动2",
        start_time=datetime(2026, 4, 11, 9, 30, 0),
        end_time=datetime(2026, 4, 11, 11, 0, 0),
        location="综合教学楼B203",
        address="",
        time_place="",
    )

    content = export_events_to_ics([event], title="测试日历")

    assert "LOCATION:综教B203" in content
