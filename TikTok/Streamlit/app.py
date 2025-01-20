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

def explore_dataset(items, find_type):
    """
    Explores the dataset for subtitle/caption language distribution,
    including earliest url expiration date if present.
    Returns:
      - summary_stats: dict with total_videos, videos_with_data, unique_lang_count
      - lang_rows: list of dict for each language row in the final table
      - available_languages: list of available languages
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

def download_subtitle(item, languages, strip_timestamps, find_type):
    """
    Downloads or retrieves subtitles/captions for a single video item.
    Returns a list of dict results, each with:
      [id, language, success, reason, content, extension]
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
                    # Attempt download
                    try:
                        resp = requests.get(url, timeout=10)
                        resp.raise_for_status()
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

                    except Exception as e:
                        results.append({
                            "id": video_id,
                            "language": lang,
                            "success": False,
                            "reason": str(e),
                            "content": "",
                            "extension": None
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
    lines.append(f"Languages requested: {', '.join(languages)}")
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
    else:
        # Single-thread
        for item in to_process:
            res = download_subtitle(item, languages, strip_timestamps, find_type)
            all_results.extend(res)
            done_count += 1
            update_progress(done_count)

    if status_container:
        status_container.write("Download complete. Preparing output...")

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

    # Read all items into memory
    lines = uploaded_file.read().decode("utf-8").splitlines()
    items = [json.loads(line) for line in lines if line.strip()]

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


if __name__ == "__main__":
    main()
