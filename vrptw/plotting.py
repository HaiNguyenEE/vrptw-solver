"""Trực quan hóa lời giải VRPTW / VRPTW solution visualization.

Hai biểu đồ: bản đồ tuyến đường + Gantt khung thời gian (song ngữ VI/EN).
Hàm trả về Figure để dùng được trong cả CLI (lưu PNG) và Streamlit app.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # render không cần màn hình / headless rendering
import matplotlib.pyplot as plt

from .solution import Solution

COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
          "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

LABELS = {
    "vi": {
        "veh": "Xe", "x": "Tọa độ X", "y": "Tọa độ Y", "time": "Thời gian",
        "cust": "KH",
        "routes_title": "Lời giải VRPTW ({solver}) — tổng quãng đường: {dist:.2f}",
        "gantt_title": ("Lịch phục vụ vs. khung thời gian cho phép\n"
                        "(nhạt = TW cho phép, đậm = thời gian phục vụ thực tế)"),
    },
    "en": {
        "veh": "Vehicle", "x": "X coordinate", "y": "Y coordinate", "time": "Time",
        "cust": "Cust.",
        "routes_title": "VRPTW solution ({solver}) — total distance: {dist:.2f}",
        "gantt_title": ("Service schedule vs. allowed time windows\n"
                        "(light = allowed TW, solid = actual service time)"),
    },
}


def plot_routes(sol: Solution, path: str | None = None,
                lang: str = "vi") -> plt.Figure:
    """Bản đồ tuyến đường / route map: depot, khách hàng (TW & demand), mũi tên."""
    lbl = LABELS.get(lang, LABELS["vi"])
    inst = sol.instance
    fig, ax = plt.subplots(figsize=(11, 8))

    # Depot & khách hàng / depot & customers
    for node, (x, y) in enumerate(inst.locations):
        if node == inst.depot:
            ax.scatter(x, y, s=320, marker="s", c="#2c5f9e",
                       edgecolors="black", linewidths=1.5, zorder=5, label="Depot")
            ax.annotate("Depot", (x, y), xytext=(8, 6), textcoords="offset points",
                        fontsize=11, fontweight="bold")
        else:
            a, b = inst.time_windows[node]
            ax.scatter(x, y, s=140, c="white", edgecolors="black",
                       linewidths=1.2, zorder=5)
            ax.annotate(f"{node}\nTW[{a}, {b}]\nD={inst.demands[node]}",
                        (x, y), xytext=(7, 5), textcoords="offset points", fontsize=8)

    # Tuyến đường từng xe / route per vehicle
    for r in sol.routes:
        if not r.used:
            continue
        color = COLORS[r.vehicle % len(COLORS)]
        xs = [inst.locations[i][0] for i in r.nodes]
        ys = [inst.locations[i][1] for i in r.nodes]
        label = (f"{lbl['veh']} {r.vehicle + 1}: " + " → ".join(map(str, r.nodes))
                 + f"  (d={r.distance:.1f})")
        ax.plot(xs, ys, marker="o", linewidth=2.6, color=color, alpha=0.85,
                label=label, zorder=3)
        for i in range(len(xs) - 1):
            ax.annotate("", xy=((xs[i] + xs[i + 1]) / 2 + (xs[i + 1] - xs[i]) * 0.12,
                                (ys[i] + ys[i + 1]) / 2 + (ys[i + 1] - ys[i]) * 0.12),
                        xytext=((xs[i] + xs[i + 1]) / 2, (ys[i] + ys[i + 1]) / 2),
                        arrowprops=dict(arrowstyle="-|>", color=color, lw=2),
                        zorder=4)

    ax.set_title(lbl["routes_title"].format(solver=sol.solver, dist=sol.total_distance),
                 fontsize=14, fontweight="bold")
    ax.set_xlabel(lbl["x"])
    ax.set_ylabel(lbl["y"])
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig


def plot_schedule(sol: Solution, path: str | None = None,
                  lang: str = "vi") -> plt.Figure:
    """Biểu đồ Gantt / Gantt chart: TW [a_i, b_i] và thời điểm phục vụ thực tế."""
    lbl = LABELS.get(lang, LABELS["vi"])
    inst = sol.instance
    fig, ax = plt.subplots(figsize=(11, 0.5 * inst.n_customers + 2.5))

    served_by = {}
    for r in sol.routes:
        for idx, node in enumerate(r.nodes):
            if node != inst.depot:
                served_by[node] = (r.vehicle, r.start_times[idx])

    customers = sorted(served_by, key=lambda c: served_by[c][1])
    for row, c in enumerate(customers):
        a, b = inst.time_windows[c]
        v, t_start = served_by[c]
        color = COLORS[v % len(COLORS)]
        # Khung thời gian cho phép / allowed time window
        ax.barh(row, b - a, left=a, height=0.55, color=color, alpha=0.25,
                edgecolor=color)
        # Thời gian phục vụ thực tế / actual service time
        ax.barh(row, max(inst.service_times[c], 1), left=t_start, height=0.55,
                color=color, edgecolor="black", linewidth=0.8)
        ax.annotate(f"t={t_start:.0f}", (t_start, row), xytext=(2, 12),
                    textcoords="offset points", fontsize=7.5)

    ax.set_yticks(range(len(customers)))
    ax.set_yticklabels([f"{lbl['cust']} {c} ({lbl['veh']} {served_by[c][0] + 1})"
                        for c in customers], fontsize=9)
    ax.set_xlabel(lbl["time"])
    ax.set_title(lbl["gantt_title"], fontsize=12, fontweight="bold")
    ax.grid(True, axis="x", linestyle="--", alpha=0.5)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig
