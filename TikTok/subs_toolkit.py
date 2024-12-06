# CLI script updated to V0.2; added append mode and custom grouping.
import argparse
import json
from pathlib import Path
from collections import Counter
from tqdm import tqdm  # Progress bar for better user feedback
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import time
import re
import os

# Helper function to parse WebVTT content and optionally strip timestamps
def parse_webvtt(content, strip_timestamps):
    """
    Parses WebVTT subtitle content.

    Args:
        content (str): The raw subtitle content.
        strip_timestamps (bool): Whether to remove timestamps from the subtitle.

    Returns:
        str: The cleaned subtitle content (with or without timestamps).
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

# Function to explore the dataset and generate language statistics
def explore_dataset(input_file, top_languages=5):
    """
    Explores the dataset for subtitle language distribution.

    Args:
        input_file (str): Path to the NDJSON file.
        top_languages (int): Number of top languages to display.
    """
    total_videos = 0
    subtitle_language_counter = Counter()
    videos_with_subtitles = 0

    with open(input_file, "r", encoding="utf-8") as infile:
        for line in infile:
            total_videos += 1
            try:
                entry = json.loads(line)
                data_content = entry.get("data", {})
                video_content = data_content.get("video", {})
                subtitles = video_content.get("subtitleInfos", [])

                if subtitles:
                    videos_with_subtitles += 1
                    for subtitle in subtitles:
                        language = subtitle.get("LanguageCodeName", "unknown").lower()
                        subtitle_language_counter[language] += 1

            except json.JSONDecodeError:
                print(f"Skipping invalid JSON entry at line {total_videos}")

    print(f"Total Videos in Dataset: {total_videos}")
    print(f"Videos with Subtitles: {videos_with_subtitles} ({(videos_with_subtitles / total_videos) * 100:.2f}%)\n")

    print(f"Top {top_languages} Languages in Subtitles:")
    for language, count in subtitle_language_counter.most_common(top_languages):
        percentage = (count / total_videos) * 100
        print(f"{language}: {count} videos ({percentage:.2f}%)")

    remaining_languages = len(subtitle_language_counter) - top_languages
    if remaining_languages > 0:
        print(f"...and {remaining_languages} more languages. Use -toplang to see the full list.")

def get_nested_value(d, path):
    """
    Retrieves a nested value from a dictionary given a dot-separated path.
    For example, path="data.video.id" would return d["data"]["video"]["id"] if it exists.

    Args:
        d (dict): The dictionary to navigate.
        path (str): The dot-separated key path.

    Returns:
        The nested value if found, else None.
    """
    keys = path.split(".")
    current = d
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current

# Ensures a nested path exists in a dictionary, creating empty dicts as needed
def ensure_nested_path(d, path):
    """
    Ensures that the nested path in a dictionary exists by creating intermediate dictionaries.

    Args:
        d (dict): The dictionary to modify.
        path (str): Dot-separated path, e.g. "data.video.subtitle".
    """
    keys = path.split(".")
    current = d
    for key in keys:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]

# Function to download subtitles for a single video
def download_subtitle(item, languages, strip_timestamps, output_dir, verbose, append_mode=False, group_by=None):
    """
    Downloads or retrieves subtitles for a specific video.

    Args:
        item (dict): Metadata for a single video.
        languages (list): List of language codes to download subtitles for.
        strip_timestamps (bool): Whether to remove timestamps.
        output_dir (Path): Directory to save subtitles.
        verbose (bool): Verbose output during processing.
        append_mode (bool): If True, return subtitle texts instead of writing files.
        group_by (str or None): If not None and not append_mode, group files by 'language' or by a nested key path.

    Returns:
        list: Results indicating success or failure for each language, and possibly the subtitle text if append_mode is True.
    """
    try:
        video_id = item.get("data", {}).get("item_id", item.get("data", {}).get("id", "unknown"))
        data_content = item.get("data", {})
        video_content = data_content.get("video", {})
        subtitles = video_content.get("subtitleInfos", [])

        results = []
        for language in languages:
            # Filter subtitles matching the requested language
            matching_subtitles = [
                sub for sub in subtitles
                if sub.get("LanguageCodeName", "").lower().startswith(language) and sub.get("Format") == "webvtt"
            ]

            if matching_subtitles:
                subtitle = matching_subtitles[0]
                url = subtitle.get("Url")
                url_expire = subtitle.get("UrlExpire", 0)

                # Check if URL is valid and not expired
                if url and int(url_expire) > time.time():
                    try:
                        response = requests.get(url, timeout=10)
                        response.raise_for_status()
                    except Exception as e:
                        results.append({"id": video_id, "language": language, "success": False, "reason": str(e), "content": "" if append_mode else None})
                        continue

                    subtitle_content = parse_webvtt(response.text, strip_timestamps)

                    if append_mode:
                        # In append mode, just return the content
                        results.append({
                            "id": video_id,
                            "language": language,
                            "success": True,
                            "reason": None,
                            "content": subtitle_content
                        })
                    else:
                        # Determine grouping if needed
                        if group_by is None:
                            # No grouping
                            pass_dir = output_dir
                        else:
                            if group_by.lower() == "language":
                                pass_dir = output_dir / language
                            else:
                                # Group by a nested key
                                val = get_nested_value(item, group_by)
                                val_str = str(val) if val is not None else "unknown"
                                pass_dir = output_dir / val_str

                        pass_dir.mkdir(parents=True, exist_ok=True)
                        extension = "txt" if strip_timestamps else "vtt"
                        output_file = pass_dir / f"{video_id}_{language}.{extension}"
                        with open(output_file, "w", encoding="utf-8") as outfile:
                            outfile.write(subtitle_content)
                        results.append({"id": video_id, "language": language, "success": True, "reason": None, "content": None})
                else:
                    # Expired or invalid URL
                    if append_mode:
                        results.append({"id": video_id, "language": language, "success": False, "reason": "Expired URL", "content": ""})
                    else:
                        results.append({"id": video_id, "language": language, "success": False, "reason": "Expired URL", "content": None})
            else:
                # Language not available
                if append_mode:
                    results.append({"id": video_id, "language": language, "success": False, "reason": "Language unavailable", "content": ""})
                else:
                    results.append({"id": video_id, "language": language, "success": False, "reason": "Language unavailable", "content": None})

        return results
    except Exception as e:
        if verbose:
            print(f"Error processing video {item.get('data', {}).get('id', 'unknown')}: {e}")
        return [{
            "id": item.get("data", {}).get("item_id", item.get("data", {}).get("id", "unknown")),
            "language": None,
            "success": False,
            "reason": str(e),
            "content": "" if append_mode else None
        }]

def scrape_subtitles(input_file, output_dir, languages, amount, strip_timestamps, verbose, threads, append_mode=False, group_by=None):
    """
    Scrapes subtitles for a batch of videos.

    Args:
        input_file (str): Path to the NDJSON file.
        output_dir (str): Directory to save subtitles or appended file.
        languages (list): List of languages to download.
        amount (int): Number of videos to process.
        strip_timestamps (bool): Whether to remove timestamps.
        verbose (bool): Verbose output during processing.
        threads (int): Number of threads for parallel processing.
        append_mode (bool): If True, append subtitles to a new NDJSON file instead of writing files.
        group_by (str or None): Grouping criterion (language or nested key).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as infile:
        items = [json.loads(line) for line in infile]

    # Limit the number of items to process
    items_to_process = items[:amount]
    progress = tqdm(total=len(items_to_process), desc="Processing Subtitles", disable=verbose)

    all_results = []
    if threads > 1:
        # Multi-threaded processing
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [
                executor.submit(
                    download_subtitle,
                    item,
                    languages,
                    strip_timestamps,
                    output_dir,
                    verbose,
                    append_mode,
                    group_by
                )
                for item in items_to_process
            ]
            for future in as_completed(futures):
                res = future.result()
                all_results.extend(res)
                progress.update(1)
    else:
        # Single-threaded processing
        for item in items_to_process:
            res = download_subtitle(item, languages, strip_timestamps, output_dir, verbose, append_mode, group_by)
            all_results.extend(res)
            progress.update(1)

    progress.close()

    if append_mode:
        # Create a new NDJSON file with appended subtitles
        appended_file = output_dir / "appended_subtitles.ndjson"
        # Organise results by video_id
        video_map = {}
        for r in all_results:
            vid = r["id"]
            if vid not in video_map:
                video_map[vid] = {"languages": {}}
            if r["language"] is not None:
                video_map[vid]["languages"][r["language"]] = r["content"] if r["success"] else ""

        # Create the appended NDJSON lines
        with open(appended_file, "w", encoding="utf-8") as out_f:
            for item in items_to_process:
                vid = item.get("data", {}).get("item_id", item.get("data", {}).get("id", "unknown"))
                lang_contents = video_map.get(vid, {}).get("languages", {})
                # Append language fields to the item under data.video.subtitle.{lang}
                ensure_nested_path(item, "data.video.subtitle")
                for lang, subtitle_text in lang_contents.items():
                    item["data"]["video"]["subtitle"][lang] = subtitle_text
                out_f.write(json.dumps(item, ensure_ascii=False) + "\n")

    generate_summary_report(all_results, input_file, output_dir, languages, amount)

