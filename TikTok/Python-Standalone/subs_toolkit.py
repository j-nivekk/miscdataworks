import argparse
import json
from pathlib import Path
from collections import Counter
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import time
import re
import csv
import os
import sys

def parse_webvtt(content, strip_timestamps):
    """
    Parses WebVTT subtitle content.

    Args:
        content (str): The raw subtitle content.
        strip_timestamps (bool): Whether to remove timestamps from the subtitle text.

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

def explore_dataset(input_file, top_languages=5):
    """
    Explores the dataset for subtitle language distribution.
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
        print(f"...and {remaining_languages} more languages. Use --top-languages to see the full list.")

def get_nested_value(d, path):
    """
    Retrieves a nested value from a dictionary given a dot-separated path.
    """
    keys = path.split(".")
    current = d
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current

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

def download_subtitle(item, languages, strip_timestamps, output_dir, verbose, save_format, group_by=None):
    """
    Downloads or retrieves subtitles for a single video.

    Args:
        item (dict): The video metadata item.
        languages (list): List of language codes.
        strip_timestamps (bool): Whether to remove timestamps.
        output_dir (Path): Output directory.
        verbose (bool): Verbose mode.
        save_format (str): One of {'text', 'ndjson', 'csv'}.
        group_by (str or None): Grouping key for text mode.
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
                        results.append({"id": video_id, "language": language, "success": False, "reason": str(e), "content": ""})
                        continue

                    subtitle_content = parse_webvtt(response.text, strip_timestamps)

                    if save_format == "text":
                        # Text mode: save files directly
                        if group_by is None:
                            pass_dir = output_dir
                        else:
                            if group_by.lower() == "language":
                                pass_dir = output_dir / language
                            else:
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
                        # ndjson or csv: store content in memory
                        results.append({"id": video_id, "language": language, "success": True, "reason": None, "content": subtitle_content})
                else:
                    # Expired or invalid URL
                    results.append({"id": video_id, "language": language, "success": False, "reason": "Expired URL", "content": ""})
            else:
                # Language not available
                results.append({"id": video_id, "language": language, "success": False, "reason": "Language unavailable", "content": ""})

        return results
    except Exception as e:
        if verbose:
            print(f"Error processing video {item.get('data', {}).get('id', 'unknown')}: {e}")
        return [{
            "id": item.get("data", {}).get("item_id", item.get("data", {}).get("id", "unknown")),
            "language": None,
            "success": False,
            "reason": str(e),
            "content": ""
        }]

def scrape_subtitles(input_file, output_dir, languages, num_videos, strip_timestamps, verbose, threads, save_format, group_by=None):
    """
    Scrapes subtitles for a batch of videos.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as infile:
        items = [json.loads(line) for line in infile]

    # Limit the number of items to process
    items_to_process = items[:num_videos]
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
                    save_format,
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
            res = download_subtitle(item, languages, strip_timestamps, output_dir, verbose, save_format, group_by)
            all_results.extend(res)
            progress.update(1)

    progress.close()

    # Handle NDJSON and CSV output
    if save_format == "ndjson":
        appended_file = output_dir / "appended_subtitles.ndjson"
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
                ensure_nested_path(item, "data.video.subtitle")
                for lang, subtitle_text in lang_contents.items():
                    item["data"]["video"]["subtitle"][lang] = subtitle_text
                out_f.write(json.dumps(item, ensure_ascii=False) + "\n")

    elif save_format == "csv":
        # CSV mode: produce subtitles.csv
        video_map = {}
        for r in all_results:
            vid = r["id"]
            if vid not in video_map:
                video_map[vid] = {}
            if r["language"] is not None:
                video_map[vid][r["language"]] = r["content"] if r["success"] else ""

        csv_file = output_dir / "subtitles.csv"
        with open(csv_file, "w", encoding="utf-8", newline="") as csv_out:
            writer = csv.writer(csv_out)
            header = ["video_id"] + languages
            writer.writerow(header)
            for item in items_to_process:
                vid = item.get("data", {}).get("item_id", item.get("data", {}).get("id", "unknown"))
                row = [vid]
                for lang in languages:
                    row.append(video_map.get(vid, {}).get(lang, ""))
                writer.writerow(row)

    generate_summary_report(all_results, input_file, output_dir, languages, len(items_to_process))

def generate_summary_report(results, input_file, output_dir, languages, amount):
    """
    Generates a summary report after scraping.
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

def main():
    parser = argparse.ArgumentParser(description="TikTok Subtitle Dataset Exploration and Scraping Tool (v0.3)")
    parser.add_argument("input_file", type=str, help="Path to the input NDJSON file containing TikTok metadata.")
    
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save outputs (required for scraping).")
    parser.add_argument("-E", "--explore", action="store_true", help="Run in exploration mode to analyse subtitle language availability.")
    parser.add_argument("--top-languages", type=int, default=5, help="Number of top languages to display in exploration mode (default: 5).")
    parser.add_argument("-L", "--languages", nargs="+", default=["en"], help="Language codes for subtitles (e.g., en fr).")
    parser.add_argument("-n", "--num-videos", type=int, default=100, help="Maximum number of videos to process (default: 100).")
    parser.add_argument("-s", "--strip-timestamps", action="store_true", help="Remove timestamps for cleaner subtitle text.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable detailed logs instead of a progress bar.")
    parser.add_argument("-t", "--threads", type=int, default=1, help="Number of threads for parallel processing (default: 1).")
    parser.add_argument("-f", "--format", choices=["text", "ndjson", "csv"], default="text",
                        help="Output format: 'text' (default), 'ndjson' (append subtitles to dataset), or 'csv' (single CSV file).")
    parser.add_argument("-g", "--group", type=str, default=None, help="Group subtitles by 'language' or a nested key (text mode only).")

    # Legacy argument: --append
    parser.add_argument("-apd", "--append", action="store_true", help="(Deprecated) Append subtitles into NDJSON. Use --format ndjson instead.")

    args = parser.parse_args()

    # Handle legacy append
    if args.append:
        print("Warning: The --append option is deprecated. Please use --format ndjson instead.")
        args.format = "ndjson"

    if args.explore:
        # Exploration Mode
        explore_dataset(args.input_file, top_languages=args.top_languages)
    else:
        # Scraping Modes
        if not args.output_dir:
            print("Error: --output-dir is required for scraping mode.")
            sys.exit(1)

        # If grouping is used in non-text modes, warn and ignore
        if args.group is not None and args.format in ["ndjson", "csv"]:
            print("Warning: Grouping is only applicable in text mode. Ignoring --group option.")
            args.group = None

        scrape_subtitles(
            args.input_file, args.output_dir, [lang.lower() for lang in args.languages],
            args.num_videos, args.strip_timestamps, args.verbose, args.threads,
            save_format=args.format, group_by=args.group
        )

if __name__ == "__main__":
    main()
