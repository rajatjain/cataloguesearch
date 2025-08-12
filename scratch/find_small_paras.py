import os

def identify_small_paras(root_dir, min_words=20, min_chars=120):
    """
    Recursively finds small paragraphs in .txt files within a directory.

    This function walks through a directory tree, reads all .txt files, and
    splits their content into paragraphs based on a "----" delimiter. It then
    identifies paragraphs that have a word count or character count less than
    the specified minimums.

    Args:
        root_dir (str): The path to the base directory to search.
        min_words (int, optional): The word count threshold. Defaults to 20.
        min_chars (int, optional): The character count threshold. Defaults to 120.

    Returns:
        list: A list of tuples. Each tuple contains the shortened file path
              (e.g., parent_dir/filename.txt), the paragraph text, its word count,
              and its character count.
              Example: [('level2/report.txt', 'Short para.', 2, 11)]
    """
    small_paragraphs = []

    # Ensure the provided directory path exists
    if not os.path.isdir(root_dir):
        print(f"Error: Directory not found at '{root_dir}'")
        return []

    # os.walk generates the file names in a directory tree
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            # Process only .txt files
            if filename.endswith(".txt"):
                full_path = os.path.join(dirpath, filename)
                # Get the file path relative to the starting directory
                relative_path = os.path.relpath(full_path, root_dir)

                # Shorten the path to show only the parent directory and filename
                path_parts = relative_path.split(os.sep)
                if len(path_parts) > 1:
                    # e.g., from 'a/b/c/d/e.txt' to 'd/e.txt'
                    display_path = os.path.join(path_parts[-2], path_parts[-1])
                else:
                    # e.g., 'e.txt' remains 'e.txt'
                    display_path = relative_path

                try:
                    # Open and read the file
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                        # Split the content into paragraphs using the delimiter
                        paragraphs = content.split('----')

                        for para in paragraphs:
                            # Clean up paragraph by removing leading/trailing whitespace
                            cleaned_para = para.strip()

                            # Skip empty strings that result from the split operation
                            if not cleaned_para:
                                continue

                            # Count words and characters
                            word_count = len(cleaned_para.split())
                            char_count = len(cleaned_para)

                            # Check if the paragraph is smaller than either threshold
                            if word_count < min_words or char_count < min_chars:
                                # Use the shortened display_path
                                small_paragraphs.append((display_path, cleaned_para, word_count, char_count))
                except Exception as e:
                    print(f"Could not read or process file {full_path}: {e}")

    return small_paragraphs

# --- Example Usage ---
# The following block demonstrates how to use the function.
# It creates a temporary directory structure with sample files for testing.
if __name__ == '__main__':
    # Define the name for our test directory
    test_dir = "/Users/r0j08wt/cataloguesearch/text/Pravachans/hindi/Dravyanuyog/"

    small_paras_found = identify_small_paras(test_dir, min_words=3, min_chars=20)

    if small_paras_found:
        print("\nFound the following small paragraphs:")
        for path, para, wc, cc in small_paras_found:
            # The path returned from the function is now the desired display path.
            print(f"  - File: {path}, Para: \"{para}\"\n")
            print(f"------------------------")
    else:
        print("\nNo small paragraphs found with the specified thresholds.")
