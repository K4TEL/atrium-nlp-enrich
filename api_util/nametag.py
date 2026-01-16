import json
import sys
import os
from collections import defaultdict


def get_ne_suffix(tag_string):
    """
    Extracts the entity suffix (type) from a BIO tag.
    Handles single tags (e.g., "B-per") and multi-tags (e.g., "B-C|B-ic").
    If the tag is "O", it returns "O".
    """
    if not tag_string:
        return ""

    # Split by pipe in case of ambiguity/multiple tags (e.g., "B-T|B-td")
    sub_tags = tag_string.split('|')
    suffixes = []

    for t in sub_tags:
        # Check for standard B- or I- prefixes
        if t.startswith('B-') or t.startswith('I-'):
            # Return everything after the first hyphen
            # split('-', 1) ensures we only split on the prefix hyphen
            parts = t.split('-', 1)
            if len(parts) > 1:
                suffixes.append(parts[1])
            else:
                suffixes.append(t)
        else:
            # Usually "O" or raw tags without prefixes
            suffixes.append("")

    return '|'.join(suffixes)


def parse_nametag_response():
    if len(sys.argv) < 5:
        print("Usage: python3 nametag.py <orig_conllu> <json_resp> <out_dir> <basename>", file=sys.stderr)
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
    # Store simply as list of (word, tag) tuples per page
    tokens_by_page = defaultdict(list)

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

            for line in lines:
                if line.startswith('#'): continue

                parts = line.split('\t')

                # NameTag "conll" output is: [Word] [TAB] [Tag]
                if len(parts) < 2:
                    continue

                word = parts[0]  # Column 0 is the Word
                tag = parts[1]  # Column 1 is the Tag (B-per, O, etc.)

                # We save every word and its tag directly
                tokens_by_page[page_num].append((word, tag))

        # --- PART C: Write Output Files ---
        for page_num, token_list in tokens_by_page.items():
            out_filename = f"{file_base}-{page_num}.tsv"
            out_path = os.path.join(output_dir, out_filename)

            with open(out_path, 'w', encoding='utf-8') as f_out:
                # Header for 3 columns
                f_out.write("Word\tTag\tNE\n")

                for word, tag in token_list:
                    # Calculate the NE column (suffix)
                    ne_val = get_ne_suffix(tag)
                    f_out.write(f"{word}\t{tag}\t{ne_val}\n")

    except Exception as e:
        sys.stderr.write(f"Error parsing JSON/CoNLL: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    parse_nametag_response()