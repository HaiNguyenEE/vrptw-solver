"""Định nghĩa và nạp dữ liệu bài toán VRPTW."""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass, field


@dataclass
class VRPTWInstance:
    """Một instance của bài toán VRPTW.

    Node 0 luôn là depot. Các node 1..n là khách hàng.
    """

    locations: list[tuple[float, float]]          # tọa độ (x, y) từng node
    demands: list[int]                            # nhu cầu d_i (depot = 0)
    time_windows: list[tuple[int, int]]           # khung thời gian [a_i, b_i]
    service_times: list[int]                      # thời gian phục vụ s_i
    num_vehicles: int = 3                         # số xe |K|
    vehicle_capacity: int = 10                    # sức chứa C
    depot: int = 0
    name: str = "instance"
    _dist: list[list[float]] = field(default=None, repr=False)

    # ------------------------------------------------------------------
    @property
    def n_customers(self) -> int:
        return len(self.locations) - 1

    @property
    def distance_matrix(self) -> list[list[float]]:
        """Ma trận khoảng cách Euclid (đồng thời là thời gian di chuyển t_ij)."""
        if self._dist is None:
            n = len(self.locations)
            self._dist = [[0.0] * n for _ in range(n)]
            for i in range(n):
                xi, yi = self.locations[i]
                for j in range(n):
                    xj, yj = self.locations[j]
                    self._dist[i][j] = math.hypot(xi - xj, yi - yj)
        return self._dist

    def validate(self) -> None:
        n = len(self.locations)
        assert len(self.demands) == n == len(self.time_windows) == len(self.service_times), \
            "Số phần tử của locations/demands/time_windows/service_times phải bằng nhau"
        assert self.demands[self.depot] == 0, "Depot phải có demand = 0"
        total = sum(self.demands)
        cap = self.num_vehicles * self.vehicle_capacity
        assert total <= cap, f"Tổng demand ({total}) vượt tổng sức chứa đội xe ({cap})"

    # ------------------------------------------------------------------
    # Các cách tạo instance
    # ------------------------------------------------------------------
    @classmethod
    def sample(cls) -> "VRPTWInstance":
        """Instance mẫu: depot + 9 khách hàng (ví dụ trong bài Vận trù học P.11)."""
        return cls(
            name="sample",
            locations=[
                (50, 50),  # 0 - Depot
                (20, 80), (25, 65), (30, 50), (35, 30), (55, 20),
                (65, 35), (70, 55), (60, 75), (45, 85),
            ],
            demands=[0, 2, 3, 2, 4, 3, 2, 4, 3, 2],
            time_windows=[
                (0, 300),                       # depot
                (30, 120), (20, 130), (10, 140), (30, 160), (40, 180),
                (50, 200), (40, 210), (30, 190), (20, 170),
            ],
            service_times=[0] + [5] * 9,
            num_vehicles=3,
            vehicle_capacity=10,
        )

    @classmethod
    def from_csv(cls, path: str, num_vehicles: int = 3,
                 vehicle_capacity: int = 10) -> "VRPTWInstance":
        """Đọc instance từ file CSV.

        Định dạng cột: node,x,y,demand,ready_time,due_time,service_time
        Hàng có node = 0 là depot.
        """
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        rows.sort(key=lambda r: int(r["node"]))
        inst = cls(
            name=path.rsplit("/", 1)[-1].removesuffix(".csv"),
            locations=[(float(r["x"]), float(r["y"])) for r in rows],
            demands=[int(r["demand"]) for r in rows],
            time_windows=[(int(r["ready_time"]), int(r["due_time"])) for r in rows],
            service_times=[int(r["service_time"]) for r in rows],
            num_vehicles=num_vehicles,
            vehicle_capacity=vehicle_capacity,
        )
        inst.validate()
        return inst

    @classmethod
    def random(cls, n_customers: int = 12, num_vehicles: int = 4,
               vehicle_capacity: int = 12, seed: int = 42) -> "VRPTWInstance":
        """Sinh instance ngẫu nhiên (có thể tái lập bằng seed)."""
        rng = random.Random(seed)
        depot = (50, 50)
        locations = [depot]
        demands = [0]
        time_windows = [(0, 480)]
        service_times = [0]
        for _ in range(n_customers):
            x, y = rng.uniform(5, 95), rng.uniform(5, 95)
            locations.append((x, y))
            demands.append(rng.randint(1, 4))
            travel = math.hypot(x - depot[0], y - depot[1])
            ready = rng.randint(int(travel), 200)        # đảm bảo có thể đến kịp
            width = rng.randint(60, 150)
            time_windows.append((ready, min(ready + width, 470)))
            service_times.append(5)
        inst = cls(
            name=f"random_n{n_customers}_seed{seed}",
            locations=locations, demands=demands, time_windows=time_windows,
            service_times=service_times, num_vehicles=num_vehicles,
            vehicle_capacity=vehicle_capacity,
        )
        inst.validate()
        return inst

    def to_csv(self, path: str) -> None:
        """Xuất instance ra CSV (cùng định dạng with from_csv)."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["node", "x", "y", "demand", "ready_time", "due_time", "service_time"])
            for i, (x, y) in enumerate(self.locations):
                a, b = self.time_windows[i]
                w.writerow([i, round(x, 3), round(y, 3), self.demands[i], a, b,
                            self.service_times[i]])