# Generate a summary report after processing
def generate_summary_report(results, input_file, output_dir, languages, amount):
    """
    Generates a summary report after scraping.

    Args:
        results (list): List of results from subtitle downloads.
        input_file (str): Path to the NDJSON file.
        output_dir (Path): Directory where output was saved.
        languages (list): List of processed languages.
        amount (int): Number of videos processed.
    """
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    report_path = output_dir / "summary_report.txt"
    with open(report_path, "w", encoding="utf-8") as report:
        report.write("Subtitle Scraping Summary\n")
        report.write("=" * 30 + "\n")
        report.write(f"Input File: {input_file}\n")
        report.write(f"Languages: {', '.join(languages)}\n")
        report.write(f"Total Attempts (video-language pairs): {len(results)}\n")
        report.write(f"Successful Downloads: {len(successful)}\n")
        report.write(f"Failed Downloads: {len(failed)}\n\n")

        report.write("Failed Cases:\n")
        for failure in failed:
            report.write(f"Video ID: {failure['id']} - Language: {failure['language']} - Reason: {failure['reason']}\n")

    print(f"Summary report generated at: {report_path}")

# Main entry point for the script
def main():
    parser = argparse.ArgumentParser(description="TikTok Subtitle Dataset Exploration and Scraping Tool")
    parser.add_argument("input_file", type=str, help="Path to the input NDJSON file.")
    parser.add_argument("--output_dir", type=str, default=None, help="Path to the directory where subtitles will be saved or appended NDJSON will be created.")
    parser.add_argument("-e", "--explore", action="store_true", help="Explore the dataset instead of scraping subtitles.")
    parser.add_argument("-toplang", "--top-languages", type=int, default=5, help="Number of top languages to display in explore mode.")
    parser.add_argument("-lang", "--language", nargs="+", default=["en"], help="Language codes for subtitles (e.g., en nl).")
    parser.add_argument("-a", "--amount", type=int, default=100, help="Maximum number of subtitles to process (default: 100).")
    parser.add_argument("-s", "--strip-timestamps", action="store_true", help="Remove timestamps from subtitles.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable detailed logs during scraping.")
    parser.add_argument("-t", "--threads", type=int, default=1, help="Number of threads for parallel processing (default: 1).")

    # New arguments
    parser.add_argument("-apd", "--append", action="store_true", help="Append subtitles as nested fields under data.video.subtitle.{language} in a new NDJSON file rather than saving separate files.")
    parser.add_argument("-g", "--group", type=str, default=None, help="Group downloaded files by 'language' or a nested key path (e.g. data.video.id). Not applicable in append mode.")

    args = parser.parse_args()

    if args.explore:
        explore_dataset(args.input_file, top_languages=args.top_languages)
    else:
        if not args.output_dir:
            print("Error: --output_dir is required for scraping mode.")
            return

        # If append mode is enabled, grouping does not apply
        group_by = None if args.append else args.group

        scrape_subtitles(
            args.input_file, args.output_dir, [lang.lower() for lang in args.language],
            args.amount, args.strip_timestamps, args.verbose, args.threads,
            append_mode=args.append, group_by=group_by
        )

if __name__ == "__main__":
    main()
