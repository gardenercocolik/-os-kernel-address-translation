#!/usr/bin/env bash
set -euo pipefail

# 用法：
#   bash run_experiment_on_pi.sh [mem_mb] [seconds]
# 例：
#   bash run_experiment_on_pi.sh 512 90

MEM_MB="${1:-512}"
SECONDS="${2:-90}"

mkdir -p data figures

echo "[1/4] 编译"
gcc -O2 adaptive_thp_multimetric.c -o adaptive_thp_multimetric

echo "[2/4] 运行 THP_OFF 对照组"
sudo ./adaptive_thp_multimetric "${MEM_MB}" "${SECONDS}" off data/off.csv

echo "[3/4] 运行 Adaptive 实验组"
sudo ./adaptive_thp_multimetric "${MEM_MB}" "${SECONDS}" adaptive data/adaptive.csv

echo "[4/4] 运行 THP_ON 对照组"
sudo ./adaptive_thp_multimetric "${MEM_MB}" "${SECONDS}" on data/on.csv

echo "[done] 数据已生成到 data/ 目录"
echo "[next] 生成图表：python3 plot_real_charts.py --adaptive data/adaptive.csv --off data/off.csv --on data/on.csv --out figures"
