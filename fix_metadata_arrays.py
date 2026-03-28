#!/usr/bin/env python3
"""
Fix metadata files to remove or convert array fields for AWS Bedrock compatibility.

AWS Bedrock Knowledge Base only accepts: strings, numbers, booleans
Arrays are NOT supported and cause "invalid metadata attributes" errors.
"""

import json
import os
import sys
from pathlib import Path


def fix_metadata_arrays(filepath: str) -> bool:
    """
    Fix metadata by converting arrays to strings or removing empty arrays.
    
    Args:
        filepath: Path to the metadata.json file
        
    Returns:
        True if file was updated, False if no changes needed
    """
    try:
        # Read the current file
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "metadataAttributes" not in data:
            print(f"✗ Missing metadataAttributes: {filepath}")
            return False
        
        metadata = data["metadataAttributes"]
        modified = False
        
        # Process each field
        for key, value in list(metadata.items()):
            if isinstance(value, list):
                if len(value) == 0:
                    # Remove empty arrays
                    del metadata[key]
                    print(f"  Removed empty array: {key}")
                    modified = True
                else:
                    # Convert non-empty arrays to comma-separated strings
                    metadata[key] = ", ".join(str(v) for v in value)
                    print(f"  Converted array to string: {key} = {metadata[key]}")
                    modified = True
        
        if not modified:
            print(f"✓ No arrays found: {filepath}")
            return False
        
        # Write back to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
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
        directories = ["transcripts"]
    
    print("AWS Bedrock Metadata Array Fixer")
    print("=" * 50)
    print("Removing/converting arrays (not supported by Bedrock)")
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
            if fix_metadata_arrays(str(filepath)):
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
        print("  Arrays have been removed or converted to strings.")
        print("  You can now re-upload them to S3 and sync your Knowledge Base.")
    else:
        print("\n✓ All metadata files are already in the correct format.")


if __name__ == "__main__":
    main()
