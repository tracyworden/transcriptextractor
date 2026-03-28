# Playlist Filtering Feature

## Overview
Added the ability to ignore videos that are exclusively in certain playlists. This prevents unwanted content from being processed and added to the knowledge base.

## Configuration

### Ignored Playlists List
Located at the top of `extract_transcripts.py`:

```python
# Configuration: Playlists to ignore (videos exclusively in these playlists will be skipped)
IGNORED_PLAYLISTS = [
    "NOVO-WIDIA",
    "NOVO - Kennametal"
]
```

### How to Update
To add or remove ignored playlists, simply edit the `IGNORED_PLAYLISTS` list:

```python
IGNORED_PLAYLISTS = [
    "NOVO-WIDIA",
    "NOVO - Kennametal",
    "Your New Playlist Name"  # Add new playlists here
]
```

## Filtering Logic

### Videos That Are Skipped
- Videos that are **ONLY** in ignored playlists
- Example: Video in `["NOVO-WIDIA"]` → **SKIPPED**
- Example: Video in `["NOVO-WIDIA", "NOVO - Kennametal"]` → **SKIPPED**

### Videos That Are Processed
- Videos in at least one non-ignored playlist
- Example: Video in `["Chuck's corner"]` → **PROCESSED**
- Example: Video in `["Chuck's corner", "NOVO-WIDIA"]` → **PROCESSED** (has non-ignored playlist)
- Videos not in any playlist → **PROCESSED**

### Key Principle
**A video is only skipped if ALL of its playlists are in the ignored list.**

## Implementation Details

### New Function: `should_process_video()`
```python
def should_process_video(video_id: str, video_to_playlists: dict) -> bool:
    """
    Determines if a video should be processed based on its playlists.
    
    Returns:
        True if video should be processed, False if it should be skipped
    """
```

**Logic:**
1. If video has no playlists → Process
2. If video is in any non-ignored playlist → Process
3. If video is ONLY in ignored playlists → Skip

### Integration in main()
The filtering happens after transcript extraction but before saving:

```python
# Extract transcript
video_id, transcript_text, language_code = extract_transcript(video_url, use_whisper_fallback)

# Check if video should be processed
if not should_process_video(video_id, video_to_playlists):
    skipped_count += 1
    update_processed_urls(processed_file, video_url)  # Mark as processed
    continue

# Continue with metadata extraction and saving...
```

### Why Extract Transcript First?
We extract the transcript before checking playlists because:
1. The video_id is needed for the playlist lookup
2. Transcript extraction is fast (~2-3 seconds)
3. Skipped videos are still marked as "processed" to avoid re-checking them

## Statistics

### Summary Output
The script now reports skipped videos in the summary:

```
Extraction complete!
Total videos in channel: 137
Previously processed: 0
Newly processed: 120
Skipped (ignored playlists): 15
Failed: 2
Total processed: 137
```

### Logging
When a video is skipped, you'll see:
```
INFO - Skipping video abc123 - only in ignored playlists: NOVO-WIDIA, NOVO - Kennametal
```

## Testing

### Test Script
Run `test_playlist_filtering.py` to verify the filtering logic:

```bash
python test_playlist_filtering.py
```

**Test cases:**
1. ✓ Video in non-ignored playlist → Process
2. ✓ Video ONLY in ignored playlist → Skip
3. ✓ Video in multiple ignored playlists → Skip
4. ✓ Video in both ignored and non-ignored → Process
5. ✓ Video with no playlists → Process

All tests pass! ✅

## Expected Impact

### For @MachiningCloud Channel
- **Total videos**: 137
- **Videos in playlists**: 124
- **Videos in NOVO-WIDIA**: ~8-10 (estimated)
- **Videos in NOVO - Kennametal**: ~5-7 (estimated)
- **Videos exclusively in ignored playlists**: ~10-15 (estimated)

**Result:** Approximately 120-127 videos will be processed, 10-15 will be skipped.

## Usage

### Normal Operation
No changes needed! The filtering happens automatically:

```bash
python extract_transcripts.py
```

### With S3 Upload
```bash
python extract_transcripts.py \
  --s3-bucket dev-machiningcloud-chatbot-kb \
  --s3-prefix transcripts/ \
  --aws-profile your-profile
```

## Maintenance

### Adding New Ignored Playlists
1. Open `extract_transcripts.py`
2. Find the `IGNORED_PLAYLISTS` list (near the top, after dataclass definitions)
3. Add the playlist name exactly as it appears in YouTube
4. Save the file

### Removing Ignored Playlists
1. Open `extract_transcripts.py`
2. Find the `IGNORED_PLAYLISTS` list
3. Remove or comment out the playlist name
4. Save the file

### Finding Playlist Names
To see all available playlists:
```python
from extract_transcripts import get_channel_playlists
playlists = get_channel_playlists('@MachiningCloud')
print(set(p for playlists_list in playlists.values() for p in playlists_list))
```

## Files Modified
- ✅ `extract_transcripts.py` - Added `IGNORED_PLAYLISTS` constant and `should_process_video()` function
- ✅ `test_playlist_filtering.py` - Created test script
- ✅ `PLAYLIST_FILTERING.md` - This documentation

## Benefits
1. **Cleaner Knowledge Base**: Only relevant content is included
2. **Faster Processing**: Skipped videos don't go through metadata extraction and storage
3. **Easy Maintenance**: Simple list-based configuration
4. **Flexible**: Videos in multiple playlists are handled intelligently
5. **Auditable**: Skipped videos are logged and counted in statistics
