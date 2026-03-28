# Playlist Extraction Feature Added

## Problem
The `playlists` field in metadata was always empty because the script was fetching videos from the channel URL, which doesn't include playlist information in individual video metadata.

## Solution
Added comprehensive playlist extraction that:
1. Fetches all playlists from the channel
2. For each playlist, fetches all video IDs
3. Creates a mapping of video_id → playlist_names
4. Uses this mapping when extracting metadata for each video

## Changes Made

### New Function: `get_channel_playlists()`
Located after `get_channel_videos()` in `extract_transcripts.py`

**What it does:**
- Fetches all playlists from the channel's `/playlists` page
- For each playlist, fetches all videos in that playlist
- Builds a dictionary mapping video IDs to their playlist names
- Returns: `dict[video_id] = [playlist_name1, playlist_name2, ...]`

**Performance:**
- For @MachiningCloud: ~23 seconds to fetch 13 playlists and map 124 videos
- This is done once at the start, then reused for all videos

### Updated Function: `extract_metadata()`
**Changes:**
- Added optional parameter: `video_to_playlists: dict = None`
- Now looks up the video_id in the playlist mapping
- Populates the `playlists` field with actual playlist names

### Updated Function: `main()`
**Changes:**
- Added Step 2: Calls `get_channel_playlists(channel)` after fetching videos
- Passes the playlist mapping to `extract_metadata(video_url, video_to_playlists)`

### Bedrock Compatibility
The existing metadata conversion logic automatically handles playlists:
- **Empty playlists**: Removed from metadata (not included)
- **Single playlist**: Converted to string (e.g., `"Chuck's corner"`)
- **Multiple playlists**: Converted to comma-separated string (e.g., `"Playlist1, Playlist2"`)

## Test Results

### Test Video: Fe4aMP6oEAU ("The Probe that cried Wolf")
```json
{
  "metadataAttributes": {
    "video_id": "Fe4aMP6oEAU",
    "title": "The Probe that cried Wolf",
    "url": "https://www.youtube.com/watch?v=Fe4aMP6oEAU",
    "upload_date": "20260224",
    "playlists": "Chuck's corner",
    "transcript_language": "en",
    "processed_timestamp": "2026-02-25T00:32:12.995603Z"
  }
}
```

✅ Playlist information correctly extracted
✅ Bedrock-compatible format (string, not array)
✅ metadataAttributes wrapper present

### Channel Statistics
- **Total playlists found**: 13
- **Videos mapped to playlists**: 124 out of 137 total videos
- **Playlists include**:
  - Chuck's corner
  - Exploring MachiningCloud: Features and Functionality
  - Webinars
  - Walter
  - Mitsubishi
  - Why MachiningCloud?
  - NOVO-WIDIA
  - Digital Manufacturing
  - Technology Partners
  - Iscar
  - MachiningCloud App
  - NOVO - Kennametal
  - MachiningCloud Software Partners

## Usage

### Normal Operation
No changes needed! The script automatically fetches playlist information:

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

## Performance Impact

**Before:** ~2-3 seconds per video (transcript + metadata extraction)
**After:** 
- Initial playlist fetch: ~23 seconds (one-time at start)
- Per video: ~2-3 seconds (unchanged)

**Total for 137 videos:**
- Playlist fetch: 23 seconds
- Video processing: 274-411 seconds (137 × 2-3 seconds)
- **Total: ~5-7 minutes** (vs ~4.5-6.8 minutes before)

The overhead is minimal and only happens once at the start.

## Next Steps

1. **Test with new videos**: Run the script to process any new videos and verify playlist metadata is correct
2. **Update existing metadata** (optional): If you want to add playlist information to your existing 137 metadata files, we can create a migration script
3. **Upload to S3**: Once verified, upload the new metadata files with playlist information

## Files Modified
- ✅ `extract_transcripts.py` - Added playlist extraction
- ✅ `test_playlist_extraction.py` - Created test script

## Verification
Run the test script to verify everything works:
```bash
python test_playlist_extraction.py
```

This will:
1. Fetch playlists from @MachiningCloud
2. Extract metadata for a test video
3. Save and verify the metadata format
4. Confirm Bedrock compatibility
