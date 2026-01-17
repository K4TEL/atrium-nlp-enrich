import sys
import os
import argparse
from pathlib import Path
import csv
import re
import glob

# Increase CSV field size limit just in case
csv.field_size_limit(sys.maxsize)


def load_config(config_path="api_config.env"):
    if not os.path.exists(config_path):
        return
    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key not in os.environ:
                os.environ[key] = value


def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '_', name)


def get_sorted_tsv_content(doc_tsv_dir):
    """
    Reads all .tsv files in the document directory, sorts them by page number
    (assuming format doc-PAGE.tsv), and returns a single list of tokens/tags.
    """
    all_data = []

    files = list(Path(doc_tsv_dir).glob("*.tsv"))

    def sort_key(filepath):
        try:
            match = re.search(r'-(\d+)\.tsv$', filepath.name)
            if match:
                return int(match.group(1))
            return 0
        except:
            return 0

    files.sort(key=sort_key)

    for fpath in files:
        with open(fpath, 'r', encoding='utf-8') as f:
            header = next(f, None)
            for line in f:
                line = line.strip()
                if not line: continue

                parts = line.split('\t')
                if len(parts) >= 2:
                    all_data.append({'token': parts[0], 'tag': parts[1]})
                else:
                    all_data.append({'token': parts[0], 'tag': 'O'})

    return all_data


def merge_and_write(conllu_path, tsv_data, output_path):
    tsv_index = 0
    tsv_len = len(tsv_data)

    try:
        with open(conllu_path, 'r', encoding='utf-8') as f_conllu, \
                open(output_path, 'w', encoding='utf-8') as f_out:

            for line in f_conllu:
                stripped_line = line.strip()

                if not stripped_line or stripped_line.startswith('#'):
                    f_out.write(line)
                    continue

                cols = stripped_line.split('\t')

                if len(cols) >= 2 and '-' not in cols[0] and '.' not in cols[0]:
                    if tsv_index < tsv_len:
                        tsv_item = tsv_data[tsv_index]
                        new_attr = f"NER={tsv_item['tag']}"

                        if len(cols) > 9:
                            if cols[9] == '_':
                                cols[9] = new_attr
                            else:
                                cols[9] += f"|{new_attr}"
                        else:
                            while len(cols) < 9:
                                cols.append('_')
                            cols.append(new_attr)

                        f_out.write('\t'.join(cols) + '\n')
                        tsv_index += 1
                    else:
                        f_out.write(line)
                else:
                    f_out.write(line)

        return True

    except Exception as e:
        print(f"Error merging {conllu_path}: {e}", file=sys.stderr)
        return False


def parse_features(feat_str):
    if feat_str == '_' or not feat_str: return {}
    return {k: v for item in feat_str.split('|') if '=' in item for k, v in [item.split('=', 1)]}


def parse_misc(misc_str):
    if misc_str == '_' or not misc_str: return {}
    misc = {}
    for item in misc_str.split('|'):
        if '=' in item:
            k, v = item.split('=', 1)
            misc[k] = v
        else:
            misc[item] = "Yes"
    return misc


def write_page_csv(rows, output_dir, page_id, file_counter):
    if not rows: return

    feature_keys = set()
    misc_keys = set()
    for r in rows:
        for k in r.keys():
            if k.startswith('udpipe.feats.'):
                feature_keys.add(k)
            elif k.startswith('udpipe.misc.'):
                misc_keys.add(k)

    header = ['page_id', 'token', 'lemma', 'position', 'nameTag'] + \
             sorted(list(feature_keys)) + sorted(list(misc_keys))

    doc_name = os.path.basename(output_dir)
    safe_id = sanitize_filename(str(page_id))
    filename = f"{doc_name}-{safe_id}.csv"

    out_path = os.path.join(output_dir, filename)

    try:
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        print(f"  [Error] writing {filename}: {e}", file=sys.stderr)


