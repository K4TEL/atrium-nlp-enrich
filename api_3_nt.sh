#!/bin/bash
source ./api_util/api_common.sh


echo "=========================================="
echo " STEP 3: NAMETAG PROCESSING"
echo " Model: $MODEL_NAMETAG"
echo "=========================================="

mkdir -p "$OUTPUT_DIR/NE"
log "Starting NameTag processing..."

count=0

for conllu_file in "$WORK_DIR/UDPIPE"/*.conllu; do
    [ -e "$conllu_file" ] || continue

    filename=$(basename "$conllu_file")

    final_output="$OUTPUT_DIR/NE/${filename%.conllu}.tsv"
    temp_output="${final_output}.tmp"

    # Check if already done
    if [ -s "$final_output" ]; then continue; fi

    log " -> Tagging: $filename"
    resp_file="$WORK_DIR/nametag_response_${filename}.json"

    # --- DEBUG VERSION OF THE CALL ---
    if api_call_with_retry "NameTag" "$NAMETAG_URL" "$resp_file" \
        -F "data=@${conllu_file}" -F "input=conllu-ne" -F "output=conll" \
        -F "model=${MODEL_NAMETAG}"; then

        parse_json_result "$resp_file" > "$temp_output"

        if [ -s "$temp_output" ]; then
            mv "$temp_output" "$final_output"
            ((count++))
        else
            rm -f "$temp_output"
        fi
    else
        # !!! ADDED DEBUGGING !!!
        echo "=============================="
        echo "API ERROR RESPONSE CONTENT:"
        cat "$resp_file"
        echo "=============================="
    fi
    # ---------------------------------
    rate_limit
done

log "Finished. Tagged $count new documents."
echo "------------------------------------------"
echo "Done. Please run ./api_4_stats.sh next."