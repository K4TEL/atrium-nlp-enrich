# api_util/analyze.py

import sys
import os
import csv
from collections import Counter

# Increase field limit for large CSVs
csv.field_size_limit(sys.maxsize)

# --- CNEC 2.0 Type Hierarchy Mapping ---
# Based on: https://ufal.mff.cuni.cz/~strakova/cnec2.0/ne-type-hierarchy.pdf
CNEC_TYPE_MAP = {
    # a: Numbers, addresses, time
    "a": "Address/Number/Time (General)",
    "A": "Complex Address/Number/Time",
    "ah": "Street address",
    "at": "Phone/Fax number",
    "az": "Zip code",

    # g: Geographical names
    "g": "Geographical name (General)",
    "G": "Geographical name (General)",
    "g_": "Geographical name (General)",
    "gu": "Settlement name (City/Town)",
    "gl": "Nature/Landscape name (Mountain/River)",
    "gq": "Urban geographical name (Street/Square)",
    "gr": "Territorial name (State/Region)",
    "gs": "Super-terrestrial name (Star/Planet)",
    "gc": "States/Provinces/Regions",
    "gt": "Continents",
    "gh": "Hydronym (Bodies of water)",

    # i: Institutions
    "i": "Institution name (General)",
    "i_": "Institution name (General)",
    "I": "Institution name (General)",
    "ia": "Conference/Contest",
    "if": "Company/Firm",
    "io": "Organization/Society",
    "ic": "Cult/Educational institution",

    # m: Media names
    "m": "Media name (General)",
    "mn": "Periodical name (Newspaper/Magazine)",
    "ms": "Radio/TV station",
    "mi": "Internet links",

    # o: Artifact names
    "o": "Artifact name (General)",
    "o_": "Artifact name (General)",
    "oa": "Cultural artifact (Book/Painting)",
    "oe": "Measure unit",
    "om": "Currency",
    "or": "Directives, norms",
    "op": "Product (General)",

    # p: Personal names
    "p": "Personal name (General)",
    "p_": "Personal name (General)",
    "P": "Complex personal names",
    "pf": "First name",
    "ps": "Surname",
    "pm": "Second name",
    "ph": "Nickname/Pseudonym",
    "pc": "Inhabitant name",
    "pd": "Academic titles",
    "pp": "Relig./myth persons",
    "me": "Email address",

    # t: Time expressions
    "t": "Time expression (General)",
    "T": "Complex time expressions",
    "td": "Day",
    "th": "Hour",
    "tm": "Month",
    "ty": "Year",
    "tf": "Holiday/Feast",
    "tt": "Time block",

    # n: Number expressions
    "n": "Number expression (General)",
    "N": "Complex number expressions",
    "n_": "Number expression (General)",
    "na": "Age",
    "nb": "Volu-metric number",
    "nc": "Cardinal number",
    "ni": "Itemizer (1.)",
    "no": "Ordinal number",
    "ns": "Sport score",

    # General / Fallback
    "unk": "Unknown Type",
    "O": "None",
    "C": "Complex bibliographic expression",
}


def parse_tag_and_type(raw_tag_field):
    """
    Parses a raw tag field, extracts the CNEC type code,
    and returns the BIO tag and the Full Description.
    """
    # 1. Handle CoNLL-U MISC column format (Key=Value)
    if "NE=" in raw_tag_field:
        for feat in raw_tag_field.split('|'):
            if feat.startswith("NE="):
                raw_tag_field = feat.split("=")[1]
                break

    # 2. Handle Multi-layer tags (e.g., "B-P|B-pf")
    primary_tag = raw_tag_field.split('|')[0]

    # 3. Extract purely the BIO tag and the Type
    if primary_tag == "O":
        return "O", None

    if primary_tag.startswith("B-") or primary_tag.startswith("I-"):
        if len(primary_tag) > 2:
            short_code = primary_tag[2:]
        else:
            short_code = "unk"

        full_type_name = CNEC_TYPE_MAP.get(short_code, f"Unknown Code ({short_code})")
        return primary_tag, full_type_name

    return "O", None


