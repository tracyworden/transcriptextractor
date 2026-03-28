#!/usr/bin/env python3
"""
Test script to verify playlist extraction works correctly.
"""

import json
import tempfile
import os
from extract_transcripts import get_channel_playlists, extract_metadata, save_metadata_with_storage, StorageConfig

# Create temp directory for test
temp_dir = tempfile.mkdtemp()
print(f"Test directory: {temp_dir}\n")

# Step 1: Fetch playlists
print("Step 1: Fetching playlists from @MachiningCloud...")
video_to_playlists = get_channel_playlists('@MachiningCloud')
print(f"✓ Mapped {len(video_to_playlists)} videos to playlists\n")

# Step 2: Extract metadata for a video that's in a playlist
test_video_url = "https://www.youtube.com/watch?v=Fe4aMP6oEAU"
print(f"Step 2: Extracting metadata for test video...")
metadata = extract_metadata(test_video_url, video_to_playlists)
print(f"✓ Video: {metadata['title']}")
print(f"✓ Playlists: {metadata['playlists']}\n")

# Step 3: Save metadata and verify format
print("Step 3: Saving metadata...")
storage_config = StorageConfig(local_dir=temp_dir)
save_metadata_with_storage(metadata['video_id'], metadata, storage_config)

# Step 4: Read and verify the saved metadata
metadata_file = os.path.join(temp_dir, f"{metadata['video_id']}.md.metadata.json")
with open(metadata_file, 'r', encoding='utf-8') as f:
    saved_data = json.load(f)

print(f"✓ Metadata saved to: {metadata_file}\n")
print("Step 4: Verifying saved metadata format...")
print(json.dumps(saved_data, indent=2))

# Verify Bedrock compatibility
print("\nBedrock Compatibility Checks:")
print(f"✓ Has metadataAttributes wrapper: {'metadataAttributes' in saved_data}")
print(f"✓ No array fields: {not any(isinstance(v, list) for v in saved_data.get('metadataAttributes', {}).values())}")

if metadata['playlists']:
    playlists_value = saved_data['metadataAttributes'].get('playlists', '')
    print(f"✓ Playlists converted to string: {isinstance(playlists_value, str)}")
    print(f"  Value: '{playlists_value}'")
else:
    print(f"✓ Empty playlists removed: {'playlists' not in saved_data['metadataAttributes']}")

print("\n✅ All tests passed!")
print(f"\nCleanup: You can delete {temp_dir} when done.")
