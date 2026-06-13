#!/usr/bin/env python3
"""VRPTW Solver — chạy tự động: giải bài toán, in kết quả, vẽ plot.

Ví dụ:
    python main.py                                    # instance mẫu, OR-Tools
    python main.py --solver milp                      # giải exact bằng MILP/CBC
    python main.py --solver both                      # so sánh cả hai
    python main.py --instance random --customers 15   # instance ngẫu nhiên
    python main.py --instance examples/sample_instance.csv --vehicles 3 --capacity 10
"""

from __future__ import annotations

import argparse
import os

from vrptw import VRPTWInstance
from vrptw import plotting, solver_milp, solver_ortools
from vrptw.costing import CostParams, route_cost_breakdown
from vrptw.excel_export import solution_to_excel


def build_instance(args: argparse.Namespace) -> VRPTWInstance:
    if args.instance == "sample":
        return VRPTWInstance.sample()
    if args.instance == "random":
        return VRPTWInstance.random(
            n_customers=args.customers, num_vehicles=args.vehicles,
            vehicle_capacity=args.capacity, seed=args.seed)
    # còn lại: đường dẫn file CSV
    return VRPTWInstance.from_csv(
        args.instance, num_vehicles=args.vehicles, vehicle_capacity=args.capacity)


def main() -> None:
    p = argparse.ArgumentParser(description="VRPTW solver (OR-Tools + MILP) kèm plotting")
    p.add_argument("--instance", default="sample",
                   help="'sample' | 'random' | đường dẫn file CSV (mặc định: sample)")
    p.add_argument("--solver", default="ortools", choices=["ortools", "milp", "both"],
                   help="ortools = heuristic nhanh; milp = exact (CBC); both = so sánh")
    p.add_argument("--vehicles", type=int, default=3, help="số xe (CSV/random)")
    p.add_argument("--capacity", type=int, default=10, help="sức chứa mỗi xe (CSV/random)")
    p.add_argument("--customers", type=int, default=12, help="số khách hàng (random)")
    p.add_argument("--seed", type=int, default=42, help="seed (random)")
    p.add_argument("--time-limit", type=int, default=10, help="giới hạn thời gian giải (s)")
    p.add_argument("--out", default="results", help="thư mục lưu kết quả")
    # ---- Tham số chi phí / cost parameters --------------------------------
    p.add_argument("--fuel-cost", type=float, default=0.15,
                   help="nhiên liệu / đơn vị quãng đường")
    p.add_argument("--maint-cost", type=float, default=0.05,
                   help="bảo trì / đơn vị quãng đường")
    p.add_argument("--wage", type=float, default=20.0, help="lương tài xế / giờ")
    p.add_argument("--mgmt-fee", type=float, default=15.0, help="phí quản lý / xe")
    p.add_argument("--deduct-fee", type=float, default=10.0,
                   help="phí khấu trừ (bảo hiểm) / xe")
    p.add_argument("--currency", default="$", help="ký hiệu tiền tệ")
    args = p.parse_args()

    cost_params = CostParams(
        fuel_per_unit=args.fuel_cost, maintenance_per_unit=args.maint_cost,
        wage_per_hour=args.wage, mgmt_fee_per_vehicle=args.mgmt_fee,
        deductible_per_vehicle=args.deduct_fee, currency=args.currency)

    inst = build_instance(args)
    os.makedirs(args.out, exist_ok=True)

    solvers = {"ortools": solver_ortools.solve, "milp": solver_milp.solve}
    chosen = ["ortools", "milp"] if args.solver == "both" else [args.solver]

    for name in chosen:
        sol = solvers[name](inst, time_limit_s=args.time_limit)
        print(sol.summary())
        if not sol.routes:
            continue
        prefix = os.path.join(args.out, f"{inst.name}_{name}")
        import matplotlib.pyplot as plt
        plt.close(plotting.plot_routes(sol, path=f"{prefix}_routes.png"))
        plt.close(plotting.plot_schedule(sol, path=f"{prefix}_schedule.png"))
        sol.to_json(f"{prefix}_solution.json")

        # Báo cáo chi phí + Excel kế toán
        cost_rows, cost_totals = route_cost_breakdown(sol, cost_params)
        cur = cost_params.currency
        print(f"Tổng chi phí: {cur}{cost_totals['total']:,.2f} "
              f"(nhiên liệu {cur}{cost_totals['fuel']:,.2f}, "
              f"bảo trì {cur}{cost_totals['maintenance']:,.2f}, "
              f"nhân công {cur}{cost_totals['labor']:,.2f}, "
              f"quản lý {cur}{cost_totals['mgmt_fee']:,.2f}, "
              f"khấu trừ {cur}{cost_totals['deductible']:,.2f})")
        with open(f"{prefix}_report.xlsx", "wb") as f:
            f.write(solution_to_excel(sol, cost_rows, cost_totals, cost_params))
        print(f"Đã lưu: {prefix}_routes.png, {prefix}_schedule.png, "
              f"{prefix}_solution.json, {prefix}_report.xlsx\n")


if __name__ == "__main__":
    main()
