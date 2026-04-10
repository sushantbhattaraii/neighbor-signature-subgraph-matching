#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 6 ]; then
  echo "Usage: run_pipeline.sh <adj_dir> <query_file> <base_output_dir> <baseline|signature> <k> <jar_path>"
  exit 1
fi

ADJ_DIR="$1"
QUERY_FILE="$2"
BASE_OUT="$3"
MODE="$4"
K="$5"
JAR_PATH="$6"

SIG_OUT="$BASE_OUT/signatures"
CAND_OUT="$BASE_OUT/candidates_$MODE"
VERIFY_OUT="$BASE_OUT/matches_$MODE"
CAND_FILE="$CAND_OUT/part-r-00000"

hdfs dfs -rm -r -f "$SIG_OUT" "$CAND_OUT" "$VERIFY_OUT" >/dev/null 2>&1 || true

hadoop jar "$JAR_PATH" edu.kent.cs730.graphmatch.jobs.signature.SignatureConstructionDriver \
  "$ADJ_DIR" "$SIG_OUT"

hadoop jar "$JAR_PATH" edu.kent.cs730.graphmatch.jobs.candidate.CandidateGenerationDriver \
  "$SIG_OUT" "$QUERY_FILE" "$CAND_OUT" "$MODE" "$K"

hadoop jar "$JAR_PATH" edu.kent.cs730.graphmatch.jobs.verify.SubgraphVerificationDriver \
  "$ADJ_DIR" "$QUERY_FILE" "$CAND_FILE" "$VERIFY_OUT"

echo "Done. Outputs:"
echo "  $SIG_OUT"
echo "  $CAND_OUT"
echo "  $VERIFY_OUT"
