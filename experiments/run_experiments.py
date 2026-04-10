#!/usr/bin/env python3
"""Run baseline and signature pipelines and collect simple metrics into CSV."""

import argparse
import csv
import subprocess
import time
from pathlib import Path


def sh(cmd: str):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)


def hdfs_count_lines(path: str) -> int:
    result = sh(f"hdfs dfs -cat {path} | wc -l")
    return int(result.stdout.strip() or 0)


def hdfs_cat(path: str) -> str:
    result = sh(f"hdfs dfs -cat {path}")
    return result.stdout


def candidate_count_from_file(path: str) -> int:
    total = 0
    data = hdfs_cat(path)
    for line in data.splitlines():
        parts = line.split('\t')
        if len(parts) < 2 or parts[1].strip() in ('', '-'):
            continue
        total += len(parts[1].split(','))
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adj-dir', required=True)
    parser.add_argument('--query-file', required=True)
    parser.add_argument('--base-output', required=True)
    parser.add_argument('--k', type=int, default=2)
    parser.add_argument('--jar', required=True)
    parser.add_argument('--csv', default='experiment_results.csv')
    args = parser.parse_args()

    rows = []
    for mode in ('baseline', 'signature'):
        start = time.time()
        cmd = f"bash scripts/run_pipeline.sh {args.adj_dir} {args.query_file} {args.base_output} {mode} {args.k} {args.jar}"
        proc = subprocess.run(cmd, shell=True, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
        elapsed = time.time() - start
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr)

        cand_file = f"{args.base_output}/candidates_{mode}/part-r-00000"
        match_file = f"{args.base_output}/matches_{mode}/part-r-00000"
        candidate_count = candidate_count_from_file(cand_file)
        match_count = hdfs_count_lines(match_file)

        rows.append({
            'mode': mode,
            'k': args.k,
            'cpu_time_sec': round(elapsed, 3),
            'candidate_count_after_pruning': candidate_count,
            'valid_matches_found': match_count,
        })

    baseline_candidates = next(r['candidate_count_after_pruning'] for r in rows if r['mode'] == 'baseline')
    for row in rows:
        row['pruning_ratio_pct_vs_baseline'] = round(
            100.0 * (baseline_candidates - row['candidate_count_after_pruning']) / max(1, baseline_candidates), 3
        )

    with open(args.csv, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote metrics to {args.csv}")


if __name__ == '__main__':
    main()
