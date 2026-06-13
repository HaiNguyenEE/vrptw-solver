"""VRPTW Solver App — Streamlit, song ngữ Việt/Anh (bilingual VI/EN).

Người dùng tự nhập dữ liệu (bảng, CSV, hoặc sinh ngẫu nhiên), chọn solver,
nhận lời giải tối ưu kèm biểu đồ và file kết quả.

Chạy / Run:  streamlit run app.py
"""

from __future__ import annotations

import io
import json

import pandas as pd
import streamlit as st

from vrptw import VRPTWInstance, plotting, solver_milp, solver_ortools
from vrptw.costing import CostParams, route_cost_breakdown
from vrptw.excel_export import solution_to_excel

# ===========================================================================
# Song ngữ / Translations
# ===========================================================================
T = {
    "vi": {
        "title": "🚚 VRPTW — Định tuyến xe có ràng buộc khung thời gian",
        "subtitle": "Nhập dữ liệu khách hàng → giải → nhận tuyến đường tối ưu kèm biểu đồ.",
        "lang": "Ngôn ngữ / Language",
        "settings": "⚙️ Cấu hình",
        "solver": "Thuật toán giải",
        "solver_help": "OR-Tools: heuristic nhanh, phù hợp bài lớn. MILP (CBC): tối ưu chứng minh được, phù hợp ≤ ~25 khách hàng.",
        "vehicles": "Số xe",
        "capacity": "Sức chứa mỗi xe",
        "time_limit": "Giới hạn thời gian giải (giây)",
        "data": "📋 Dữ liệu bài toán",
        "data_help": "Hàng đầu tiên (node 0) là **depot** (kho). Mỗi hàng sau là một khách hàng. Thêm/xóa hàng trực tiếp trong bảng. Xem mục **📖 Giải thích các cột** ngay dưới để hiểu rõ từng tham số.",
        "cols_guide": "📖 Giải thích các cột dữ liệu",
        "cols_guide_body": """
**Đơn vị thời gian:** bạn tự chọn một đơn vị thống nhất cho cả bài (phút hoặc giờ). Cách phổ biến là tính theo **phút kể từ đầu ca** — ví dụ ca bắt đầu 8:00 sáng thì mốc 0 = 8:00, mốc 120 = 10:00, mốc 540 = 17:00. Mọi cột thời gian (`ready_time`, `due_time`, `service_time`) và quãng đường phải dùng **cùng một đơn vị**.

| Cột | Ý nghĩa | Cách xác định |
|---|---|---|
| **node** | Số thứ tự điểm. `0` = kho (depot). | Tự đánh số, app tự sắp lại. |
| **x, y** | Tọa độ điểm trên mặt phẳng. | Lấy từ bản đồ/GPS (km), hoặc tọa độ tương đối. Khoảng cách giữa 2 điểm = đường chim bay, dùng làm cả quãng đường **và** thời gian di chuyển. |
| **demand** | Lượng hàng khách cần nhận. | Cùng đơn vị với *sức chứa xe* (thùng, kg, pallet…). Depot = 0. |
| **ready_time** | Thời điểm **sớm nhất** được bắt đầu giao. Đến sớm hơn thì xe phải **chờ**. | Khách mở cửa lúc nào? VD khách nhận hàng từ 9:00 → nếu mốc 0 = 8:00 thì `ready_time = 60`. |
| **due_time** | Thời điểm **muộn nhất** được bắt đầu giao. Đến trễ hơn → tuyến **không hợp lệ**. | Hạn chót khách nhận. VD chỉ nhận đến 11:00 → `due_time = 180`. Khoảng `[ready_time, due_time]` chính là **khung giờ** của khách. |
| **service_time** | Thời gian đỗ lại để giao/bốc dỡ tại khách đó. | Ước lượng thực tế: bốc dỡ + ký nhận. VD mất 5 phút → `service_time = 5`. |

**Mẹo:** muốn khách nhận bất cứ lúc nào trong ngày thì để `ready_time = 0` và `due_time` = một số lớn (vd 1000). Depot thường để khung rộng `[0, 1000]` để xe xuất phát/về tự do.
""",
        "load_sample": "📦 Nạp dữ liệu mẫu",
        "gen_random": "🎲 Sinh ngẫu nhiên",
        "n_random": "Số khách hàng (ngẫu nhiên)",
        "upload": "Hoặc tải lên file CSV (cột: node,x,y,demand,ready_time,due_time,service_time)",
        "solve": "🚀 Giải bài toán",
        "solving": "Đang giải...",
        "status": "Trạng thái",
        "total_dist": "Tổng quãng đường",
        "veh_used": "Số xe sử dụng",
        "runtime": "Thời gian giải",
        "routes_tab": "🗺️ Bản đồ tuyến",
        "gantt_tab": "📅 Lịch phục vụ",
        "detail_tab": "📄 Chi tiết",
        "route_detail": "Chi tiết tuyến đường",
        "col_vehicle": "Xe", "col_route": "Tuyến", "col_times": "Thời điểm phục vụ",
        "col_load": "Tải", "col_dist": "Quãng đường",
        "download_json": "⬇️ Tải lời giải (JSON)",
        "download_csv": "⬇️ Tải lịch trình (CSV)",
        "download_xlsx": "📊 Xuất Excel kế toán (.xlsx)",
        "costs": "💰 Chi phí vận hành",
        "costs_help": "Đơn giá để tính chi phí mỗi tuyến: nhiên liệu & bảo trì theo quãng đường, lương tài xế theo giờ, phí quản lý & khấu trừ theo xe sử dụng.",
        "fuel_cost": "Nhiên liệu / đơn vị quãng đường",
        "maint_cost": "Bảo trì / đơn vị quãng đường",
        "wage_mode": "Cách trả lương tài xế",
        "wage_mode_dist": "Theo dặm ($/mile)",
        "wage_mode_hour": "Theo giờ ($/giờ)",
        "wage_mode_help": "Trả theo dặm tránh việc tài xế đi chậm để câu giờ.",
        "wage_dist": "Lương tài xế / dặm",
        "wage": "Lương tài xế / giờ",
        "mgmt_fee": "Phí quản lý / xe",
        "deduct_fee": "Phí khấu trừ (bảo hiểm) / xe",
        "currency": "Ký hiệu tiền tệ",
        "costs_tab": "💰 Chi phí",
        "total_cost": "Tổng chi phí",
        "cost_table": "Chi phí từng xe (thời gian tính bằng phút, lương quy đổi theo giờ)",
        "cost_chart": "Cơ cấu chi phí theo xe",
        "valid": "✔ Lời giải hợp lệ — thỏa mãn mọi ràng buộc (mỗi khách 1 lần, tải trọng, khung thời gian).",
        "invalid": "✘ Lời giải vi phạm ràng buộc:",
        "no_solution": "Không tìm thấy lời giải khả thi. Hãy nới khung thời gian, tăng số xe hoặc sức chứa.",
        "err_data": "Dữ liệu không hợp lệ: ",
        "err_capacity": "Tổng nhu cầu ({total}) vượt tổng sức chứa đội xe ({cap}). Tăng số xe hoặc sức chứa.",
        "guide": "ℹ️ Hướng dẫn",
        "guide_body": """
**Cách dùng:**
1. Nhập dữ liệu vào bảng (hoặc nạp mẫu / sinh ngẫu nhiên / tải CSV).
2. Chỉnh số xe, sức chứa, thuật toán ở thanh bên trái.
3. Bấm **Giải bài toán** — app tự động tính toán và vẽ kết quả.

**Ý nghĩa cột:** `x, y` — tọa độ; `demand` — nhu cầu hàng; `ready_time / due_time` — thời điểm sớm nhất / muộn nhất được bắt đầu phục vụ; `service_time` — thời gian phục vụ tại chỗ.

Khoảng cách Euclid được dùng làm cả chi phí lẫn thời gian di chuyển (tốc độ = 1).
""",
    },
    "en": {
        "title": "🚚 VRPTW — Vehicle Routing with Time Windows",
        "subtitle": "Enter customer data → solve → get optimal routes with charts.",
        "lang": "Ngôn ngữ / Language",
        "settings": "⚙️ Settings",
        "solver": "Solver",
        "solver_help": "OR-Tools: fast heuristic, good for large instances. MILP (CBC): provably optimal, good for ≤ ~25 customers.",
        "vehicles": "Number of vehicles",
        "capacity": "Capacity per vehicle",
        "time_limit": "Solver time limit (seconds)",
        "data": "📋 Problem data",
        "data_help": "The first row (node 0) is the **depot**. Each following row is a customer. Add/remove rows directly in the table. See **📖 Column reference** below to understand each parameter.",
        "cols_guide": "📖 Column reference (what each field means)",
        "cols_guide_body": """
**Time unit:** pick one consistent unit for the whole problem (minutes or hours). The common convention is **minutes since shift start** — e.g. if the shift starts at 8:00 AM, then 0 = 8:00, 120 = 10:00, 540 = 5:00 PM. All time columns (`ready_time`, `due_time`, `service_time`) and distances must use the **same unit**.

| Column | Meaning | How to determine |
|---|---|---|
| **node** | Point index. `0` = warehouse (depot). | Just number them; the app re-indexes automatically. |
| **x, y** | Point coordinates on a plane. | From a map/GPS (km) or relative coords. Distance between two points = straight-line, used as both travel distance **and** travel time. |
| **demand** | Goods the customer needs. | Same unit as *vehicle capacity* (boxes, kg, pallets…). Depot = 0. |
| **ready_time** | **Earliest** time service may start. Arrive earlier → the vehicle **waits**. | When does the customer open? E.g. receives from 9:00 → if 0 = 8:00, then `ready_time = 60`. |
| **due_time** | **Latest** time service may start. Arrive later → route is **infeasible**. | Customer's cutoff. E.g. only until 11:00 → `due_time = 180`. The range `[ready_time, due_time]` is the customer's **time window**. |
| **service_time** | Time parked to unload/serve at that stop. | Real estimate: unloading + sign-off. E.g. 5 minutes → `service_time = 5`. |

**Tip:** to let a customer be served anytime, set `ready_time = 0` and a large `due_time` (e.g. 1000). The depot usually has a wide window `[0, 1000]` so vehicles can leave/return freely.
""",
        "load_sample": "📦 Load sample data",
        "gen_random": "🎲 Generate random",
        "n_random": "Number of customers (random)",
        "upload": "Or upload a CSV file (columns: node,x,y,demand,ready_time,due_time,service_time)",
        "solve": "🚀 Solve",
        "solving": "Solving...",
        "status": "Status",
        "total_dist": "Total distance",
        "veh_used": "Vehicles used",
        "runtime": "Solve time",
        "routes_tab": "🗺️ Route map",
        "gantt_tab": "📅 Schedule",
        "detail_tab": "📄 Details",
        "route_detail": "Route details",
        "col_vehicle": "Vehicle", "col_route": "Route", "col_times": "Service start times",
        "col_load": "Load", "col_dist": "Distance",
        "download_json": "⬇️ Download solution (JSON)",
        "download_csv": "⬇️ Download schedule (CSV)",
        "download_xlsx": "📊 Export accounting Excel (.xlsx)",
        "costs": "💰 Operating costs",
        "costs_help": "Unit prices used to compute per-route costs: fuel & maintenance per distance, driver wage per hour, management & deductible fees per used vehicle.",
        "fuel_cost": "Fuel / distance unit",
        "maint_cost": "Maintenance / distance unit",
        "wage_mode": "Driver pay mode",
        "wage_mode_dist": "Per mile ($/mile)",
        "wage_mode_hour": "Per hour ($/h)",
        "wage_mode_help": "Paying per mile avoids drivers going slow to rack up hours.",
        "wage_dist": "Driver wage / mile",
        "wage": "Driver wage / hour",
        "mgmt_fee": "Management fee / vehicle",
        "deduct_fee": "Deductible (insurance) / vehicle",
        "currency": "Currency symbol",
        "costs_tab": "💰 Costs",
        "total_cost": "Total cost",
        "cost_table": "Per-vehicle costs (time in minutes, labor converted hourly)",
        "cost_chart": "Cost structure by vehicle",
        "valid": "✔ Solution is valid — all constraints satisfied (each customer once, capacity, time windows).",
        "invalid": "✘ Solution violates constraints:",
        "no_solution": "No feasible solution found. Try widening time windows, adding vehicles or capacity.",
        "err_data": "Invalid data: ",
        "err_capacity": "Total demand ({total}) exceeds total fleet capacity ({cap}). Add vehicles or capacity.",
        "guide": "ℹ️ How to use",
        "guide_body": """
**Steps:**
1. Enter data in the table (or load sample / generate random / upload CSV).
2. Adjust vehicles, capacity and solver in the left sidebar.
3. Click **Solve** — the app computes and plots everything automatically.

**Columns:** `x, y` — coordinates; `demand` — goods demand; `ready_time / due_time` — earliest / latest service start; `service_time` — on-site service duration.

Euclidean distance is used as both cost and travel time (speed = 1).
""",
    },
}

