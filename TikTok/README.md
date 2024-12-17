
# TikTok Subtitles Toolkit (v0.3)
_Tested compatibility up to Zeeschuimer version 1.11.3._

A powerful and flexible CLI tool for exploring and scraping subtitle data from TikTok metadata (in NDJSON format), collected via [Zeeschuimer](https://github.com/digitalmethodsinitiative/zeeschuimer). This tool converts a given TikTok dataset into a rich corpus of spoken text data with minimal effort. Version 0.3 refines the command-line interface, making it more intuitive and flexible, and adds new export options.

A 4CAT processor module based on the CLI version is in active development.

## What's New in v0.3?  
- **Unified Output Format Choice (`--format`)**: Easily switch between `text`, `ndjson` (append mode), or `csv` outputs.  
- **Improved Argument Structure**: More logical, concise, and user-friendly flags.  
- **Extended Functionality**: CSV exports with clean text columns and NDJSON integration remain simple and convenient.  
- **Clear Mode Separation**: Grouping is now text-mode only, ensuring no accidental misuse with CSV or NDJSON modes.

## Version 0.2

- **Write Directly to NDJSON databases**: The script can now create a new ndjson file that appends subtitle texts to your dataset, preserving other data points.
- **Grouping**: Organise downloaded subtitles by language or custom metadata fields.
- **Refined VTT Stripping**: Apply clean, timestamp-free subtitle text both to exported files and appended data.

---

## Roadmap

![Toolkit overview map](https://github.com/user-attachments/assets/8c2f4895-5c5e-4f8e-a388-096c0bfee65d)

## Features and Advantages
### 1. Exploration Mode (`--explore`)
- Quickly assess how many videos contain subtitles and identify the most frequent subtitle languages.
- Ideal for gauging spoken word prevalence before intensive text analysis.

### 2. Scraping Modes
- **Text Mode (`--format text`)**: Save individual `.vtt` or `.txt` files.  
- **NDJSON Mode (`--format ndjson`)**: Integrate fetched subtitles directly into a new NDJSON file under `data.video.subtitle.<language>`.  
- **CSV Mode (`--format csv`)**: Export a single CSV containing `video_id` and one column per requested language.

#### Additional Benefits:
- Scrape multiple languages simultaneously.
- Optionally remove timestamps (`--strip-timestamps`) to get cleaner text.
- Efficiently leverage TikTok's subtitles—no costly speech-to-text operations needed.

### 3. Grouping (Text Mode Only)
- Organise downloaded subtitles by language folders or a custom nested metadata key.
- Perfect for corpus organisation, comparative linguistic analysis, or author-based groupings.

### 4. High Performance
- Multithreaded downloads (`--threads`) process large datasets in minutes.
- Progress bars or detailed logs (`--verbose`) keep you informed.
- Summary reports detail successes, failures, and reasons.

---

## Getting Started

### Dependencies
- **Python**: 3.7+
- **Libraries**:  
  - `requests` for HTTP requests  
  - `tqdm` for progress bars  

Install via:
```bash
pip install requests tqdm
```

### Installation
#### 1. Obtain the Script
Clone and navigate into the repository:
```bash
git clone https://github.com/j-nivekk/miscdataworks/tree/c47fc1a3fb1179c88a15cfb8334472625c710bca/TikTok/Python-Standalone
```

#### 2. Prepare Your NDJSON Data
Have a properly formatted NDJSON file with TikTok video metadata including `data.video.subtitleInfos`.

---

## Usage

### General Syntax
```bash
python subs_toolkit.py [INPUT_FILE] [OPTIONS]
```

### Arguments & Options

| **Argument / Option**       | **Short** | **Description**                                                                 | **Mode(s)**         |
|------------------------------|-----------|---------------------------------------------------------------------------------|---------------------|
| `INPUT_FILE`                | N/A       | Path to the NDJSON file with TikTok metadata.                                   | All                 |
| `--output-dir PATH`         | N/A       | Directory for saving subtitles or final outputs. Required for scraping modes.   | Scraping Modes      |
| `--explore`                 | `-E`      | Run in exploration mode to analyse subtitle language availability.              | Exploration Only    |
| `--top-languages N`         | N/A       | Display the top N languages in exploration mode (default: 5).                   | Exploration Only    |
| `--languages LANG [LANG ...]` | `-L`    | One or more language codes to scrape (e.g., en, fr).                            | Scraping Modes      |
| `--num-videos N`            | `-n`      | Maximum number of videos to process (default: 100).                             | Scraping Modes      |
| `--strip-timestamps`        | `-s`      | Remove timestamps, producing cleaner `.txt` (text mode) or cleaned fields (others). | Scraping Modes |
| `--verbose`                 | `-v`      | Show detailed logs instead of a progress bar.                                   | Scraping Modes      |
| `--threads N`               | `-t`      | Number of parallel threads for faster processing (default: 1).                  | Scraping Modes      |
| `--format {text,ndjson,csv}`| `-f`      | Output format: text (default, individual files), ndjson (appended dataset), csv (single file). | Scraping Modes |
| `--group KEY`               | `-g`      | Group subtitles by language or a nested key path. Text mode only.               | Text Mode Only      |

---

## Examples

### 1. Explore the Dataset
Analyse subtitle availability:
```bash
python subs_toolkit.py my_data.ndjson --explore --top-languages 10
```

### 2. Scrape (Text Mode)
Download English subtitles as individual `.vtt` or `.txt` files:
```bash
python subs_toolkit.py my_data.ndjson --output-dir subtitles_out --languages en --num-videos 50
```

### 3. NDJSON Mode
Append English subtitles directly into a new NDJSON dataset:
```bash
python subs_toolkit.py my_data.ndjson --output-dir enriched_data -f ndjson --languages en
```

### 4. CSV Mode
Export multiple languages (English & French) into a single CSV:
```bash
python subs_toolkit.py my_data.ndjson --output-dir csv_out -f csv --languages en fr --strip-timestamps
```

### 5. Group by Language (Text Mode Only)
Organise English and French subtitles into separate language folders. Note that the `language` argument can be added to directly group files by downloaded language; otherwise you need to specify its grouping condition using a specific key path, such as `data.video.author`:
```bash
python subs_toolkit.py my_data.ndjson --output-dir grouped_text -f text --languages en fr --group language
```

---

## Output Details

### Exploration Mode
- Prints statistics directly to the terminal.

### Scraping Mode (Text)
- Saves files per video-language pair.
- Generates a `summary_report.txt`.

### Scraping Mode (NDJSON)
- Produces `appended_subtitles.ndjson` with integrated subtitles under `data.video.subtitle.<language>`.
- Generates a `summary_report.txt`.

### Scraping Mode (CSV)
- Creates `subtitles.csv` with a `video_id` column and one column per requested language.
- Generates a `summary_report.txt`.

### Group Mode (Text Only)
- When `--format text` and `--group` are set, files are placed into directories by language or the nested key value.

---

## FAQ

### Q1: Expired URL errors?
**A**: TikTok subtitle URLs expire after a short period (test successful scrape up to 8 hours after data collection). Try processing as soon after data retrieval as possible.

### Q2: Which language codes are valid?
**A**: Two-letter (`en`, `nl`) or full codes (`en-US`) are fine. Codes are case-insensitive.

### Q3: Can I combine grouping with NDJSON or CSV?
**A**: No. Grouping only applies in text mode. If `--group` is used with `ndjson` or `csv`, it’s ignored and a warning is shown.

### Q4: Can I explore and scrape simultaneously?
**A**: No. Exploration is a separate mode from scraping.

---

## License

This tool is open-sourced under the [GNU General Public License v3.0](https://github.com/j-nivekk/miscdataworks/blob/main/LICENSE). Use, modify, and distribute freely for research and projects.

**Happy scraping and exploring!**
