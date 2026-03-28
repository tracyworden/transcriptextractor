#!/usr/bin/env python3
"""
Remove duplicate sentences from transcript markdown files.
"""

import os
import re
import argparse
from pathlib import Path


def remove_duplicate_sentences(text):
    """
    Remove consecutive duplicate sentences from text.
    
    Args:
        text: The text content to deduplicate
        
    Returns:
        Text with consecutive duplicate sentences removed
    """
    # Split into sentences (simple approach - split on . ! ?)
    # Keep the punctuation with the sentence
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Remove consecutive duplicates
    deduplicated = []
    prev_sentence = None
    
    for sentence in sentences:
        # Normalize whitespace for comparison
        normalized = ' '.join(sentence.split())
        prev_normalized = ' '.join(prev_sentence.split()) if prev_sentence else None
        
        if normalized != prev_normalized:
            deduplicated.append(sentence)
            prev_sentence = sentence
    
    return ' '.join(deduplicated)


def process_markdown_file(filepath, dry_run=False):
    """
    Process a single markdown file to remove duplicate sentences.
    
    Args:
        filepath: Path to the markdown file
        dry_run: If True, only show what would be changed without modifying files
        
    Returns:
        Tuple of (original_length, new_length, changed)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split into header and body
        lines = content.split('\n', 1)
        if len(lines) == 2 and lines[0].startswith('#'):
            header = lines[0]
            body = lines[1]
        else:
            header = ''
            body = content
        
        # Remove duplicate sentences from body
        original_body = body
        deduplicated_body = remove_duplicate_sentences(body)
        
        # Reconstruct content
        if header:
            new_content = f"{header}\n{deduplicated_body}"
        else:
            new_content = deduplicated_body
        
        changed = original_body != deduplicated_body
        
        if changed and not dry_run:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
        
        return len(content), len(new_content), changed
        
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return 0, 0, False


def main():
    parser = argparse.ArgumentParser(
        description='Remove duplicate sentences from transcript markdown files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deduplicate_transcripts.py
  python deduplicate_transcripts.py --directory ./transcripts
  python deduplicate_transcripts.py --dry-run
        """
    )
    
    parser.add_argument(
        '--directory',
        type=str,
        default='.',
        help='Directory containing markdown files (default: current directory)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    
    args = parser.parse_args()
    
    # Find all .md files (excluding .metadata.json files)
    directory = Path(args.directory)
    md_files = [f for f in directory.glob('*.md') if not f.name.endswith('.metadata.json')]
    
    if not md_files:
        print(f"No markdown files found in {directory}")
        return
    
    print(f"Found {len(md_files)} markdown file(s)")
    if args.dry_run:
        print("DRY RUN MODE - No files will be modified\n")
    
    total_original = 0
    total_new = 0
    changed_count = 0
    
    for md_file in sorted(md_files):
        original_len, new_len, changed = process_markdown_file(md_file, args.dry_run)
        
        if changed:
            changed_count += 1
            reduction = original_len - new_len
            percent = (reduction / original_len * 100) if original_len > 0 else 0
            status = "[DRY RUN]" if args.dry_run else "[MODIFIED]"
            print(f"{status} {md_file.name}: {original_len} → {new_len} chars ({reduction} removed, {percent:.1f}%)")
        
        total_original += original_len
        total_new += new_len
    
    print(f"\nSummary:")
    print(f"  Files processed: {len(md_files)}")
    print(f"  Files changed: {changed_count}")
    print(f"  Total size: {total_original} → {total_new} chars")
    if total_original > 0:
        total_reduction = total_original - total_new
        total_percent = (total_reduction / total_original * 100)
        print(f"  Total reduction: {total_reduction} chars ({total_percent:.1f}%)")
    
    if args.dry_run and changed_count > 0:
        print(f"\nRun without --dry-run to apply changes")


if __name__ == "__main__":
    main()
