import re
import argparse

def log_lines(file_name, min_chars, max_chars):
    """
    Analyzes a log file to find specific log message formats and filters them
    by the length of the captured content.

    Args:
        file_name (str): The path to the log file.
        min_chars (int): The minimum character length of the content to match.
        max_chars (int): The maximum character length of the content to match.
    """
    # Regex to find lines with "Stripped: '...'"
    # It captures the content inside the single quotes.
    stripped_regex = re.compile(r"Stripped: '(.*?)'")

    # Regex to find lines with "matched: '...'"
    # It captures the content inside the single quotes.
    matched_regex = re.compile(r"matched: '(.*?)'")

    print(f"\n--- Analyzing '{file_name}' for content between {min_chars} and {max_chars} characters ---\n")

    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            # Using enumerate to get both the line number (starting from 1) and the line content
            for line_num, line in enumerate(f, 1):
                # Search for the "Stripped" pattern in the current line
                stripped_match = stripped_regex.search(line)
                # Search for the "matched" pattern in the current line
                matched_match = matched_regex.search(line)

                content = None

                if stripped_match:
                    # Extract the captured group (the stripped_content)
                    content = stripped_match.group(1)
                elif matched_match:
                    # Extract the captured group (the para)
                    content = matched_match.group(1)

                # If we found content from either pattern, check its length
                if content is not None:
                    content_len = len(content)
                    if min_chars <= content_len <= max_chars:
                        print(f"Line {line_num}: '{content}'")

    except FileNotFoundError:
        print(f"Error: The file '{file_name}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    # Set up argument parser to accept command-line arguments
    parser = argparse.ArgumentParser(
        description="Analyze log files to find 'Stripped' and 'matched' content within a specific character length."
    )
    # Argument for the log file name
    parser.add_argument(
        "file_name",
        type=str,
        help="The name of the log file to analyze (e.g., verbose.log)"
    )
    # Optional argument for minimum characters
    parser.add_argument(
        "--min",
        type=int,
        default=0,
        help="Minimum character length for the content."
    )
    # Optional argument for maximum characters
    parser.add_argument(
        "--max",
        type=int,
        default=100000,
        help="Maximum character length for the content."
    )

    args = parser.parse_args()

    # Call the function with the parsed arguments
    log_lines(args.file_name, args.min, args.max)
