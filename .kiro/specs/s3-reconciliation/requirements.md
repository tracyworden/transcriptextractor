# Requirements Document

## Introduction

Enhance the YouTube transcript extraction pipeline (`extract_transcripts.py`) with two changes: (1) upgrade `processed.json` from a flat URL list to a richer format that maps each video URL to its output filename, and (2) add an S3 reconciliation step that runs before each extraction run, using the S3 bucket contents as the source of truth to bring `processed.json` into sync.

## Glossary

- **Pipeline**: The `extract_transcripts.py` script that extracts YouTube transcripts and uploads them to S3.
- **Processed_File**: The local `processed.json` file that tracks which videos have been processed.
- **S3_Bucket**: The AWS S3 bucket (`dev-machiningcloud-chatbot-kb`) storing transcript `.md` files and `.md.metadata.json` files under the `transcripts/` prefix.
- **Reconciler**: The new module/function responsible for listing S3 contents and synchronizing the Processed_File against S3.
- **Video_Record**: A JSON object containing a video URL and its corresponding output filename (e.g., `{"url": "https://...", "filename": "abc123.md"}`). The `"url"` field may be an empty string for entries created by reconciliation (files found in S3 that were not processed through the Pipeline).
- **Video_ID**: The 11-character YouTube video identifier extracted from a URL via regex `(?:v=|/)([a-zA-Z0-9_-]{11})(?:[&?]|$)`.

## Requirements

### Requirement 1: Enhanced Processed File Format

**User Story:** As a pipeline operator, I want `processed.json` to store both the video URL and the output filename for each processed video, so that I can trace which URL produced which file.

#### Acceptance Criteria

1. THE Processed_File SHALL store entries as a list of Video_Record objects under a `"processed"` key, where each Video_Record contains a `"url"` string and a `"filename"` string (e.g., `{"url": "https://www.youtube.com/watch?v=abc123", "filename": "abc123.md"}`).
2. WHEN the Pipeline writes a new entry to the Processed_File after successfully processing a video from YouTube, THE Pipeline SHALL write a Video_Record containing a non-empty video URL and the filename `"{Video_ID}.md"`. THE Pipeline SHALL reject any attempt to write a Video_Record with an empty URL during normal YouTube processing.
3. WHEN the Pipeline reads the Processed_File, THE Pipeline SHALL treat any URL present in a Video_Record as already processed (equivalent to the old `processed_urls` set membership check).
4. WHEN the Pipeline encounters a Processed_File in the legacy format (containing a `"processed_urls"` key with a flat list of URL strings), THE Pipeline SHALL migrate it to the new format by converting each URL to a Video_Record with the URL and a filename derived from the Video_ID extracted from that URL.
5. IF the Pipeline fails to extract a Video_ID from a legacy URL during migration, THEN THE Pipeline SHALL log a warning and skip that URL entry.

### Requirement 2: S3 Reconciliation Before Each Run

**User Story:** As a pipeline operator, I want the pipeline to reconcile `processed.json` against the actual S3 bucket contents before each run, so that S3 is the source of truth and my local state stays accurate.

#### Acceptance Criteria

1. WHEN S3 storage is configured (i.e., `--s3-bucket` is provided), THE Reconciler SHALL list all `.md` files in the S3_Bucket under the configured prefix before the Pipeline begins processing new videos.
2. THE Reconciler SHALL exclude `.md.metadata.json` files from the list of S3 transcript files (only `.md` files count as processed transcripts).
3. WHEN a `.md` file exists in S3 but has no corresponding Video_Record in the Processed_File, THE Reconciler SHALL add a Video_Record with the filename set to the S3 object key's basename and the URL set to an empty string. An empty URL is expected because the file may have been uploaded to S3 outside the Pipeline (e.g., manual upload) and does not necessarily originate from YouTube.
4. WHEN a Video_Record exists in the Processed_File but no corresponding `.md` file exists in S3, THE Reconciler SHALL remove that Video_Record from the Processed_File.
5. WHEN reconciliation adds or removes entries, THE Reconciler SHALL write the updated Processed_File to disk before the Pipeline proceeds with extraction.
6. WHEN reconciliation completes, THE Reconciler SHALL log the count of entries added and entries removed.
7. IF the Reconciler fails to list S3 contents (e.g., network error, permission denied), THEN THE Pipeline SHALL log the error and abort the run. There is no sense processing files that cannot be stored to S3.
8. IF S3 storage is not configured (no `--s3-bucket` provided), THE Pipeline SHALL log an error and abort the run. S3 is required because it is the source of truth for determining what has been processed and is the primary storage destination.

### Requirement 3: Reconciliation Uses Configured AWS Credentials

**User Story:** As a pipeline operator, I want the reconciliation step to use the same AWS profile and region settings I already pass via CLI, so that I don't need separate configuration.

#### Acceptance Criteria

1. THE Reconciler SHALL use the `--aws-profile` CLI argument value (if provided) when creating the boto3 session for listing S3 objects.
2. THE Reconciler SHALL use the `--s3-bucket` and `--s3-prefix` CLI argument values to determine which bucket and prefix to list.
3. WHEN `--aws-profile` is not provided, THE Reconciler SHALL use the default AWS credential chain (same behavior as the existing `upload_to_s3` function).

### Requirement 4: Incremental Processing Compatibility

**User Story:** As a pipeline operator, I want the normal incremental processing logic to work seamlessly with the new format, so that only unprocessed videos are extracted.

#### Acceptance Criteria

1. WHEN determining which videos to process, THE Pipeline SHALL consider a video URL as already processed if any Video_Record in the Processed_File has a matching `"url"` field.
2. WHEN determining which videos to process, THE Pipeline SHALL also consider a video as already processed if any Video_Record in the Processed_File has a `"filename"` matching `"{Video_ID}.md"` for that video's Video_ID, even if the URL field is empty (covers S3-reconciled entries).
3. THE Pipeline SHALL produce identical extraction results for videos that are not yet processed, regardless of whether the Processed_File was in legacy or new format.

### Requirement 5: Processed File Serialization Round-Trip

**User Story:** As a pipeline operator, I want the processed file to survive read-write cycles without data loss, so that repeated runs don't corrupt my state.

#### Acceptance Criteria

1. FOR ALL valid Processed_File contents, reading the file and writing it back without modification SHALL produce a file with equivalent JSON content (round-trip property).
2. FOR ALL valid legacy-format Processed_File contents, migrating to the new format and then reading the migrated file SHALL preserve all original URLs in the resulting Video_Record list.
