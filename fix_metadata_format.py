#!/usr/bin/env python3
"""
Fix metadata files to wrap content in metadataAttributes for AWS Bedrock Knowledge Base.

This script updates all .metadata.json files to use the correct format:
{
  "metadataAttributes": {
    "key1": "value1",
    ...
  }
}
"""

import json
import os
import sys
from pathlib import Path


def fix_metadata_file(filepath: str) -> bool:
    """
    Fix a single metadata file by wrapping content in metadataAttributes.
    
    Args:
        filepath: Path to the metadata.json file
        
    Returns:
        True if file was updated, False if already in correct format or error
    """
    try:
        # Read the current file
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if already in correct format
        if "metadataAttributes" in data:
            print(f"✓ Already correct: {filepath}")
            return False
        
        # Wrap in metadataAttributes
        fixed_data = {
            "metadataAttributes": data
        }
        
        # Write back to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(fixed_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Fixed: {filepath}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"✗ JSON error in {filepath}: {e}")
        return False
    except Exception as e:
        print(f"✗ Error processing {filepath}: {e}")
        return False


def main():
    """Main function to process all metadata files."""
    # Get directories to process from command line or use defaults
    if len(sys.argv) > 1:
        directories = sys.argv[1:]
    else:
        directories = ["transcripts", "transcriptorig", "transcripts - Copy"]
    
    print("AWS Bedrock Metadata Format Fixer")
    print("=" * 50)
    print(f"Processing directories: {', '.join(directories)}\n")
    
    total_files = 0
    fixed_files = 0
    
    for directory in directories:
        if not os.path.exists(directory):
            print(f"⚠ Directory not found: {directory}")
            continue
        
        print(f"\nProcessing directory: {directory}")
        print("-" * 50)
        
        # Find all .metadata.json files
        metadata_files = list(Path(directory).glob("*.metadata.json"))
        
        if not metadata_files:
            print(f"No metadata files found in {directory}")
            continue
        
        print(f"Found {len(metadata_files)} metadata files\n")
        
        for filepath in metadata_files:
            total_files += 1
            if fix_metadata_file(str(filepath)):
                fixed_files += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Files updated: {fixed_files}")
    print(f"  Files already correct: {total_files - fixed_files}")
    print("=" * 50)
    
    if fixed_files > 0:
        print("\n✓ Metadata files have been updated!")
        print("  You can now re-upload them to S3 and sync your Knowledge Base.")
    else:
        print("\n✓ All metadata files are already in the correct format.")


if __name__ == "__main__":
    main()
