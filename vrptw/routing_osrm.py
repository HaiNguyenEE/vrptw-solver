"""Khoảng cách & thời gian lái xe theo ĐƯỜNG THẬT qua OSRM.

OSRM (Open Source Routing Machine) chạy trên dữ liệu bản đồ OpenStreetMap,
miễn phí, không cần API key. Dùng dịch vụ /table để lấy ma trận khoảng cách
(mét) và thời gian (giây) giữa mọi cặp điểm, rồi quy đổi sang dặm/km & phút.

Lưu ý: máy chủ demo công khai (router.project-osrm.org) giới hạn ~100 điểm và
chỉ nên dùng lượng nhỏ. Có thể tự host OSRM rồi đổi `server`.
"""

from __future__ import annotations

import json
import urllib.request

PUBLIC_SERVER = "https://router.project-osrm.org"

_METERS_TO_MI = 0.000621371
_METERS_TO_KM = 0.001


def table(coords: list[tuple[float, float]], unit: str = "mi",
          server: str = PUBLIC_SERVER, profile: str = "driving",
          timeout: int = 30):
    """Ma trận đường thật cho danh sách (lat, lon).

    Trả về (dist_matrix theo unit, time_matrix theo phút).
    Ném lỗi nếu OSRM không trả 'Ok' hoặc mạng lỗi.
    """
    # OSRM nhận thứ tự lon,lat
    locstr = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coords)
    url = (f"{server}/table/v1/{profile}/{locstr}"
           "?annotations=distance,duration")
    req = urllib.request.Request(url, headers={"User-Agent": "vrptw-solver/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM error: {data.get('code')} {data.get('message','')}")

    factor = _METERS_TO_MI if unit == "mi" else _METERS_TO_KM
    dist_m = data["distances"]   # mét
    dur_s = data["durations"]    # giây
    dist = [[(d or 0.0) * factor for d in row] for row in dist_m]
    time_min = [[(s or 0.0) / 60.0 for s in row] for row in dur_s]
    return dist, time_min
