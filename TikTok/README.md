# **TikTok Subtitles Toolkit**

A powerful and flexible script for exploring and scraping subtitle data from TikTok metadata collected from [Zeeschuimer](https://github.com/digitalmethodsinitiative/zeeschuimer) in NDJSON format. This script enables you to:
- Analyse subtitle languages in your dataset.
- Scrape subtitles in multiple languages simultaneously.
- Generate comprehensive processing reports.
- Handle large datasets with multithreading support.

## **Features**
1. **Exploration Mode**:
   - Explore subtitle language availability in the dataset.
   - Display the most frequent languages by percentage.

2. **Scraping Mode**:
   - Scrape subtitles in one or more languages.
   - Optionally strip timestamps from subtitle files.
   - Save subtitles in `.vtt` or `.txt` formats based on your preferences.

3. **Efficient Processing**:
   - Supports multithreading for faster scraping.
   - Generates progress bars and summary reports for easy monitoring.

---

## **Getting Started**

### **Dependencies**
The script requires Python 3.7+ and the following libraries:
- `argparse`: For handling command-line arguments (included with Python).
- `json`: For parsing NDJSON files (included with Python).
- `requests`: For downloading subtitles.
- `tqdm`: For progress bar visualisation.

### **Installation**
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/j-nivekk/miscdataworks/blob/acd457765e63882f1956f2e6e690025932ee8e7d/TikTok/subs_toolkit.py
   ```

2. **Install Dependencies**:
   Install the required Python packages:
   ```bash
   pip install requests tqdm
   ```

3. **Ensure Your Environment**:
   - Python 3.7 or higher.
   - An NDJSON file containing TikTok metadata.

---

## **Usage**

### **General Syntax**
```bash
python subs_toolkit.py [INPUT_FILE] [OPTIONS]
```

### **Arguments**
| **Argument**       | **Description**                                                                                         | **Required** |
|---------------------|-----------------------------------------------------------------------------------------------------|-------------|
| `INPUT_FILE`       | Path to the input NDJSON file containing TikTok metadata.                                             | Yes         |
| `--output_dir`     | Directory to save subtitles (required in scraping mode).                                              | Yes (scraping) |
| `-e, --explore`    | Run exploration mode to analyse subtitle language availability.                                       | No          |
| `-toplang`         | Number of top languages to display in exploration mode (default: 5).                                  | No          |
| `-lang`            | List of language codes for scraping (e.g., `en`, `nl`). Supports full or short codes, case-insensitive. | No          |
| `-a, --amount`     | Maximum number of videos to process (default: 100).                                                   | No          |
| `-s, --strip-timestamps` | Remove timestamps from subtitles and save as `.txt` files.                                       | No          |
| `-v, --verbose`    | Enable detailed logs during scraping.                                                                 | No          |
| `-t, --threads`    | Number of threads for parallel processing (default: 1).                                               | No          |

---

### **Examples**

#### **1. Explore Dataset**
Analyse subtitle language availability in the dataset:
```bash
python subs_toolkit.py subtitle_test.ndjson -e -toplang 10
```

#### **2. Scrape Subtitles in English**
Download English subtitles only:
```bash
python subs_toolkit.py subtitle_test.ndjson --output_dir -lang en
```

#### **3. Scrape Multiple Languages**
Download subtitles in English and Dutch simultaneously:
```bash
python subs_toolkit.py subtitle_test.ndjson --output_dir -lang en nl
```

#### **4. Enable Multithreading for Faster Processing**
Scrape Dutch subtitles with 5 parallel threads:
```bash
python subs_toolkit.py subtitle_test.ndjson --output_dir -lang nl -t 5
```

#### **5. Verbose Logging**
Print detailed logs during scraping:
```bash
python subs_toolkit.py subtitle_test.ndjson --output_dir -lang en -v
```

---

## **Output Details**

### **Exploration Mode**
Outputs the following statistics to the terminal:
- Total number of videos in the dataset.
- Number and percentage of videos with subtitles.
- Top languages by availability and their percentages.

Example Output:
```
Total Videos in Dataset: 1000
Videos with Subtitles: 800 (80.00%)

Top 5 Languages in Subtitles:
en: 500 videos (50.00%)
es: 200 videos (20.00%)
fr: 50 videos (5.00%)
de: 30 videos (3.00%)
it: 20 videos (2.00%)
```

---

### **Scraping Mode**
- Subtitles are saved in the specified output directory.
- File names follow this format: `{video_id}_{language}.vtt` (or `.txt` if `--strip-timestamps` is used).

A `summary_report.txt` is generated, containing:
- Total videos processed.
- Number of successful and failed downloads.
- Reasons for failures.

---

## **FAQ**

### **1. What language codes should I use?**
- You can use either:
  - Two-letter language codes (`en`, `nl`).
  - Full codes (`en-US`, `nl-NL`).
- Codes are **case insensitive**.

### **2. How does multithreading improve performance?**
- By downloading subtitles in parallel, multithreading significantly reduces processing time for large datasets.

### **3. Can I scrape and explore at the same time?**
- No. Exploration mode and scraping mode are mutually exclusive.

---

## **Contributing**
Feel free to submit issues or pull requests to enhance the tool!

---

## **License**
This tool is open-sourced under [GNU General Public License v3.0](https://github.com/j-nivekk/miscdataworks/blob/main/LICENSE).

---
