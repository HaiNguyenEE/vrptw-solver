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
from vrptw.timeutil import clock_to_minutes, make_time_formatter, minutes_to_clock
from vrptw import geocode, routing_osrm

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
        "loc_mode": "Cách nhập vị trí",
        "loc_xy": "Tọa độ X, Y",
        "loc_addr": "Địa chỉ thật",
        "loc_help": "Chọn 'Địa chỉ thật' để nhập địa chỉ giao hàng — app sẽ tự tìm tọa độ (OpenStreetMap) và tính khoảng cách.",
        "avg_speed": "Tốc độ trung bình",
        "dist_unit": "Đơn vị khoảng cách",
        "road_factor": "Hệ số đường thực (so với chim bay)",
        "country": "Giới hạn quốc gia (mã 2 chữ, để trống nếu không)",
        "depot_addr": "📍 Địa chỉ kho (depot)",
        "addr_search": "🔎 Tìm & thêm địa chỉ giao hàng",
        "addr_query": "Gõ địa chỉ để tìm gợi ý",
        "addr_find": "🔎 Tìm",
        "addr_pick": "Chọn địa chỉ đúng",
        "addr_add": "➕ Thêm vào bảng",
        "addr_none": "Không tìm thấy gợi ý. Thử gõ chi tiết hơn (số nhà, đường, thành phố).",
        "depot_find": "🔎 Tìm kho",
        "depot_set": "✅ Đặt làm kho",
        "depot_current": "Kho hiện tại",
        "geocoding": "Đang tìm tọa độ các địa chỉ…",
        "routing": "Đang tính quãng đường lái xe theo đường thật (OSRM)…",
        "routing_ok": "✅ Khoảng cách & thời gian tính theo đường thật (OSRM / OpenStreetMap).",
        "routing_fail": "⚠️ Không kết nối được OSRM — tạm dùng khoảng cách chim bay × hệ số đường và tốc độ trung bình.",
        "geo_err": "Không tìm được tọa độ cho: ",
        "addr_col": "Địa chỉ",
        "no_depot": "Hãy đặt địa chỉ kho (depot) trước khi giải.",
        "no_customers": "Hãy thêm ít nhất một địa chỉ giao hàng.",
        "time_mode": "Định dạng thời gian",
        "time_mode_clock": "Giờ đồng hồ (HH:MM)",
        "time_mode_min": "Số phút",
        "time_mode_help": "Chọn 'Giờ đồng hồ' để nhập 08:00, 17:30… cho dễ — app tự quy đổi sang phút.",
        "shift_start": "Giờ bắt đầu ca (mốc 0)",
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
        "cost_scroll_hint": "↔ Kéo thanh cuộn ngang dưới bảng để xem hết các cột. Cột 'Tuyến' đầy đủ ở tab Chi tiết.",
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
        "loc_mode": "Location input",
        "loc_xy": "X, Y coordinates",
        "loc_addr": "Real addresses",
        "loc_help": "Pick 'Real addresses' to type delivery addresses — the app finds coordinates (OpenStreetMap) and computes distances.",
        "avg_speed": "Average speed",
        "dist_unit": "Distance unit",
        "road_factor": "Road factor (vs straight-line)",
        "country": "Country filter (2-letter code, blank = none)",
        "depot_addr": "📍 Depot (warehouse) address",
        "addr_search": "🔎 Find & add a delivery address",
        "addr_query": "Type an address to get suggestions",
        "addr_find": "🔎 Search",
        "addr_pick": "Pick the correct address",
        "addr_add": "➕ Add to table",
        "addr_none": "No suggestions found. Try a more detailed address (number, street, city).",
        "depot_find": "🔎 Search depot",
        "depot_set": "✅ Set as depot",
        "depot_current": "Current depot",
        "geocoding": "Finding coordinates for addresses…",
        "routing": "Computing real driving distances (OSRM)…",
        "routing_ok": "✅ Distances & times use the real road network (OSRM / OpenStreetMap).",
        "routing_fail": "⚠️ Could not reach OSRM — falling back to straight-line × road factor and average speed.",
        "geo_err": "Could not geocode: ",
        "addr_col": "Address",
        "no_depot": "Set a depot address before solving.",
        "no_customers": "Add at least one delivery address.",
        "time_mode": "Time format",
        "time_mode_clock": "Clock time (HH:MM)",
        "time_mode_min": "Minutes",
        "time_mode_help": "Pick 'Clock time' to enter 08:00, 5:30 PM… for convenience — the app converts to minutes for you.",
        "shift_start": "Shift start time (the 0 mark)",
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
        "cost_scroll_hint": "↔ Drag the horizontal scrollbar below the table to see all columns. Full 'Route' is in the Details tab.",
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


