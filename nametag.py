import json
import sys
import re
import os
from collections import defaultdict


def parse_nametag_response():
    if len(sys.argv) < 5:
        print("Usage: python3 nametag_parser.py <orig_conllu> <json_resp> <out_dir> <basename>", file=sys.stderr)
        sys.exit(1)

    orig_file = sys.argv[1]
    json_file = sys.argv[2]
    output_dir = sys.argv[3]
    file_base = sys.argv[4]

    # --- PART A: Map Sentences to Page Numbers ---
    # We read the original CoNLL-U file to track '# newdoc' page breaks
    sent_to_page = []
    current_page = 0

    try:
        with open(orig_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue

                if line.startswith('# newdoc'):
                    current_page += 1
                elif line.startswith('# sent_id'):
                    # If file starts without newdoc, assume page 1
                    if current_page == 0: current_page = 1
                    sent_to_page.append(current_page)
    except Exception as e:
        sys.stderr.write(f"Error reading original CoNLL-U: {e}\n")
        sys.exit(1)

    # --- PART B: Parse NameTag Result ---
    entities_by_page = defaultdict(list)

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        tagged_content = data.get('result', '')
        # Split by empty lines to get sentences
        sentences = [s for s in tagged_content.strip().split('\n\n') if s.strip()]

        for idx, sent_block in enumerate(sentences):
            # Match this sentence to its page number
            page_num = sent_to_page[idx] if idx < len(sent_to_page) else current_page

            lines = sent_block.split('\n')
            current_entity_text = []
            current_entity_type = None

            for line in lines:
                if line.startswith('#'): continue
                parts = line.split('\t')

                # --- FIX IS HERE ---
                # NameTag "conll" output is: [Word] [TAB] [Tag]
                if len(parts) < 2: continue

                word = parts[0]  # Column 0 is the Word
                tag = parts[1]  # Column 1 is the Tag (B-per, etc.)

                # BIO Logic
                if tag.startswith('B-'):
                    if current_entity_text:
                        # Save previous entity
                        entities_by_page[page_num].append((current_entity_text, current_entity_type))
                    current_entity_type = tag[2:]  # remove 'B-'
                    current_entity_text = [word]

                elif tag.startswith('I-') and current_entity_type == tag[2:]:
                    current_entity_text.append(word)

                else:
                    # Tag is 'O' or a mismatch
                    if current_entity_text:
                        entities_by_page[page_num].append((current_entity_text, current_entity_type))
                        current_entity_text = []
                        current_entity_type = None

            # Flush entity if sentence ends while inside one
            if current_entity_text:
                entities_by_page[page_num].append((current_entity_text, current_entity_type))

        # --- PART C: Write Output Files ---
        for page_num, entity_list in entities_by_page.items():
            out_filename = f"{file_base}-{page_num}.tsv"
            out_path = os.path.join(output_dir, out_filename)

            with open(out_path, 'w', encoding='utf-8') as f_out:
                f_out.write("Entity\tType\n")
                for words, e_type in entity_list:
                    # Join words with space
                    f_out.write(f"{' '.join(words)}\t{e_type}\n")

    except Exception as e:
        sys.stderr.write(f"Error parsing JSON/CoNLL: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    parse_nametag_response()