import os
import argparse
import logging
from bs4 import BeautifulSoup, NavigableString
import chardet
import re
from unidecode import unidecode
import unicodedata
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename='extraction.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def sanitize_filename(title: str) -> str:
    """
    Sanitizes the title to create a valid filename by removing invalid characters,
    replacing spaces with underscores, and truncating to a maximum length.

    Args:
        title (str): The original title extracted from HTML.

    Returns:
        str: A sanitized filename.
    """
    # Remove invalid characters
    sanitized = re.sub(r'[^\w\s\-_]', '', title)
    # Replace spaces with underscores
    sanitized = sanitized.strip().replace(' ', '_')
    # Truncate to a reasonable length (255 characters)
    return sanitized[:255]


def detect_file_encoding(file_path: str, sample_size: int = 10000) -> str:
    """
    Detects the encoding of a file by reading a sample of its content.

    Args:
        file_path (str): Path to the HTML file.
        sample_size (int, optional): Number of bytes to read for detection. Defaults to 10000.

    Returns:
        str: Detected encoding or 'utf-8' as a fallback.
    """
    try:
        with open(file_path, 'rb') as file:
            raw_data = file.read(sample_size)
        detection = chardet.detect(raw_data)
        encoding = detection.get('encoding', 'utf-8')
        confidence = detection.get('confidence', 0)
        logging.info(f"Detected encoding for '{file_path}': {encoding} (Confidence: {confidence})")
        return encoding if encoding else 'utf-8'
    except Exception as error:
        logging.error(f"Error detecting encoding for '{file_path}': {error}")
        return 'utf-8'


def extract_timestamp_from_html(html_content: str) -> str:
    """
    Extracts a 14-digit timestamp from the HTML content using predefined regex patterns.

    Args:
        html_content (str): The raw HTML content.

    Returns:
        str: Extracted timestamp or None if not found.
    """
    timestamp_patterns = [
        r'Cached/compressed (\d{14})',            # Older archives
        r'timestamp (\d{14})',                    # Newer archives
        r'parser cache.*?timestamp (\d{14})',      # More specific newer archives
    ]

    for pattern in timestamp_patterns:
        match = re.search(pattern, html_content)
        if match:
            timestamp = match.group(1)
            logging.info(f"Extracted timestamp: {timestamp}")
            return timestamp
    logging.warning("No timestamp found in HTML content.")
    return None


def normalize_and_transliterate(text: str) -> str:
    """
    Normalizes Unicode characters to NFC form and transliterates to ASCII.

    Args:
        text (str): The text to normalize and transliterate.

    Returns:
        str: The normalized and transliterated text.
    """
    normalized_text = unicodedata.normalize('NFC', text)
    ascii_text = unidecode(normalized_text)
    return ascii_text


