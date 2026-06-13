"""Mô hình chi phí vận hành / operating cost model.

Tính chi phí từng tuyến xe từ lời giải VRPTW:
- Nhiên liệu & bảo trì theo quãng đường (fuel & maintenance per distance unit)
- Nhân công theo thời lượng tuyến (driver labor per hour)
- Phí quản lý & phí khấu trừ/bảo hiểm cố định theo xe sử dụng
  (management & deductible/insurance fee per used vehicle)
"""

from __future__ import annotations

from dataclasses import dataclass

from .solution import Solution


@dataclass
class CostParams:
    """Đơn giá chi phí / unit costs. Đơn vị tiền tự chọn (currency symbol).

    Lương tài xế tính theo 1 trong 2 cách (wage_mode):
    - "per_distance" (mặc định): $/dặm — không khuyến khích đi chậm câu giờ
    - "per_hour": $/giờ — theo thời lượng tuyến
    """

    fuel_per_unit: float = 0.15        # nhiên liệu trên 1 đơn vị quãng đường
    maintenance_per_unit: float = 0.05  # bảo trì trên 1 đơn vị quãng đường
    wage_mode: str = "per_distance"    # "per_distance" | "per_hour"
    wage_per_distance: float = 0.60    # lương tài xế trên 1 đơn vị quãng đường ($/dặm)
    wage_per_hour: float = 20.0        # lương tài xế mỗi giờ
    mgmt_fee_per_vehicle: float = 15.0  # phí quản lý mỗi xe sử dụng
    deductible_per_vehicle: float = 10.0  # phí khấu trừ/bảo hiểm mỗi xe sử dụng
    currency: str = "$"


def route_cost_breakdown(sol: Solution, params: CostParams
                         ) -> tuple[list[dict], dict]:
    """Trả về (danh sách chi phí từng xe, tổng hợp).

    Thời lượng tuyến = từ lúc rời depot đến lúc quay về depot, suy ra từ
    thời điểm phục vụ khách đầu/cuối + thời gian di chuyển (phút).
    """
    inst = sol.instance
    dist = inst.distance_matrix
    rows: list[dict] = []

    for r in sol.routes:
        if not r.used:
            continue
        first, last = r.nodes[1], r.nodes[-2]
        # Rời depot muộn nhất có thể để đến khách đầu tiên đúng giờ (không chờ)
        depart = r.start_times[1] - dist[inst.depot][first]
        finish = (r.start_times[-2] + inst.service_times[last]
                  + dist[last][inst.depot])
        duration = max(0.0, finish - depart)  # phút

        fuel = r.distance * params.fuel_per_unit
        maint = r.distance * params.maintenance_per_unit
        if params.wage_mode == "per_hour":
            labor = duration / 60.0 * params.wage_per_hour
        else:  # per_distance — trả theo dặm
            labor = r.distance * params.wage_per_distance
        mgmt = params.mgmt_fee_per_vehicle
        deduct = params.deductible_per_vehicle

        rows.append({
            "vehicle": r.vehicle + 1,
            "route": " → ".join(map(str, r.nodes)),
            "stops": len(r.nodes) - 2,
            "load": r.load,
            "distance": round(r.distance, 2),
            "depart": round(depart, 1),
            "return": round(finish, 1),
            "duration_min": round(duration, 1),
            "fuel": round(fuel, 2),
            "maintenance": round(maint, 2),
            "labor": round(labor, 2),
            "mgmt_fee": round(mgmt, 2),
            "deductible": round(deduct, 2),
            "total": round(fuel + maint + labor + mgmt + deduct, 2),
        })

    totals = {
        "distance": round(sum(x["distance"] for x in rows), 2),
        "duration_min": round(sum(x["duration_min"] for x in rows), 1),
        "fuel": round(sum(x["fuel"] for x in rows), 2),
        "maintenance": round(sum(x["maintenance"] for x in rows), 2),
        "labor": round(sum(x["labor"] for x in rows), 2),
        "mgmt_fee": round(sum(x["mgmt_fee"] for x in rows), 2),
        "deductible": round(sum(x["deductible"] for x in rows), 2),
        "total": round(sum(x["total"] for x in rows), 2),
        "vehicles_used": len(rows),
    }
    return rows, totals
