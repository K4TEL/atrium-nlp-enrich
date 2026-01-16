#!/bin/bash
source ./api_util/api_common.sh

echo "=========================================="
echo " STEP 4: SUMMARIZATION & STATISTICS"
echo "=========================================="

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# Adjust these subdirectories if your pipeline names them differently
# Input 1: The UDPipe CoNLL-U files
INPUT_UDP_DIR="$WORK_DIR/UDPIPE"

# Input 2: The NameTag TSV files
INPUT_TSV_DIR="$OUTPUT_DIR/NE"

# Output: Where the per-page CSV summaries will go
SUMMARY_OUT_DIR="$OUTPUT_DIR/SUMMARY"

# Stats Output: Where the entity count CSV will go
STATS_FILE="$OUTPUT_DIR/STATS/summary_ne_counts.csv"

mkdir -p "$SUMMARY_OUT_DIR"
mkdir -p "$(dirname "$STATS_FILE")"

# -----------------------------------------------------------------------------
# PART A: MERGE & SUMMARIZE (Main Result)
# -----------------------------------------------------------------------------
log "Starting consolidation: Merging CoNLL-U and TSV into per-page CSVs..."
log "Input CoNLL-U: $INPUT_UDP_DIR"
log "Input TSV:     $INPUT_TSV_DIR"

# Calls the new python script to generate the detailed CSVs
python3 api_util/summarize_nt_udp.py \
    --conllu-dir "$INPUT_UDP_DIR" \
    --tsv-dir "$INPUT_TSV_DIR" \
    --out-dir "$SUMMARY_OUT_DIR"

if [ $? -eq 0 ]; then
    log "Summarization complete. CSVs saved to: $SUMMARY_OUT_DIR"
else
    log "Error: Summarization script failed."
    exit 1
fi

# -----------------------------------------------------------------------------
# PART B: GENERATE STATISTICS (Additional Result)
# -----------------------------------------------------------------------------
log "Generating entity statistics..."

# We analyze the Named Entity folder (or the new summary folder if analyze.py supports CSV).
# Assuming analyze.py works on the TSV/NE output as per original script:
NE_SOURCE_DIR="$INPUT_TSV_DIR"

python3 api_util/analyze.py "$NE_SOURCE_DIR" "$STATS_FILE"

if [ $? -eq 0 ]; then
    log "Statistics saved to: $STATS_FILE"
else
    log "Warning: Statistics generation encountered an issue."
fi

echo "------------------------------------------"
echo "PIPELINE COMPLETE."
echo "Main Output: $SUMMARY_OUT_DIR"
echo "Stats Output: $STATS_FILE"