ADDR_COLS = ["address", "demand", "ready_time", "due_time", "service_time"]


def sample_addr_df() -> pd.DataFrame:
    """Vài địa chỉ phố thật (Long Beach, CA) để thử nhanh chế độ địa chỉ.

    Đây chỉ là ví dụ — hãy dùng ô '🔎 Tìm & thêm địa chỉ' để nhập địa chỉ thật
    của bạn (có gợi ý tự động để tránh gõ sai).
    """
    rows = [
        ["100 Aquarium Way, Long Beach, CA 90802", 2, 0, 120, 10],
        ["1250 Bellflower Blvd, Long Beach, CA 90840", 3, 0, 180, 10],
        ["4100 Donald Douglas Dr, Long Beach, CA 90808", 4, 30, 200, 15],
        ["95 S Pine Ave, Long Beach, CA 90802", 2, 20, 160, 10],
    ]
    return pd.DataFrame(rows, columns=ADDR_COLS)


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

# ---- Chế độ vị trí / location mode -----------------------------------------
loc_mode_label = st.sidebar.radio(
    t["loc_mode"], [t["loc_addr"], t["loc_xy"]], help=t["loc_help"],
    key="loc_mode")
addr_mode = loc_mode_label == t["loc_addr"]
if addr_mode:
    unit_choice = st.sidebar.selectbox(t["dist_unit"], ["mi", "km"], key="dist_unit")
    default_speed = 30.0 if unit_choice == "mi" else 50.0
    avg_speed = st.sidebar.number_input(
        f"{t['avg_speed']} ({unit_choice}/h)", 1.0, 200.0, default_speed,
        step=1.0, key="avg_speed")
    road_factor = st.sidebar.number_input(t["road_factor"], 1.0, 2.0, 1.3,
                                          step=0.05, key="road_factor")
    country = st.sidebar.text_input(t["country"], "", max_chars=2,
                                    key="country").strip().lower() or None
else:
    unit_choice, avg_speed, road_factor, country = "unit", 1.0, 1.0, None

# ---- Chế độ thời gian / time format ----------------------------------------
time_mode_label = st.sidebar.radio(
    t["time_mode"], [t["time_mode_clock"], t["time_mode_min"]],
    help=t["time_mode_help"], key="time_mode")
clock_mode = time_mode_label == t["time_mode_clock"]
if clock_mode:
    shift_start_str = st.sidebar.text_input(t["shift_start"], "08:00",
                                            key="shift_start")
    try:
        shift_start_min = clock_to_minutes(shift_start_str)
    except Exception:
        shift_start_min = 8 * 60
else:
    shift_start_min = 0.0
time_fmt = make_time_formatter(clock_mode, shift_start_min)

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

# Cache geocoding để không gọi mạng lại mỗi lần rerun
@st.cache_data(show_spinner=False)
def cached_suggest(query: str, country):
    return geocode.suggest(query, 6, country)


@st.cache_data(show_spinner=False)
def cached_geocode_many(addr_tuple, country):
    return geocode.geocode_many(list(addr_tuple), country)


@st.cache_data(show_spinner=False)
def cached_osrm_table(coords_tuple, unit):
    return routing_osrm.table([tuple(c) for c in coords_tuple], unit=unit)


# Giá trị mặc định cho ô bỏ trống ở hàng mới / defaults for blank cells
DEF_READY = 0.0       # phút kể từ đầu ca (= giờ bắt đầu ca)
DEF_DUE = 480.0       # khung giờ rộng 8 tiếng (không cuộn qua nửa đêm)
DEF_SERVICE = 10.0    # phút phục vụ
DEF_DEMAND = 1


def _empty(v) -> bool:
    """True nếu ô trống/None/NaN."""
    if v is None:
        return True
    try:
        if isinstance(v, float) and pd.isna(v):
            return True
    except Exception:
        pass
    return str(v).strip() in ("", "None", "nan", "NaN")