COLS = ["node", "x", "y", "demand", "ready_time", "due_time", "service_time"]


def instance_to_df(inst: VRPTWInstance) -> pd.DataFrame:
    rows = []
    for i, (x, y) in enumerate(inst.locations):
        a, b = inst.time_windows[i]
        rows.append([i, x, y, inst.demands[i], a, b, inst.service_times[i]])
    return pd.DataFrame(rows, columns=COLS)


def df_to_instance(df: pd.DataFrame, num_vehicles: int,
                   capacity: int) -> VRPTWInstance:
    df = df.dropna().copy()
    df["node"] = range(len(df))  # đánh lại số node theo thứ tự hàng
    inst = VRPTWInstance(
        name="user_input",
        locations=[(float(r.x), float(r.y)) for r in df.itertuples()],
        demands=[int(r.demand) for r in df.itertuples()],
        time_windows=[(int(r.ready_time), int(r.due_time)) for r in df.itertuples()],
        service_times=[int(r.service_time) for r in df.itertuples()],
        num_vehicles=num_vehicles,
        vehicle_capacity=capacity,
    )
    return inst


# ===========================================================================
# Giao diện / UI
# ===========================================================================
st.set_page_config(page_title="VRPTW Solver", page_icon="🚚", layout="wide")

lang_choice = st.sidebar.radio("Ngôn ngữ / Language", ["Tiếng Việt", "English"],
                               horizontal=True, key="lang")
