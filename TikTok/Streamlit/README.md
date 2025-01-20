# TikTok Subtitle/Caption Tool

A Streamlit-based web application for exploring and extracting subtitles and closed captions from TikTok video metadata stored in NDJSON format.

## Features
_refer to /miscdataworks/TikTok/README.md_
## Installation

1. Download app.py to a _folder_:
```bash
cd folder_path
```

2. Create environment:
```bash
# run these commands line-by-line, do not copy this whole block!
python -m venv .venv
# Windows command prompt
.venv\Scripts\activate.bat
# PowerShell
.venv\Scripts\Activate.ps1
# macOS and Linux
source .venv/bin/activate
```
3. Install Dependecies:
```bash
pip install streamlit pandas requests
```

## Usage

1. Run the Streamlit application:
```bash
streamlit run app.py
```

2. Open your web browser and navigate to the provided local URL (typically http://localhost:8501)

3. Upload your NDJSON file containing TikTok video metadata

4. Use either the Explore or Scrape tab:
   - **Explore**: Analyze language distribution and availability
   - **Scrape**: Download subtitles/captions in your chosen format

## Requirements

- Python 3.7+
- Streamlit
- Pandas
- Requests

## License

This project is licensed under the GNU General Public License v3.0.
