"""Giải VRPTW bằng MILP (PuLP + CBC) — đúng theo mô hình toán (1)-(11).

Mô hình (theo bài "Vận trù học — Phần 11"):

    (VRPTW)  min  Σ_k Σ_(i,j)∈A  c_ij · x_ijk                          (1)
    s.t.
      Σ_k Σ_{j∈A+(i)} x_ijk = 1                ∀ i ∈ N                  (2)
      Σ_{j∈A+(0)}  x_0jk  = 1                  ∀ k                      (3)
      Σ_{i∈A-(j)} x_ijk − Σ_{i∈A+(j)} x_jik = 0  ∀ k, ∀ j ∈ N           (4)
      Σ_{i∈A-(n+1)} x_{i,n+1,k} = 1            ∀ k                      (5)
      x_ijk·(w_ik + s_i + t_ij − w_jk) ≤ 0     ∀ k, ∀(i,j) ∈ A          (6)
          → tuyến tính hóa Big-M:
            w_ik + s_i + t_ij − w_jk ≤ M_ij·(1 − x_ijk)
      a_i·Σ x_ijk ≤ w_ik ≤ b_i·Σ x_ijk         ∀ k, ∀ i ∈ N             (7)
      E ≤ w_ik ≤ L                             ∀ k, i ∈ {0, n+1}        (8)
      Σ_{i∈N} d_i Σ_{j∈A+(i)} x_ijk ≤ C        ∀ k                      (9)
      x_ijk ∈ {0, 1}                                                (10, 11)

Depot được tách đôi: node 0 (xuất phát) và node n+1 (kết thúc).
Cung không khả thi bị loại trước khi giải (arc pruning):
    a_i + s_i + t_ij > b_j  hoặc  d_i + d_j > C.
"""

from __future__ import annotations

import time

import pulp

from .instance import VRPTWInstance
from .solution import Route, Solution


