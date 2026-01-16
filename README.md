# 📦 ALTO XML Files Postprocessing Pipeline - NLP Enrichment

This project provides a complete workflow for processing ALTO XML files. It takes raw ALTO 
XMLs and transforms them into structured statistics tables, performs text classification, 
filters low-quality OCR results, and extracts high-level linguistic features like 
Named Entities (NER), CONLL-U files with lemmas & part-of-sentence tags, and keywords (KER).

The core of the quality filtering relies on language identification and perplexity measures 
to identify and categorize noisy or unreliable OCR output.

---

## ⚙️ Setup

Before you begin, set up your environment.

1.  Create and activate a new virtual environment in the project directory 🖥.
2.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
3.  Clone and install `alto-tools` 🔧, which is used for statistics and text extraction:
    ```bash
    git clone https://github.com/cneud/alto-tools.git
    cd alto-tools
    pip install .
    cd .. 
    ```
4.  Download the FastText model 😊 for language identification:
    ```bash
    wget (https://huggingface.co/facebook/fasttext-language-identification/resolve/main/model.bin) -O lid.176.bin
    ```
You are now ready to start the workflow.

---

## Workflow Stages

The process is divided into sequential steps, starting from raw ALTO files and ending 
with extracted linguistic and statistic data.

### ▶ Step 1: Page-Specific ALTOs Statistics Table and Extracted Text

First, ensure you have a directory 📁 containing your page-level `<file>.alto.xml` files. 

    <input_dir>
    ├── <file1>
        ├── <file1>-<page>.alto.xml 
        └── ...
    ├── <file2>
        ├── <file2>-<page>.alto.xml 
        └── ...
    └── ...

Each page-specific file retains the header from its original source document.

Next, use the directory the input for this script to generate a 
foundational CSV statistics file, capturing metadata for each page:

    file, page, textlines, illustrations, graphics, strings, path
    CTX200205348, 1, 33, 1, 10, 163, /lnet/.../A-PAGE/CTX200205348/CTX200205348-1.alto.xml
    CTX200205348, 2, 0, 1, 12, 0, /lnet/.../A-PAGE/CTX200205348/CTX200205348-2.alto.xml
    ...

The extraction is powered by the [alto-tools](https://github.com/cneud/alto-tools) 🔗 framework.

Then the script runs in parallel (using multiple **CPU** cores) to extract text from ALTO XMLs into `.txt` files. 
It reads the CSV with stats and process paths into output text files.

    python3 api_0_extract_TXT.py

* **Input:** `../ALTO/A-PAGE/` (directory containing ALTO XML files)
* **Output:** `../PAGE_TXT/` (directory containing raw text files)
* **Output:** `alto_statistics.csv/` (table of page-level statistics and ALTO file paths)


### ▶ Step 2: Extract NER and CONLL-U

This stage performs advanced NLP analysis using external APIs (Lindat/CLARIAH-CZ) to generate Universal Dependencies (CoNLL-U) and Named Entity Recognition (NER) data.

Unlike previous steps, this process is split into modular shell scripts to handle large-scale processing, text chunking, and API rate limiting.

#### Configuration ⚙️

Before running the pipeline, review the [api_config.env](api_config.env) 📎 file. This file controls directory paths, API endpoints, and model selection.
```bash
# Example settings in api_config.env
INPUT_DIR="../PAGE_TXT"        # Source of text files (from Step 3.1)
OUTPUT_DIR="../OUT_API"        # Destination for results
MODEL_UDPIPE="czech-pdt-ud-2.15-241121"
MODEL_NAMETAG="nametag3-czech-cnec2.0-240830"
WORD_CHUNK_LIMIT=900           # Word limit per API call
```

#### Execution Pipeline

Run the following scripts in sequence. Each script utilizes [api_common.sh](api_util/api_common.sh) 📎 for logging, retry logic, and error handling.

##### I. Generate Manifest

Maps input text files to document IDs and page numbers to ensure correct processing order.
```bash
./api_manifest.sh
```

* **Input:** `INPUT_DIR` (raw text files in subdirectories).
* **Output:** `processing_work/manifest.tsv`.

##### II. UDPipe Processing (Morphology & Syntax)

Sends text to the UDPipe API. Large pages are automatically split into chunks (default 900 words) using 
[chunk.py](api_util/chunk.py) 📎 to respect API limits, then merged back into valid CoNLL-U files.
```bash
./api_udp.sh
```

* **Output:** `processing_work/UDPIPE_INTERMEDIATE/*.conllu` (Intermediate CoNLL-U files).

##### III. NameTag Processing (NER)

Takes the valid CoNLL-U files and passes them through the NameTag API to annotate Named Entities 
(NE) directly into the syntax trees.
```bash
./api_nt.sh
```

* **Output:** `OUTPUT_DIR/CONLLU_FINAL/` (Final annotated files).

##### IV. Generate Statistics

Aggregates the entity counts from the final CoNLL-U files into a summary CSV. It utilizes 
[analyze.py](api_util/analyze.py) 📎 to map complex 
CNEC 2.0 tags (e.g., `g`, `pf`, `if`) into human-readable categories (e.g., "Geographical name", "First name", "Company/Firm").

```bash
./api_stats.sh
```

* **Output:** `OUTPUT_DIR/STATS/summary_ne_counts.csv`.

Example: [summary_ne_counts.csv](summary_ne_counts.csv) 📎.

#### Output Structure

After completing the pipeline, your output directory will be organized as follows:
```
processing_work/
├── UDPIPE_INTERMEDIATE/  # Intermediate CONLL-U files
│   ├── <doc_id>_part1.conllu
│   ├── <doc_id>_part2.conllu
│   └── ...
├── nametag_response_docname1.conllu.json
├── nametag_response_docname2.conllu.json
├── ...
└── manifest.tsv
```
AND
```
<OUTPUT_DIR>
├── CONLLU_FINAL/           # Full linguistic analysis
│   ├── <doc_id>.conllu     # Parsed sentences with NER tags
│   └── ...
└── STATS/
    └── summary_ne_counts.csv  # Table of top entities per document
```

---

## Acknowledgements 🙏

**For support write to:** lutsai.k@gmail.com responsible for this GitHub repository [^8] 🔗

- **Developed by** UFAL [^7] 👥
- **Funded by** ATRIUM [^4]  💰
- **Shared by** ATRIUM [^4] & UFAL [^7] 🔗

**©️ 2025 UFAL & ATRIUM**

[^4]: https://atrium-research.eu/
[^8]: https://github.com/ufal/atrium-alto-postprocess
[^7]: https://ufal.mff.cuni.cz/home-page
