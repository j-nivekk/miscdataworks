
# HTML to Text Extractor

![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)
![Python Version](https://img.shields.io/badge/Python-3.6%2B-blue.svg)
![Status](https://img.shields.io/badge/status-Active-brightgreen.svg)

A quick-and-dirty Python script designed to extract titles and main content from archived Wikipedia pages in HTML, used by the Internet Archive Wayback Machine. It normalizes and transliterates text to ensure compatibility and readability, handling various edge cases and encoding issues. An effective alternative approach to batch-download all Wikipedia archives and extract a few _when you only need a few_. Its activity is visualised in CLI.

- [Features](#features)
- [Dependencies](#dependencies)
- [Installation](#installation)
- [Usage](#usage)
  - [Command-Line Arguments](#command-line-arguments)
  - [Naming Options](#naming-options)
  - [Example Commands](#example-commands)
- [Potential Issues](#potential-issues)
- [Use Case Examples](#use-case-examples)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Features

- **Title Extraction:** Accurately extracts titles from various HTML structures, including edge cases like `<h1 class="firstHeading">`.
- **Content Extraction:** Extracts main body content while removing unwanted sections such as tables of contents, footers, and navigation elements.
- **Unicode Normalization:** Ensures consistent representation of characters using Unicode Normalization Form C (NFC).
- **Transliteration:** Converts extended Latin characters and special symbols (e.g., em dashes) to their closest ASCII equivalents using the `Unidecode` library.
- **Encoding Detection:** Automatically detects file encoding using the `chardet` library, with fallbacks for unknown encodings.
- **Flexible Naming Conventions:** Offers two naming options for output files:
  - **Option A:** Appends internal timestamps extracted from HTML content.
  - **Option B:** Appends external timestamps derived from input filenames.
- **Duplicate Handling:** Prevents filename collisions by appending counters to duplicate filenames.
- **Empty File Detection:** Identifies and reports empty HTML files that were processed.
- **Comprehensive Logging:** Logs all operations, warnings, and errors to `extraction.log` for easy monitoring and troubleshooting.
- **Visual Progress Bar:** Displays a real-time progress bar using the `tqdm` library during batch processing for enhanced user experience.


## Dependencies

Ensure you have the following Python libraries installed:

- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [chardet](https://github.com/chardet/chardet)
- [Unidecode](https://pypi.org/project/Unidecode/)
- [tqdm](https://github.com/tqdm/tqdm)

## Installation

1. **Clone the Repository**


2. **Create a Virtual Environment (Optional but Recommended)**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Required Dependencies**

   You can install the required dependencies using `pip`:

   ```bash
   pip install -r requirements.txt
   ```

   **`requirements.txt` Example:**

   ```
   beautifulsoup4
   chardet
   Unidecode
   tqdm
   ```

## Usage

The script can process individual HTML files or entire directories containing multiple HTML files.

### Command-Line Arguments

- **Input Path:** Path to the input HTML file or directory.
- **Output Directory:** Path to the directory where extracted text files will be saved.

### Naming Options

Upon running the script, you will be prompted to choose a naming convention for the output files:

- **Option A:** Appends an internal timestamp extracted from the HTML content to the filename.
- **Option B:** Appends an external timestamp derived from the input file's name to the filename.

### Example Commands

#### Processing a Single File

```bash
python3 html_to_text.py /path/to/input_file.html /path/to/output_directory
```

#### Processing an Entire Directory

```bash
python3 html_to_text.py /path/to/input_directory /path/to/output_directory
```

**Example Interaction:**

```
Choose the output naming convention for the text files:
A. Rename output files using internal timestamps.
B. Rename output files with external timestamps.
Enter 'A' or 'B': A

Selected Naming Option: Internal Timestamps
Processing HTML files:  75%|███████████████████▌       | 75/100 [00:30<00:10,  2.50file/s]
...
1 file is empty but still renamed. The empty file is listed below:
- /path/to/output_directory/Empty_Page_20080609053936.txt

Batch processing completed.

Processing completed. Check 'extraction.log' for detailed logs.
```

## Potential Issues

- **Missing Timestamps (Option A):** If the script cannot find an internal timestamp within an HTML file, it will skip renaming that file and log a warning.
- **Unsupported Encodings:** While the script attempts to detect file encodings, some rare or corrupted encodings might not be detected correctly, leading to improper extraction.
- **Filename Collisions:** Although the script handles duplicate filenames by appending counters, excessive duplicates might lead to long filenames.
- **Malformed HTML:** Extremely malformed HTML files might cause the extraction to fail or produce incomplete content.
- **Permission Issues:** Ensure that the script has read permissions for input files and write permissions for the output directory.
- **Progress Bar Display Issues:** In some terminal environments, the `tqdm` progress bar might not render correctly.

## Use Case Examples

### 1. **Archiving Wikipedia Articles**

**Scenario:**
You have a large collection of archived Wikipedia HTML pages. This script can extract the titles and main content, converting them into clean, readable `.txt` files for easier storage and analysis.

**Command:**

```bash
python3 html_to_text.py /WIKIAI_init /Processed_Texts
```

**Interaction:**

```
Choose the output naming convention for the text files:
A. Rename output files using internal timestamps.
B. Rename output files with external timestamps.
Enter 'A' or 'B': A

Selected Naming Option: Internal Timestamps
Processing HTML files:  50%|███████████████████████████▌ | 50/100 [00:20<00:20, 2.50file/s]
...
```

### 2. **Data Preparation for Text Analysis**

**Scenario:**
Before performing text analysis or natural language processing tasks, you need to preprocess raw HTML data. This script cleans and normalizes the text, making it suitable for further processing.

**Command:**

```bash
python3 html_to_text.py /data/raw_html /data/clean_text
```

**Interaction:**

```
Choose the output naming convention for the text files:
A. Rename output files using internal timestamps.
B. Rename output files with external timestamps.
Enter 'A' or 'B': B

Selected Naming Option: External Timestamps
Processing HTML files: 100%|████████████████████████████| 200/200 [01:20<00:00, 2.50file/s]

The following files were skipped due to missing timestamps:
- File_Without_Timestamp.html

2 file(s) are empty but still renamed. The empty files are listed below:
- /data/clean_text/Empty_Page_20080609053936.txt
- /data/clean_text/Another_Empty_Page_20080609053936.txt

Batch processing completed.

Processing completed. Check 'extraction.log' for detailed logs.
```

### 3. **Migrating Content to a New Platform**

**Scenario:**
When migrating content from a wiki-based platform to another system that supports plain text, this script can facilitate the conversion by extracting and formatting the necessary text.

**Command:**

```bash
python3 html_to_text.py /path/to/wiki_html /path/to/new_platform_texts
```

**Interaction:**

```
Choose the output naming convention for the text files:
A. Rename output files using internal timestamps.
B. Rename output files with external timestamps.
Enter 'A' or 'B': A

Selected Naming Option: Internal Timestamps
Processing HTML files: 100%|████████████████████████████| 150/150 [02:00<00:00, 1.25file/s]

1 file is empty but still renamed. The empty file is listed below:
- /path/to/new_platform_texts/Empty_Page_20080609053936.txt

Batch processing completed.

Processing completed. Check 'extraction.log' for detailed logs.
```

## Troubleshooting

- **Encoding Errors:**
  - **Symptom:** Garbled or unreadable characters in the output.
  - **Solution:** Ensure that the correct encoding is detected. You can manually specify encodings if needed by modifying the `detect_file_encoding` function.

- **Skipped Files Due to Missing Timestamps (Option A):**
  - **Symptom:** Certain files are not processed because no timestamp is found.
  - **Solution:** Verify if the HTML files contain recognizable timestamp patterns. If not, consider using Option B or updating the `extract_timestamp_from_html` regex patterns.

- **Filename Collisions:**
  - **Symptom:** Multiple files have the same name after sanitization.
  - **Solution:** The script appends a counter to duplicate filenames. Ensure that this behavior is acceptable or modify the naming logic as needed.

- **Empty Output Files:**
  - **Symptom:** Some output `.txt` files are empty.
  - **Solution:** Check if the corresponding HTML files are genuinely empty or if content extraction failed. Review `extraction.log` for detailed error messages.

- **Permission Denied Errors:**
  - **Symptom:** Unable to read input files or write to the output directory.
  - **Solution:** Ensure that the script has the necessary permissions. You might need to adjust file permissions or run the script with elevated privileges.

- **Progress Bar Not Showing:**
  - **Symptom:** No progress bar appears during execution.
  - **Solution:** Ensure that the `tqdm` library is correctly installed and imported. Also, verify that the script is processing multiple files (progress bar is most useful for batch processing).

- **Malformed HTML:**
  - **Symptom:** Extraction fails or produces incomplete content due to poorly structured HTML.
  - **Solution:** Consider using more robust HTML parsers or cleaning the HTML before processing. Update the `extract_title_and_content` function to handle additional HTML structures.



## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

## Acknowledgements

- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) for HTML parsing.
- [chardet](https://github.com/chardet/chardet) for encoding detection.
- [Unidecode](https://pypi.org/project/Unidecode/) for text transliteration.
- [tqdm](https://github.com/tqdm/tqdm) for the progress bar implementation.

---
