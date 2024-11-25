import argparse
import json
from pathlib import Path
from collections import Counter
from tqdm import tqdm  # Progress bar for better user feedback
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import time
import re

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

# Function to download subtitles for a single video
def download_subtitle(item, languages, strip_timestamps, output_dir, verbose):
    """
    Downloads subtitles for a specific video.

    Args:
        item (dict): Metadata for a single video.
        languages (list): List of language codes to download subtitles for.
        strip_timestamps (bool): Whether to remove timestamps.
        output_dir (Path): Directory to save subtitles.
        verbose (bool): Verbose output during processing.

    Returns:
        list: Results indicating success or failure for each language.
    """
    try:
        # Extract unique video ID
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
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()

                    subtitle_content = parse_webvtt(response.text, strip_timestamps)
                    extension = "txt" if strip_timestamps else "vtt"
                    output_file = output_dir / f"{video_id}_{language}.{extension}"
                    with open(output_file, "w", encoding="utf-8") as outfile:
                        outfile.write(subtitle_content)
                    results.append({"id": video_id, "language": language, "success": True, "reason": None})
                else:
                    results.append({"id": video_id, "language": language, "success": False, "reason": "Expired URL"})
            else:
                results.append({"id": video_id, "language": language, "success": False, "reason": "Language unavailable"})

        return results
    except Exception as e:
        if verbose:
            print(f"Error processing video {item.get('data', {}).get('id', 'unknown')}: {e}")
        return [{"id": item.get("data", {}).get("item_id", item.get("data", {}).get("id", "unknown")), "language": None, "success": False, "reason": str(e)}]

# Main scraping function for subtitles
def scrape_subtitles(input_file, output_dir, languages, amount, strip_timestamps, verbose, threads):
    """
    Scrapes subtitles for a batch of videos.

    Args:
        input_file (str): Path to the NDJSON file.
        output_dir (str): Directory to save subtitles.
        languages (list): List of languages to download.
        amount (int): Number of videos to process.
        strip_timestamps (bool): Whether to remove timestamps.
        verbose (bool): Verbose output during processing.
        threads (int): Number of threads for parallel processing.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with open(input_file, "r", encoding="utf-8") as infile:
        items = [json.loads(line) for line in infile]

    # Limit the number of items to process
    items_to_process = items[:amount]
    progress = tqdm(total=len(items_to_process), desc="Processing Subtitles", disable=verbose)

    if threads > 1:
        # Multi-threaded processing
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [
                executor.submit(download_subtitle, item, languages, strip_timestamps, output_dir, verbose)
                for item in items_to_process
            ]
            for future in as_completed(futures):
                results.extend(future.result())
                progress.update(1)
    else:
        # Single-threaded processing
        for item in items_to_process:
            results.extend(download_subtitle(item, languages, strip_timestamps, output_dir, verbose))
            progress.update(1)

    progress.close()

    generate_summary_report(results, input_file, output_dir, languages, amount)

# Generate a summary report after processing
def generate_summary_report(results, input_file, output_dir, languages, amount):
    """
    Generates a summary report after scraping.

    Args:
        results (list): List of results from subtitle downloads.
        input_file (str): Path to the NDJSON file.
        output_dir (Path): Directory where subtitles were saved.
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
        report.write(f"Videos Processed: {len(results)}\n")
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
    parser.add_argument("--output_dir", type=str, default=None, help="Path to the directory where subtitles will be saved.")
    parser.add_argument("-e", "--explore", action="store_true", help="Explore the dataset instead of scraping subtitles.")
    parser.add_argument("-toplang", "--top-languages", type=int, default=5, help="Number of top languages to display in explore mode.")
    parser.add_argument("-lang", "--language", nargs="+", default=["en"], help="Language codes for subtitles (e.g., en nl).")
    parser.add_argument("-a", "--amount", type=int, default=100, help="Maximum number of subtitles to process (default: 100).")
    parser.add_argument("-s", "--strip-timestamps", action="store_true", help="Remove timestamps from subtitles.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable detailed logs during scraping.")
    parser.add_argument("-t", "--threads", type=int, default=1, help="Number of threads for parallel processing (default: 1).")
    args = parser.parse_args()

    if args.explore:
        explore_dataset(args.input_file, top_languages=args.top_languages)
    else:
        if not args.output_dir:
            print("Error: --output_dir is required for scraping mode.")
            return

        scrape_subtitles(
            args.input_file, args.output_dir, [lang.lower() for lang in args.language],
            args.amount, args.strip_timestamps, args.verbose, args.threads
        )

if __name__ == "__main__":
    main()
