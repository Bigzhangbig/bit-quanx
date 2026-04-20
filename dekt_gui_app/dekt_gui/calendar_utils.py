"""日历数据模型和时间处理工具。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any


@dataclass
class CalendarEvent:
    """日历事件数据模型。"""
    id: int
    title: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str = ""
    address: str = ""
    category: str = ""
    duration: int | str = ""  # 分钟数或字符串描述
    score: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    is_enrolled: bool = False
    sign_in_start_time: str = ""
    sign_in_end_time: str = ""
    sign_out_start_time: str = ""
    sign_out_end_time: str = ""
    time_place: str = ""


def parse_datetime(date_str: str) -> datetime | None:
    """解析时间字符串。支持格式:
    - YYYY-MM-DD HH:MM:SS
    - YYYY/MM/DD HH:MM
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    raw = date_str.strip()
    if not raw:
        return None

    # 兼容“4月19日（周日）15:00-17:00~”这类无年份的时间区间，返回区间起始时间。
    raw_range = raw.replace("：", ":")
    range_match = re.search(
        r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日(?:[（(](?:周|星期)[一二三四五六日天][）)])?\s*(?P<meridiem>上午|中午|下午|晚上)?\s*(?P<hour>\d{1,2}):(?P<minute>\d{1,2})\s*[-~～至到]\s*\d{1,2}:\d{1,2}(?::\d{1,2})?",
        raw_range,
    )
    if range_match:
        current_year = datetime.now().year
        month = int(range_match.group("month"))
        day = int(range_match.group("day"))
        hour = int(range_match.group("hour"))
        minute = int(range_match.group("minute"))
        meridiem_marker = range_match.group("meridiem") or ""
        if meridiem_marker in {"下午", "晚上"} and hour < 12:
            hour += 12
        elif meridiem_marker == "上午" and hour == 12:
            hour = 0
        try:
            return datetime(current_year, month, day, hour, minute)
        except ValueError:
            return None

    # 统一全角符号、中文日期分隔符与尾部标点。
    normalized = raw.replace("：", ":").replace("（", "(").replace("）", ")")
    normalized = normalized.replace("年", "-").replace("月", "-").replace("日", " ")
    normalized = normalized.replace("T", " ")
    normalized = re.sub(r"\((?:周|星期)[一二三四五六日天]\)", " ", normalized)
    meridiem = None
    for marker in ["上午", "中午", "下午", "晚上"]:
        if marker in normalized:
            meridiem = marker
            normalized = normalized.replace(marker, " ")
            break
    normalized = re.sub(r"[;；。．、，,~～]+$", "", normalized)
    normalized = re.sub(
        r"^(?P<date>\d{1,4}[-/]\d{1,2}[-/]\d{1,2})\s+(?P<start>\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*[-~～至到]\s*\d{1,2}:\d{1,2}(?::\d{1,2})?$",
        r"\g<date> \g<start>",
        normalized,
    )
    normalized = re.sub(
        r"^(?P<date>\d{1,2}[-/]\d{1,2})\s+(?P<start>\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*[-~～至到]\s*\d{1,2}:\d{1,2}(?::\d{1,2})?$",
        r"\g<date> \g<start>",
        normalized,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # 兼容缺少年份格式：MM-DD HH:MM(:SS)
    if re.fullmatch(r"\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2}(?::\d{1,2})?", normalized):
        current_year = datetime.now().year
        normalized = f"{current_year}-{normalized}"
    
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(normalized, fmt)
            if meridiem in {"下午", "晚上"} and parsed.hour < 12:
                parsed = parsed.replace(hour=parsed.hour + 12)
            elif meridiem in {"上午", "中午"} and parsed.hour == 12:
                parsed = parsed.replace(hour=0 if meridiem == "上午" else 12)
            return parsed
        except ValueError:
            continue

    # 从夹杂标签或说明文字的内容中提取时间片段，例如“时间：2026年4月17日18:30；\n地点：综教B203”。
    patterns = [
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{1,2}(?::\d{1,2}(?:\.\d+)?)?",
        r"\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{1,2}(?::\d{1,2}(?:\.\d+)?)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        candidate = match.group(0)
        if re.fullmatch(r"\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{1,2}(?::\d{1,2}(?:\.\d+)?)?", candidate):
            candidate = f"{datetime.now().year}-{candidate}"
        for fmt in formats:
            try:
                parsed = datetime.strptime(candidate, fmt)
                if meridiem in {"下午", "晚上"} and parsed.hour < 12:
                    parsed = parsed.replace(hour=parsed.hour + 12)
                elif meridiem in {"上午", "中午"} and parsed.hour == 12:
                    parsed = parsed.replace(hour=0 if meridiem == "上午" else 12)
                return parsed
            except ValueError:
                continue
    
    return None


def extract_time_place_fields(text: str | None) -> tuple[str, str]:
    """从 time_place 字段中提取时间与地点。"""
    if not text or not isinstance(text, str):
        return "", ""

    raw = text.strip()
    if not raw:
        return "", ""

    time_match = re.search(
        r"(?:时间|活动开始|开始时间|活动时间)\s*[:：]\s*(.+?)(?=(?:\s*(?:地点|打卡地点|位置)\s*[:：])|[\n\r]|[;；])",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    place_match = re.search(
        r"(?:地点|打卡地点|位置)\s*[:：]\s*(.+?)(?=[\n\r]|[;；]|$)",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )

    def clean(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"[;；。．、，,]+$", "", value.strip()).strip()

    time_text = clean(time_match.group(1) if time_match else "")
    place_text = clean(place_match.group(1) if place_match else "")

    if time_text and place_text:
        return time_text, place_text

    def looks_like_time_line(value: str) -> bool:
        if not value:
            return False
        if parse_datetime(value):
            return True
        normalized = value.replace("：", ":")
        return bool(
            re.search(
                r"(?:周[一二三四五六日天]|星期[一二三四五六日天])?.*"
                r"(?:早|上午|中午|下午|晚上)?\s*\d{1,2}:\d{1,2}\s*[-~～至到]\s*\d{1,2}:\d{1,2}",
                normalized,
            )
        )

    def is_instruction_line(value: str) -> bool:
        normalized = normalize_display_text(value)
        if not normalized:
            return True
        keywords = (
            "请",
            "注意",
            "随机",
            "即可",
            "结束后",
            "联系",
            "协助",
            "群内",
            "扫码",
            "收集",
            "录入",
        )
        return any(keyword in normalized for keyword in keywords)

    # 兼容无标签两行格式：第一行时间，第二行地点。
    lines = [clean(line) for line in re.split(r"[\r\n]+", raw) if clean(line)]
    if len(lines) >= 2:
        first_line = lines[0]
        if looks_like_time_line(first_line):
            for candidate in lines[1:]:
                if not is_instruction_line(candidate):
                    return first_line, candidate
            return first_line, lines[1]

    # 兼容无标签单行格式："2026年4月9日19:00-20:30 北京理工大学..."。
    range_patterns = [
        r"(?P<start>\d{4}年\d{1,2}月\d{1,2}日(?:上午|中午|下午|晚上)?\d{1,2}[:：]\d{1,2})\s*[-~～至到]\s*\d{1,2}[:：]\d{1,2}(?::\d{1,2})?",
        r"(?P<start>\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}[:：]\d{1,2})\s*[-~～至到]\s*\d{1,2}[:：]\d{1,2}(?::\d{1,2})?",
    ]
    for pattern in range_patterns:
        match = re.search(pattern, raw)
        if not match:
            continue
        start_text = clean(match.group("start"))
        remainder = clean(raw[match.end():])
        if remainder.startswith("地点"):
            remainder = clean(re.sub(r"^地点\s*[:：]?", "", remainder))
        if parse_datetime(start_text):
            return start_text, remainder

    # 兜底：若全文中能识别到时间，则将时间后的文本作为地点。
    for pattern in [
        r"\d{4}年\d{1,2}月\d{1,2}日(?:上午|中午|下午|晚上)?\d{1,2}[:：]\d{1,2}(?::\d{1,2})?",
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}[:：]\d{1,2}(?::\d{1,2})?",
    ]:
        match = re.search(pattern, raw)
        if not match:
            continue
        candidate_time = clean(match.group(0))
        remainder = clean(raw[match.end():])
        if remainder.startswith("地点"):
            remainder = clean(re.sub(r"^地点\s*[:：]?", "", remainder))
        if parse_datetime(candidate_time):
            return candidate_time, remainder

    return time_text, place_text


def _extract_time_place_source(data: dict[str, Any]) -> str:
    """提取可用于解析时间/地点的原始文本，优先使用结构化字段。"""
    candidates = [
        data.get("time_place"),
        data.get("body"),
        data.get("detail"),
        data.get("content"),
        data.get("description"),
        data.get("intro"),
        data.get("course_detail"),
        data.get("course_content"),
        data.get("activity_detail"),
        data.get("activity_content"),
        data.get("summary"),
        data.get("remark"),
        data.get("text"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            text = candidate.strip()
            if text:
                return text
    return ""


def _extract_time_range(text: str | None) -> tuple[datetime | None, datetime | None]:
    """从文本中提取时间区间，返回起止时间。"""
    if not text or not isinstance(text, str):
        return None, None

    raw = text.replace("：", ":")
    pattern = (
        r"(?P<date>(?:\d{4}年)?\d{1,2}月\d{1,2}日|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2})"
        r"\s*(?:[（(](?:周|星期)[一二三四五六日天][）)])?\s*"
        r"(?P<meridiem>上午|中午|下午|晚上)?\s*"
        r"(?P<start>\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*[-~～至到]\s*"
        r"(?P<end>\d{1,2}:\d{1,2}(?::\d{1,2})?)"
    )
    match = re.search(pattern, raw)
    if not match:
        return None, None

    date_text = match.group("date")
    meridiem_text = match.group("meridiem") or ""
    start_text = f"{date_text} {meridiem_text}{match.group('start')}".strip()
    end_text = f"{date_text} {meridiem_text}{match.group('end')}".strip()

    start_dt = parse_datetime(start_text)
    end_dt = parse_datetime(end_text)
    return start_dt, end_dt


def _parse_time_hm(text: str, meridiem_text: str = "") -> tuple[int, int] | None:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{1,2})(?::\d{1,2})?\s*", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    if meridiem_text in {"下午", "晚上"} and hour < 12:
        hour += 12
    elif meridiem_text in {"上午", "早"} and hour == 12:
        hour = 0
    return hour, minute


def _extract_time_only_range(
    text: str | None,
    anchor_date: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    """从无完整日期的时间区间文本中提取起止时间，并使用 anchor_date 补日期。"""
    if not text or not isinstance(text, str) or anchor_date is None:
        return None, None

    raw = text.replace("：", ":")
    pattern = (
        r"(?<!\d)(?P<meridiem>早|上午|中午|下午|晚上)?\s*"
        r"(?P<start>\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*[-~～至到]\s*"
        r"(?P<end>\d{1,2}:\d{1,2}(?::\d{1,2})?)"
    )
    match = re.search(pattern, raw)
    if not match:
        return None, None

    meridiem_text = (match.group("meridiem") or "").strip()
    start_hm = _parse_time_hm(match.group("start"), meridiem_text)
    end_hm = _parse_time_hm(match.group("end"), meridiem_text)
    if not start_hm or not end_hm:
        return None, None

    start_dt = anchor_date.replace(hour=start_hm[0], minute=start_hm[1], second=0, microsecond=0)
    end_dt = anchor_date.replace(hour=end_hm[0], minute=end_hm[1], second=0, microsecond=0)
    if end_dt < start_dt:
        from datetime import timedelta
        end_dt = end_dt + timedelta(days=1)
    return start_dt, end_dt


def normalize_display_text(text: str | None) -> str:
    """把多行或多空白文本压成单行，适合表格显示。"""
    if not text or not isinstance(text, str):
        return ""
    normalized = re.sub(r"\s+", " ", text.replace("\r", " ").replace("\n", " ")).strip()
    return normalized


def _normalize_campus_prefix_for_display(location: str) -> str:
    """标准化地点前缀：仅保留中关村校区前缀，去掉良乡校区前缀。"""
    if not location:
        return ""

    if "中关村校区" in location:
        return location

    normalized = location.strip()
    normalized = re.sub(r"北京理工大学", "", normalized).strip()
    normalized = re.sub(r"良乡(?:校区)?", "", normalized).strip()
    normalized = re.sub(r"[南北]校区", "", normalized).strip()
    normalized = re.sub(r"\(\s*\)", "", normalized)
    normalized = re.sub(r"（\s*）", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _compress_location_aliases(location: str) -> str:
    """压缩常见地点别名，提升展示简洁度。"""
    if not location:
        return ""
    return location.replace("综合教学楼", "综教")


def _extract_campus_line(*texts: str | None) -> str:
    for text in texts:
        if isinstance(text, str) and "北京理工大学" in text:
            return "北京理工大学"
    return ""


def build_display_location(time_place_text: str | None, fallback_text: str | None = "") -> str:
    """构造 app 中用于显示的地点，优先取 time_place 的第一行地点。"""
    if time_place_text:
        _time_text, place_text = extract_time_place_fields(time_place_text)
        display = normalize_display_text(place_text)
        if display:
            display = _normalize_campus_prefix_for_display(display)
            return _compress_location_aliases(display)
    display = _normalize_campus_prefix_for_display(normalize_display_text(fallback_text))
    return _compress_location_aliases(display)


def build_export_location(display_location: str | None, *sources: str | None) -> str:
    """构造 ICS 导出的地点，第二行补充北京理工大学。"""
    display = _compress_location_aliases(normalize_display_text(display_location))
    campus = _extract_campus_line(*sources)
    if display and campus and campus not in display:
        return f"{display}\n{campus}"
    if display:
        return display
    return campus


def calculate_event_time(data: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    """计算事件的开始和结束时间。
    
    开始时间优先级:
    1. time_place 中提取的活动时间
    2. activity_start_time (API 的活动开始时间)
    3. (sign_in_start_time + sign_in_end_time) / 2 (签到时间窗口的中点)
    4. None (不显示)
    
    结束时间:
    1. sign_out_start_time (签退开始时间)
    2. activity_end_time (API的活动结束时间)
    3. 若开始时间存在，设置为开始时间后2小时
    """
    start_time = None
    end_time = None
    
    source_text = _extract_time_place_source(data)

    # 优先使用文本中的时间区间（通常比签到窗口更接近真实活动时间）。
    range_start, range_end = _extract_time_range(source_text)
    if range_start:
        start_time = range_start
    if range_end:
        end_time = range_end

    if not start_time:
        anchor_date = (
            parse_datetime(str(data.get("activity_start_time") or ""))
            or parse_datetime(str(data.get("sign_in_start_time") or ""))
            or parse_datetime(str(data.get("sign_out_start_time") or ""))
        )
        hm_start, hm_end = _extract_time_only_range(source_text, anchor_date)
        if hm_start:
            start_time = hm_start
        if hm_end:
            end_time = hm_end

    # 仅有开始时间文本时，继续按单点时间解析。
    if not start_time and source_text:
        extracted_time, _ = extract_time_place_fields(source_text)
        start_time = parse_datetime(extracted_time or source_text)

    # 若 time_place 无法解析，再使用 activity_start_time。
    if not start_time:
        activity_start = data.get("activity_start_time")
        if activity_start:
            start_time = parse_datetime(activity_start)
    
    # 若无activity_start_time，尝试使用签到窗口中点
    if not start_time:
        sign_in_start = parse_datetime(data.get("sign_in_start_time", ""))
        sign_in_end = parse_datetime(data.get("sign_in_end_time", ""))
        
        if sign_in_start and sign_in_end:
            # 计算中点
            mid_timestamp = (sign_in_start.timestamp() + sign_in_end.timestamp()) / 2
            start_time = datetime.fromtimestamp(mid_timestamp)
    
    # 计算结束时间：若文本区间结束与签退开始都存在，取较晚值。
    sign_out_start = data.get("sign_out_start_time")
    sign_out_time = parse_datetime(sign_out_start) if sign_out_start else None
    if sign_out_time and end_time:
        end_time = max(end_time, sign_out_time)
    elif sign_out_time and not end_time:
        end_time = sign_out_time
    
    if not end_time:
        activity_end = data.get("activity_end_time")
        if activity_end:
            end_time = parse_datetime(activity_end)
    
    # 若还是没有结束时间但有开始时间，设置为2小时后
    if start_time and not end_time:
        from datetime import timedelta
        end_time = start_time + timedelta(hours=2)
    
    return start_time, end_time


def is_in_checkin_window(data: dict[str, Any]) -> bool:
    """判断当前时间是否在签到窗口内。"""
    now = datetime.now()
    
    sign_in_start = parse_datetime(data.get("sign_in_start_time", ""))
    sign_in_end = parse_datetime(data.get("sign_in_end_time", ""))
    
    if not sign_in_start or not sign_in_end:
        return False
    
    return sign_in_start <= now <= sign_in_end


def is_in_checkout_window(data: dict[str, Any]) -> bool:
    """判断当前时间是否在签退窗口内。"""
    now = datetime.now()
    
    sign_out_start = parse_datetime(data.get("sign_out_start_time", ""))
    sign_out_end = parse_datetime(data.get("sign_out_end_time", ""))
    
    if not sign_out_start or not sign_out_end:
        return False
    
    return sign_out_start <= now <= sign_out_end


def is_event_ended(event: CalendarEvent, now: datetime | None = None) -> bool:
    """判断活动是否已结束，优先使用签退结束时间，其次使用结束时间。"""
    current = now or datetime.now()

    sign_out_end = parse_datetime(event.sign_out_end_time)
    if sign_out_end is not None:
        return current > sign_out_end

    if event.end_time is not None:
        return current > event.end_time

    return False


def parse_event_from_list_my_courses(
    courses: list[dict[str, Any]],
) -> list[CalendarEvent]:
    """将list_my_courses()返回的活动转为CalendarEvent列表。"""
    events = []
    
    for course in courses:
        if not isinstance(course, dict):
            continue
        
        course_id = course.get("id") or course.get("course_id")
        title = course.get("title") or course.get("course_title", "未命名活动")
        
        start_time, end_time = calculate_event_time(course)
        
        # 无有效时间则跳过
        if not start_time:
            continue
        
        # 提取地址（可能是数组）
        address = ""
        sign_in_address = course.get("sign_in_address", [])
        if isinstance(sign_in_address, list) and sign_in_address:
            address = sign_in_address[0].get("address", "")

        time_place = _extract_time_place_source(course)
        display_location = build_display_location(time_place, address)
        
        # 提取类别
        category = ""
        transcript_index = course.get("transcript_index", {})
        if isinstance(transcript_index, dict):
            category = transcript_index.get("transcript_name", "")
        
        # 提取时长
        duration = course.get("duration", "")
        
        event = CalendarEvent(
            id=int(course_id) if course_id else 0,
            title=title,
            start_time=start_time,
            end_time=end_time,
            location=display_location,
            address=address,
            category=category,
            duration=duration,
            score="",  # list_my_courses不含积分信息
            contact_name="",
            contact_phone="",
            is_enrolled=True,
            sign_in_start_time=course.get("sign_in_start_time", ""),
            sign_in_end_time=course.get("sign_in_end_time", ""),
            sign_out_start_time=course.get("sign_out_start_time", ""),
            sign_out_end_time=course.get("sign_out_end_time", ""),
            time_place=time_place,
        )
        events.append(event)
    
    return events


def parse_event_from_list_courses(
    courses: list[dict[str, Any]],
) -> list[CalendarEvent]:
    """将list_courses()返回的未报名活动转为CalendarEvent列表。"""
    events = []
    
    for course in courses:
        if not isinstance(course, dict):
            continue
        
        course_id = course.get("id") or course.get("course_id")
        title = course.get("title", "未命名活动")
        
        start_time, end_time = calculate_event_time(course)
        
        # 无有效时间则跳过
        if not start_time:
            continue
        
        # 提取类别
        category = ""
        transcript_index = course.get("transcript_index", {})
        if isinstance(transcript_index, dict):
            category = transcript_index.get("transcript_name", "")

        # 提取地址（尽量保留原始打卡地点，供 ICS 导出补充第二行）
        address = ""
        sign_in_address = course.get("sign_in_address", [])
        if isinstance(sign_in_address, list) and sign_in_address:
            address = sign_in_address[0].get("address", "")

        time_place = _extract_time_place_source(course)
        display_location = build_display_location(time_place, address)
        
        event = CalendarEvent(
            id=int(course_id) if course_id else 0,
            title=title,
            start_time=start_time,
            end_time=end_time,
            location=display_location,
            address=address,
            category=category,
            duration="",
            score="",
            contact_name="",
            contact_phone="",
            is_enrolled=False,
            sign_in_start_time=course.get("sign_in_start_time", ""),
            sign_in_end_time=course.get("sign_in_end_time", ""),
            sign_out_start_time=course.get("sign_out_start_time", ""),
            sign_out_end_time=course.get("sign_out_end_time", ""),
            time_place=time_place,
        )
        events.append(event)
    
    return events


def enrich_event_with_detail(
    event: CalendarEvent,
    detail: dict[str, Any],
) -> CalendarEvent:
    """用get_course_detail()的完整数据补充CalendarEvent。"""
    # 更新地址和联系方式
    if detail.get("location"):
        event.location = detail["location"]
    
    sign_in_address = detail.get("sign_in_address", [])
    if isinstance(sign_in_address, list) and sign_in_address:
        event.address = sign_in_address[0].get("address", event.address)

    time_place = _extract_time_place_source(detail) or event.time_place or ""
    event.time_place = time_place
    event.location = build_display_location(time_place, event.location or event.address)
    
    # 更新时间（detail中的时间可能更准确）
    start_time, end_time = calculate_event_time(detail)
    if start_time:
        event.start_time = start_time
    if end_time:
        event.end_time = end_time
    
    # 更新联系方式
    if detail.get("contact_name"):
        event.contact_name = detail["contact_name"]
    if detail.get("contact_phone"):
        event.contact_phone = detail["contact_phone"]
    
    # 更新积分信息
    if detail.get("score_method"):
        event.score = detail["score_method"]
    
    # 更新时长
    if detail.get("duration"):
        event.duration = detail["duration"]
    
    return event
