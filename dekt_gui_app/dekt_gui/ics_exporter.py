"""ICS日历文件导出工具。"""
from __future__ import annotations

from datetime import datetime
from html import unescape
import re
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from .calendar_utils import CalendarEvent
from .calendar_utils import build_export_location


def _datetime_to_ics(dt: datetime | None) -> str:
    """将datetime对象转换为iCalendar格式。
    
    格式: YYYYMMDDTHHMMSSZ (UTC+8转换为UTC)
    """
    if not dt:
        return ""
    
    # 将本地时间转换为UTC (中国时区为UTC+8)
    # 注意：这里简单处理，假设输入是本地时间（北京时间）
    # 转换为UTC需要减去8小时
    from datetime import timedelta
    utc_dt = dt - timedelta(hours=8)
    return utc_dt.strftime("%Y%m%dT%H%M%SZ")


def _escape_text(text: str | None) -> str:
    """转义ICS文本，处理特殊字符。"""
    if not text:
        return ""

    text = _to_plain_text(text)
    # ICS格式需要转义的字符: ; , \
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "")
    return text


def _to_plain_text(text: str | None) -> str:
    """将可能包含 HTML 的文本转换为纯文本。"""
    if not text:
        return ""

    normalized = unescape(str(text))
    # 保留常见块级标签的换行语义。
    normalized = re.sub(r"<br\\s*/?>", "\\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"</(?:p|div|li|h[1-6]|tr)\\s*>", "\\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<[^>]+>", "", normalized)
    normalized = normalized.replace("\r", "")

    lines = [re.sub(r"[ \\t]+", " ", line).strip() for line in normalized.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def export_events_to_ics(
    events: list[CalendarEvent],
    title: str = "DEKT日历",
) -> str:
    """将CalendarEvent列表导出为ICS格式字符串。
    
    RFC 5545标准。
    
    Args:
        events: CalendarEvent对象列表
        title: 日历标题
    
    Returns:
        ICS格式的字符串
    """
    lines: list[str] = []
    
    # ICS头部
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//DEKT//DEKT Calendar//ZH")
    lines.append(f"CALSCALE:GREGORIAN")
    lines.append("METHOD:PUBLISH")
    lines.append(f"X-WR-CALNAME:{_escape_text(title)}")
    lines.append("X-WR-TIMEZONE:Asia/Shanghai")
    lines.append("X-WR-CALDESC:DEKT活动日历")
    
    # 遍历每个事件
    for event in events:
        if not event.start_time:
            continue
        
        lines.append("BEGIN:VEVENT")
        
        # 唯一标识符
        uid_title = _to_plain_text(event.title)
        uid_title = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff_-]+", "-", uid_title).strip("-")
        if not uid_title:
            uid_title = "event"
        uid = f"{event.id}-{uid_title}-{uuid.uuid4().hex[:8]}@dekt.local"
        lines.append(f"UID:{uid}")
        
        # 时间戳
        created_time = datetime.now()
        lines.append(f"DTSTAMP:{_datetime_to_ics(created_time)}")
        
        # 事件标题
        lines.append(f"SUMMARY:{_escape_text(event.title)}")
        
        # 开始时间
        lines.append(f"DTSTART:{_datetime_to_ics(event.start_time)}")
        
        # 结束时间
        if event.end_time:
            lines.append(f"DTEND:{_datetime_to_ics(event.end_time)}")
        
        # 位置（地点）
        if event.location or event.address or getattr(event, "time_place", ""):
            location = build_export_location(
                event.location,
                event.time_place,
                event.address,
            )
            lines.append(f"LOCATION:{_escape_text(location)}")
        
        # 描述（包含类别、积分、时长、联系方式）
        description_parts: list[str] = []
        
        if event.category:
            description_parts.append(f"类别: {event.category}")
        
        if event.score:
            description_parts.append(f"积分: {event.score}")
        
        if event.duration:
            duration_str = str(event.duration)
            if isinstance(event.duration, int):
                duration_str = f"{event.duration}分钟"
            description_parts.append(f"时长: {duration_str}")
        
        if event.contact_name or event.contact_phone:
            contact_info = event.contact_name or ""
            if event.contact_phone:
                contact_info = f"{contact_info}({event.contact_phone})" if contact_info else event.contact_phone
            description_parts.append(f"联系: {contact_info}")
        
        if description_parts:
            description = "\n".join(description_parts)
            lines.append(f"DESCRIPTION:{_escape_text(description)}")
        
        # 状态
        lines.append("STATUS:CONFIRMED")
        
        # 可用性
        lines.append("TRANSP:OPAQUE")
        
        lines.append("END:VEVENT")
    
    # ICS尾部
    lines.append("END:VCALENDAR")
    
    return "\n".join(lines)


def export_events_to_ics_file(
    events: list[CalendarEvent],
    file_path: str,
    title: str = "DEKT日历",
) -> bool:
    """将CalendarEvent列表导出为ICS文件。
    
    Args:
        events: CalendarEvent对象列表
        file_path: 输出文件路径
        title: 日历标题
    
    Returns:
        是否成功
    """
    try:
        content = export_events_to_ics(events, title)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"导出ICS文件失败: {e}")
        return False