def get_entities_by_page(path):
    """
    Parses a file and extracts Named Entities grouped by page.
    Page boundaries are detected via '# sent_id = 1'.

    Returns a dict: { page_number (int): [ (Entity_Text, Entity_Full_Type_Name), ... ] }
    """
    pages = {}
    curr_page = 0

    curr_toks = []
    curr_type = None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                # --- Page Detection ---
                # Check for standard CoNLL-U sentence ID reset which implies a new page in this pipeline
                if line.startswith('# sent_id'):
                    parts = line.split('=', 1)
                    if len(parts) > 1 and parts[1].strip() == '1':
                        curr_page += 1
                        # Note: We assume entities do not cross sentence/page boundaries.
                        # If an entity was open, the logic below (start of new B tag or O)
                        # effectively closes it on the page where it started.
                    continue

                if not line or line.startswith('#'):
                    continue

                # Ensure we are on at least page 1 if we hit data tokens
                if curr_page == 0:
                    curr_page = 1

                # --- Token Parsing ---
                parts = line.split('\t')
                if len(parts) < 2:
                    parts = line.split()

                if len(parts) < 2:
                    continue

                if len(parts) == 2:
                    tok = parts[0]
                    raw_tag = parts[1]
                else:
                    tok = parts[1]
                    raw_tag = parts[-1]

                tag, full_etype = parse_tag_and_type(raw_tag)

                # --- BIO LOGIC ---
                if tag.startswith('B') or (tag != 'O' and not curr_toks):
                    # Save previous entity if exists
                    if curr_toks:
                        pages.setdefault(curr_page, []).append((" ".join(curr_toks), curr_type))

                    # Start new entity
                    curr_toks = [tok]
                    curr_type = full_etype

                elif tag.startswith('I') and curr_toks:
                    # Continue entity
                    curr_toks.append(tok)

                else:  # Tag is O
                    if curr_toks:
                        pages.setdefault(curr_page, []).append((" ".join(curr_toks), curr_type))
                        curr_toks = []
                        curr_type = None

        # Flush remaining entity at end of file
        if curr_toks:
            pages.setdefault(curr_page, []).append((" ".join(curr_toks), curr_type))

    except Exception as e:
        print(f"[Error] parsing {os.path.basename(path)}: {e}", file=sys.stderr)
        return {}

    return pages


def main():
    if len(sys.argv) < 3:
        print("Usage: analyze.py <input_dir> <stats_file>")
        sys.exit(1)

    input_dir = sys.argv[1]
    stats_file = sys.argv[2]
    top_n = 20

    os.makedirs(os.path.dirname(stats_file), exist_ok=True)
    print(f"[Stats] Aggregating entities from: {input_dir}")

    with open(stats_file, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)

        # Updated Header: Added 'page' column
        header = ["file", "page"] + [x for i in range(1, top_n + 1) for x in (f"ne{i}", f"type{i}", f"cnt-{i}")]
        w.writerow(header)

        if os.path.exists(input_dir):
            files = sorted([fn for fn in os.listdir(input_dir) if fn.endswith(".conllu")])

            count_processed = 0
            for fn in files:
                full_path = os.path.join(input_dir, fn)

                # Get entities grouped by page
                pages_data = get_entities_by_page(full_path)

                if not pages_data:
                    continue

                # Iterate through pages in order
                for page_num in sorted(pages_data.keys()):
                    entities = pages_data[page_num]

                    if not entities:
                        continue

                    # Count unique (Text, Type) pairs for this page
                    c = Counter(entities).most_common(top_n)

                    row = [fn.split('.')[0], page_num]
                    for (ne_text, ne_type), cnt in c:
                        row.extend([ne_text, ne_type, cnt])

                    # Padding
                    missing = top_n - len(c)
                    if missing > 0:
                        row.extend(["", "", 0] * missing)

                    w.writerow(row)

                count_processed += 1

            print(f"[Stats] Processed {count_processed} files.")
            print(f"[Stats] Saved to {stats_file}")


if __name__ == "__main__":
    main()