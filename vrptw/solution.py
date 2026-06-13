"""Cấu trúc lời giải VRPTW + kiểm tra tính khả thi + xuất kết quả."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .instance import VRPTWInstance


def _compact_vehicles(routes: "list[Route]") -> "list[Route]":
    """Đánh số lại để các xe DÙNG THẬT là 0,1,2… (hiển thị Xe 1, 2, 3 liên tiếp).

    Các xe giống hệt nhau nên việc bỏ trống xe index 0 là hợp lệ nhưng gây
    khó hiểu; hàm này gom xe đã dùng lên đầu, xe trống xuống cuối.
    """
    used = [r for r in routes if r.used]
    unused = [r for r in routes if not r.used]
    for i, r in enumerate(used):
        r.vehicle = i
    for j, r in enumerate(unused):
        r.vehicle = len(used) + j
    return used + unused


@dataclass
class Route:
    vehicle: int
    nodes: list[int]                  # [0, ..., 0] — bắt đầu & kết thúc tại depot
    start_times: list[float]          # thời điểm bắt đầu phục vụ w_i tại từng node
    load: int = 0
    distance: float = 0.0

    @property
    def used(self) -> bool:
        return len(self.nodes) > 2


@dataclass
class Solution:
    instance: VRPTWInstance
    routes: list[Route]
    solver: str = ""
    status: str = ""
    objective: float = 0.0
    runtime_s: float = 0.0
    gap: float | None = None
    _log: list[str] = field(default_factory=list, repr=False)

    @property
    def total_distance(self) -> float:
        return sum(r.distance for r in self.routes)

    @property
    def vehicles_used(self) -> int:
        return sum(1 for r in self.routes if r.used)

    # ------------------------------------------------------------------
    def verify(self) -> list[str]:
        """Kiểm tra lời giải: mỗi khách 1 lần, tải trọng, khung thời gian.

        Trả về danh sách lỗi (rỗng nếu lời giải hợp lệ).
        """
        inst, errors = self.instance, []
        dist = inst.time_matrix  # kiểm tra trình tự dùng thời gian di chuyển (phút)
        TOL = 0.5  # dung sai phút do OR-Tools làm tròn (scale x100)
        visited: list[int] = []
        for r in self.routes:
            if not r.used:
                continue
            # Tải trọng
            load = sum(inst.demands[i] for i in r.nodes)
            if load > inst.vehicle_capacity:
                errors.append(f"Xe {r.vehicle + 1}: tải {load} > sức chứa {inst.vehicle_capacity}")
            # Thời gian
            for idx in range(1, len(r.nodes)):
                i, j = r.nodes[idx - 1], r.nodes[idx]
                earliest = r.start_times[idx - 1] + inst.service_times[i] + dist[i][j]
                if r.start_times[idx] < earliest - TOL:
                    errors.append(
                        f"Xe {r.vehicle + 1}: w[{j}]={r.start_times[idx]:.1f} < "
                        f"w[{i}]+s+t={earliest:.1f} (vi phạm trình tự thời gian)")
            for idx, node in enumerate(r.nodes):
                a, b = inst.time_windows[node]
                if not (a - TOL <= r.start_times[idx] <= b + TOL):
                    errors.append(
                        f"Xe {r.vehicle + 1}: node {node} phục vụ lúc "
                        f"{r.start_times[idx]:.1f} ngoài TW [{a}, {b}]")
            visited += [n for n in r.nodes if n != inst.depot]
        # Mỗi khách hàng đúng 1 lần
        for c in range(1, inst.n_customers + 1):
            cnt = visited.count(c)
            if cnt != 1:
                errors.append(f"Khách hàng {c} được phục vụ {cnt} lần (phải đúng 1 lần)")
        return errors

    # ------------------------------------------------------------------
    def summary(self) -> str:
        inst = self.instance
        lines = [
            "=" * 72,
            f"KẾT QUẢ VRPTW — solver: {self.solver} | instance: {inst.name}",
            f"Trạng thái: {self.status} | thời gian giải: {self.runtime_s:.2f}s"
            + (f" | gap: {self.gap:.2%}" if self.gap is not None else ""),
            "=" * 72,
        ]
        for r in self.routes:
            if not r.used:
                lines.append(f"Xe {r.vehicle + 1}: (không sử dụng)")
                continue
            steps = []
            for idx, node in enumerate(r.nodes):
                t = r.start_times[idx]
                if node == inst.depot:
                    steps.append(f"Depot[t={t:.0f}]")
                else:
                    a, b = inst.time_windows[node]
                    steps.append(f"{node}[t={t:.0f}, TW {a}-{b}]")
            lines.append(f"Xe {r.vehicle + 1}: " + " → ".join(steps))
            lines.append(f"   Quãng đường: {r.distance:.2f} | Tải: {r.load}/{inst.vehicle_capacity}")
        lines.append("-" * 72)
        lines.append(f"Tổng quãng đường: {self.total_distance:.2f} | "
                     f"Số xe sử dụng: {self.vehicles_used}/{inst.num_vehicles}")
        errs = self.verify()
        lines.append("Kiểm tra ràng buộc: " +
                     ("HỢP LỆ ✔" if not errs else f"VI PHẠM ✘ ({len(errs)} lỗi)"))
        lines.extend("   - " + e for e in errs)
        return "\n".join(lines)

    def to_json(self, path: str) -> None:
        data = {
            "solver": self.solver,
            "instance": self.instance.name,
            "status": self.status,
            "objective_total_distance": round(self.total_distance, 3),
            "runtime_s": round(self.runtime_s, 3),
            "routes": [
                {
                    "vehicle": r.vehicle + 1,
                    "nodes": r.nodes,
                    "service_start_times": [round(t, 2) for t in r.start_times],
                    "load": r.load,
                    "distance": round(r.distance, 3),
                }
                for r in self.routes if r.used
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
