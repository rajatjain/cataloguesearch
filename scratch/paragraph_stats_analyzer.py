#!/usr/bin/env python3
"""
Paragraph Statistics Analyzer

This script recursively browses through all sub-directories from a base directory,
finds all page_*.txt files, splits paragraphs by "----", calculates character counts,
and provides statistics on paragraph length distribution.
"""

import os
import glob
import argparse
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


def worker_process_files(file_chunk):
    """
    Worker function to process a chunk of files and return aggregated statistics.
    
    Args:
        file_chunk (list): List of file paths to process
        
    Returns:
        tuple: (stats_dict, total_paragraphs, total_files)
    """
    # Initialize worker statistics counters
    worker_stats = {
        '0-30': 0,
        '30-100': 0,
        '100-200': 0,
        '200-500': 0,
        '500-1000': 0,
        '1000-1500': 0,
        '1500-2000': 0,
        '2000-5000': 0,
        '5000+': 0
    }
    
    worker_paragraphs = 0
    worker_files = 0
    
    for file_path in file_chunk:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Split content by "----" to get paragraphs
            paragraphs = content.split('----')
            
            # Process each paragraph
            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                if not paragraph:  # Skip empty paragraphs
                    continue
                    
                char_count = len(paragraph)
                worker_paragraphs += 1
                
                # Categorize by character count
                if char_count <= 30:
                    worker_stats['0-30'] += 1
                elif char_count <= 100:
                    worker_stats['30-100'] += 1
                elif char_count <= 200:
                    worker_stats['100-200'] += 1
                elif char_count <= 500:
                    worker_stats['200-500'] += 1
                elif char_count <= 1000:
                    worker_stats['500-1000'] += 1
                elif char_count <= 1500:
                    worker_stats['1000-1500'] += 1
                elif char_count <= 2000:
                    worker_stats['1500-2000'] += 1
                elif char_count <= 5000:
                    worker_stats['2000-5000'] += 1
                else:
                    worker_stats['5000+'] += 1
                    
            worker_files += 1
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    return worker_stats, worker_paragraphs, worker_files


def analyze_paragraph_stats(base_dir, max_workers=None):
    """
    Analyze paragraph statistics from page_*.txt files using parallel processing (map-reduce pattern).
    
    Args:
        base_dir (str): Base directory to start the recursive search
        max_workers (int): Maximum number of worker threads (None for default)
        
    Returns:
        tuple: (stats_dict, total_paragraphs, total_files)
    """
    # Recursively find all page_*.txt files
    pattern = os.path.join(base_dir, '**/page_*.txt')
    page_files = glob.glob(pattern, recursive=True)
    
    print(f"Found {len(page_files)} page_*.txt files in {base_dir}")
    
    if not page_files:
        return {}, 0, 0
    
    # Determine number of workers
    if max_workers is None:
        max_workers = min(32, (os.cpu_count() or 1) + 4)
    
    print(f"Processing with {max_workers} worker threads...")
    
    # Split files into chunks for workers (MAP phase)
    chunk_size = max(1, len(page_files) // max_workers)
    file_chunks = [page_files[i:i + chunk_size] for i in range(0, len(page_files), chunk_size)]
    
    # Process chunks in parallel
    worker_results = []
    processed_files = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all chunks to workers
        futures = [executor.submit(worker_process_files, chunk) for chunk in file_chunks]
        
        # Collect results as they complete
        for i, future in enumerate(as_completed(futures)):
            worker_stats, worker_paragraphs, worker_files = future.result()
            worker_results.append((worker_stats, worker_paragraphs, worker_files))
            processed_files += worker_files
            
            # Progress update
            if processed_files >= 1000 and processed_files % 1000 <= worker_files:
                print(f"Finished ~{processed_files} of {len(page_files)} pages")
    
    # REDUCE phase: Combine all worker results
    final_stats = {
        '0-30': 0,
        '30-100': 0,
        '100-200': 0,
        '200-500': 0,
        '500-1000': 0,
        '1000-1500': 0,
        '1500-2000': 0,
        '2000-5000': 0,
        '5000+': 0
    }
    
    total_paragraphs = 0
    total_files = 0
    
    for worker_stats, worker_paragraphs, worker_files in worker_results:
        for key in final_stats:
            final_stats[key] += worker_stats[key]
        total_paragraphs += worker_paragraphs
        total_files += worker_files
    
    print(f"All {total_files} files processed!")
    return final_stats, total_paragraphs, total_files


def print_statistics(stats, total_paragraphs, total_files):
    """
    Print formatted statistics in a fixed-width table.
    
    Args:
        stats (dict): Statistics dictionary with character range counts
        total_paragraphs (int): Total number of paragraphs processed
        total_files (int): Total number of files processed
    """
    print("\n" + "="*60)
    print("PARAGRAPH STATISTICS")
    print("="*60)
    print(f"Total files processed: {total_files}")
    print(f"Total paragraphs: {total_paragraphs:,}")
    print("="*60)
    
    # Table header
    print("┌──────────────┬─────────────────┬─────────────┐")
    print("│  Char Range  │      Count      │ Percentage  │")
    print("├──────────────┼─────────────────┼─────────────┤")
    
    # Table rows
    for range_key, count in stats.items():
        percentage = (count / total_paragraphs * 100) if total_paragraphs > 0 else 0
        print(f"│ {range_key:^12} │ {count:>15,} │ {percentage:>9.2f}% │")
    
    print("└──────────────┴─────────────────┴─────────────┘")
    
    # Summary line
    total_check = sum(stats.values())
    print(f"\nVerification: {total_check:,} paragraphs accounted for")
    print("="*60)


def main():
    """
    Main function to handle command line arguments and execute the analysis.
    """
    parser = argparse.ArgumentParser(
        description='Analyze paragraph statistics from page_*.txt files'
    )
    parser.add_argument(
        'base_dir',
        help='Base directory to search for page_*.txt files'
    )
    
    args = parser.parse_args()
    
    # Check if base directory exists
    if not os.path.isdir(args.base_dir):
        print(f"Error: Directory '{args.base_dir}' does not exist.")
        return 1
    
    try:
        # Record start time
        start_time = time.time()
        
        # Analyze paragraph statistics
        stats, total_paragraphs, total_files = analyze_paragraph_stats(args.base_dir)
        
        # Record end time and calculate duration
        end_time = time.time()
        duration = end_time - start_time
        
        # Print results
        print_statistics(stats, total_paragraphs, total_files)
        
        # Print timing information
        print(f"Total processing time: {duration:.2f} seconds")
        print(f"Average time per file: {duration/total_files:.4f} seconds" if total_files > 0 else "N/A")
        
        return 0
        
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
        return 1
    except Exception as e:
        print(f"Error during analysis: {e}")
        return 1


if __name__ == '__main__':
    exit(main())