lang = "vi" if lang_choice == "Tiếng Việt" else "en"
t = T[lang]

st.title(t["title"])
st.caption(t["subtitle"])

# ---- Sidebar: cấu hình / settings -----------------------------------------
st.sidebar.header(t["settings"])
solver_name = st.sidebar.selectbox(
    t["solver"], ["OR-Tools (heuristic)", "MILP — CBC (exact)"],
    help=t["solver_help"], key="solver")
num_vehicles = st.sidebar.number_input(t["vehicles"], 1, 50, 3, key="vehicles")
capacity = st.sidebar.number_input(t["capacity"], 1, 100000, 10, key="capacity")
time_limit = st.sidebar.slider(t["time_limit"], 1, 300, 10, key="time_limit")

# ---- Sidebar: chi phí / cost parameters ------------------------------------
with st.sidebar.expander(t["costs"], expanded=False):
    st.caption(t["costs_help"])
    currency = st.text_input(t["currency"], "$", max_chars=4, key="currency")
    fuel_cost = st.number_input(t["fuel_cost"], 0.0, 1e6, 0.15, step=0.01,
                                format="%.3f", key="fuel_cost")
    maint_cost = st.number_input(t["maint_cost"], 0.0, 1e6, 0.05, step=0.01,
                                 format="%.3f", key="maint_cost")
    wage_mode_label = st.radio(t["wage_mode"],
                               [t["wage_mode_dist"], t["wage_mode_hour"]],
                               help=t["wage_mode_help"], key="wage_mode")
    if wage_mode_label == t["wage_mode_dist"]:
        wage_mode = "per_distance"
        wage_dist = st.number_input(t["wage_dist"], 0.0, 1e6, 0.60, step=0.05,
                                    format="%.2f", key="wage_dist")
        wage = 20.0
    else:
        wage_mode = "per_hour"
        wage = st.number_input(t["wage"], 0.0, 1e6, 20.0, step=1.0, key="wage")
        wage_dist = 0.60
    mgmt_fee = st.number_input(t["mgmt_fee"], 0.0, 1e6, 15.0, step=1.0,
                               key="mgmt_fee")
    deduct_fee = st.number_input(t["deduct_fee"], 0.0, 1e6, 10.0, step=1.0,
                                 key="deduct_fee")

