# 📦 ALTO XML Files Postprocessing Pipeline - NLP Enrichment

This project provides a workflow for processing ALTO XML files with NLP services. It takes raw ALTO 
XMLs and transforms them into structured statistics tables and extracts high-level linguistic features like 
Named Entities (NER) with tags and CONLL-U files with lemmas & part-of-sentence tags.

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
You are now ready to start the workflow.

---

## Workflow Stages

The process is divided into sequential steps, starting from raw ALTO files and ending 
with extracted linguistic and statistic data.

### ▶ Step 1: Page-Specific ALTOs Statistics Table and Extracted Text

More about this step ypu can find in [GitHub repository](https://github.com/K4TEL/atrium-alto-postprocess.git) of ATRIUM project dedicated to ALTO XML
processing into TXT and collection of statistics from these files.

First, ensure you have a directory 📁 containing your page-level `<file>.alto.xml` files. 

    PAGE_ALTO/
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

* **Input:** `../PAGE_ALTO/` (directory containing per-page ALTO XML files)
* **Output:** `alto_statistics.csv/` (table of page-level statistics and ALTO file paths)
* **Output:** `../PAGE_TXT/` (directory containing per-page raw text files)

```
    PAGE_TXT/
    ├── <file1>
        ├── <file1>-<page>.txt 
        └── ...
    ├── <file2>
        ├── <file2>-<page>.txt 
        └── ...
    └── ...
```

### ▶ Step 2: Extract NER and CONLL-U

This stage performs advanced NLP analysis using external APIs (Lindat/CLARIAH-CZ) to generate Universal Dependencies (CoNLL-U) and Named Entity Recognition (NER) data.

Unlike previous steps, this process is split into modular shell scripts to handle large-scale processing, text chunking, and API rate limiting.

#### Configuration ⚙️

Before running the pipeline, review the [api_config.env](config_api.env) 📎 file. This file controls directory paths, API endpoints, and model selection.

```bash
# Example settings in config_api.env
INPUT_DIR="../PAGE_TXT"        # Source of text files (from Step 3.1)
OUTPUT_DIR="../OUT_API"        # Destination for results
MODEL_UDPIPE="czech-pdt-ud-2.15-241121"
MODEL_NAMETAG="nametag3-czech-cnec2.0-240830"
WORD_CHUNK_LIMIT=900           # Word limit per API call
```

#### Execution Pipeline

Run the following scripts in sequence. Each script utilizes [api_common.sh](api_util/api_common.sh) 📎 for logging, retry logic, and error handling.

##### 1. Generate Manifest

Maps input text files to document IDs and page numbers to ensure correct processing order.

```bash
./api_1_manifest.sh
```

* **Input:** `../PAGE_TXT/` (raw text files in subdirectories).
* **Output:** `TEMP/manifest.tsv`.

Example manifest file: [manifest.tsv](data_samples/manifest.tsv) 📎 with **file**, **page** number, and **path** columns.


##### 2.UDPipe Processing (Morphology & Syntax)

Sends text to the UDPipe API. Large pages are automatically split into chunks (default 900 words) using 
[chunk.py](api_util/chunk.py) 📎 to respect API limits, then merged back into valid CoNLL-U files.

```bash
./api_2_udp.sh
```

* **Input:** `TEMP/manifest.tsv` (mapping of text files to document IDs and page numbers).
* **Input:** `../PAGE_TXT/` (raw text files in subdirectories).
* **Output:** `TEMP/UDPIPE/*.conllu` (Intermediate per-document CoNLL-U files).

[UDPIPE](data_samples%2FUDPIPE) 📁 example output, CONLLU per-document file

> [!TIP]
> You can launch the next step when a portion of CONLL-U files are ready, 
> without waiting for the entire input collection to finish. You will have to relaunch 
> the next step after all CONLL-U files are ready to process the files created after the previous
> run began.

##### 3. NameTag Processing (NER)

Takes the valid CoNLL-U files and passes them through the NameTag API to annotate Named Entities 
(NE) directly into the syntax trees.

```bash
./api_3_nt.sh
```

* **Input:** `TEMP/manifest.tsv` (mapping of text files to document IDs and page numbers).
* **Input:** `TEMP/UDPIPE/*.conllu` (Intermediate per-document CoNLL-U files).
* **Output:** `OUTPUT_DIR/NE/` (NE annotated per-page files)

[NE](data_samples%2FNE) 📁 example output, per-page TSV files with NE annotations


##### 4. Generate Statistics

Aggregates the entity counts from the final CoNLL-U files into a summary CSV. It utilizes 
[analyze.py](api_util/analyze.py) 📎 to map complex 
CNEC 2.0 tags (e.g., `g`, `pf`, `if`) into human-readable categories (e.g., "Geographical name", "First name", "Company/Firm").

```bash
./api_4_stats.sh
```

* **Input:** `OUTPUT_DIR/NE/` (NE annotated per-page files).
* **Input:** `TEMP/UDPIPE/*.conllu` (Intermediate per-document CoNLL-U files).
* **Output:** `OUTPUT_DIR/summary_ne_counts.csv`.
* **Output:** `OUTPUT_DIR/UDP_NE/` (per-page CSV files with NE and UDPipe features).

Example summary table: [summary_ne_counts.csv](data_samples/summary_ne_counts.csv) 📎.

Example output directory [UDP_NE](data_samples%2FUDP_NE) 📁 containing per-page CSV tables with NE and UDPipe features

#### Output Structure

After completing the pipeline, your output directory will be organized as follows:
```
TEMP/
├── UDPIPE/  
│   ├── <doc_id>.conllu
│   ├── <doc_id>.conllu
│   └── ...
├── CHUNKS/
│   └── ...
├── nametag_response_docname1.conllu.json
├── ...
└── manifest.tsv
```
AND
```
<OUTPUT_DIR>
├── UDP_NE/          
│   ├── <doc_id>-<page_num>.csv     
│   ├── <doc_id>-<page_num>.csv     
│   └── ...
├── NE/           
│   ├── <doc_id>-<page_num>.tsv     
│   ├── <doc_id>-<page_num>.tsv     
│   └── ...
├── processing.log
└── summary_ne_counts.csv  
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
