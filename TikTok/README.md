**TikTok Subtitles Toolkit**
Version 0.2

A powerful and flexible CLI tool for exploring and scraping subtitle data from TikTok metadata (in NDJSON format), originally collected via [Zeeschuimer](https://github.com/digitalmethodsinitiative/zeeschuimer) version 1.11.2. It allows you to analyse and convert TikTok datasets into a rich corpus of spoken text data with minimal effort.

**What’s New?**

•**Append Mode**: Insert downloaded subtitles directly back into your NDJSON data under data.video.subtitle..

•**Grouping**: Organise downloaded subtitles by language or custom metadata fields.

•**Timestamp Stripping**: Apply clean, timestamp-free subtitle text both to exported files and appended data.

**Features and Advantages**

1.**Exploration Mode**:

•Quickly assess how many videos contain subtitles and identify the most frequent subtitle languages.

•Ideal for gauging the _spoken word prevalence_ in your dataset before performing more intensive text analyses.

2.**Scraping Mode**:

•Download multiple languages simultaneously.

•Optionally remove timestamps from subtitles to produce cleaner text files for natural language processing or data visualisation tools like [Orange](https://orangedatamining.com/), [Voyant Tools](https://voyant-tools.org/), or [Knime](https://www.knime.com/).

•Efficiently leverage TikTok’s provided subtitles, eliminating the need for costly speech-to-text operations.

3.**Append Mode (**\--append**)**:

•Instead of saving subtitles to separate files, enrich your NDJSON dataset by appending fetched subtitles under data.video.subtitle..

•Maintains dataset integrity, making it simpler to handle downstream analysis without juggling multiple files.

•Stripping timestamps works here too, ensuring clean textual data is directly integrated into your dataset.

4.**Grouping (**\--group**)**:

•Organise downloaded subtitle files by language (e.g. output\_dir/en/, output\_dir/nl/) or by a custom nested field (e.g. data.author.id), resulting in a neatly structured corpus.

•Perfect for comparative linguistic analysis, author-based groupings, or other custom sorting needs.

5.**High Performance**:

•Multithreaded downloads let you handle large datasets in minutes.

•Detailed summary reports and progress bars keep you informed.

**Getting Started**

**Dependencies**

•**Python**: 3.7+

•**Libraries**:

•requests for HTTP requests

•tqdm for progress bars

These can be installed via:

pip install requests tqdm

**Installation**

1.**Obtain the Script**:

Download from your repository, place it into a desired directory:

git clone https://github.com/yourusername/tiktok-subtitle-tool.git

cd tiktok-subtitle-tool

2.**Prepare Your NDJSON Data**:

Ensure you have a properly formatted NDJSON file with TikTok video metadata that includes data.video.subtitleInfos.

**Usage**

**General Syntax**:

python subs\_toolkit.py \[INPUT\_FILE\] \[OPTIONS\]

**Arguments & Options**:

**Argument / Option****Description**

INPUT\_FILEPath to the NDJSON file with TikTok metadata.

\--output\_dirDirectory for saving subtitles or producing appended NDJSON. Required for scraping mode.

\-e, --exploreExplore the dataset’s subtitle language availability.

\-toplang NShow the top N languages in exploration mode (default: 5).

\-lang CODE \[CODE ...\]Language codes to scrape (e.g., en, fr). Multiple codes supported.

\-a, --amount NMaximum number of videos to process (default: 100).

\-s, --strip-timestampsRemove timestamps from subtitles. Generates .txt files in normal mode, and cleaned text fields in append mode.

\-v, --verboseEnable verbose logging instead of a progress bar.

\-t, --threads NNumber of parallel threads for scraping (default: 1).

\-apd, --appendAppend downloaded subtitles under data.video.subtitle. in a new NDJSON file instead of saving separate files.

\-g, --group VALUEGroup output files by language or a nested key path (e.g., data.author.id). No effect in append mode.

**Examples**

**1\. Explore the Dataset**

Check how many videos have subtitles and identify top languages:

python subs\_toolkit.py my\_data.ndjson --explore -toplang 10

**2\. Basic Scrape (English)**

Download English subtitles into an output directory:

python subs\_toolkit.py my\_data.ndjson --output\_dir subtitles\_out -lang en

**3\. Multiple Languages Simultaneously**

Scrape English and Dutch subtitles:

python subs\_toolkit.py my\_data.ndjson --output\_dir subtitles\_out -lang en nl

**4\. Append Mode**

Integrate English subtitles directly into your dataset file:

python subs\_toolkit.py my\_data.ndjson --output\_dir enriched\_data -lang en --append

This creates enriched\_data/appended\_subtitles.ndjson where each entry now has data.video.subtitle.en containing the text.

**5\. Group by Language**

Organise downloaded subtitles into language-specific folders:

python subs\_toolkit.py my\_data.ndjson --output\_dir grouped\_subs -lang en fr -g language

Results in grouped\_subs/en/ and grouped\_subs/fr/ directories.

**6\. Group by a Nested Key**

Group by the data.author.id field:

python subs\_toolkit.py my\_data.ndjson --output\_dir author\_groups -lang en -g data.author.id

This creates one folder per unique author ID.

**7\. Strip Timestamps**

Produce cleaner .txt files without timestamps:

python subs\_toolkit.py my\_data.ndjson --output\_dir clean\_txt -lang en -s

When appending, the field data.video.subtitle.en will similarly exclude timestamps.

**8\. Use Multiple Threads**

Speed up processing with 5 threads:

python subs\_toolkit.py my\_data.ndjson --output\_dir fast\_downloads -lang en -t 5

**Output Details**

**Exploration Mode**:

Prints statistics to the terminal (no files created).

**Scraping Mode** (without append):

•Saves files named {video\_id}\_{language}.vtt or .txt in --output\_dir.

•Creates summary\_report.txt summarising successes, failures, and reasons for any failed downloads.

**Append Mode**:

•Produces appended\_subtitles.ndjson enriched with a data.video.subtitle dictionary containing each requested language’s subtitle text.

•Also generates a summary\_report.txt.

**Group Mode** (no append):

•Creates subdirectories named by language codes or the extracted value of the chosen nested key.

•Neatly organises the resulting subtitles, aiding structured analysis.

**FAQ**

**Q1: Expired URL errors?**

A: TikTok’s subtitle URLs expire after some time. Try processing the dataset soon after extraction. Currently, no built-in URL refresh is available.

**Q2: Which language codes should I use?**

A: Both short codes (en) and full codes (en-US) work. Codes are case-insensitive.

**Q3: Can I both append and group simultaneously?**

A: No. Append mode and grouping of separate files are mutually exclusive. Append mode integrates subtitles directly into NDJSON without generating separate files.

**Q4: Can I explore and scrape at the same time?**

A: No, these modes are separate. Exploration helps inform scraping choices.

**License**

This tool is open-sourced under the [GNU General Public License v3.0](https://github.com/j-nivekk/miscdataworks/blob/main/LICENSE). Feel free to use, modify, and distribute for your research or projects.

**Happy scraping and exploring!**
