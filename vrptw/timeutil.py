"""Quy đổi giữa giờ đồng hồ (HH:MM) và phút / clock-time ↔ minutes helpers.

Mô hình bên trong VRPTW dùng "phút kể từ đầu ca" (minutes since shift start).
Người dùng có thể nhập giờ đồng hồ cho dễ; các hàm dưới đây lo việc quy đổi.
"""

from __future__ import annotations


def clock_to_minutes(value: str | float | int) -> float:
    """'HH:MM' (hoặc 'H:MM AM/PM', hoặc số phút) → phút kể từ 00:00.

    Ví dụ: '08:00' → 480, '5:30 PM' → 1050, 90 → 90.
    """
    if value is None or value == "":
        raise ValueError("Giờ trống / empty time")
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().upper()
    ampm = 0
    if s.endswith("AM") or s.endswith("PM"):
        ampm = s[-2:]
        s = s[:-2].strip()
    if ":" in s:
        h, m = s.split(":", 1)
        hh, mm = int(h), int(m)
    else:
        hh, mm = int(s), 0
    if ampm == "PM" and hh != 12:
        hh += 12
    elif ampm == "AM" and hh == 12:
        hh = 0
    return hh * 60 + mm


def minutes_to_clock(minutes: float) -> str:
    """Phút kể từ 00:00 → 'HH:MM' (24h). Cuộn vòng nếu vượt quá 1 ngày."""
    total = int(round(minutes)) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def make_time_formatter(clock_mode: bool, shift_start_min: float):
    """Trả về hàm format(value_in_minutes_since_shift_start) → chuỗi hiển thị.

    - clock_mode=True : hiện 'HH:MM' (cộng lại mốc giờ bắt đầu ca)
    - clock_mode=False: hiện số phút (làm tròn)
    """
    if clock_mode:
        return lambda v: minutes_to_clock(shift_start_min + v)
    return lambda v: f"{v:.0f}"
