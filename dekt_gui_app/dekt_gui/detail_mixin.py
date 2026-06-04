"""Mixin for course detail formatting and HTML generation.

This module provides DetailMixin, which extracts all detail-related
helper methods from MainWindow for better code organization.  Methods
that depend on image handling (``_normalize_media_url``,
``_embedded_image_block``) are assumed to exist on ``self`` via
ImageMixin.
"""

from __future__ import annotations

import re
from html import escape
from typing import Any

from .calendar_utils import build_display_location, extract_time_place_fields
from .constants import STATUS_MAP


class DetailMixin:
    # ------------------------------------------------------------------
    # Simple value helpers
    # ------------------------------------------------------------------

    def _first_non_empty(self: Any, data: dict[str, Any], keys: list[str]) -> str:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() not in {"none", "null"}:
                return text
        return ""

    def _parse_duration_minutes(self: Any, value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(round(float(value)))

        text = str(value).strip()
        if not text:
            return None

        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return int(round(float(text)))

        hour_match = re.search(r"(\d+(?:\.\d+)?)\s*小时", text)
        minute_match = re.search(r"(\d+(?:\.\d+)?)\s*分钟", text)
        if not hour_match and not minute_match:
            return None

        hours = float(hour_match.group(1)) if hour_match else 0.0
        minutes = float(minute_match.group(1)) if minute_match else 0.0
        return int(round(hours * 60 + minutes))

    def _duration_text(self: Any, course_obj: dict[str, Any]) -> str:
        duration_candidates: list[Any] = [
            course_obj.get("duration"),
            course_obj.get("course_duration"),
            course_obj.get("completion_duration"),
            course_obj.get("completion_flag_text"),
        ]

        type_obj = course_obj.get("transcript_index_type")
        if isinstance(type_obj, dict):
            duration_candidates.append(type_obj.get("duration"))

        for candidate in duration_candidates:
            minutes = self._parse_duration_minutes(candidate)
            if minutes is not None and minutes > 0:
                return f"{minutes} 分钟"

        return "无"

    def _score_method_text(self: Any, course_obj: dict[str, Any]) -> str:
        explicit = self._first_non_empty(
            course_obj,
            [
                "completion_flag_text",
                "completion_type_text",
                "score_method",
                "point_method",
                "credit_method",
            ],
        )
        if explicit:
            return explicit

        flag = self._first_non_empty(course_obj, ["completion_flag", "completion_type"]).lower()
        if flag == "time":
            return "按时长累计"
        if flag:
            return f"按{flag}方式累计"

        if self._duration_text(course_obj) != "无":
            return "按时长累计"
        return "按活动要求完成提交"

    def _enroll_status_text(self: Any, course_obj: dict[str, Any]) -> str:
        # 优先读取显式状态字段。
        for key in ["__enrolled", "is_sign", "is_apply", "enrolled", "applied"]:
            if key not in course_obj:
                continue
            value = course_obj.get(key)
            if value in (1, True, "1", "true", "True", "yes", "YES"):
                return "已报名"
            if value in (0, False, "0", "false", "False", "no", "NO"):
                return "未报名"

        status_value = str(course_obj.get("apply_status") or course_obj.get("enroll_status") or "").strip().lower()
        if status_value in {"1", "enrolled", "applied", "success", "signed"}:
            return "已报名"
        if status_value in {"0", "not_enrolled", "none", "unsigned", "cancel"}:
            return "未报名"

        return "未知"

    # ------------------------------------------------------------------
    # HTML / text helpers
    # ------------------------------------------------------------------

    def _section_html(self: Any, title: str, lines: list[str]) -> str:
        if not lines:
            return ""
        safe_lines = "<br>".join(escape(line).replace("\n", "<br>") for line in lines)
        return f"<h3>{escape(title)}</h3><p>{safe_lines}</p>"

    def _is_image_url(self: Any, text: str) -> bool:
        return (
            re.fullmatch(
                r"https?://\S+\.(?:png|jpg|jpeg|gif|webp|bmp)(?:\?\S*)?",
                text.strip(),
                flags=re.IGNORECASE,
            )
            is not None
        )

    def _looks_like_html(self: Any, text: str) -> bool:
        return re.search(r"</?(?:p|div|span|br|img|ul|ol|li|strong|b|h[1-6])(?:\s|>|/)", text, re.IGNORECASE) is not None

    def _plain_text_from_html(self: Any, text: str) -> str:
        # 用于判断 HTML 是否含有效文本，不用于最终展示。
        stripped = re.sub(r"<[^>]+>", " ", text)
        stripped = re.sub(r"\s+", " ", stripped)
        return stripped.strip()

    def _sanitize_detail_html(self: Any, text: str) -> str:
        # 去掉大量内联样式，避免详情显示臃肿难读。
        cleaned = re.sub(r"\sstyle=(\"[^\"]*\"|'[^']*')", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\sclass=(\"[^\"]*\"|'[^']*')", "", cleaned, flags=re.IGNORECASE)
        return cleaned

    def _extract_image_urls(self: Any, text: str) -> list[str]:
        urls: list[str] = []

        for src in re.findall(r"<img\b[^>]*\ssrc=['\"]([^'\"]+)['\"][^>]*>", text, flags=re.IGNORECASE):
            norm = self._normalize_media_url(src)
            if norm:
                urls.append(norm)

        for match in re.findall(
            r"https?://[^\s<\"']+\.(?:png|jpg|jpeg|gif|webp|bmp)(?:\?[^\s<\"']*)?",
            text,
            flags=re.IGNORECASE,
        ):
            norm = self._normalize_media_url(match)
            if norm:
                urls.append(norm)

        uniq: list[str] = []
        for u in urls:
            if u not in uniq:
                uniq.append(u)
        return uniq

    def _activity_detail_section_html(self: Any, detail_text: str) -> str:
        text = (detail_text or "").strip()
        if not text:
            return self._section_html("活动详情", ["无"])

        if self._is_image_url(text):
            img_url = self._normalize_media_url(text)
            img_block = self._embedded_image_block(img_url, width=640)
            if img_block:
                return f"<h3>活动详情</h3>{img_block}"
            return self._section_html("活动详情", ["图片加载失败"])

        if self._looks_like_html(text):
            image_urls = self._extract_image_urls(text)
            cleaned = self._sanitize_detail_html(text)
            cleaned = re.sub(r"<img\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(
                r"https?://[^\s<\"']+\.(?:png|jpg|jpeg|gif|webp|bmp)(?:\?[^\s<\"']*)?",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
            if not self._plain_text_from_html(cleaned):
                if not image_urls:
                    return self._section_html("活动详情", ["无"])
                image_only = "".join(self._embedded_image_block(u, width=640) for u in image_urls)
                if not image_only:
                    return self._section_html("活动详情", ["图片加载失败"])
                return f"<h3>活动详情</h3>{image_only}"

            img_blocks = "".join(self._embedded_image_block(u, width=640) for u in image_urls)
            return f"<h3>活动详情</h3><div>{cleaned}</div>{img_blocks}"

        return self._section_html("活动详情", [text])

    # ------------------------------------------------------------------
    # Detail text extraction
    # ------------------------------------------------------------------

    def _coerce_detail_text(self: Any, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            text = value.strip()
            if text and text.lower() not in {"none", "null"}:
                return text
            return ""
        if isinstance(value, list):
            parts = [self._coerce_detail_text(v) for v in value]
            parts = [p for p in parts if p]
            return "\n".join(parts)
        if isinstance(value, dict):
            for key in ["detail", "content", "description", "intro", "text", "value", "html"]:
                if key in value:
                    text = self._coerce_detail_text(value.get(key))
                    if text:
                        return text
            return ""
        text = str(value).strip()
        if text and text.lower() not in {"none", "null"}:
            return text
        return ""

    def _activity_detail_text(self: Any, course_obj: dict[str, Any]) -> str:
        preferred_keys = [
            "body",
            "detail",
            "content",
            "description",
            "intro",
            "course_detail",
            "course_content",
            "activity_detail",
            "activity_content",
            "summary",
            "remark",
        ]
        image_only_candidates: list[str] = []
        for key in preferred_keys:
            if key in course_obj:
                text = self._coerce_detail_text(course_obj.get(key))
                if text:
                    if self._is_image_url(text):
                        image_only_candidates.append(text)
                        continue
                    return text

        for nested_key in ["course", "info", "item"]:
            nested_obj = course_obj.get(nested_key)
            if isinstance(nested_obj, dict):
                text = self._activity_detail_text(nested_obj)
                if text:
                    if self._is_image_url(text):
                        image_only_candidates.append(text)
                    else:
                        return text

        # 最后兜底：在对象中挑选最长的可读文本字段，避免误显示"无"。
        fallback_candidates: list[str] = []
        for key, value in course_obj.items():
            if key in {
                "id",
                "title",
                "status",
                "status_label",
                "sign_in_start_time",
                "sign_in_end_time",
                "sign_out_start_time",
                "sign_out_end_time",
                "sign_in_address",
            }:
                continue
            text = self._coerce_detail_text(value)
            if self._is_image_url(text):
                image_only_candidates.append(text)
                continue
            if len(text) >= 12:
                fallback_candidates.append(text)

        if fallback_candidates:
            fallback_candidates.sort(key=len, reverse=True)
            return fallback_candidates[0]

        if image_only_candidates:
            return image_only_candidates[0]

        return ""

    # ------------------------------------------------------------------
    # Full course detail HTML
    # ------------------------------------------------------------------

    def _format_course_detail_html(self: Any, course_obj: dict[str, Any]) -> str:
        status_raw = course_obj.get("sign_status")
        try:
            if status_raw is None:
                raise ValueError("empty status")
            status_text = STATUS_MAP.get(int(status_raw), str(status_raw))
        except (TypeError, ValueError):
            status_text = "未知"

        max_count = int(course_obj.get("max", 0) or 0)
        apply_count = int(course_obj.get("course_apply_count", 0) or 0)
        surplus = course_obj.get("surplus")
        if surplus is None:
            surplus_text = str(max_count - apply_count)
        else:
            surplus_text = str(surplus)

        enroll_text = self._enroll_status_text(course_obj)

        cat_name = ""
        cat_obj = course_obj.get("transcript_index")
        if isinstance(cat_obj, dict):
            cat_name = str(cat_obj.get("transcript_name") or "")
        if not cat_name:
            cat_name = self._first_non_empty(course_obj, ["transcript_name", "category_name"]) or "未知"

        section_basic = [
            f"课程ID：{course_obj.get('id', '')}",
            f"课程标题：{self._first_non_empty(course_obj, ['title', 'transcript_name']) or '无'}",
            f"所属栏目：{cat_name}",
            f"课程状态：{status_text}",
            f"积分：{self._first_non_empty(course_obj, ['score', 'credit', 'point']) or '无'}",
            f"时长：{self._duration_text(course_obj)}",
        ]

        section_apply = [
            f"报名开始：{self._first_non_empty(course_obj, ['sign_start_time', 'apply_start_time']) or '无'}",
            f"报名截止：{self._first_non_empty(course_obj, ['sign_end_time', 'apply_end_time']) or '无'}",
            f"人数限制：{max_count if max_count > 0 else '无'}",
            f"已报名人数：{apply_count if apply_count > 0 else '0'}",
            f"剩余名额：{surplus_text}",
            f"报名状态：{enroll_text}",
        ]

        college_limit = self._first_non_empty(course_obj, ['college_limit', 'college', 'academy_limit'])
        grade_limit = self._first_non_empty(course_obj, ['grade_limit', 'grade'])
        type_limit = self._first_non_empty(course_obj, ['type_limit', 'student_type_limit'])

        section_limit_lines: list[str] = []
        if college_limit:
            section_limit_lines.append(f"学院限制：{college_limit}")
        if grade_limit:
            section_limit_lines.append(f"年级限制：{grade_limit}")
        if type_limit:
            section_limit_lines.append(f"类型限制：{type_limit}")

        detail_text = self._activity_detail_text(course_obj)
        cover_url = self._cover_url(course_obj)

        time_place_text = self._first_non_empty(course_obj, ['time_place'])
        parsed_time_text, parsed_place_text = extract_time_place_fields(time_place_text)

        place_text = build_display_location(
            time_place_text,
            self._first_non_empty(course_obj, ['place', 'location', 'address']) or parsed_place_text,
        )
        act_start_text = self._first_non_empty(course_obj, ['activity_start_time', 'start_time']) or parsed_time_text
        act_end_text = self._first_non_empty(course_obj, ['activity_end_time', 'end_time'])

        sign_in_start = self._first_non_empty(course_obj, ['sign_in_start_time'])
        sign_in_end = self._first_non_empty(course_obj, ['sign_in_end_time'])
        sign_out_start = self._first_non_empty(course_obj, ['sign_out_start_time'])
        sign_out_end = self._first_non_empty(course_obj, ['sign_out_end_time'])
        sign_place_text = self._first_non_empty(course_obj, ['sign_place', 'checkin_location'])
        map_name, map_lat, map_lon, map_radius_m = self._extract_checkin_location(course_obj)

        section_time_place = [
            f"地点：{place_text or '无'}",
            f"活动开始：{act_start_text or '无'}",
            f"活动结束：{act_end_text or '无'}",
        ]

        section_checkin_lines = [
            f"签到时间：{sign_in_start or '无'} 至 {sign_in_end or '无'}",
            f"签退时间：{sign_out_start or '无'} 至 {sign_out_end or '无'}",
        ]
        if map_radius_m is not None:
            section_checkin_lines.append(f"签到范围：约 {map_radius_m:.0f} 米")
        if map_lat is not None and map_lon is not None:
            label = map_name or sign_place_text or "打卡地点"
            section_checkin_html_place = f"打卡地点：{escape(label)}（可点下方“显示地图”）"
        elif sign_place_text:
            section_checkin_html_place = f"打卡地点：{escape(sign_place_text)}"
        else:
            section_checkin_html_place = "打卡地点：无"

        contact_name = self._first_non_empty(course_obj, ['contact', 'contact_name', 'teacher'])
        contact_phone = self._first_non_empty(course_obj, ['phone', 'contact_phone', 'mobile'])
        section_contact = [
            f"联系人：{contact_name or '无'}",
            f"联系电话：{contact_phone or '无'}",
        ]

        section_score_method = [f"积分方式：{self._score_method_text(course_obj)}"]

        blocks: list[str] = []
        if cover_url:
            cover_block = self._embedded_image_block(cover_url, width=680)
            if cover_block:
                blocks.append(cover_block)
        blocks.append(self._section_html("基础信息", section_basic))
        blocks.append(self._section_html("报名信息", section_apply))

        if section_limit_lines:
            blocks.append(self._section_html("报名限制", section_limit_lines))

        blocks.append(self._activity_detail_section_html(detail_text))

        has_time_place = any((place_text, act_start_text, act_end_text))
        if has_time_place:
            blocks.append(self._section_html("时间地点", section_time_place))

        has_checkin = any((sign_in_start, sign_in_end, sign_out_start, sign_out_end, sign_place_text))
        if has_checkin:
            checkin_html = "<h3>打卡方式</h3><p>"
            checkin_html += "<br>".join(escape(line) for line in section_checkin_lines)
            checkin_html += "<br>" + section_checkin_html_place + "</p>"
            blocks.append(checkin_html)
        else:
            # 无打卡方式时，展示积分方式。
            blocks.append(self._section_html("积分方式", section_score_method))

        has_contact = any((contact_name, contact_phone))
        if has_contact:
            blocks.append(self._section_html("联系方式", section_contact))

        return "".join(blocks)
