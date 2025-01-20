import streamlit as st
import json
import time
import re
import csv
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import defaultdict
from datetime import datetime, UTC
from io import StringIO, BytesIO
import zipfile
import pandas as pd
from time import sleep
from functools import wraps
from contextlib import contextmanager

# -----------------------------
# Session State Initialisation
# -----------------------------
# We store exploration data (summary + language rows) for the current file.
# Also track the filename to detect when user uploads a new file, so that we
# can reset exploration results when a different NDJSON is provided.

if "explore_data" not in st.session_state:
    st.session_state["explore_data"] = {
        "summary_stats": None,  # Will store total_videos, videos_with_data, unique_lang_count
        "lang_rows": None       # Will store rows for the language table
    }

if "uploaded_filename" not in st.session_state:
    st.session_state["uploaded_filename"] = None

if "available_languages" not in st.session_state:
    st.session_state["available_languages"] = {
        "subtitle": [],
        "caption": []
    }

if "scrape_summary" not in st.session_state:
    st.session_state["scrape_summary"] = None

# Add session state for recovery
if "last_successful_scrape" not in st.session_state:
    st.session_state["last_successful_scrape"] = None

# Add configuration management
DEFAULT_CONFIG = {
    "max_file_size": 500 * 1024 * 1024,
    "request_timeout": 10,
    "max_threads": 32,
    "max_videos": 100000,
    "rate_limit_calls": 10,
    "rate_limit_period": 1.0
}

if "config" not in st.session_state:
    st.session_state["config"] = DEFAULT_CONFIG

# -----------------------------
# Core Functions
# -----------------------------

def parse_webvtt(content, strip_timestamps):
    """
    Parses WebVTT subtitle content, optionally stripping timestamps.
    """
    if not strip_timestamps:
        return content

    parsed_content = []
    for line in content.splitlines():
        # Skip timestamp lines
        if re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}$", line):
            continue
        # Skip WEBVTT headers or empty lines
        if line.startswith("WEBVTT") or line.strip() == "":
            continue
        parsed_content.append(line)

    return "\n".join(parsed_content)


def get_media_info(video_content, find_type):
    """
    Retrieves the list of subtitle or caption infos based on find_type.
    """
    if find_type.lower() == "caption":
        # Retrieve captionInfos under data.video.claInfo
        cla_info = video_content.get("claInfo", {})
        return cla_info.get("captionInfos", [])
    else:
        # Default: subtitleInfos under data.video
        return video_content.get("subtitleInfos", [])


def ensure_nested_path(d, path):
    """
    Ensures that a nested path in a dictionary exists, creating intermediate dictionaries if needed.
    """
    keys = path.split(".")
    current = d
    for key in keys:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]


# -----------------------------
# Exploration
# -----------------------------

def explore_dataset(items: list, find_type: str) -> tuple[dict, list]:
    """
    Analyze subtitle/caption language distribution in the dataset.
    
    Args:
        items: List of video data dictionaries
        find_type: Type of data to analyze ('subtitle' or 'caption')
    
    Returns:
        tuple: (summary_stats, lang_rows)
            - summary_stats: Dict with total_videos, videos_with_data, unique_lang_count
            - lang_rows: List of dicts with language statistics
    """
    total_videos = len(items)
    videos_with_data = 0

    lang_info_map = defaultdict(lambda: {
        "videos": set(),
        "expires": []
    })

    for entry in items:
        data_content = entry.get("data", {})
        video_content = data_content.get("video", {})
        media_infos = get_media_info(video_content, find_type)

        if media_infos:
            videos_with_data += 1

        # Record language usage
        for m in media_infos:
            language = m.get("LanguageCodeName", "unknown").lower()
            lang_info = lang_info_map[language]
            video_id = data_content.get("item_id", data_content.get("id", "unknown"))
            lang_info["videos"].add(video_id)

            # Track url_expire if present
            url_expire = m.get("UrlExpire", 0)
            try:
                url_expire = int(url_expire)
                if url_expire > 0:
                    lang_info["expires"].append(url_expire)
            except ValueError:
                pass  # ignore non-numeric expires

    all_languages = list(lang_info_map.keys())
    unique_lang_count = len(all_languages)

    # Build the table rows
    lang_rows = []
    for language in sorted(all_languages):
        data = lang_info_map[language]
        vid_count = len(data["videos"])
        perc = (vid_count / total_videos * 100) if total_videos else 0.0

        # Earliest expiration
        if data["expires"]:
            earliest = min(data["expires"])
            earliest_str = datetime.fromtimestamp(earliest, UTC).strftime("%Y-%m-%d %H:%M:%S")
        else:
            earliest_str = "N/A"

        lang_rows.append({
            "language": language,
            "in # videos": vid_count,
            "percentage of all videos": f"{perc:.2f}%",
            "earliest url expiration (UTC)": earliest_str
        })

    summary_stats = {
        "total_videos": total_videos,
        "videos_with_data": videos_with_data,
        "unique_lang_count": unique_lang_count
    }

    # Store available languages in session state
    st.session_state["available_languages"][find_type] = sorted(all_languages)

    return summary_stats, lang_rows


