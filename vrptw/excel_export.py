"""Xuất báo cáo Excel kế toán / accounting Excel report (.xlsx).

4 sheet: Summary (tổng hợp), Routes & Costs (chi phí từng xe),
Schedule (lịch trình từng điểm dừng), Input Data (dữ liệu đầu vào).
"""

from __future__ import annotations

import io

import pandas as pd

from .costing import CostParams
from .solution import Solution


def _autofit(ws) -> None:
    """Chỉnh độ rộng cột vừa với nội dung."""
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None),
                    default=8)
        ws.column_dimensions[col[0].column_letter].width = min(width + 3, 60)


def solution_to_excel(sol: Solution, cost_rows: list[dict], totals: dict,
                      params: CostParams, time_fmt=None) -> bytes:
    """Tạo file .xlsx (bytes) — dùng được cho st.download_button hoặc ghi file.

    time_fmt: hàm tùy chọn (phút → chuỗi) để thêm cột giờ đồng hồ.
    """
    inst = sol.instance
    cur = params.currency
    clock = time_fmt is not None

    # ---- Sheet 1: Summary ---------------------------------------------------
    summary = pd.DataFrame([
        ["Solver", sol.solver],
        ["Status", sol.status],
        ["Instance", inst.name],
        ["Customers", inst.n_customers],
        ["Vehicles available", inst.num_vehicles],
        ["Vehicles used", totals.get("vehicles_used", 0)],
        ["Vehicle capacity", inst.vehicle_capacity],
        ["Total distance", totals.get("distance", round(sol.total_distance, 2))],
        ["Total duration (min)", totals.get("duration_min", "")],
        [f"Fuel cost ({cur})", totals.get("fuel", "")],
        [f"Maintenance ({cur})", totals.get("maintenance", "")],
        [f"Labor ({cur})", totals.get("labor", "")],
        [f"Management fee ({cur})", totals.get("mgmt_fee", "")],
        [f"Deductible/Insurance ({cur})", totals.get("deductible", "")],
        [f"TOTAL COST ({cur})", totals.get("total", "")],
        ["", ""],
        ["— Cost parameters —", ""],
        [f"Fuel per distance unit ({cur})", params.fuel_per_unit],
        [f"Maintenance per distance unit ({cur})", params.maintenance_per_unit],
        ["Labor mode", "per distance ($/mile)"
         if params.wage_mode == "per_distance" else "per hour ($/h)"],
        [f"Driver wage per distance ({cur}/mile)", params.wage_per_distance],
        [f"Driver wage per hour ({cur}/h)", params.wage_per_hour],
        [f"Management fee per vehicle ({cur})", params.mgmt_fee_per_vehicle],
        [f"Deductible per vehicle ({cur})", params.deductible_per_vehicle],
    ], columns=["Item", "Value"])

    # ---- Sheet 2: Routes & Costs ---------------------------------------------
    cost_df = pd.DataFrame(cost_rows)
    if not cost_df.empty:
        total_row = {c: totals.get(c, "") for c in cost_df.columns}
        total_row["vehicle"] = "TOTAL"
        total_row["route"] = ""
        total_row["stops"] = sum(x["stops"] for x in cost_rows)
        total_row["load"] = sum(x["load"] for x in cost_rows)
        total_row["depart"] = ""
        total_row["return"] = ""
        cost_df = pd.concat([cost_df, pd.DataFrame([total_row])],
                            ignore_index=True)
        cost_df = cost_df.rename(columns={
            "vehicle": "Vehicle", "route": "Route", "stops": "Stops",
            "load": "Load", "distance": "Distance", "depart": "Depart",
            "return": "Return", "duration_min": "Duration (min)",
            "fuel": f"Fuel ({cur})", "maintenance": f"Maintenance ({cur})",
            "labor": f"Labor ({cur})", "mgmt_fee": f"Mgmt fee ({cur})",
            "deductible": f"Deductible ({cur})", "total": f"Total ({cur})",
        })

    # ---- Sheet 3: Schedule -----------------------------------------------------
    sched_rows = []
    for r in sol.routes:
        if not r.used:
            continue
        for idx, node in enumerate(r.nodes):
            x, y = inst.locations[node]
            a, b = inst.time_windows[node]
            row = {
                "Vehicle": r.vehicle + 1, "Stop #": idx,
                "Node": "Depot" if node == inst.depot else node,
            }
            if inst.addresses:
                row["Address"] = inst.addresses[node]
            else:
                row["X"], row["Y"] = x, y
            row.update({
                "Demand": inst.demands[node],
                "TW ready": a, "TW due": b,
                "Service start": round(r.start_times[idx], 1),
                "Service time": inst.service_times[node],
            })
            if clock:
                row["TW ready (clock)"] = time_fmt(a)
                row["TW due (clock)"] = time_fmt(b)
                row["Service start (clock)"] = time_fmt(r.start_times[idx])
            sched_rows.append(row)
    schedule = pd.DataFrame(sched_rows)

    # ---- Sheet 4: Input data ----------------------------------------------------
    input_rows = []
    for i, (x, y) in enumerate(inst.locations):
        a, b = inst.time_windows[i]
        input_rows.append({
            "node": i, "x": x, "y": y, "demand": inst.demands[i],
            "ready_time": a, "due_time": b,
            "service_time": inst.service_times[i],
        })
    input_df = pd.DataFrame(input_rows)

    # ---- Ghi workbook -------------------------------------------------------------
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="Summary", index=False)
        cost_df.to_excel(xw, sheet_name="Routes & Costs", index=False)
        schedule.to_excel(xw, sheet_name="Schedule", index=False)
        input_df.to_excel(xw, sheet_name="Input Data", index=False)
        for name in xw.sheets:
            _autofit(xw.sheets[name])
    return buf.getvalue()