def extract_title_and_content(html_content: str) -> (str, str):
    """
    Parses HTML content to extract the title and main body text.

    Args:
        html_content (str): The raw HTML content.

    Returns:
        tuple: A tuple containing the extracted title and body text.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Potential selectors for the title
        title_selectors = [
            {'tag': 'h1', 'attrs': {'id': 'firstHeading'}},
            {'tag': 'h1', 'attrs': {'class': 'pagetitle'}},
            {'tag': 'h1', 'attrs': {'class': 'firstHeading'}},  # Edge case
            {'tag': 'title'},  # Fallback
        ]

        title = 'No Title Found'
        for selector in title_selectors:
            title_tag = soup.find(selector['tag'], attrs=selector.get('attrs', {}))
            if title_tag:
                title = title_tag.get_text(strip=True)
                if selector['tag'] == 'title':
                    logging.warning("Used <title> tag as fallback for title extraction.")
                else:
                    logging.info(f"Extracted title using selector: {selector}")
                break

        # Potential selectors for the main content
        content_selectors = [
            {'name': 'div', 'attrs': {'id': 'mw-content-text'}},
            {'name': 'div', 'attrs': {'id': 'content'}},
            {'name': 'div', 'attrs': {'id': 'article'}},  # Older structures
            {'name': 'article'},
            {'name': 'main'},
        ]

        main_content = None
        for selector in content_selectors:
            main_content = soup.find(selector['name'], attrs=selector.get('attrs', {}))
            if main_content:
                logging.info(f"Found main content using selector: {selector}")
                break

        if not main_content:
            logging.warning("Main content section not found.")
            return normalize_and_transliterate(title), ""

        # Remove unwanted sections by ID
        unwanted_ids = ['toc', 'footer', 'mw-navigation', 'mw-page-base', 'siteSub', 'jump-to-nav']
        for uid in unwanted_ids:
            for tag in main_content.find_all(id=uid):
                tag.decompose()

        # Remove unwanted sections by class
        unwanted_classes = ['mw-editsection', 'reference', 'infobox', 'navbox', 'metadata']
        for cls in unwanted_classes:
            for tag in main_content.find_all(class_=cls):
                tag.decompose()

        # Remove all hyperlinks but retain text
        for anchor in main_content.find_all('a'):
            anchor.replace_with(anchor.get_text())

        # Handle inline tags to preserve spaces
        for tag in main_content.find_all(['strong', 'em']):
            if tag.previous_sibling and isinstance(tag.previous_sibling, NavigableString):
                if not tag.previous_sibling.string.endswith(' '):
                    tag.insert_before(' ')
            if tag.next_sibling and isinstance(tag.next_sibling, NavigableString):
                if not tag.next_sibling.string.startswith(' '):
                    tag.insert_after(' ')

        # Extract text while preserving paragraphs and headers
        paragraphs = main_content.find_all(['p', 'h2', 'h3', 'h4', 'h5', 'h6'])
        body = '\n\n'.join([para.get_text(separator=' ', strip=True) for para in paragraphs])

        # Normalize and transliterate text
        normalized_body = normalize_and_transliterate(body)
        normalized_title = normalize_and_transliterate(title)

        logging.info(f"Successfully extracted content for '{normalized_title}'")
        return normalized_title, normalized_body

    except Exception as error:
        logging.error(f"Error extracting content: {error}")
        return 'No Title', 'No Content'


def process_html_file(file_path: str, naming_option: str) -> (str, str, str):
    """
    Processes a single HTML file to extract the title, body, and determine the suffix
    based on the naming option.

    Args:
        file_path (str): Path to the HTML file.
        naming_option (str): Naming option ('A' or 'B').

    Returns:
        tuple: A tuple containing the title, body, and suffix.
    """
    encoding = detect_file_encoding(file_path)

    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as file:
            html_content = file.read()

        title, body = extract_title_and_content(html_content)

        if naming_option == 'A':
            # Internal timestamp from HTML
            timestamp = extract_timestamp_from_html(html_content)
            suffix = timestamp if timestamp else None
        elif naming_option == 'B':
            # External timestamp from filename
            input_filename = os.path.basename(file_path)
            input_name, _ = os.path.splitext(input_filename)
            suffix = input_name
        else:
            suffix = None  # Should not occur

        return title, body, suffix

    except Exception as error:
        logging.error(f"Error processing file '{file_path}': {error}")
        return 'No Title', 'No Content', None


def save_content_to_file(title: str, body: str, output_dir: str, suffix: str, existing_filenames: set):
    """
    Saves the extracted title and body to a text file with the specified suffix.

    Args:
        title (str): Extracted title.
        body (str): Extracted body content.
        output_dir (str): Directory to save the text file.
        suffix (str): Suffix to append to the filename.
        existing_filenames (set): Set of existing filenames to avoid duplicates.
    """
    filename_base = sanitize_filename(title)
    filename = f"{filename_base}_{suffix}" if suffix else filename_base

    # Ensure filename uniqueness
    original_filename = filename
    counter = 1
    while filename in existing_filenames:
        filename = f"{original_filename}_{counter}"
        counter += 1
    existing_filenames.add(filename)

    filepath = os.path.join(output_dir, f"{filename}.txt")

    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(f"{title}\n\n{body}")
        logging.info(f"Saved extracted content to '{filepath}'")
    except Exception as error:
        logging.error(f"Error saving content to '{filepath}': {error}")


def process_directory(input_dir: str, output_dir: str, naming_option: str) -> (list, list):
    """
    Processes all HTML files within a directory, extracting content and saving to text files.

    Args:
        input_dir (str): Path to the input directory containing HTML files.
        output_dir (str): Path to the output directory for text files.
        naming_option (str): Naming option ('A' or 'B').

    Returns:
        tuple: A tuple containing a list of skipped files and a list of empty files.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logging.info(f"Created output directory '{output_dir}'")

    skipped_files = []
    empty_files = []
    existing_filenames = set()

    # Gather all HTML files (case-insensitive)
    html_files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.html', '.htm'))]

    # Initialize tqdm progress bar
    for html_file in tqdm(html_files, desc="Processing HTML files", unit="file"):
        file_path = os.path.join(input_dir, html_file)
        logging.info(f"Processing file '{file_path}'")
        title, body, suffix = process_html_file(file_path, naming_option)

        if naming_option == 'A' and not suffix:
            # Skip file if internal timestamp is missing
            skipped_files.append(html_file)
            logging.warning(f"Skipped '{html_file}' due to missing timestamp.")
            continue

        save_content_to_file(title, body, output_dir, suffix, existing_filenames)
        print(f"Processed '{title}'")

        # Check if original HTML file is empty
        if os.path.getsize(file_path) == 0:
            output_filename = f"{sanitize_filename(title)}_{suffix}.txt" if suffix else f"{sanitize_filename(title)}.txt"
            empty_filepath = os.path.join(output_dir, output_filename)
            empty_files.append(empty_filepath)

    return skipped_files, empty_files


