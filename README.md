# 面向树莓派4B的地址转换优化实验

本仓库给出课程论文配套代码，核心实现位于 `adaptive_thp_multimetric.c`：

- 面向 ARMv8-A/Linux 的用户态可部署方案；
- 监控三类地址转换相关指标：`dTLB miss`、`cache miss`、`page fault`；
- 通过多指标加权评分动态切换 `MADV_HUGEPAGE` / `MADV_NOHUGEPAGE`；
- 使用双阈值 + 冷却窗口 + 低压稳定判定抑制策略震荡。

## 1. 编译

在树莓派 4B (Ubuntu Server / Raspberry Pi OS 64-bit) 上执行：

```bash
gcc -O2 adaptive_thp_multimetric.c -o adaptive_thp_multimetric
```

## 2. 运行（支持三种模式）

```bash
sudo ./adaptive_thp_multimetric [内存MB] [运行秒数] [mode] [csv路径]
```

示例：

```bash
sudo ./adaptive_thp_multimetric 512 90 adaptive data/adaptive.csv
sudo ./adaptive_thp_multimetric 512 90 off data/off.csv
sudo ./adaptive_thp_multimetric 512 90 on data/on.csv
```

说明：

- 第一个参数：测试缓冲区大小（MB，默认 256）；
- 第二个参数：运行时长（秒，默认 60）；
- 第三个参数：模式（`adaptive` / `off` / `on`）；
- 第四个参数：CSV 输出路径（可选，建议提供）；
- 需要 `perf_event_open` 权限；若受限，请检查 `/proc/sys/kernel/perf_event_paranoid`。

## 3. 一键采集真实数据并出图（推荐）

在树莓派上直接执行：

```bash
bash run_experiment_on_pi.sh 512 90
python3 plot_real_charts.py --adaptive data/adaptive.csv --off data/off.csv --on data/on.csv --out figures
```

将生成：

- `figures/fig1_score_timeline.png`
- `figures/fig2_metrics_bar.png`
- `figures/fig3_latency_boxplot.png`
- `figures/results_summary.md`

## 3.1 本地仿真数据出图（无树莓派时）

```bash
python generate_simulated_data.py --seconds 90 --seed 20260614 --out data
python plot_real_charts.py --adaptive data/adaptive.csv --off data/off.csv --on data/on.csv --out figures
```

说明：该流程用于论文写作阶段的图表占位与方法验证，正式结论建议以板卡实测数据替换。

## 4. 输出字段

每秒打印一行：

- `score`：多指标压力评分（0~1）；
- `dtlb_mpki`：每千指令 dTLB miss；
- `llc_mpki`：每千指令 LLC miss（硬件不支持时回退到 cache miss）；
- `pf_rate`：每秒 page fault 数；
- `work_ms`：每个采样窗口内工作负载执行时延；
- `ops/s`：每秒页面写入操作数；
- `state`：当前大页策略状态（`THP_ON` / `THP_OFF`）；
- `switch_event`：切换事件（CSV 中，`1` 表示切到 ON，`-1` 表示切到 OFF，`0` 为无切换）。

## 5. 与论文正文对应关系

- 论文正文仅展示核心控制逻辑片段；
- 完整可运行实现见 `adaptive_thp_multimetric.c`；
- 图表由 `plot_real_charts.py` 基于真实 CSV 自动生成，可直接插入正文；
- 参数与阈值可根据实验平台调整。
