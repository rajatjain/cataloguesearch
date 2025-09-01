#!/usr/bin/env python3
"""
Metrics Export Script

This script parses the metrics.log file and exports the data to a CSV format
suitable for Excel analysis. Optionally includes IP geolocation data.

Usage:
    # Basic export
    python scripts/metrics_exporter.py
    
    # With geolocation lookups
    python scripts/metrics_exporter.py --geo
    
    # With summary statistics
    python scripts/metrics_exporter.py --summary --geo
    
    # Custom files
    python scripts/metrics_exporter.py -i logs/metrics.log -o my_export.csv --geo
"""

import argparse
import csv
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests


class IPGeolocator:
    """
    IP Geolocation lookup class with caching and rate limiting.
    Uses ip-api.com free service (1000 requests/hour).
    """
    
    def __init__(self):
        self.cache = {}
        self.last_request_time = 0
        self.request_delay = 0.1  # 100ms between requests to be respectful
    
    def get_location(self, ip_address: str) -> Dict[str, Optional[str]]:
        """
        Get geolocation information for an IP address.
        
        Returns:
            Dictionary with location fields or None values if lookup fails.
        """
        # Default response
        default_location = {
            'country': None,
            'country_code': None,
            'region': None,
            'city': None,
            'latitude': None,
            'longitude': None
        }
        
        # Handle local/private IPs
        if self._is_private_ip(ip_address):
            return {
                'country': 'Local/Private',
                'country_code': 'LOCAL',
                'region': 'Private Network',
                'city': 'Local',
                'latitude': None,
                'longitude': None
            }
        
        # Check cache first
        if ip_address in self.cache:
            return self.cache[ip_address]
        
        # Rate limiting
        current_time = time.time()
        if current_time - self.last_request_time < self.request_delay:
            time.sleep(self.request_delay - (current_time - self.last_request_time))
        
        try:
            # Make API request
            response = requests.get(
                f'http://ip-api.com/json/{ip_address}',
                timeout=5
            )
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    location = {
                        'country': data.get('country'),
                        'country_code': data.get('countryCode'),
                        'region': data.get('regionName'),
                        'city': data.get('city'),
                        'latitude': data.get('lat'),
                        'longitude': data.get('lon')
                    }
                    
                    # Cache the result
                    self.cache[ip_address] = location
                    return location
                
        except requests.RequestException as e:
            print(f"Warning: Failed to lookup IP {ip_address}: {e}")
        
        # Cache the default result to avoid repeated failed lookups
        self.cache[ip_address] = default_location
        return default_location
    
    def _is_private_ip(self, ip_address: str) -> bool:
        """Check if IP address is private/local."""
        if ip_address in ['127.0.0.1', 'localhost', '::1', 'unknown']:
            return True
        
        try:
            # Check for private IP ranges
            parts = [int(x) for x in ip_address.split('.')]
            if len(parts) != 4:
                return True  # Invalid IP, treat as private
            
            # Private IP ranges
            if parts[0] == 10:
                return True
            if parts[0] == 172 and 16 <= parts[1] <= 31:
                return True
            if parts[0] == 192 and parts[1] == 168:
                return True
                
        except (ValueError, IndexError):
            return True  # Invalid IP format, treat as private
        
        return False


def enrich_with_geolocation(metrics_data: List[Dict[str, Any]], enable_geo: bool = False) -> List[Dict[str, Any]]:
    """
    Enrich metrics data with geolocation information.
    
    Args:
        metrics_data: List of metrics records
        enable_geo: Whether to perform IP geolocation lookups
        
    Returns:
        Enhanced metrics data with location fields
    """
    if not enable_geo:
        # Add empty geo fields
        for record in metrics_data:
            record.update({
                'country': None,
                'country_code': None,
                'region': None,
                'city': None,
                'latitude': None,
                'longitude': None
            })
        return metrics_data
    
    print("Performing IP geolocation lookups...")
    print("This may take a while for large datasets due to rate limiting.")
    
    geolocator = IPGeolocator()
    unique_ips = set(record['client_ip'] for record in metrics_data)
    
    print(f"Looking up {len(unique_ips)} unique IP addresses...")
    
    for i, record in enumerate(metrics_data, 1):
        if i % 100 == 0:
            print(f"Processing record {i}/{len(metrics_data)}...")
        
        location = geolocator.get_location(record['client_ip'])
        record.update(location)
    
    print("Geolocation lookup complete!")
    return metrics_data


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
    
    # Define CSV headers (including geolocation fields)
    headers = [
        'timestamp', 'date', 'hour', 'day_of_week',
        'client_ip', 'country', 'country_code', 'region', 'city', 'latitude', 'longitude',
        'query', 'search_type', 'exact_match',
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
    
    # Calculate queries per day breakdown
    queries_per_day = {}
    for m in metrics_data:
        date = m['date']
        queries_per_day[date] = queries_per_day.get(date, 0) + 1
    
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
        
        # Print queries per day breakdown
        print("\n=== QUERIES PER DAY BREAKDOWN ===")
        for date in sorted(queries_per_day.keys()):
            print(f"{date}: {queries_per_day[date]} queries")


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
    parser.add_argument(
        '--geo', '-g',
        action='store_true',
        help='Perform IP geolocation lookups (requires internet connection)'
    )
    
    args = parser.parse_args()
    
    print(f"Parsing metrics from: {args.input}")
    metrics_data = parse_metrics_log(args.input)
    
    if metrics_data:
        # Enrich with geolocation data if requested
        metrics_data = enrich_with_geolocation(metrics_data, enable_geo=args.geo)
        
        if args.summary:
            print_summary(metrics_data)
        
        export_to_csv(metrics_data, args.output)
    else:
        print("No metrics data found to export.")


if __name__ == "__main__":
    main()