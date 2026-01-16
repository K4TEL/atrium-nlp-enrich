import sys
import os
import argparse
from pathlib import Path
import csv
import glob
import re

# Increase CSV field size limit just in case
csv.field_size_limit(sys.maxsize)


def load_config(config_path="api_config.env"):
    """
    Manually parses a simple .env file to set environment variables
    so we don't depend on python-dotenv.
    """
    if not os.path.exists(config_path):
        # It's okay if file doesn't exist, we might have args passed manually
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                # Clean quotes if present
                value = value.strip().strip('"').strip("'")

                # Set env var if not already set (shell priority)
                if key not in os.environ:
                    os.environ[key] = value


def sanitize_filename(name):
    """
    Sanitizes a string to be safe for use as a filename.
    Replaces characters like :, /, \ with underscores.
    """
    safe_name = re.sub(r'[\\/*?:"<>|]', '_', name)
    return safe_name


def merge_single_pair(conllu_path, tsv_path, output_path):
    """
    Merges a single pair of CoNLL-U and TSV files.
    Reads tokens from TSV and inserts NER tags into the MISC column of CoNLL-U.
    """
    tsv_data = []
    try:
        with open(tsv_path, 'r', encoding='utf-8') as f_tsv:
            for line_num, line in enumerate(f_tsv, 1):
                line = line.strip()
                if not line:
                    continue  # Skip empty lines

                parts = line.split('\t')
                if len(parts) >= 2:
                    tsv_data.append({'token': parts[0], 'tag': parts[1], 'line': line_num})
                else:
                    # Fallback for lines with only a token
                    tsv_data.append({'token': parts[0], 'tag': '_', 'line': line_num})
    except FileNotFoundError:
        print(f"Error: TSV file not found: {tsv_path}", file=sys.stderr)
        return False

    tsv_index = 0
    tsv_len = len(tsv_data)

    try:
        with open(conllu_path, 'r', encoding='utf-8') as f_conllu, \
                open(output_path, 'w', encoding='utf-8') as f_out:

            for line in f_conllu:
                stripped_line = line.strip()

                # Passthrough for comments and empty lines
                if not stripped_line or stripped_line.startswith('#'):
                    f_out.write(line)
                    continue

                cols = stripped_line.split('\t')

                # Check for valid ID column (skip multiword tokens like 1-2)
                if len(cols) >= 2 and '-' not in cols[0] and '.' not in cols[0]:
                    if tsv_index < tsv_len:
                        tsv_item = tsv_data[tsv_index]

                        # Add tag to MISC column (column index 9)
                        new_attr = f"NER={tsv_item['tag']}"

                        if len(cols) > 9:
                            if cols[9] == '_':
                                cols[9] = new_attr
                            else:
                                cols[9] += f"|{new_attr}"
                        else:
                            # Fill missing columns if malformed
                            while len(cols) < 9:
                                cols.append('_')
                            cols.append(new_attr)

                        # Write updated line
                        f_out.write('\t'.join(cols) + '\n')
                        tsv_index += 1
                    else:
                        # TSV ended early
                        f_out.write(line)
                else:
                    # Write lines that aren't standard tokens as-is
                    f_out.write(line)

        print(f"[Info] Merged: {os.path.basename(conllu_path)} -> {output_path}")
        return True

    except FileNotFoundError:
        print(f"Error: CoNLL-U file not found: {conllu_path}", file=sys.stderr)
        return False


def parse_features(feat_str):
    """Parses the FEATS column (e.g., 'Case=Nom|Gender=Masc') into a dictionary."""
    if feat_str == '_' or not feat_str:
        return {}
    features = {}
    for item in feat_str.split('|'):
        if '=' in item:
            key, value = item.split('=', 1)
            features[key] = value
    return features


def parse_misc(misc_str):
    """Parses the MISC column (e.g., 'NER=B-per|SpaceAfter=No') into a dictionary."""
    if misc_str == '_' or not misc_str:
        return {}
    misc = {}
    for item in misc_str.split('|'):
        if '=' in item:
            key, value = item.split('=', 1)
            misc[key] = value
        else:
            # Handle singleton flags if any
            misc[item] = "Yes"
    return misc


def write_page_csv(rows, output_dir, page_id, file_counter):
    """
    Writes a list of row dictionaries to a CSV file.
    """
    if not rows:
        return

    # Collect all dynamic keys
    feature_keys = set()
    misc_keys = set()
    for r in rows:
        for k in r.keys():
            if k.startswith('udpipe.feats.'):
                feature_keys.add(k)
            elif k.startswith('udpipe.misc.'):
                misc_keys.add(k)

    # Define Header
    base_header = ['page_id', 'token', 'lemma', 'position', 'nameTag']
    header = base_header + sorted(list(feature_keys)) + sorted(list(misc_keys))

    # Construct filename
    safe_id = sanitize_filename(page_id)
    if not safe_id or safe_id == "unknown":
        filename = f"page_{file_counter:03d}.csv"
    else:
        filename = f"{safe_id}.csv"

    output_path = os.path.join(output_dir, filename)

    try:
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        print(f"  [Error] Failed to write {filename}: {e}", file=sys.stderr)