cost_params = CostParams(
    fuel_per_unit=float(fuel_cost), maintenance_per_unit=float(maint_cost),
    wage_mode=wage_mode, wage_per_distance=float(wage_dist),
    wage_per_hour=float(wage), mgmt_fee_per_vehicle=float(mgmt_fee),
    deductible_per_vehicle=float(deduct_fee), currency=currency or "$")

with st.sidebar.expander(t["guide"]):
    st.markdown(t["guide_body"])

# ---- Dữ liệu / data ---------------------------------------------------------
st.header(t["data"])
st.markdown(t["data_help"])

with st.expander(t["cols_guide"]):
    st.markdown(t["cols_guide_body"])

if "df" not in st.session_state:
    st.session_state.df = instance_to_df(VRPTWInstance.sample())

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button(t["load_sample"], width="stretch"):
        st.session_state.df = instance_to_df(VRPTWInstance.sample())
with c2:
    n_rand = st.number_input(t["n_random"], 3, 60, 12, label_visibility="collapsed", key="n_rand")
    if st.button(t["gen_random"], width="stretch"):
        st.session_state.df = instance_to_df(VRPTWInstance.random(
            n_customers=int(n_rand), num_vehicles=int(num_vehicles),
            vehicle_capacity=int(capacity)))
with c3:
    uploaded = st.file_uploader(t["upload"], type="csv", label_visibility="collapsed")
    if uploaded is not None:
        st.session_state.df = pd.read_csv(uploaded)[COLS]

