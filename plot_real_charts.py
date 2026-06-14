#!/usr/bin/env python3
import argparse
import csv
import math
import os
from statistics import mean, pstdev

try:
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "matplotlib 未安装，请先执行: pip install matplotlib\n"
        f"详细错误: {exc}"
    )


def read_rows(path: str):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "second": int(float(row["second"])),
                    "mode": row["mode"],
                    "score": float(row["score"]),
                    "dtlb_mpki": float(row["dtlb_mpki"]),
                    "llc_mpki": float(row["llc_mpki"]),
                    "pf_rate": float(row["pf_rate"]),
                    "work_ms": float(row["work_ms"]),
                    "ops_per_sec": float(row["ops_per_sec"]),
                    "thp_state": row["thp_state"],
                    "switch_event": int(float(row["switch_event"])),
                }
            )
    if not rows:
        raise ValueError(f"CSV 文件无数据: {path}")
    return rows


def ensure_dir(path: str):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def metric_mean(rows, key):
    return mean(r[key] for r in rows)


def metric_std(rows, key):
    values = [r[key] for r in rows]
    return pstdev(values) if len(values) > 1 else 0.0


def draw_score_timeline(adaptive_rows, out_path):
    x = [r["second"] for r in adaptive_rows]
    y = [r["score"] for r in adaptive_rows]
    states = [1 if r["thp_state"] == "THP_ON" else 0 for r in adaptive_rows]
    switch_points = [r["second"] for r in adaptive_rows if r["switch_event"] != 0]

    plt.figure(figsize=(9, 4.8))
    plt.plot(x, y, linewidth=2.0, label="score")
    plt.step(x, states, where="post", alpha=0.35, label="THP state (1=ON)")
    for sp in switch_points:
        plt.axvline(sp, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
    plt.title("Adaptive-THP-M Score Timeline")
    plt.xlabel("Time (s)")
    plt.ylabel("Score / State")
    plt.ylim(-0.05, 1.10)
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def draw_group_bar(mode_rows, out_path):
    labels = list(mode_rows.keys())
    dtlb = [metric_mean(mode_rows[k], "dtlb_mpki") for k in labels]
    llc = [metric_mean(mode_rows[k], "llc_mpki") for k in labels]
    pf = [metric_mean(mode_rows[k], "pf_rate") for k in labels]

    x = list(range(len(labels)))
    w = 0.24

    plt.figure(figsize=(9, 4.8))
    plt.bar([i - w for i in x], dtlb, width=w, label="dTLB MPKI")
    plt.bar(x, llc, width=w, label="LLC MPKI")
    plt.bar([i + w for i in x], pf, width=w, label="Page Fault Rate (/s)")
    plt.xticks(x, labels)
    plt.title("Mean Metrics by Mode")
    plt.ylabel("Metric Value")
    plt.grid(axis="y", alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def draw_latency_box(mode_rows, out_path):
    labels = list(mode_rows.keys())
    series = [[r["work_ms"] for r in mode_rows[k]] for k in labels]
    plt.figure(figsize=(8.5, 4.8))
    plt.boxplot(series, tick_labels=labels, showmeans=True)
    plt.title("Workload Latency Distribution")
    plt.ylabel("work_ms per window")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def render_summary_markdown(mode_rows, out_path):
    lines = []
    lines.append("# 实验结果汇总（自动生成）")
    lines.append("")
    lines.append("| 模式 | dTLB MPKI | LLC MPKI | PageFault(/s) | work_ms | ops/s |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for mode, rows in mode_rows.items():
        lines.append(
            f"| {mode} | "
            f"{metric_mean(rows, 'dtlb_mpki'):.3f}±{metric_std(rows, 'dtlb_mpki'):.3f} | "
            f"{metric_mean(rows, 'llc_mpki'):.3f}±{metric_std(rows, 'llc_mpki'):.3f} | "
            f"{metric_mean(rows, 'pf_rate'):.3f}±{metric_std(rows, 'pf_rate'):.3f} | "
            f"{metric_mean(rows, 'work_ms'):.3f}±{metric_std(rows, 'work_ms'):.3f} | "
            f"{metric_mean(rows, 'ops_per_sec'):.1f}±{metric_std(rows, 'ops_per_sec'):.1f} |"
        )
    lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="根据真实实验 CSV 生成论文图表")
    parser.add_argument("--adaptive", required=True, help="adaptive 模式 CSV 路径")
    parser.add_argument("--off", required=True, help="off 模式 CSV 路径")
    parser.add_argument("--on", required=True, help="on 模式 CSV 路径")
    parser.add_argument("--out", default="figures", help="输出目录")
    args = parser.parse_args()

    ensure_dir(args.out)
    adaptive_rows = read_rows(args.adaptive)
    off_rows = read_rows(args.off)
    on_rows = read_rows(args.on)
    mode_rows = {
        "THP_OFF": off_rows,
        "Adaptive": adaptive_rows,
        "THP_ON": on_rows,
    }

    score_path = os.path.join(args.out, "fig1_score_timeline.png")
    bar_path = os.path.join(args.out, "fig2_metrics_bar.png")
    box_path = os.path.join(args.out, "fig3_latency_boxplot.png")
    summary_path = os.path.join(args.out, "results_summary.md")

    draw_score_timeline(adaptive_rows, score_path)
    draw_group_bar(mode_rows, bar_path)
    draw_latency_box(mode_rows, box_path)
    render_summary_markdown(mode_rows, summary_path)

    print(f"[ok] 生成图表: {score_path}")
    print(f"[ok] 生成图表: {bar_path}")
    print(f"[ok] 生成图表: {box_path}")
    print(f"[ok] 生成汇总: {summary_path}")


if __name__ == "__main__":
    main()
