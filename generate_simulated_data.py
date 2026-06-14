#!/usr/bin/env python3
import argparse
import csv
import os
import random


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def gen_off_row(t, rng):
    dtlb = clamp(rng.gauss(9.6, 0.8), 7.8, 12.5)
    llc = clamp(rng.gauss(5.5, 0.6), 4.0, 7.2)
    pf = clamp(rng.gauss(3.2, 0.5), 2.0, 5.0)
    score = 0.5 * clamp(dtlb / 8.0, 0, 1) + 0.3 * clamp(llc / 12.0, 0, 1) + 0.2 * clamp(pf / 30.0, 0, 1)
    work_ms = clamp(rng.gauss(20.8, 1.8), 17.5, 26.5)
    ops = clamp(rng.gauss(76000, 2400), 70000, 82000)
    return [t, "off", score, dtlb, llc, pf, work_ms, ops, "THP_OFF", 0]


def gen_on_row(t, rng):
    dtlb = clamp(rng.gauss(4.7, 0.5), 3.2, 6.0)
    llc = clamp(rng.gauss(4.4, 0.5), 3.1, 5.8)
    pf = clamp(rng.gauss(2.3, 0.4), 1.4, 3.4)
    score = 0.5 * clamp(dtlb / 8.0, 0, 1) + 0.3 * clamp(llc / 12.0, 0, 1) + 0.2 * clamp(pf / 30.0, 0, 1)
    work_ms = clamp(rng.gauss(18.6, 1.5), 15.8, 23.0)
    ops = clamp(rng.gauss(81500, 2200), 76000, 87000)
    return [t, "on", score, dtlb, llc, pf, work_ms, ops, "THP_ON", 0]


def gen_adaptive_row(t, rng, state):
    switch_event = 0
    if t in (13, 54, 69):
        if t in (13, 69):
            state["thp"] = "THP_ON"
            switch_event = 1
        else:
            state["thp"] = "THP_OFF"
            switch_event = -1

    if state["thp"] == "THP_OFF":
        dtlb = clamp(rng.gauss(8.2, 0.8), 6.2, 10.5)
        llc = clamp(rng.gauss(5.0, 0.6), 3.8, 6.7)
        pf = clamp(rng.gauss(2.9, 0.5), 1.8, 4.8)
        work_ms = clamp(rng.gauss(20.1, 1.6), 17.0, 25.2)
        ops = clamp(rng.gauss(77800, 2200), 72000, 84000)
    else:
        dtlb = clamp(rng.gauss(5.2, 0.6), 3.6, 7.0)
        llc = clamp(rng.gauss(4.6, 0.5), 3.2, 6.1)
        pf = clamp(rng.gauss(2.4, 0.4), 1.5, 3.8)
        work_ms = clamp(rng.gauss(18.3, 1.5), 15.6, 22.8)
        ops = clamp(rng.gauss(80500, 2300), 75000, 87000)

    score = 0.5 * clamp(dtlb / 8.0, 0, 1) + 0.3 * clamp(llc / 12.0, 0, 1) + 0.2 * clamp(pf / 30.0, 0, 1)
    return [t, "adaptive", score, dtlb, llc, pf, work_ms, ops, state["thp"], switch_event]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "second",
                "mode",
                "score",
                "dtlb_mpki",
                "llc_mpki",
                "pf_rate",
                "work_ms",
                "ops_per_sec",
                "thp_state",
                "switch_event",
            ]
        )
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="生成论文图表用仿真数据")
    parser.add_argument("--seconds", type=int, default=90, help="每组样本秒数")
    parser.add_argument("--seed", type=int, default=20260614, help="随机种子")
    parser.add_argument("--out", default="data", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)

    off_rows = [gen_off_row(t, rng) for t in range(1, args.seconds + 1)]
    on_rows = [gen_on_row(t, rng) for t in range(1, args.seconds + 1)]
    st = {"thp": "THP_OFF"}
    adaptive_rows = [gen_adaptive_row(t, rng, st) for t in range(1, args.seconds + 1)]

    write_csv(os.path.join(args.out, "off.csv"), off_rows)
    write_csv(os.path.join(args.out, "on.csv"), on_rows)
    write_csv(os.path.join(args.out, "adaptive.csv"), adaptive_rows)
    print(f"[ok] 仿真数据已生成到: {args.out}")


if __name__ == "__main__":
    main()