def _clock_editor(df):
    """Hiển thị bảng với ready/due theo HH:MM (nếu clock_mode); trả df đã quy đổi phút."""
    if clock_mode:
        disp = df.copy()
        disp["ready_time"] = disp["ready_time"].apply(
            lambda v: "" if _empty(v) else minutes_to_clock(shift_start_min + float(v)))
        disp["due_time"] = disp["due_time"].apply(
            lambda v: "" if _empty(v) else minutes_to_clock(shift_start_min + float(v)))
        disp = disp.rename(columns={"ready_time": "ready (HH:MM)",
                                    "due_time": "due (HH:MM)",
                                    "service_time": "service (min)"})
        ed = st.data_editor(disp, num_rows="dynamic", width="stretch",
                            hide_index=True)
        ed = ed.rename(columns={"ready (HH:MM)": "ready_time",
                                "due (HH:MM)": "due_time",
                                "service (min)": "service_time"})
        # Hàng mới có thể bỏ trống → dùng mặc định, tránh lỗi parse
        ed["ready_time"] = ed["ready_time"].apply(
            lambda v: DEF_READY if _empty(v) else clock_to_minutes(v) - shift_start_min)
        ed["due_time"] = ed["due_time"].apply(
            lambda v: DEF_DUE if _empty(v) else clock_to_minutes(v) - shift_start_min)
        ed["service_time"] = ed["service_time"].apply(
            lambda v: DEF_SERVICE if _empty(v) else float(v))
        return ed
    ed = st.data_editor(df, num_rows="dynamic", width="stretch", hide_index=True)
    ed["ready_time"] = ed["ready_time"].apply(
        lambda v: DEF_READY if _empty(v) else float(v))
    ed["due_time"] = ed["due_time"].apply(
        lambda v: DEF_DUE if _empty(v) else float(v))
    ed["service_time"] = ed["service_time"].apply(
        lambda v: DEF_SERVICE if _empty(v) else float(v))
    return ed


# ---- Dữ liệu / data ---------------------------------------------------------
st.header(t["data"])
edited_df = None          # chế độ X/Y
edited_addr_df = None     # chế độ địa chỉ

if not addr_mode:
    # ===================== CHẾ ĐỘ TỌA ĐỘ X/Y =====================
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
        n_rand = st.number_input(t["n_random"], 3, 60, 12,
                                 label_visibility="collapsed", key="n_rand")
        if st.button(t["gen_random"], width="stretch"):
            st.session_state.df = instance_to_df(VRPTWInstance.random(
                n_customers=int(n_rand), num_vehicles=int(num_vehicles),
                vehicle_capacity=int(capacity)))
    with c3:
        uploaded = st.file_uploader(t["upload"], type="csv",
                                    label_visibility="collapsed")
        if uploaded is not None:
            st.session_state.df = pd.read_csv(uploaded)[COLS]

    edited_df = _clock_editor(st.session_state.df)

else:
    # ===================== CHẾ ĐỘ ĐỊA CHỈ THẬT =====================
    if "addr_df" not in st.session_state:
        st.session_state.addr_df = sample_addr_df()
    # Đặt sẵn địa chỉ kho mẫu (người dùng có thể đổi bằng ô tìm kho)
    st.session_state.setdefault("depot_addr",
                                "411 W Ocean Blvd, Long Beach, CA 90802")
    # Lưu tọa độ đã geocode để KHỎI geocode lại chuỗi đầy đủ (tránh lỗi)
    st.session_state.setdefault("addr_coords", {})  # {địa chỉ: (lat, lon)}

    # --- Địa chỉ kho (depot) — gõ là gợi ý hiện ra ngay ---
    st.subheader(t["depot_addr"])
    depot_query = st.text_input(t["addr_query"], key="depot_query")
    if depot_query and len(depot_query.strip()) >= 4:
        sugg = cached_suggest(depot_query, country)
        if sugg:
            names = [s["display_name"] for s in sugg]
            pick = st.selectbox(t["addr_pick"], names, key="depot_pick")
            if st.button(t["depot_set"]):
                chosen = sugg[names.index(pick)]
                st.session_state.depot_addr = pick
                st.session_state.addr_coords[pick] = (chosen["lat"], chosen["lon"])
                st.rerun()
        else:
            st.caption(t["addr_none"])
    if st.session_state.depot_addr:
        st.success(f"📍 {t['depot_current']}: {st.session_state.depot_addr}")

    # --- Tìm & thêm địa chỉ giao hàng — gõ là gợi ý hiện ra ngay ---
    with st.expander(t["addr_search"], expanded=True):
        addr_query = st.text_input(t["addr_query"], key="addr_query")
        if addr_query and len(addr_query.strip()) >= 4:
            sugg = cached_suggest(addr_query, country)
            if sugg:
                names = [s["display_name"] for s in sugg]
                picked = st.selectbox(t["addr_pick"], names, key="addr_pick")
                if st.button(t["addr_add"], type="primary"):
                    chosen = sugg[names.index(picked)]
                    st.session_state.addr_coords[picked] = (chosen["lat"],
                                                            chosen["lon"])
                    new = pd.DataFrame(
                        [[picked, DEF_DEMAND, DEF_READY, DEF_DUE, DEF_SERVICE]],
                        columns=ADDR_COLS)
                    st.session_state.addr_df = pd.concat(
                        [st.session_state.addr_df, new], ignore_index=True)
                    st.rerun()
            else:
                st.caption(t["addr_none"])

    st.markdown(f"**{t['addr_col']}** + demand / ready / due / service:")
    edited_addr_df = _clock_editor(st.session_state.addr_df)

