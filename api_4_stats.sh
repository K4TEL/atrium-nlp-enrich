#!/bin/bash
source ./api_util/api_common.sh


echo "=========================================="
echo " STEP 4: GENERATING STATISTICS"
echo " Output: $OUTPUT_DIR/STATS"
echo "=========================================="

mkdir -p "$OUTPUT_DIR/STATS"
STATS_FILE="$OUTPUT_DIR/STATS/summary_ne_counts.csv"

log "Aggregating entities from final CONLLU files..."

python3 api_util/analyze.py "$OUTPUT_DIR/CONLLU_FINAL" "$STATS_FILE"

log "Statistics saved to: $STATS_FILE"
echo "------------------------------------------"
echo "PIPELINE COMPLETE."