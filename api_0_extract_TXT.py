#!/usr/bin/env python3
"""
api_0_extract_TXT.py

This script scans a given input folder for ALTO XML files. It can scan
both the root of the folder and one level of subdirectories.

For each ALTO XML file found, it executes the external command 'alto-tools -s'
(statistics) to get counts of various XML elements (e.g., <TextLine>,
<String>, <Illustration>).

It then parses this output and compiles all the statistics into a single
CSV file, along with the file/page identifiers derived from the filenames
and the full path to the XML file.

This CSV is the primary input for the next step in the pipeline

Step 2: Extract text from ALTO XML files in parallel.
"""
import pandas as pd
import subprocess
import concurrent.futures
import os
import sys
from pathlib import Path
from tqdm import tqdm
import re  # For regular expressions, to parse the command output

INPUT_ALTO_DIR = "../ALTO/A-PAGE"
STATS_CSV = "alto_statistics.csv"
OUTPUT_TEXT_DIR = "../PAGE_TXT"
MAX_WORKERS = 16


def parse_alto_tools_stats_line(line):
    """
    Parses a single line of output from `alto-tools -s`.

    Example input line:
      "# of <TextLine> elements: 33"

    Example output dict:
      {"textlines": 33}

    Args:
        line (str): A single line of text from the command output.

    Returns:
        dict or None: A dictionary with a normalized key (e.g., "textlines")
                      and the integer count, or None if the line doesn't match.
    """
    # This regex looks for:
    #   "# of <" + (one or more word characters) + "> elements:" + (optional whitespace) + (one or more digits)
    m = re.match(r"# of <(\w+)> elements:\s+(\d+)", line.strip())

    if not m:
        # Line didn't match the pattern (e.g., it's an empty line)
        return None

    # m.groups() will be ("TextLine", "33")
    element, count = m.groups()
    element = element.lower()  # Normalize to lowercase (e.g., "textline")

    # Map from the XML element name to the desired CSV column name
    mapping = {
        "textline": "textlines",
        "string": "strings",
        "glyph": "glyphs",
        "illustration": "illustrations",
        "graphicalelement": "graphics",
    }

    # Use the mapped name if it exists, otherwise just use the element name
    key = mapping.get(element, element)
    return {key: int(count)}


def run_alto_tools_stats(xml_path):
    """
    Runs the `alto-tools -s` command on a single XML file and parses its output.

    Args:
        xml_path (str): The full path to the ALTO XML file.

    Returns:
        dict or None: A dictionary containing all statistics for the file,
                      or None if the command fails.
    """
    cmd = ["alto-tools", "-s", xml_path]
    try:
        # Run the command and capture its standard output
        # 'stderr=subprocess.STDOUT' merges error messages into the output
        # 'text=True' decodes the output as text (not bytes)
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        # The command failed (returned a non-zero exit code)
        print(f"⚠️ Error running alto-tools on {xml_path}: {e.output}")
        return None

    stats = {}
    # Process the command's output line by line
    for line in out.splitlines():
        parsed = parse_alto_tools_stats_line(line)
        if parsed:
            # Add the parsed {key: value} to our main stats dictionary
            stats.update(parsed)
    return stats


def process_alto_files_with_alto_tools(directory_path):
    """
    Processes all ALTO XML files found directly within a given directory.

    Args:
        directory_path (str): The folder to scan for .xml files.

    Returns:
        list[dict]: A list of dictionaries, where each dict holds the
                    stats for one file.
    """
    results = []
    # Loop through every file in the directory
    for fname in os.listdir(directory_path):
        # Skip files that don't end in .xml
        if not fname.lower().endswith(".xml"):
            continue

        xml_path = os.path.join(directory_path, fname)

        # Get the statistics for this file
        stats = run_alto_tools_stats(xml_path)
        if stats is None:
            # An error occurred and was already printed, so just skip this file
            continue

        # --- Derive file ID and page ID from the filename ---
        # e.g., "doc123-001.alto.xml"
        base = os.path.basename(fname).split(".")[0]  # "doc123-001"
        parts = base.split("-")  # ["doc123", "001"]
        file_id = parts[0]  # "doc123"
        page = parts[1] if len(parts) > 1 else ""  # "001"

        # Build the result dictionary for this file
        rec = {
            "file": file_id,
            "page": page,
        }

        # Map the parsed keys to our final dictionary keys, defaulting to 0
        rec["textlines"] = int(stats.get("textlines", 0))
        rec["illustrations"] = int(stats.get("illustrations", 0))
        rec["graphics"] = int(stats.get("graphics", 0))
        rec["strings"] = int(stats.get("strings", 0))
        # Add the full path, as this is needed by later scripts
        rec["path"] = xml_path

        results.append(rec)
    return results