# ---- Giải / solve -----------------------------------------------------------
if st.button(t["solve"], type="primary", width="stretch"):
    try:
        if not addr_mode:
            inst = df_to_instance(edited_df, int(num_vehicles), int(capacity))
        else:
            adf = edited_addr_df.dropna(subset=["address"]).copy()
            adf = adf[adf["address"].astype(str).str.strip() != ""]
            if not st.session_state.depot_addr:
                st.error(t["no_depot"]); st.stop()
            if len(adf) == 0:
                st.error(t["no_customers"]); st.stop()
            all_addr = [st.session_state.depot_addr] + adf["address"].tolist()
            # Ưu tiên tọa độ đã lưu lúc chọn gợi ý; chỉ geocode địa chỉ gõ tay
            saved = st.session_state.addr_coords
            need = [a for a in all_addr if a not in saved]
            if need:
                with st.spinner(t["geocoding"]):
                    gc, errs = cached_geocode_many(tuple(need), country)
                if errs:
                    st.error(t["geo_err"] + "; ".join(errs)); st.stop()
                for a, c in zip(need, gc):
                    saved[a] = c
            coords = [tuple(saved[a]) for a in all_addr]
            big = 100000
            inst = VRPTWInstance(
                name="user_addresses",
                locations=coords,
                demands=[0] + [DEF_DEMAND if _empty(v) else int(v)
                               for v in adf["demand"]],
                time_windows=([(0, big)]
                              + [(int(r), int(d)) for r, d in
                                 zip(adf["ready_time"], adf["due_time"])]),
                service_times=[0] + [int(v) for v in adf["service_time"]],
                num_vehicles=int(num_vehicles), vehicle_capacity=int(capacity),
                coord_mode="geo", avg_speed=float(avg_speed),
                distance_unit=unit_choice, road_factor=float(road_factor),
                addresses=all_addr)
            # Khoảng cách & thời gian theo ĐƯỜNG THẬT qua OSRM (fallback: chim bay)
            try:
                with st.spinner(t["routing"]):
                    dmat, tmat = cached_osrm_table(tuple(coords), unit_choice)
                inst.set_distance_time(dmat, tmat, unit=unit_choice)
                st.caption(t["routing_ok"])
            except Exception:
                st.warning(t["routing_fail"])
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
    try:
        with st.spinner(t["solving"]):
            sol = solve_fn(inst, time_limit_s=int(time_limit))
    except Exception as exc:
        st.error(t["no_solution"] + f"\n\n({exc})")
        st.stop()

    if not sol.routes:
        st.error(t["no_solution"]
                 + (f"\n\n{sol.status}" if sol.status else ""))
        st.stop()

    # ---- Kết quả / results ---------------------------------------------------
    cost_rows, cost_totals = route_cost_breakdown(sol, cost_params)

    st.markdown(f"**{t['status']}:** {sol.status}")
    dist_unit = f" {inst.distance_unit}" if addr_mode else ""
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t["total_dist"], f"{sol.total_distance:.2f}{dist_unit}")
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
        st.pyplot(plotting.plot_schedule(
            sol, lang=lang, time_fmt=time_fmt if clock_mode else None))
    with tab_cost:
        st.subheader(t["cost_table"])
        cur = cost_params.currency
        # Bỏ cột "Tuyến" dài (xem ở tab Chi tiết); giữ bảng gọn, có cuộn ngang
        cost_view = pd.DataFrame(cost_rows).drop(columns=["route"]).rename(columns={
            "vehicle": t["col_vehicle"],
            "stops": "Stops", "load": t["col_load"],
            "distance": t["col_dist"], "depart": "Depart", "return": "Return",
            "duration_min": "Min",
            "fuel": f"⛽ Fuel ({cur})", "maintenance": f"🔧 Maint ({cur})",
            "labor": f"👷 Labor ({cur})", "mgmt_fee": f"🗂 Mgmt ({cur})",
            "deductible": f"🛡 Deduct ({cur})", "total": f"Σ Total ({cur})",
        })
        st.dataframe(cost_view, width="stretch", hide_index=True, height=260)
        st.caption(t["cost_scroll_hint"])
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
                t["col_times"]: ", ".join(time_fmt(x) for x in r.start_times),
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

    xlsx_bytes = solution_to_excel(sol, cost_rows, cost_totals, cost_params,
                                   time_fmt=time_fmt if clock_mode else None)

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