# -----------------------------
# Scraping
# -----------------------------

def rate_limit(calls: int, period: float):
    def decorator(func):
        last_reset = time.time()
        calls_made = 0
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal last_reset, calls_made
            now = time.time()
            
            if now - last_reset > period:
                calls_made = 0
                last_reset = now
                
            if calls_made >= calls:
                sleep(period - (now - last_reset))
                calls_made = 0
                last_reset = time.time()
                
            calls_made += 1
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(calls=10, period=1.0)  # 10 calls per second
def download_subtitle(item: dict, languages: list, strip_timestamps: bool, find_type: str) -> list:
    """
    Download subtitles/captions for a video.
    """
    results = []
    try:
        data_content = item.get("data", {})
        video_id = data_content.get("item_id", data_content.get("id", "unknown"))

        video_content = data_content.get("video", {})
        media_infos = get_media_info(video_content, find_type)

        for lang in languages:
            matching = [
                m for m in media_infos
                if m.get("LanguageCodeName", "").lower() == lang.lower() and m.get("Format") == "webvtt"
            ]

            if matching:
                media_info = matching[0]
                url = media_info.get("Url")
                url_expire = media_info.get("UrlExpire", 0)

                if url and int(url_expire) > time.time():
                    try:
                        headers = {
                            'User-Agent': 'Mozilla/5.0',
                            'Accept': 'text/plain,text/html'
                        }
                        resp = requests.get(url, timeout=10, headers=headers, verify=True)
                        resp.raise_for_status()
                    except requests.Timeout:
                        reason = "Download timeout (10s)"
                    except requests.HTTPError as e:
                        reason = f"HTTP error: {e.response.status_code}"
                    except requests.RequestException as e:
                        reason = f"Network error: {str(e)}"
                    else:
                        # Success case
                        subtitle_content = parse_webvtt(resp.text, strip_timestamps)

                        # Decide file extension
                        extension = "txt" if strip_timestamps else "vtt"

                        results.append({
                            "id": video_id,
                            "language": lang,
                            "success": True,
                            "reason": None,
                            "content": subtitle_content,
                            "extension": extension
                        })
                else:
                    results.append({
                        "id": video_id,
                        "language": lang,
                        "success": False,
                        "reason": "Expired or invalid URL",
                        "content": "",
                        "extension": None
                    })
            else:
                results.append({
                    "id": video_id,
                    "language": lang,
                    "success": False,
                    "reason": "Language unavailable",
                    "content": "",
                    "extension": None
                })

    except Exception as e:
        results.append({
            "id": item.get("data", {}).get("item_id", item.get("data", {}).get("id", "unknown")),
            "language": None,
            "success": False,
            "reason": str(e),
            "content": "",
            "extension": None
        })

    return results


def generate_summary_report(results, languages, find_type):
    """
    Generates a summary report after scraping.
    """
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    lines = []
    lines.append(f"{find_type.capitalize()} Scraping Summary")
    lines.append("=" * 30)
    lines.append(f"Language(s) requested: {', '.join(languages)}")
    lines.append(f"Total Attempts (video-language pairs): {len(results)}")
    lines.append(f"Successful Downloads: {len(successful)}")
    lines.append(f"Failed Downloads: {len(failed)}\n")

    if failed:
        lines.append("Failed Cases:")
        for f in failed:
            lines.append(f"Video ID: {f['id']} - Language: {f['language']} - Reason: {f['reason']}")

    return "\n".join(lines)


