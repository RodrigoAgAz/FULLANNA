#!/usr/bin/env python
"""
This script searches for the text "Async chat view works" in all Python files in the current directory and subdirectories.
"""
import os
import re
import sys

def search_file(file_path, pattern):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if pattern in content:
                print(f"FOUND in {file_path}")
                # Find the line containing the pattern
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if pattern in line:
                        print(f"  Line {i+1}: {line.strip()}")
    except:
        pass  # Ignore files that can't be read

def search_directory(directory, pattern):
    print(f"Searching in {directory}...")
    for root, dirs, files in os.walk(directory):
        for file in files:
            # Search in Python, JavaScript, HTML, and JSON files
            if file.endswith(('.py', '.js', '.html', '.json', '.txt')):
                file_path = os.path.join(root, file)
                search_file(file_path, pattern)

if __name__ == "__main__":
    current_dir = os.getcwd()
    patterns = [
        "Async chat view works",
        "\"message\": \"Async chat view works\"",
        "JsonResponse({\"message\": \"Async chat view works\"})",
        "message.*Async.*works"
    ]
    
    for pattern in patterns:
        print(f"\nSearching for '{pattern}' in {current_dir} and subdirectories...")
        search_directory(current_dir, pattern)
    
    print("\nSearch completed.")