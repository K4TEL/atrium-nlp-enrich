#!/bin/bash
source ./api_util/api_common.sh

echo "=========================================="
echo " STEP 3: NAMETAG PROCESSING (Per-Page Output)"
echo " Model: $MODEL_NAMETAG"
echo "=========================================="

mkdir -p "$OUTPUT_DIR/NE"
log "Starting NameTag processing..."

count=0

for conllu_file in "$WORK_DIR/UDPIPE"/*.conllu; do
    [ -e "$conllu_file" ] || continue

    filename=$(basename "$conllu_file")
    basename_no_ext="${filename%.conllu}"

    # Create a specific directory for this document's pages
    doc_output_dir="$OUTPUT_DIR/NE/$basename_no_ext"

    # Skip if directory exists and is not empty
    if [ -d "$doc_output_dir" ] && [ "$(ls -A "$doc_output_dir")" ]; then
        continue
    fi

    mkdir -p "$doc_output_dir"
    log " -> Tagging: $filename (Page split in $doc_output_dir)"

    # 1. PREPARE CLEAN INPUT
    clean_input="${WORK_DIR}/temp_clean_${filename}"
    sed '/^# generator/d; /^# udpipe_model/d' "$conllu_file" > "$clean_input"

    resp_file="$WORK_DIR/nametag_response_${filename}.json"

    # 2. CALL API
    if api_call_with_retry "NameTag" "$NAMETAG_URL" "$resp_file" \
        -F "data=@${clean_input}" -F "input=conllu" -F "output=conll" \
        -F "model=${MODEL_NAMETAG}"; then

        # 3. PARSE JSON & WRITE PER-PAGE FILES (Using Helper)
        python3 api_util/nametag.py \
            "$conllu_file" \
            "$resp_file" \
            "$doc_output_dir" \
            "$basename_no_ext"

        ((count++))
    else
        echo "=============================="
        echo "API ERROR RESPONSE CONTENT:"
        cat "$resp_file"
        echo "=============================="
    fi

    # 4. CLEAN UP
    rm -f "$clean_input"
    rm -f "$resp_file"

    rate_limit
done

log "Finished. Processed $count documents."
echo "------------------------------------------"
echo "Done. Please run ./api_4_stats.sh next."