def scrape_subtitles(items, languages, num_videos, strip_timestamps,
                     threads, find_type, save_format, base_output_name,
                     progress_container=None, status_container=None):
    """
    Main scraping function.
    Returns:
      - summary_str
      - all_results
      - final_output (the data, e.g. ZIP bytes, NDJSON string, or CSV string)
    """
    to_process = items[:num_videos]

    all_results = []
    total_count = len(to_process)
    if total_count == 0:
        return "No videos to process.", [], None

    progress_bar = None
    if progress_container:
        progress_bar = progress_container.progress(0)

    if status_container:
        status_container.write("Starting download...")

    def update_progress(done):
        if progress_bar:
            fraction = done / total_count
            progress_bar.progress(fraction)

    done_count = 0

    # Add more detailed progress tracking
    if status_container:
        status = status_container.empty()
        progress = progress_container.empty()
        
    def update_status(message: str, progress_value: float = None):
        if status:
            status.write(message)
        if progress and progress_value is not None:
            progress.progress(progress_value)

    # Use in the scraping loop
    update_status("Initializing scraping...", 0.0)

    # Download loop
    if threads > 1:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [
                executor.submit(download_subtitle, item, languages, strip_timestamps, find_type)
                for item in to_process
            ]
            for future in as_completed(futures):
                res = future.result()
                all_results.extend(res)
                done_count += 1
                update_progress(done_count)
                update_status(f"Processing video {done_count}/{total_count}", done_count/total_count)
    else:
        # Single-thread
        for item in to_process:
            res = download_subtitle(item, languages, strip_timestamps, find_type)
            all_results.extend(res)
            done_count += 1
            update_progress(done_count)
            update_status(f"Processing video {done_count}/{total_count}", done_count/total_count)

    if status_container:
        status_container.write("Download complete. Preparing output...")
        update_status("Preparing output files...", 1.0)

    summary_str = generate_summary_report(all_results, languages, find_type)

    # Build final output
    if save_format == "text":
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in all_results:
                if r["success"]:
                    filename = f"{r['id']}_{r['language']}.{r['extension']}"
                    zf.writestr(filename, r["content"])
        zip_buffer.seek(0)
        final_output = zip_buffer.getvalue()  # Bytes
        st.session_state["last_successful_scrape"] = {
            "results": all_results,
            "output": final_output,
            "timestamp": time.time()
        }
        return summary_str, all_results, final_output

    elif save_format == "ndjson":
        video_map = {}
        for r in all_results:
            vid = r["id"]
            if vid not in video_map:
                video_map[vid] = {}
            if r["language"] is not None and r["success"]:
                video_map[vid][r["language"]] = r["content"]

        ndjson_buffer = StringIO()
        for item in to_process:
            data_content = item.get("data", {})
            vid = data_content.get("item_id", data_content.get("id", "unknown"))
            sub_map = video_map.get(vid, {})
            if find_type.lower() == "caption":
                ensure_nested_path(item, "data.video.claInfo.caption")
                for lang, cont in sub_map.items():
                    item["data"]["video"]["claInfo"]["caption"][lang] = cont
            else:
                ensure_nested_path(item, "data.video.subtitle")
                for lang, cont in sub_map.items():
                    item["data"]["video"]["subtitle"][lang] = cont
            ndjson_buffer.write(json.dumps(item, ensure_ascii=False) + "\n")

        return summary_str, all_results, ndjson_buffer.getvalue()

    else:  # CSV
        video_map = {}
        for r in all_results:
            vid = r["id"]
            if vid not in video_map:
                video_map[vid] = {}
            if r["language"] is not None:
                video_map[vid][r["language"]] = r["content"] if r["success"] else ""

        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        header = ["video_id"] + languages
        writer.writerow(header)
        for item in to_process:
            data_content = item.get("data", {})
            vid = data_content.get("item_id", data_content.get("id", "unknown"))
            row = [vid]
            for lang in languages:
                row.append(video_map.get(vid, {}).get(lang, ""))
            writer.writerow(row)

        return summary_str, all_results, csv_buffer.getvalue()


# -----------------------------
# Streamlit UI
# -----------------------------

@contextmanager
def managed_scraping_session(progress_container, status_container):
    try:
        yield
    finally:
        progress_container.empty()
        status_container.empty()

def process_large_file(file_obj, chunk_size=8192):
    """Process large files in chunks to avoid memory issues."""
    buffer = []
    for chunk in iter(lambda: file_obj.read(chunk_size).decode('utf-8'), ''):
        buffer.extend(chunk.splitlines())
        # Process complete lines
        while len(buffer) > 1000:  # Process in batches of 1000 lines
            yield buffer[:1000]
            buffer = buffer[1000:]
    if buffer:  # Process remaining lines
        yield buffer

