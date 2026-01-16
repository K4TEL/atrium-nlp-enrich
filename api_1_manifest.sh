#!/bin/bash
source ./api_util/api_common.sh

echo "=========================================="
echo " STEP 1: MANIFEST GENERATION"
echo " Input: $INPUT_DIR"
echo "=========================================="

mkdir -p "$WORK_DIR"
log "Generating sorted file manifest..."

# Calls the python script using the config variables
python3 api_util/manifest.py "$INPUT_DIR" "$WORK_DIR/manifest.tsv"

log "Manifest created at $WORK_DIR/manifest.tsv"
echo "------------------------------------------"
echo "Done. Please run ./api_2_udp.sh next."