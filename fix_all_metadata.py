#!/usr/bin/env python3
"""
Complete metadata fix for AWS Bedrock Knowledge Base compatibility.

This script applies both fixes:
1. Wraps metadata in metadataAttributes object
2. Removes/converts array fields (not supported by Bedrock)
"""

import json
import os
import sys
from pathlib import Path


def fix_metadata_file(filepath: str) -> tuple[bool, str]:
    """
    Fix a single metadata file for Bedrock compatibility.
    
    Args:
        filepath: Path to the metadata.json file
        
    Returns:
        Tuple of (was_modified, status_message)
    """
    try:
        # Read the current file
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        modified = False
        changes = []
        
        # Fix 1: Ensure metadataAttributes wrapper exists
        if "metadataAttributes" not in data:
            data = {"metadataAttributes": data}
            changes.append("Added metadataAttributes wrapper")
            modified = True
        
        metadata = data["metadataAttributes"]
        
        # Fix 2: Remove/convert arrays (Bedrock doesn't support them)
        for key, value in list(metadata.items()):
            if isinstance(value, list):
                if len(value) == 0:
                    del metadata[key]
                    changes.append(f"Removed empty array: {key}")
                    modified = True
                else:
                    metadata[key] = ", ".join(str(v) for v in value)
                    changes.append(f"Converted array to string: {key}")
                    modified = True
        
        if not modified:
            return False, f"✓ Already correct: {filepath}"
        
        # Write back to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        status = f"✓ Fixed: {filepath}\n  " + "\n  ".join(changes)
        return True, status
        
    except json.JSONDecodeError as e:
        return False, f"✗ JSON error in {filepath}: {e}"
    except Exception as e:
        return False, f"✗ Error processing {filepath}: {e}"


def main():
    """Main function to process all metadata files."""
    # Get directories to process from command line or use defaults
    if len(sys.argv) > 1:
        directories = sys.argv[1:]
    else:
        directories = ["transcripts"]
    
    print("AWS Bedrock Metadata Complete Fix")
    print("=" * 60)
    print("Applying all fixes for Bedrock Knowledge Base compatibility:")
    print("  1. Adding metadataAttributes wrapper")
    print("  2. Removing/converting arrays")
    print(f"\nProcessing directories: {', '.join(directories)}\n")
    
    total_files = 0
    fixed_files = 0
    
    for directory in directories:
        if not os.path.exists(directory):
            print(f"⚠ Directory not found: {directory}")
            continue
        
        print(f"\nProcessing directory: {directory}")
        print("-" * 60)
        
        # Find all .metadata.json files
        metadata_files = list(Path(directory).glob("*.metadata.json"))
        
        if not metadata_files:
            print(f"No metadata files found in {directory}")
            continue
        
        print(f"Found {len(metadata_files)} metadata files\n")
        
        for filepath in metadata_files:
            total_files += 1
            was_modified, status = fix_metadata_file(str(filepath))
            print(status)
            if was_modified:
                fixed_files += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Files updated: {fixed_files}")
    print(f"  Files already correct: {total_files - fixed_files}")
    print("=" * 60)
    
    if fixed_files > 0:
        print("\n✓ Metadata files have been updated!")
        print("  All files are now Bedrock Knowledge Base compatible.")
        print("\nNext steps:")
        print("  1. Re-upload metadata files to S3")
        print("  2. Sync your Knowledge Base")
        print("  3. Test with metadata filtering")
    else:
        print("\n✓ All metadata files are already in the correct format.")


if __name__ == "__main__":
    main()
