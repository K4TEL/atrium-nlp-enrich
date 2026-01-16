#!/bin/bash
source ./api_util/api_common.sh

echo "=========================================="
echo " STEP 2: UDPIPE PROCESSING"
echo " Model: $MODEL_UDPIPE"
echo "=========================================="

mkdir -p "$WORK_DIR/UDPIPE" "$WORK_DIR/CHUNKS"
MANIFEST="$WORK_DIR/manifest.tsv"

if [ ! -f "$MANIFEST" ]; then
    echo "Error: Manifest not found. Please run ./api_1_manifest.sh first."
    exit 1
fi

log "Starting UDPipe processing..."

prev_doc_id=""
current_temp_file=""
skipping_current=false
doc_count=0

# Loop through manifest
while IFS=$'\t' read -r doc_id page_num file_path; do

    if [ "$doc_id" != "$prev_doc_id" ]; then
        # 1. Finalize Previous Document
        if [ -n "$prev_doc_id" ] && [ "$prev_doc_id" != "__END__" ] && [ "$skipping_current" = false ]; then
            final_target="${current_temp_file%.tmp}"
            if [ -s "$current_temp_file" ]; then
                mv "$current_temp_file" "$final_target"
                log " [Saved] $(basename "$final_target")"
                ((doc_count++))
            else
                rm -f "$current_temp_file"
            fi
        fi

        if [ "$doc_id" == "__END__" ]; then break; fi

        # 2. Setup New Document
        safe_doc_id=$(basename "$doc_id")
        final_conllu="$WORK_DIR/UDPIPE/${safe_doc_id}.conllu"
        current_temp_file="${final_conllu}.tmp"

        if [ -s "$final_conllu" ]; then
            skipping_current=true
        else
            skipping_current=false
            log " -> Processing Doc: $safe_doc_id"
            : > "$current_temp_file"
        fi
        prev_doc_id="$doc_id"
    fi

    if [ "$skipping_current" = true ]; then continue; fi

    # 3. Process Page Chunks
    page_chunk_dir="$WORK_DIR/CHUNKS/$(basename "$doc_id")_${page_num}"
    rm -rf "$page_chunk_dir" && mkdir -p "$page_chunk_dir"

    # Split text into chunks
    python3 api_util/chunk.py "$file_path" "$page_chunk_dir" "$WORD_CHUNK_LIMIT"

    # Flag to identify the very first chunk of the document
    # If the file is empty (newly created), this is the first chunk.
    if [ ! -s "$current_temp_file" ]; then
        is_first_chunk=true
    else
        is_first_chunk=false
    fi

    for chunk_file in "$page_chunk_dir"/*.txt; do
        [ -e "$chunk_file" ] || continue
        resp_file="${chunk_file}.json"

        # Call UDPipe
        if api_call_with_retry "UDPipe" "$UDPIPE_URL" "$resp_file" \
            -F "data=@${chunk_file}" \
            -F "model=${MODEL_UDPIPE}" \
            -F "tokenizer=" \
            -F "tagger=" \
            -F "parser="; then

            # Parse JSON to get CoNLL-U content
            # We capture it in a variable first
            raw_conllu=$(parse_json_result "$resp_file")

            if [ "$is_first_chunk" = true ]; then
                # First chunk: Write everything (including headers)
                echo "$raw_conllu" >> "$current_temp_file"
                is_first_chunk=false
            else
                # Subsequent chunks: Strip metadata headers to keep file valid
                # Removes lines starting with # newdoc, # newpar, # generator, # udpipe
                echo "$raw_conllu" | grep -vE "^# (newdoc|newpar|generator|udpipe)" >> "$current_temp_file"
            fi

            # Ensure exactly one newline between chunks (CoNLL-U requirement)
            # We check if the last line of the file is already empty
            last_line=$(tail -n 1 "$current_temp_file")
            if [ -n "$last_line" ]; then
                echo "" >> "$current_temp_file"
            fi
        fi
        rate_limit
    done
    rm -rf "$page_chunk_dir"

done < <(cat "$MANIFEST" <(echo -e "__END__\t0\t__END__"))

echo "------------------------------------------"
echo "Done. Processed $doc_count documents."
echo "Please run ./api_3_nt.sh next."