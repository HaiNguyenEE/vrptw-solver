"""Geocoding địa chỉ → tọa độ (lat, lon) qua OpenStreetMap Nominatim.

Miễn phí, không cần API key. Tôn trọng giới hạn của Nominatim (≤ 1 req/giây)
bằng RateLimiter, và cache kết quả để tránh gọi lại.

Nếu sau này có Google Maps API key, có thể bổ sung provider "google" ở đây.
"""

from __future__ import annotations

import functools

_USER_AGENT = "vrptw-solver/1.0 (routing app)"


@functools.lru_cache(maxsize=2048)
def _geocode_one(address: str, country: str | None = None):
    """Trả về (lat, lon, display_name) cho 1 địa chỉ, hoặc None nếu không thấy."""
    from geopy.geocoders import Nominatim

    geo = Nominatim(user_agent=_USER_AGENT, timeout=10)
    kwargs = {"country_codes": country} if country else {}
    loc = geo.geocode(address, addressdetails=False, **kwargs)
    if loc is None:
        return None
    return (loc.latitude, loc.longitude, loc.address)


def geocode(address: str, country: str | None = None):
    """(lat, lon, display_name) hoặc None. Bao lỗi mạng thành None."""
    try:
        return _geocode_one(address.strip(), country)
    except Exception:
        return None


def suggest(query: str, limit: int = 5, country: str | None = None) -> list[dict]:
    """Gợi ý địa chỉ (autocomplete) — trả về danh sách ứng viên khớp query.

    Mỗi phần tử: {display_name, lat, lon}. Dùng cho dropdown chọn địa chỉ
    để tránh gõ sai.
    """
    if not query or not query.strip():
        return []
    try:
        from geopy.geocoders import Nominatim
        geo = Nominatim(user_agent=_USER_AGENT, timeout=10)
        kwargs = {"country_codes": country} if country else {}
        results = geo.geocode(query.strip(), exactly_one=False, limit=limit,
                              addressdetails=False, **kwargs) or []
        return [{"display_name": r.address, "lat": r.latitude, "lon": r.longitude}
                for r in results]
    except Exception:
        return []


def geocode_many(addresses: list[str], country: str | None = None
                 ) -> tuple[list[tuple[float, float] | None], list[str]]:
    """Geocode một danh sách địa chỉ (tuân thủ ≤1 req/s).

    Trả về (danh sách (lat, lon) hoặc None, danh sách địa chỉ lỗi).
    """
    try:
        from geopy.geocoders import Nominatim
        from geopy.extra.rate_limiter import RateLimiter
    except ImportError as exc:
        raise RuntimeError(
            "Cần cài geopy: pip install geopy") from exc

    geo = Nominatim(user_agent=_USER_AGENT, timeout=10)
    kwargs = {"country_codes": country} if country else {}
    do = RateLimiter(geo.geocode, min_delay_seconds=1.0, max_retries=2,
                     error_wait_seconds=2.0)
    coords: list[tuple[float, float] | None] = []
    errors: list[str] = []
    for addr in addresses:
        cached = _geocode_one.cache_info()  # noqa: F841 (giữ cache ấm)
        try:
            loc = do(addr.strip(), **kwargs)
        except Exception:
            loc = None
        if loc is None:
            coords.append(None)
            errors.append(addr)
        else:
            coords.append((loc.latitude, loc.longitude))
    return coords, errors