def prompt_naming_option() -> str:
    """
    Prompts the user to select the naming convention for output files.

    Returns:
        str: The selected naming option ('A' or 'B').
    """
    print("Choose the output naming convention for the text files:")
    print("A. Rename output files using internal timestamps.")
    print("B. Rename output files with external timestamps.")

    while True:
        choice = input("Enter 'A' or 'B': ").strip().upper()
        if choice in {'A', 'B'}:
            return choice
        else:
            print("Invalid input. Please enter 'A' or 'B'.")


def main():
    """
    The main function orchestrates the extraction process based on user inputs
    and command-line arguments.
    """
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description="Extract titles and main content from Wikipedia HTML files."
    )
    parser.add_argument(
        'input_path',
        type=str,
        help='Path to the input HTML file or directory containing HTML files.'
    )
    parser.add_argument(
        'output_directory',
        type=str,
        help='Directory where the extracted text files will be saved.'
    )
    args = parser.parse_args()

    # Prompt for naming option
    naming_option = prompt_naming_option()

    # Display chosen naming option
    if naming_option == 'A':
        print("\nSelected Naming Option: Internal Timestamps")
    else:
        print("\nSelected Naming Option: External Timestamps")

    # Determine if input path is a file or directory
    if os.path.isfile(args.input_path):
        if not os.path.exists(args.output_directory):
            os.makedirs(args.output_directory)
            logging.info(f"Created output directory '{args.output_directory}'")

        title, body, suffix = process_html_file(args.input_path, naming_option)

        if naming_option == 'A' and not suffix:
            print(f"Skipped '{args.input_path}' due to missing timestamp.")
            logging.warning(f"Skipped file '{args.input_path}' due to missing timestamp.")
        else:
            # Save content
            existing_filenames = set()
            save_content_to_file(title, body, args.output_directory, suffix, existing_filenames)
            print(f"Extracted content saved for '{title}'")

            # Check if original file is empty
            if os.path.getsize(args.input_path) == 0:
                output_filename = f"{sanitize_filename(title)}_{suffix}.txt" if suffix else f"{sanitize_filename(title)}.txt"
                empty_filepath = os.path.join(args.output_directory, output_filename)
                print("\n1 file is empty but still renamed. The empty file is listed below:")
                print(f"- {empty_filepath}")

    elif os.path.isdir(args.input_path):
        skipped_files, empty_files = process_directory(args.input_path, args.output_directory, naming_option)

        # Report skipped files
        if naming_option == 'A' and skipped_files:
            print("\nThe following files were skipped due to missing timestamps:")
            for skipped in skipped_files:
                print(f"- {skipped}")

        # Report empty files
        if empty_files:
            print(f"\n{len(empty_files)} file(s) are empty but still renamed. The empty files are listed below:")
            for empty in empty_files:
                print(f"- {empty}")

        print("\nBatch processing completed.")

    else:
        print("Error: The input path must be a valid file or directory.")
        logging.error(f"Invalid input path: '{args.input_path}'")

    print("\nProcessing completed. Check 'extraction.log' for detailed logs.")


if __name__ == "__main__":
    main()
