# AWS Bedrock Knowledge Base Metadata Fix

## Problem
AWS Bedrock Knowledge Base was rejecting metadata files with errors:
1. "No metadata was provided in metadata file"
2. "Ignored files due to invalid metadata attributes"

## Root Causes

### Issue 1: Missing metadataAttributes Wrapper
The metadata files were in the wrong format. Bedrock requires metadata to be wrapped in a `metadataAttributes` object.

### Issue 2: Array Values Not Supported
AWS Bedrock Knowledge Base only accepts: **strings, numbers, and booleans**. Arrays/lists are NOT supported.

## Incorrect Format (Old)
```json
{
  "video_id": "4zJDg0q2RLQ",
  "title": "The Air Hose Surprise",
  "playlists": [],
  ...
}
```

## Correct Format (New)
```json
{
  "metadataAttributes": {
    "video_id": "4zJDg0q2RLQ",
    "title": "The Air Hose Surprise"
  }
}
```

Note: The `playlists` field is removed when empty, or converted to a comma-separated string when it has values.

## Solution Applied

### 1. Fixed Existing Files - Step 1: Add metadataAttributes Wrapper
Created and ran `fix_metadata_format.py` to wrap all metadata in `metadataAttributes` object.

**Results:**
- ✅ 137 files updated successfully

### 2. Fixed Existing Files - Step 2: Remove Arrays
Created and ran `fix_metadata_arrays.py` to remove/convert array fields.

**Results:**
- ✅ 137 files updated successfully
- ✅ Empty `playlists` arrays removed
- ✅ Non-empty arrays converted to comma-separated strings

### 3. Updated Script for Future Files
Modified `extract_transcripts.py` to generate metadata files in the correct format going forward.

**Changes in `save_metadata_with_storage()` function:**
1. Convert arrays to Bedrock-compatible format:
   - Empty arrays: Skip entirely
   - Non-empty arrays: Convert to comma-separated strings
2. Wrap metadata in `metadataAttributes` object
3. Serialize to JSON

## Next Steps

### 1. Re-upload Fixed Metadata Files to S3
You need to upload the corrected metadata files to your S3 bucket:

```bash
# Upload all fixed metadata files
aws s3 sync transcripts/ s3://dev-machiningcloud-chatbot-kb/transcripts/ \
  --exclude "*" \
  --include "*.metadata.json" \
  --profile your-profile-name
```

Or use the script with S3 upload:
```bash
python extract_transcripts.py \
  --s3-bucket dev-machiningcloud-chatbot-kb \
  --s3-prefix transcripts/ \
  --no-local-save \
  --aws-profile your-profile-name
```

### 2. Configure Knowledge Base Data Source
Make sure your Bedrock Knowledge Base data source is configured to index the metadata fields:

```json
{
  "s3Configuration": {
    "bucketName": "dev-machiningcloud-chatbot-kb",
    "inclusionPrefixes": ["transcripts/"],
    "metadata": {
      "fields": [
        "video_id",
        "title",
        "url",
        "upload_date",
        "transcript_language",
        "processed_timestamp"
      ]
    }
  }
}
```

Note: Do NOT include "playlists" in the fields list since it's been removed.

### 3. Sync Knowledge Base
After uploading the fixed metadata files, sync your Knowledge Base:
- Go to AWS Bedrock Console
- Navigate to your Knowledge Base
- Click "Sync" on the data source
- Wait for sync to complete

## Verification
After syncing, test the Knowledge Base with metadata filtering:
```json
{
  "filter": {
    "equals": {
      "key": "video_id",
      "value": "4zJDg0q2RLQ"
    }
  }
}
```

## Files Modified
1. ✅ `fix_metadata_format.py` - Created (adds metadataAttributes wrapper)
2. ✅ `fix_metadata_arrays.py` - Created (removes/converts arrays)
3. ✅ `extract_transcripts.py` - Updated (permanent fix for new files)
4. ✅ `transcripts/*.metadata.json` - All 137 files fixed

## Key Learnings

### AWS Bedrock Metadata Constraints
- ✅ Must be wrapped in `metadataAttributes` object
- ✅ Only supports: strings, numbers, booleans
- ❌ Does NOT support: arrays, objects, null values
- ❌ Empty arrays cause "invalid metadata attributes" error

### Best Practices
1. Remove optional fields that are empty arrays
2. Convert non-empty arrays to comma-separated strings
3. Keep metadata simple and flat
4. Test with a small batch before full sync

## References
- [AWS Bedrock Knowledge Base Metadata Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-metadata.html)
- [Metadata Filtering Guide](https://aws.amazon.com/blogs/machine-learning/access-control-for-vector-stores-using-metadata-filtering-with-knowledge-bases-for-amazon-bedrock/)