def main():
    st.title("TikTok Subtitle/Caption Tool")

    # File Uploader
    uploaded_file = st.file_uploader("Upload your NDJSON file", type=["ndjson", "jsonl", "txt"])
    if not uploaded_file:
        st.warning("Please upload an NDJSON file to proceed.")
        st.stop()

    current_uploaded_name = uploaded_file.name
    if st.session_state["uploaded_filename"] != current_uploaded_name:
        # Reset session state exploration data
        st.session_state["uploaded_filename"] = current_uploaded_name
        st.session_state["explore_data"]["summary_stats"] = None
        st.session_state["explore_data"]["lang_rows"] = None

    try:
        MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB limit

        if uploaded_file.size > MAX_FILE_SIZE:
            st.error("File too large (max 500MB)")
            st.stop()

        if uploaded_file.size > 50 * 1024 * 1024:  # 50MB
            items = []
            for chunk in process_large_file(uploaded_file):
                items.extend([json.loads(line) for line in chunk if line.strip()])
        else:
            # Regular processing for smaller files
            lines = uploaded_file.read().decode("utf-8").splitlines()
            items = [json.loads(line) for line in lines if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        st.error(f"Error reading file: {str(e)}")
        st.stop()
    if not items:
        st.error("No valid data found in file.")
        st.stop()

    # Create two tabs for Explore and Scrape
    tab_explore, tab_scrape = st.tabs(["Explore", "Scrape"])

    # -----------------------------
    # Explore Tab
    # -----------------------------
    with tab_explore:
        st.write("Select data type to explore:")
        find_type_explore = st.segmented_control(
            "Data Type to Explore",
            ["subtitle", "caption"],
            label_visibility="collapsed",
            key="explore_type_selector"
        )

        # Only run exploration if a type is selected
        if find_type_explore:
            summary_stats, lang_rows = explore_dataset(items, find_type_explore)
            st.session_state["explore_data"]["summary_stats"] = summary_stats
            st.session_state["explore_data"]["lang_rows"] = lang_rows

        # Display the exploration data if available
        if (st.session_state["explore_data"]["summary_stats"] and
                st.session_state["explore_data"]["lang_rows"] and
                find_type_explore):
            summary_stats = st.session_state["explore_data"]["summary_stats"]
            lang_rows = st.session_state["explore_data"]["lang_rows"]

            tab1, tab2, tab3 = st.tabs(["Overview", "Distribution (Table)", "Language Count (Chart)"])

            with tab1:
                st.markdown(
                    f"""
                    **Total Videos**: {summary_stats['total_videos']}  
                    **Videos with {find_type_explore.capitalize()}s**: {summary_stats['videos_with_data']}  
                    **Count of all available languages**: {summary_stats['unique_lang_count']}
                    """
                )

            with tab2:
                st.dataframe(lang_rows, use_container_width=True)

            with tab3:
                chart_data = [(row["language"], row["in # videos"]) for row in lang_rows]
                df_chart = pd.DataFrame(chart_data, columns=["language", "count"])
                df_chart.sort_values("count", ascending=False, inplace=True)
                st.bar_chart(df_chart, x="language", y="count")
        else:
            st.write("Please select a data type above to explore this dataset.")

    # -----------------------------
    # Scrape Tab
    # -----------------------------
    with tab_scrape:
        st.write("Select data type to scrape:")
        # Add these callbacks to clear summary when inputs change
        def clear_summary():
            st.session_state["scrape_summary"] = None

        # Add the callback to all input widgets
        find_type_scrape = st.segmented_control(
            "Data Type to Scrape",
            ["subtitle", "caption"],
            label_visibility="collapsed",
            key="scrape_type_selector",
            on_change=clear_summary
        )

        # Language selection using multiselect instead of pills
        if find_type_scrape:
            available_langs = st.session_state["available_languages"][find_type_scrape]
            if available_langs:
                st.write("Select languages to scrape:")
                selected_languages = st.multiselect(
                    "Languages",
                    options=available_langs,
                    label_visibility="collapsed",
                    help="Select one or more languages to scrape",
                    on_change=clear_summary
                )
                if not selected_languages:
                    st.warning("Please select at least one language to scrape.")
            else:
                st.warning(f"No languages available for {find_type_scrape}s. Please run exploration first.")
                st.stop()
        else:
            st.info("Please select a data type to see available languages.")
            st.stop()

        # Update the languages variable used in scraping
        languages = selected_languages if 'selected_languages' in locals() else []

        # Number of Videos
        num_videos = st.number_input("Maximum number of videos to process", 
            min_value=1, 
            max_value=100000, 
            value=100,
            on_change=clear_summary
        )

        # Strip Timestamps
        strip_help_text = (
            "If enabled, all WebVTT timestamps will be removed, leaving only the raw subtitle text. "
            "This results in a cleaner text output (with a .txt extension) rather than .vtt."
        )
        strip_timestamps = st.toggle(
            "Strip Timestamps", 
            value=False, 
            help=strip_help_text,
            on_change=clear_summary
        )

        # Threads
        threads = st.number_input(
            "Threads", 
            min_value=1, 
            max_value=32, 
            value=1,
            on_change=clear_summary
        )

        # Output Format
        save_format = st.radio(
            "Output Format", 
            ["text", "ndjson", "csv"], 
            horizontal=True,
            on_change=clear_summary
        )

        # Custom output file name
        output_base_name = st.text_input(
            "Base Output Filename (no extension)", 
            "my_subtitles",
            on_change=clear_summary
        )

        # Status and progress containers
        status_container = st.empty()
        progress_container = st.empty()

        # We only proceed if user has chosen a valid data type
        if find_type_scrape is None:
            st.info("Please select either 'Scrape Subtitles' or 'Scrape Captions' to enable scraping.")
        else:
            if st.button("Start Scraping"):
                # Validate inputs before proceeding
                is_valid, error_msg = validate_input(num_videos, threads, save_format)
                if not is_valid:
                    st.error(error_msg)
                    st.stop()
                
                with managed_scraping_session(progress_container, status_container):
                    summary_str, all_results, final_output = scrape_subtitles(
                        items=items,
                        languages=languages,
                        num_videos=num_videos,
                        strip_timestamps=strip_timestamps,
                        threads=threads,
                        find_type=find_type_scrape,
                        save_format=save_format,
                        base_output_name=output_base_name,
                        progress_container=progress_container,
                        status_container=status_container
                    )
                    
                    # Store the summary in session state
                    st.session_state["scrape_summary"] = summary_str

            # Display summary report if available (outside the button click block)
            if st.session_state["scrape_summary"]:
                st.subheader("Summary Report")
                st.text_area("Scraping Summary", st.session_state["scrape_summary"], height=300)

                # Provide download buttons only if we have results
                if 'final_output' in locals():
                    if save_format == "text":
                        # final_output is a ZIP
                        zip_filename = output_base_name + ".zip"
                        st.download_button(
                            label=f"Download {zip_filename}",
                            data=final_output,
                            file_name=zip_filename,
                            mime="application/zip"
                        )
                    elif save_format == "ndjson":
                        ndjson_filename = output_base_name + ".ndjson"
                        st.download_button(
                            label=f"Download {ndjson_filename}",
                            data=final_output.encode("utf-8"),
                            file_name=ndjson_filename,
                            mime="application/ndjson"
                        )
                    else:  # CSV
                        csv_filename = output_base_name + ".csv"
                        st.download_button(
                            label=f"Download {csv_filename}",
                            data=final_output.encode("utf-8"),
                            file_name=csv_filename,
                            mime="text/csv"
                        )

        # Add recovery option in scrape tab
        if st.session_state["last_successful_scrape"]:
            last_scrape = st.session_state["last_successful_scrape"]
            time_ago = time.time() - last_scrape["timestamp"]
            if time_ago < 3600:  # Show recovery option for 1 hour
                st.info("Previous successful scrape results available")
                if st.button("Recover Last Results"):
                    summary_str = generate_summary_report(
                        last_scrape["results"], 
                        languages, 
                        find_type_scrape
                    )
                    st.text_area("Previous Scraping Summary", summary_str, height=300)
                    # Show download button for previous results
                    st.download_button(
                        "Download Previous Results",
                        data=last_scrape["output"],
                        file_name=f"{output_base_name}.{save_format}",
                        mime="application/octet-stream"
                    )


# Add constants and validation
VALID_FORMATS = ["text", "ndjson", "csv"]
MAX_THREADS = 32
MIN_THREADS = 1
MAX_VIDEOS = 100000
MIN_VIDEOS = 1

def validate_input(num_videos: int, threads: int, save_format: str) -> tuple[bool, str]:
    if not MIN_VIDEOS <= num_videos <= MAX_VIDEOS:
        return False, f"Number of videos must be between {MIN_VIDEOS} and {MAX_VIDEOS}"
    if not MIN_THREADS <= threads <= MAX_THREADS:
        return False, f"Threads must be between {MIN_THREADS} and {MAX_THREADS}"
    if save_format not in VALID_FORMATS:
        return False, f"Invalid format. Must be one of: {', '.join(VALID_FORMATS)}"
    return True, ""


if __name__ == "__main__":
    main()
