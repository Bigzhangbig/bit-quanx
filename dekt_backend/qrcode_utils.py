from __future__ import annotations


def build_course_qrcode_url(course_id: int) -> str:
    return f"https://qcbldekt.bit.edu.cn/qrcode/event/?course_id={int(course_id)}"