def solve(inst: VRPTWInstance, time_limit_s: int = 60, verbose: bool = False) -> Solution:
    inst.validate()
    n = inst.n_customers
    dist = inst.distance_matrix

    # ---- Tập node: 0 = depot xuất phát, 1..n = khách, n+1 = depot kết thúc
    start, end = 0, n + 1
    customers = list(range(1, n + 1))
    V = [start] + customers + [end]
    K = range(inst.num_vehicles)

    def loc(i: int) -> int:               # ánh xạ node mở rộng -> node gốc
        return inst.depot if i in (start, end) else i

    t = {(i, j): dist[loc(i)][loc(j)] for i in V for j in V}
    a = {i: inst.time_windows[loc(i)][0] for i in V}
    b = {i: inst.time_windows[loc(i)][1] for i in V}
    s = {i: inst.service_times[loc(i)] for i in V}
    d = {i: inst.demands[loc(i)] for i in V}
    E, L = a[start], b[start]

    # ---- Tập cung A + loại cung không khả thi (arc pruning) --------------
    A = []
    for i in V:
        for j in V:
            if i == j or j == start or i == end or (i == start and j == end):
                continue
            if a[i] + s[i] + t[i, j] > b[j]:          # không thể đến kịp TW của j
                continue
            if i in customers and j in customers and d[i] + d[j] > inst.vehicle_capacity:
                continue
            A.append((i, j))

    out_arcs = {i: [j for (ii, j) in A if ii == i] for i in V}   # A+(i)
    in_arcs = {j: [i for (i, jj) in A if jj == j] for j in V}    # A-(j)

    # ---- Biến quyết định ---------------------------------------------------
    x = pulp.LpVariable.dicts("x", [(i, j, k) for (i, j) in A for k in K], cat="Binary")
    w = pulp.LpVariable.dicts("w", [(i, k) for i in V for k in K], lowBound=0)

    prob = pulp.LpProblem("VRPTW", pulp.LpMinimize)

    # (1) Mục tiêu: tối thiểu tổng quãng đường
    prob += pulp.lpSum(t[i, j] * x[i, j, k] for (i, j) in A for k in K)

    # (2) Mỗi khách hàng được phục vụ đúng một lần
    for i in customers:
        prob += pulp.lpSum(x[i, j, k] for j in out_arcs[i] for k in K) == 1

    for k in K:
        # (3) Mỗi xe rời depot đúng một lần (có thể đi thẳng 0 → n+1? — không:
        #     cung (0, n+1) đã bị loại; xe không dùng vẫn phải đi qua 1 khách?
        #     Để cho phép xe không dùng, ta thêm cung ảo bằng ràng buộc "≤ 1".)
        prob += pulp.lpSum(x[start, j, k] for j in out_arcs[start]) <= 1
        # (5) Về depot đúng số lần đã xuất phát
        prob += (pulp.lpSum(x[i, end, k] for i in in_arcs[end])
                 == pulp.lpSum(x[start, j, k] for j in out_arcs[start]))
        # (4) Bảo toàn dòng tại mỗi khách hàng
        for j in customers:
            prob += (pulp.lpSum(x[i, j, k] for i in in_arcs[j])
                     == pulp.lpSum(x[j, i, k] for i in out_arcs[j]))
        # (9) Tải trọng
        prob += pulp.lpSum(d[i] * x[i, j, k] for i in customers
                           for j in out_arcs[i]) <= inst.vehicle_capacity
        # (6) Big-M cho trình tự thời gian
        for (i, j) in A:
            M = max(0.0, b[i] + s[i] + t[i, j] - a[j])
            prob += w[i, k] + s[i] + t[i, j] - w[j, k] <= M * (1 - x[i, j, k])
        # (7) Khung thời gian tại khách hàng (chỉ kích hoạt nếu xe k ghé i)
        for i in customers:
            visit = pulp.lpSum(x[i, j, k] for j in out_arcs[i])
            prob += w[i, k] >= a[i] * visit
            prob += w[i, k] <= b[i] * visit
        # (8) Khung thời gian tại depot
        for i in (start, end):
            prob += w[i, k] >= E
            prob += w[i, k] <= L

    # ---- Phá đối xứng (các xe giống hệt nhau) -----------------------------
    # Gán nhãn xe theo khách hàng nhỏ nhất trên tuyến: khách hàng i chỉ được
    # phục vụ bởi xe 0..i-1. Hợp lệ vì mọi xe có cùng sức chứa, giúp CBC
    # không phải duyệt các lời giải chỉ khác nhau ở cách đánh số xe.
    for i in customers:
        for k in K:
            if k >= i:
                prob += pulp.lpSum(x[i, j, k] for j in out_arcs[i]) == 0
    # Xe k+1 chỉ được dùng nếu xe k đã dùng
    for k in list(K)[:-1]:
        prob += (pulp.lpSum(x[start, j, k] for j in out_arcs[start])
                 >= pulp.lpSum(x[start, j, k + 1] for j in out_arcs[start]))

    # ---- Giải bằng CBC ------------------------------------------------------
    solver = pulp.PULP_CBC_CMD(msg=verbose, timeLimit=time_limit_s)
    t0 = time.time()
    prob.solve(solver)
    runtime = time.time() - t0
    status = pulp.LpStatus[prob.status]

    if prob.status not in (pulp.LpStatusOptimal,):
        return Solution(inst, [], solver="milp-cbc", status=status, runtime_s=runtime)

    # ---- Trích xuất tuyến đường ---------------------------------------------
    routes: list[Route] = []
    for k in K:
        succ = {i: j for (i, j) in A if pulp.value(x[i, j, k]) > 0.5}
        nodes, starts = [inst.depot], [pulp.value(w[start, k]) or 0.0]
        cur = start
        while cur in succ:
            cur = succ[cur]
            nodes.append(loc(cur))
            starts.append(pulp.value(w[cur, k]) or 0.0)
            if cur == end:
                break
        load = sum(inst.demands[i] for i in nodes)
        route_d = sum(dist[nodes[i]][nodes[i + 1]] for i in range(len(nodes) - 1))
        routes.append(Route(vehicle=k, nodes=nodes, start_times=starts,
                            load=load, distance=route_d))

    sol = Solution(inst, routes, solver="milp-cbc", status=f"{status} (exact)",
                   runtime_s=runtime)
    sol.objective = pulp.value(prob.objective)
    return sol
