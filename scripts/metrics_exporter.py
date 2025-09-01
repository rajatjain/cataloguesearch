#!/usr/bin/env python3
"""
Metrics Export Script

This script parses the metrics.log file and exports the data to a CSV format
suitable for Excel analysis.

Usage:
    python scripts/metrics_exporter.py [--input logs/metrics.log] [--output metrics_export.csv]
"""

import argparse
import csv
import os
import re
from datetime import datetime
from typing import List, Dict, Any


def parse_metrics_log(log_file_path: str) -> List[Dict[str, Any]]:
    """
    Parse the metrics log file and extract structured data.
    
    Expected log format:
    YYYY-MM-DD HH:MM:SS,client_ip,query,search_type,exact_match,categories,language,enable_reranking,page_size,page_number,latency_ms,total_results
    """
    metrics_data = []
    
    if not os.path.exists(log_file_path):
        print(f"Warning: Log file {log_file_path} not found.")
        return metrics_data
    
    with open(log_file_path, 'r', encoding='utf-8') as file:
        for line_num, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                # Split on comma, but be careful with nested data structures
                parts = line.split(',')
                
                if len(parts) < 12:  # Minimum expected fields
                    print(f"Warning: Line {line_num} has insufficient fields: {line}")
                    continue
                
                # Parse timestamp (first field)
                timestamp_str = parts[0]
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    print(f"Warning: Invalid timestamp format on line {line_num}: {timestamp_str}")
                    continue
                
                # Parse the remaining fields
                client_ip = parts[1]
                query = parts[2]
                search_type = parts[3]
                exact_match = parts[4].lower() == 'true'
                categories = parts[5]  # Keep as string for now
                language = parts[6]
                enable_reranking = parts[7].lower() == 'true'
                page_size = int(parts[8])
                page_number = int(parts[9])
                latency_ms = float(parts[10])
                total_results = int(parts[11])
                
                metrics_data.append({
                    'timestamp': timestamp,
                    'client_ip': client_ip,
                    'query': query,
                    'search_type': search_type,
                    'exact_match': exact_match,
                    'categories': categories,
                    'language': language,
                    'enable_reranking': enable_reranking,
                    'page_size': page_size,
                    'page_number': page_number,
                    'latency_ms': latency_ms,
                    'total_results': total_results,
                    'hour': timestamp.hour,
                    'day_of_week': timestamp.strftime('%A'),
                    'date': timestamp.date(),
                    'has_results': total_results > 0
                })
                
            except (ValueError, IndexError) as e:
                print(f"Warning: Error parsing line {line_num}: {e}")
                print(f"Line content: {line}")
                continue
    
    return metrics_data


def export_to_csv(metrics_data: List[Dict[str, Any]], output_file: str):
    """
    Export the metrics data to a CSV file.
    """
    if not metrics_data:
        print("No metrics data to export.")
        return
    
    # Define CSV headers
    headers = [
        'timestamp', 'date', 'hour', 'day_of_week',
        'client_ip', 'query', 'search_type', 'exact_match',
        'categories', 'language', 'enable_reranking',
        'page_size', 'page_number', 'latency_ms', 'total_results', 'has_results'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        
        for row in metrics_data:
            writer.writerow(row)
    
    print(f"Exported {len(metrics_data)} metrics records to {output_file}")


def print_summary(metrics_data: List[Dict[str, Any]]):
    """
    Print a summary of the metrics data.
    """
    if not metrics_data:
        return
    
    total_queries = len(metrics_data)
    lexical_queries = len([m for m in metrics_data if m['search_type'] == 'lexical'])
    vector_queries = len([m for m in metrics_data if m['search_type'] == 'vector'])
    zero_result_queries = len([m for m in metrics_data if m['total_results'] == 0])
    
    avg_latency = sum(m['latency_ms'] for m in metrics_data) / total_queries
    avg_results = sum(m['total_results'] for m in metrics_data) / total_queries
    
    unique_ips = len(set(m['client_ip'] for m in metrics_data))
    
    languages = {}
    for m in metrics_data:
        lang = m['language']
        languages[lang] = languages.get(lang, 0) + 1
    
    print("\n=== METRICS SUMMARY ===")
    print(f"Total queries: {total_queries}")
    print(f"Lexical queries: {lexical_queries} ({lexical_queries/total_queries*100:.1f}%)")
    print(f"Vector queries: {vector_queries} ({vector_queries/total_queries*100:.1f}%)")
    print(f"Zero result queries: {zero_result_queries} ({zero_result_queries/total_queries*100:.1f}%)")
    print(f"Average latency: {avg_latency:.1f} ms")
    print(f"Average results per query: {avg_results:.1f}")
    print(f"Unique IP addresses: {unique_ips}")
    print(f"Language distribution: {languages}")
    
    if metrics_data:
        date_range = f"{min(m['timestamp'] for m in metrics_data).date()} to {max(m['timestamp'] for m in metrics_data).date()}"
        print(f"Date range: {date_range}")


def main():
    parser = argparse.ArgumentParser(description="Export metrics log data to CSV format")
    parser.add_argument(
        '--input', '-i',
        default='logs/metrics.log',
        help='Input metrics log file path (default: logs/metrics.log)'
    )
    parser.add_argument(
        '--output', '-o',
        default='metrics_export.csv',
        help='Output CSV file path (default: metrics_export.csv)'
    )
    parser.add_argument(
        '--summary', '-s',
        action='store_true',
        help='Print summary statistics'
    )
    
    args = parser.parse_args()
    
    print(f"Parsing metrics from: {args.input}")
    metrics_data = parse_metrics_log(args.input)
    
    if args.summary:
        print_summary(metrics_data)
    
    if metrics_data:
        export_to_csv(metrics_data, args.output)
    else:
        print("No metrics data found to export.")


if __name__ == "__main__":
    main()