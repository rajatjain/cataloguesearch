import os
import difflib
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

BASE_TEXT_DIR = "/Users/r0j08wt/cataloguesearch/text"
FINAL_TEXT_DIR = "/Users/r0j08wt/cataloguesearch/text_compare"

def compare_single_file(args):
    """Worker function to compare a single pair of files."""
    relative_path, base_file_path, final_file_path = args
    
    # Check if corresponding file exists in FINAL_TEXT_DIR
    if not os.path.exists(final_file_path):
        return ("different", relative_path, "File missing in FINAL_TEXT_DIR")
        
    try:
        # Read both files
        with open(base_file_path, 'r', encoding='utf-8') as f:
            base_content = f.read()
            
        with open(final_file_path, 'r', encoding='utf-8') as f:
            final_content = f.read()
        
        # Compare contents
        if base_content == final_content:
            return ("matching", relative_path, None)
        else:
            # Calculate character differences
            diff_chars = len(set(difflib.unified_diff(
                base_content.splitlines(keepends=True),
                final_content.splitlines(keepends=True)
            )))
            return ("different", relative_path, diff_chars)
            
    except Exception as e:
        return ("different", relative_path, f"Error reading files: {str(e)}")

def compare_text_files():
    print("Scanning for .txt files...")
    
    # Collect all .txt file pairs
    file_pairs = []
    for root, dirs, files in os.walk(BASE_TEXT_DIR):
        for file in files:
            if not file.endswith('.txt'):
                continue
                
            # Get the full path of the base file
            base_file_path = os.path.join(root, file)
            
            # Calculate relative path from BASE_TEXT_DIR
            relative_path = os.path.relpath(base_file_path, BASE_TEXT_DIR)
            
            # Construct corresponding path in FINAL_TEXT_DIR
            final_file_path = os.path.join(FINAL_TEXT_DIR, relative_path)
            
            file_pairs.append((relative_path, base_file_path, final_file_path))
    
    print(f"Found {len(file_pairs)} .txt files to compare")
    
    matching_files = []
    different_files = []
    
    # Process files in parallel with progress bar
    with ProcessPoolExecutor(max_workers=8) as executor:
        results = list(tqdm(
            executor.map(compare_single_file, file_pairs),
            total=len(file_pairs),
            desc="Comparing files"
        ))
    
    # Collect results
    for result_type, relative_path, diff_info in results:
        if result_type == "matching":
            matching_files.append(relative_path)
        else:
            different_files.append((relative_path, diff_info))
    
    # Print results
    print(f"\nTotal matching files: {len(matching_files)}")
    print(f"Total different files: {len(different_files)}")
    
    if different_files:
        print("\nDifferent files:")
        for file_name, diff_info in different_files:
            print(f"  {file_name}: {diff_info}")

if __name__ == "__main__":
    compare_text_files()
