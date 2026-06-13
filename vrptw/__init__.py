"""VRPTW Solver — Vehicle Routing Problem with Time Windows.

Gói gồm:
- instance:        định nghĩa & nạp dữ liệu bài toán (sample / CSV / random)
- solver_ortools:  giải bằng Google OR-Tools (heuristic, scale tốt)
- solver_milp:     giải bằng MILP (PuLP + CBC) đúng theo mô hình toán (1)-(11)
- plotting:        vẽ tuyến đường + biểu đồ Gantt khung thời gian
"""

from .instance import VRPTWInstance
from .solution import Solution, Route

__all__ = ["VRPTWInstance", "Solution", "Route"]
__version__ = "1.0.0"