edited_df = st.data_editor(st.session_state.df, num_rows="dynamic",
                           width="stretch", hide_index=True)

# ---- Giải / solve -----------------------------------------------------------
if st.button(t["solve"], type="primary", width="stretch"):
    try:
        inst = df_to_instance(edited_df, int(num_vehicles), int(capacity))
        total, cap = sum(inst.demands), int(num_vehicles) * int(capacity)
        if total > cap:
            st.error(t["err_capacity"].format(total=total, cap=cap))
            st.stop()
        inst.validate()
    except Exception as exc:  # dữ liệu sai định dạng / malformed data
        st.error(t["err_data"] + str(exc))
        st.stop()

    solve_fn = (solver_ortools.solve if solver_name.startswith("OR-Tools")
                else solver_milp.solve)
    with st.spinner(t["solving"]):
        sol = solve_fn(inst, time_limit_s=int(time_limit))

    if not sol.routes:
        st.error(t["no_solution"])
        st.stop()

    # ---- Kết quả / results ---------------------------------------------------
    cost_rows, cost_totals = route_cost_breakdown(sol, cost_params)

    st.markdown(f"**{t['status']}:** {sol.status}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t["total_dist"], f"{sol.total_distance:.2f}")
    m2.metric(t["veh_used"], f"{sol.vehicles_used}/{inst.num_vehicles}")
    m3.metric(t["total_cost"], f"{cost_params.currency}{cost_totals['total']:,.2f}")
    m4.metric(t["runtime"], f"{sol.runtime_s:.2f}s")

    errors = sol.verify()
    if errors:
        st.error(t["invalid"])
        for e in errors:
            st.write("- " + e)
    else:
        st.success(t["valid"])

    tab1, tab2, tab_cost, tab3 = st.tabs(
        [t["routes_tab"], t["gantt_tab"], t["costs_tab"], t["detail_tab"]])
    with tab1:
        st.pyplot(plotting.plot_routes(sol, lang=lang))
    with tab2:
        st.pyplot(plotting.plot_schedule(sol, lang=lang))
    with tab_cost:
        st.subheader(t["cost_table"])
        cur = cost_params.currency
        cost_view = pd.DataFrame(cost_rows).rename(columns={
            "vehicle": t["col_vehicle"], "route": t["col_route"],
            "stops": "Stops", "load": t["col_load"],
            "distance": t["col_dist"], "depart": "Depart", "return": "Return",
            "duration_min": "Duration (min)",
            "fuel": f"⛽ Fuel ({cur})", "maintenance": f"🔧 Maint. ({cur})",
            "labor": f"👷 Labor ({cur})", "mgmt_fee": f"🗂 Mgmt ({cur})",
            "deductible": f"🛡 Deduct. ({cur})", "total": f"Σ Total ({cur})",
        })
        st.dataframe(cost_view, width="stretch", hide_index=True)
        st.subheader(t["cost_chart"])
        chart_df = pd.DataFrame(cost_rows).set_index("vehicle")[
            ["fuel", "maintenance", "labor", "mgmt_fee", "deductible"]]
        chart_df.index = [f"{t['col_vehicle']} {v}" for v in chart_df.index]
        st.bar_chart(chart_df, stack=True)
    with tab3:
        st.subheader(t["route_detail"])
        rows = []
        for r in sol.routes:
            if not r.used:
                continue
            rows.append({
                t["col_vehicle"]: r.vehicle + 1,
                t["col_route"]: " → ".join(map(str, r.nodes)),
                t["col_times"]: ", ".join(f"{x:.0f}" for x in r.start_times),
                t["col_load"]: f"{r.load}/{inst.vehicle_capacity}",
                t["col_dist"]: round(r.distance, 2),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    # ---- Tải xuống / downloads ----------------------------------------------
    sol_json = {
        "solver": sol.solver, "status": sol.status,
        "objective_total_distance": round(sol.total_distance, 3),
        "routes": [{"vehicle": r.vehicle + 1, "nodes": r.nodes,
                    "service_start_times": [round(x, 2) for x in r.start_times],
                    "load": r.load, "distance": round(r.distance, 3)}
                   for r in sol.routes if r.used],
    }
    schedule_rows = []
    for r in sol.routes:
        for idx, node in enumerate(r.nodes):
            schedule_rows.append({"vehicle": r.vehicle + 1, "stop": idx,
                                  "node": node,
                                  "service_start": round(r.start_times[idx], 2)})
    csv_buf = io.StringIO()
    pd.DataFrame(schedule_rows).to_csv(csv_buf, index=False)

    xlsx_bytes = solution_to_excel(sol, cost_rows, cost_totals, cost_params)

    d1, d2, d3 = st.columns(3)
    d1.download_button(t["download_xlsx"], xlsx_bytes,
                       file_name="vrptw_report.xlsx",
                       mime=("application/vnd.openxmlformats-officedocument"
                             ".spreadsheetml.sheet"),
                       type="primary", width="stretch")
    d2.download_button(t["download_json"],
                       json.dumps(sol_json, ensure_ascii=False, indent=2),
                       file_name="vrptw_solution.json", mime="application/json",
                       width="stretch")
    d3.download_button(t["download_csv"], csv_buf.getvalue(),
                       file_name="vrptw_schedule.csv", mime="text/csv",
                       width="stretch")