def process_merged_file_into_pages(merged_filepath, output_subdir):
    """
    Reads a merged CoNLL-U file, detects page boundaries (newdoc),
    and writes separate CSV files for each page into output_subdir.
    """
    print(f"[Processing] Splitting {os.path.basename(merged_filepath)} into pages...")

    current_rows = []
    # Initialize defaults
    page_counter = 0
    current_page_id = "unknown"

    with open(merged_filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # 1. Detect Page Boundary
            if line.startswith('# newdoc'):
                if current_rows:
                    page_counter += 1
                    write_page_csv(current_rows, output_subdir, current_page_id, page_counter)
                    current_rows = []

                if 'id =' in line:
                    parts = line.split('id =')
                    if len(parts) > 1:
                        current_page_id = parts[1].strip()
                    else:
                        current_page_id = f"page_{page_counter + 1}"
                else:
                    current_page_id = f"page_{page_counter + 1}"

                continue

            if line.startswith('#') or not line:
                continue

            parts = line.split('\t')
            if len(parts) < 10:
                continue

            token_id = parts[0]
            if '-' in token_id:
                continue

            token = parts[1]
            lemma = parts[2]
            feats_str = parts[5]
            misc_str = parts[9]

            feats = parse_features(feats_str)
            misc = parse_misc(misc_str)

            row = {
                'page_id': current_page_id,
                'token': token,
                'lemma': lemma,
                'position': token_id,
                'nameTag': misc.get('NER', ''),
            }

            for k, v in feats.items():
                row[f'udpipe.feats.{k}'] = v

            for k, v in misc.items():
                if k != 'NER':
                    row[f'udpipe.misc.{k}'] = v

            current_rows.append(row)

    if current_rows:
        page_counter += 1
        write_page_csv(current_rows, output_subdir, current_page_id, page_counter)


def process_pipeline(conllu_dir, tsv_dir, output_root):
    """
    Main pipeline controller.
    """
    conllu_path_obj = Path(conllu_dir)
    tsv_path_obj = Path(tsv_dir)
    output_root_obj = Path(output_root)

    # Basic validations
    if not conllu_path_obj.exists():
        print(f"Error: CoNLL-U directory '{conllu_dir}' does not exist.")
        sys.exit(1)
    if not tsv_path_obj.exists():
        print(f"Error: TSV directory '{tsv_dir}' does not exist.")
        sys.exit(1)

    # Get file list
    conllu_files = sorted(list(conllu_path_obj.glob('*.conllu')))
    if not conllu_files:
        print(f"No .conllu files found in {conllu_dir}")
        return

    print(f"Found {len(conllu_files)} documents. Starting pipeline...")
    output_root_obj.mkdir(parents=True, exist_ok=True)

    for conllu_file in conllu_files:
        doc_name = conllu_file.stem

        # 1. Prepare Document Output Directory
        doc_out_dir = output_root_obj / doc_name
        doc_out_dir.mkdir(exist_ok=True)

        # 2. Identify Matching TSV
        tsv_file = tsv_path_obj / conllu_file.with_suffix('.tsv').name

        if not tsv_file.exists():
            print(f"[Skip] Missing TSV for {doc_name}")
            continue

        # 3. Merge Step
        merged_file_path = doc_out_dir / f"{doc_name}_merged.conllu"
        success = merge_single_pair(conllu_file, tsv_file, merged_file_path)

        if success:
            # 4. Generate Per-Page CSVs
            process_merged_file_into_pages(merged_file_path, doc_out_dir)

    print("\nPipeline Complete.")


def main():
    # 1. Load Defaults from config file
    load_config('api_config.env')

    parser = argparse.ArgumentParser(description="Merge CoNLL-U & TSV, then generate per-page CSV summaries.")

    # 2. Set defaults using os.getenv
    parser.add_argument('--conllu-dir',
                        default=os.getenv('CONLLU_INPUT_DIR'),
                        help="Directory containing input CoNLL-U files (Default: from config)")
    parser.add_argument('--tsv-dir',
                        default=os.getenv('TSV_INPUT_DIR'),
                        help="Directory containing input TSV files (Default: from config)")
    parser.add_argument('--out-dir',
                        default=os.getenv('SUMMARY_OUTPUT_DIR'),
                        help="Root directory for output (Default: from config)")

    args = parser.parse_args()

    # 3. Manual Validation because required=True was removed
    if not args.conllu_dir:
        parser.error("CoNLL-U directory is required. Set CONLLU_INPUT_DIR in api_config.env or use --conllu-dir.")
    if not args.tsv_dir:
        parser.error("TSV directory is required. Set TSV_INPUT_DIR in api_config.env or use --tsv-dir.")
    if not args.out_dir:
        parser.error("Output directory is required. Set SUMMARY_OUTPUT_DIR in api_config.env or use --out-dir.")

    process_pipeline(args.conllu_dir, args.tsv_dir, args.out_dir)


if __name__ == "__main__":
    main()