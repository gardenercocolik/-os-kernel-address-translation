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

## 2. 运行

```bash
sudo ./adaptive_thp_multimetric [内存MB] [运行秒数]
```

示例：

```bash
sudo ./adaptive_thp_multimetric 512 90
```

说明：

- 第一个参数：测试缓冲区大小（MB，默认 256）；
- 第二个参数：运行时长（秒，默认 60）；
- 需要 `perf_event_open` 权限；若受限，请检查 `/proc/sys/kernel/perf_event_paranoid`。

## 3. 输出字段

每秒打印一行：

- `score`：多指标压力评分（0~1）；
- `dtlb_mpki`：每千指令 dTLB miss；
- `llc_mpki`：每千指令 LLC miss（硬件不支持时回退到 cache miss）；
- `pf_rate`：每秒 page fault 数；
- `state`：当前大页策略状态（`THP_ON` / `THP_OFF`）。

## 4. 与论文正文对应关系

- 论文正文仅展示核心控制逻辑片段；
- 完整可运行实现见 `adaptive_thp_multimetric.c`；
- 参数与阈值可根据实验平台调整。