def process_merged_file_into_pages(merged_filepath, output_subdir):
    current_rows = []
    page_counter = 0

    with open(merged_filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            if line.startswith('# sent_id'):
                parts = line.split('=', 1)
                if len(parts) > 1 and parts[1].strip() == '1':
                    if current_rows:
                        write_page_csv(current_rows, output_subdir, page_counter, page_counter)
                        current_rows = []
                    page_counter += 1

            if line.startswith('#') or not line:
                continue

            parts = line.split('\t')
            if len(parts) < 10 or '-' in parts[0]:
                continue

            if page_counter == 0: page_counter = 1

            misc = parse_misc(parts[9])
            feats = parse_features(parts[5])

            row = {
                'page_id': page_counter,
                'token': parts[1],
                'lemma': parts[2],
                'position': parts[0],
                'nameTag': misc.get('NER', ''),
            }
            for k, v in feats.items(): row[f'udpipe.feats.{k}'] = v
            for k, v in misc.items():
                if k != 'NER': row[f'udpipe.misc.{k}'] = v

            current_rows.append(row)

    if current_rows:
        write_page_csv(current_rows, output_subdir, page_counter, page_counter)


def process_pipeline(conllu_dir, tsv_root, output_root):
    conllu_path_obj = Path(conllu_dir)
    tsv_root_obj = Path(tsv_root)
    output_root_obj = Path(output_root)

    if not conllu_path_obj.exists():
        print(f"Error: CoNLL-U dir not found: {conllu_dir}")
        sys.exit(1)

    conllu_files = sorted(list(conllu_path_obj.glob('*.conllu')))
    print(f"Found {len(conllu_files)} documents to process.")

    output_root_obj.mkdir(parents=True, exist_ok=True)

    for conllu_file in conllu_files:
        doc_name = conllu_file.stem

        # 1. Define paths
        doc_out_dir = output_root_obj / doc_name
        doc_tsv_dir = tsv_root_obj / doc_name

        if not doc_tsv_dir.exists() or not doc_tsv_dir.is_dir():
            print(f"[Skip] No TSV directory found for: {doc_name} (checked {doc_tsv_dir})")
            continue

        # 2. Count Input vs Output to determine skip
        # We need to know how many pages exist in the input to compare with output
        input_tsvs = list(doc_tsv_dir.glob("*.tsv"))
        count_input = len(input_tsvs)

        if doc_out_dir.exists():
            output_csvs = list(doc_out_dir.glob("*.csv"))
            count_output = len(output_csvs)

            # --- STRICT SKIP LOGIC ---
            # Only skip if the output count exactly matches input count
            if count_input > 0 and count_input == count_output:
                print(f"[Skip] {doc_name}: Output complete ({count_output} CSVs match {count_input} TSVs).")
                continue
            elif count_output > 0:
                print(f"[Reprocess] {doc_name}: Count mismatch (Input: {count_input} vs Output: {count_output}).")

        print(f"[Processing] {doc_name}...")

        # 3. Gather all pages (TSVs) into one stream
        tsv_data = get_sorted_tsv_content(doc_tsv_dir)
        if not tsv_data:
            print(f"  [Warn] No valid TSV data found in {doc_tsv_dir}")
            continue

        # 4. Create output folder
        doc_out_dir.mkdir(exist_ok=True)

        # 5. Merge
        merged_file_path = doc_out_dir / f"{doc_name}_merged.tmp"
        if merge_and_write(conllu_file, tsv_data, merged_file_path):
            # 6. Generate CSVs
            process_merged_file_into_pages(merged_file_path, doc_out_dir)
            # Cleanup temp file
            try:
                os.remove(merged_file_path)
            except:
                pass

    print("\nPipeline Complete.")


def main():
    load_config('api_config.env')
    parser = argparse.ArgumentParser()
    parser.add_argument('--conllu-dir', default=os.getenv('CONLLU_INPUT_DIR'))
    parser.add_argument('--tsv-dir', default=os.getenv('TSV_INPUT_DIR'))
    parser.add_argument('--out-dir', default=os.getenv('SUMMARY_OUTPUT_DIR'))
    args = parser.parse_args()

    if not all([args.conllu_dir, args.tsv_dir, args.out_dir]):
        print("Missing arguments. Check config or flags.")
        sys.exit(1)

    process_pipeline(args.conllu_dir, args.tsv_dir, args.out_dir)


if __name__ == "__main__":
    main()