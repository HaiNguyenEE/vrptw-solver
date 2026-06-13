"""Giải VRPTW bằng Google OR-Tools Routing (heuristic — scale tốt).

Khoảng cách được scale ×100 thành số nguyên để tránh mất chính xác
(OR-Tools chỉ làm việc với int), kết quả được chia lại khi trả về.
"""

from __future__ import annotations

import time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .instance import VRPTWInstance
from .solution import Route, Solution

SCALE = 100  # hệ số scale khoảng cách/thời gian sang int


def solve(inst: VRPTWInstance, time_limit_s: int = 10) -> Solution:
    inst.validate()
    dist = inst.distance_matrix
    n = len(inst.locations)
    d_int = [[round(dist[i][j] * SCALE) for j in range(n)] for i in range(n)]
    horizon = max(b for _, b in inst.time_windows) * SCALE

    manager = pywrapcp.RoutingIndexManager(n, inst.num_vehicles, inst.depot)
    routing = pywrapcp.RoutingModel(manager)

    # ---- Chi phí di chuyển (mục tiêu: min tổng quãng đường) -------------
    def distance_cb(fi: int, ti: int) -> int:
        return d_int[manager.IndexToNode(fi)][manager.IndexToNode(ti)]

    transit = routing.RegisterTransitCallback(distance_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)

    # ---- Ràng buộc tải trọng (9) ----------------------------------------
    def demand_cb(fi: int) -> int:
        return inst.demands[manager.IndexToNode(fi)]

    demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_idx, 0, [inst.vehicle_capacity] * inst.num_vehicles, True, "Capacity")

    # ---- Ràng buộc thời gian (6)-(8) -------------------------------------
    def time_cb(fi: int, ti: int) -> int:
        f, t = manager.IndexToNode(fi), manager.IndexToNode(ti)
        return d_int[f][t] + inst.service_times[f] * SCALE

    time_idx = routing.RegisterTransitCallback(time_cb)
    routing.AddDimension(time_idx, horizon, horizon, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    for node, (a, b) in enumerate(inst.time_windows):
        if node == inst.depot:
            continue
        time_dim.CumulVar(manager.NodeToIndex(node)).SetRange(a * SCALE, b * SCALE)
    a0, b0 = inst.time_windows[inst.depot]
    for v in range(inst.num_vehicles):
        time_dim.CumulVar(routing.Start(v)).SetRange(a0 * SCALE, b0 * SCALE)
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.Start(v)))
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(routing.End(v)))

    # ---- Tham số tìm kiếm -------------------------------------------------
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    params.time_limit.FromSeconds(time_limit_s)

    t0 = time.time()
    assignment = routing.SolveWithParameters(params)
    runtime = time.time() - t0

    if assignment is None:
        return Solution(inst, [], solver="ortools", status="INFEASIBLE/NO SOLUTION",
                        runtime_s=runtime)

    # ---- Trích xuất lời giải ---------------------------------------------
    routes: list[Route] = []
    for v in range(inst.num_vehicles):
        nodes, starts = [], []
        idx = routing.Start(v)
        route_dist = 0.0
        while True:
            node = manager.IndexToNode(idx)
            nodes.append(node)
            starts.append(assignment.Min(time_dim.CumulVar(idx)) / SCALE)
            if routing.IsEnd(idx):
                break
            nxt = assignment.Value(routing.NextVar(idx))
            route_dist += d_int[node][manager.IndexToNode(nxt)] / SCALE
            idx = nxt
        load = sum(inst.demands[i] for i in nodes)
        routes.append(Route(vehicle=v, nodes=nodes, start_times=starts,
                            load=load, distance=route_dist))

    sol = Solution(inst, routes, solver="ortools", status="FEASIBLE (heuristic)",
                   runtime_s=runtime)
    sol.objective = sol.total_distance
    return sol