def extract_single_page(args):
    """Worker function to extract one page with robust de-hyphenation."""
    file_id, page_id, xml_path, output_dir = args

    # Define output path
    save_dir = Path(output_dir) / str(file_id)
    save_dir.mkdir(parents=True, exist_ok=True)
    txt_path = save_dir / f"{file_id}-{page_id}.txt"

    # Skip if exists
    if txt_path.exists():
        return True

    # Define common hyphen variations found in OCR/Typesetting
    # Standard hyphen, Soft hyphen (\xad), En dash (\u2013), Em dash (\u2014)
    HYPHEN_VARIATIONS = ('-', '\xad', '\u2013', '\u2014')

    # Run extraction (alto-tools)
    cmd = ["alto-tools", "-t", xml_path]
    backup_xml_path = Path(xml_path).parents[1] / "onepagers" / Path(xml_path).name
    if backup_xml_path.exists():
        cmd = ["alto-tools", "-t", str(backup_xml_path)]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if res.returncode == 0:
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]

            # De-hyphenation Logic
            for i in range(len(lines) - 1):
                # Check if line ends with any of the hyphen variations
                if lines[i].endswith(HYPHEN_VARIATIONS):

                    # Remove the specific hyphen character detected
                    # We strip the last character regardless of which variation it was
                    prefix = lines[i][:-1]

                    next_line_parts = lines[i + 1].split(maxsplit=1)

                    if next_line_parts:
                        suffix = next_line_parts[0]

                        # Combine prefix and suffix on the current line
                        lines[i] = prefix + suffix

                        # Remove the suffix from the next line
                        if len(next_line_parts) > 1:
                            lines[i + 1] = next_line_parts[1]
                        else:
                            lines[i + 1] = ""

            # Final cleanup: Remove any empty lines created by the merge
            final_lines = [l for l in lines if l.strip()]

            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(final_lines))
            return True
        else:
            return False
    except Exception:
        return False


def main():
    # --- 2. Prepare Output File ---
    # Remove the output file if it already exists, so we start fresh
    if os.path.exists(STATS_CSV):
        os.remove(STATS_CSV)

    # --- 3. Find Subdirectories ---
    # This script is designed to check the root input_folder *and*
    # one level of subdirectories.
    subdirs = [os.path.join(INPUT_ALTO_DIR, d)
               for d in os.listdir(INPUT_ALTO_DIR)
               if os.path.isdir(os.path.join(INPUT_ALTO_DIR, d))]

    # 'first' flag is used to ensure we only write the CSV header *once*
    first = True

    # --- 4. Process Subdirectories ---
    for subdir in subdirs:
        stats = process_alto_files_with_alto_tools(subdir)
        if stats:
            # Convert the list of dictionaries into a pandas DataFrame
            df = pd.DataFrame(stats)
            if first:
                # First write: include the header
                df.to_csv(STATS_CSV, index=False, header=True)
                first = False
            else:
                # Subsequent writes: append (mode="a") and skip the header
                df.to_csv(STATS_CSV, index=False, header=False, mode="a")
            print(f"Processed {len(stats)} files from {subdir}")

    # --- 5. Process Root Directory ---
    # After processing subdirs, process any .xml files in the root folder
    stats = process_alto_files_with_alto_tools(INPUT_ALTO_DIR)
    if stats:
        df = pd.DataFrame(stats)
        if first:
            df.to_csv(STATS_CSV, index=False, header=True)
            first = False
        else:
            df.to_csv(STATS_CSV, index=False, header=False, mode="a")
        print(f"Processed {len(stats)} files from {INPUT_ALTO_DIR}")

    print("Done.")

    df = pd.read_csv(STATS_CSV)
    print(f"Loaded {len(df)} pages to extract.")

    tasks = []
    for _, row in df.iterrows():
        tasks.append((row['file'], row['page'], row['path'], OUTPUT_TEXT_DIR))

    # Parallel Execution
    print(f"Extracting with {MAX_WORKERS} workers...")
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(tqdm(executor.map(extract_single_page, tasks), total=len(tasks)))

    print(f"Extraction complete. Success rate: {sum(results) / len(results):.2%}")


if __name__ == "__main__":
    main()