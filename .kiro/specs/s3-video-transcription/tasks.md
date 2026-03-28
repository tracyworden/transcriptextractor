# Implementation Plan: S3 Video Transcription

## Overview

Build `s3_video_transcribe.py` as a standalone Python CLI script (step 2 of the family video archive). Implement bottom-up: constants/CLI first, then pure utility functions, progress tracking, S3 scanner, transcription/metadata components, then the pipeline orchestrator. Whisper model loaded once at pipeline start and passed to `process_file`. All code in one file, all tests in `test_s3_video_transcribe.py`. Follows the same structural patterns as `s3_video_convert.py` but is a completely separate pipeline with no imports from existing modules.

## Tasks

- [x] 1. Create script skeleton with constants, imports, and CLI parsing
  - [x] 1.1 Create `s3_video_transcribe.py` with module docstring, imports (`argparse`, `boto3`, `json`, `logging`, `os`, `pathlib`, `re`, `subprocess`, `sys`, `whisper`, `datetime`), and constants (`DEFAULT_BUCKET`, `METADATA_DATE_FIELDS`, `DEFAULT_STATE_FILE`, `DEFAULT_TEMP_DIR`)
    - _Requirements: 1.1, 12.4_
  - [x] 1.2 Implement `parse_args() -> argparse.Namespace` with flags: `--dry-run`, `--limit N`, `--verbose`, `--bucket`, `--aws-profile`, `--state-file`, `--temp-dir`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_
  - [x] 1.3 Implement `main()` entry point that parses args, configures logging (DEBUG if `--verbose`, else INFO), adds a dedicated `FileHandler` for `transcription_errors.log` at ERROR level, and calls `run_pipeline`
    - Stub `run_pipeline` as a pass for now
    - _Requirements: 10.5, 10.6, 12.3_

- [x] 2. Implement pure utility functions and their tests
  - [x] 2.1 Implement `is_mp4_file(key: str) -> bool` — returns True if the S3 key's file extension, lowercased, is `.mp4`
    - _Requirements: 1.2, 1.3_
  - [ ]* 2.2 Write property test for `is_mp4_file`
    - **Property 1: MP4 extension classification is case-insensitive**
    - **Validates: Requirements 1.2, 1.3**
  - [x] 2.3 Implement `derive_output_keys(s3_key: str) -> tuple[str, str]` — given an MP4 S3 key, returns `(transcript_key, metadata_key)` by replacing `.mp4` with `.md` and `.md.metadata.json`, preserving the folder prefix
    - _Requirements: 3.1, 4.1, 4.2_
  - [ ]* 2.4 Write property test for `derive_output_keys`
    - **Property 2: Output key derivation from source key**
    - **Validates: Requirements 3.1, 4.1, 4.2**
  - [x] 2.5 Implement `humanize_title(filename_stem: str) -> str` — replaces underscores with spaces, no other transformations
    - _Requirements: 3.3, 4.6_
  - [ ]* 2.6 Write property test for `humanize_title`
    - **Property 4: Title humanization**
    - **Validates: Requirements 3.3, 4.6**
  - [x] 2.7 Implement `format_transcript(title: str, transcript: str) -> str` — returns `# {title}\n\n{transcript}\n`
    - _Requirements: 3.2_
  - [ ]* 2.8 Write property test for `format_transcript`
    - **Property 3: Transcript file formatting**
    - **Validates: Requirements 2.3, 3.2**

- [x] 3. Implement progress tracking
  - [x] 3.1 Implement `load_progress(state_file: str) -> dict` — loads JSON state file, returns `{"completed": []}` if missing or corrupted
    - _Requirements: 7.2, 7.3_
  - [x] 3.2 Implement `save_progress(state_file: str, progress: dict) -> None` — writes progress dict as JSON with 2-space indentation
    - _Requirements: 7.1, 7.4, 7.5_
  - [ ]* 3.3 Write property test for progress state round-trip
    - **Property 7: Progress state round-trip**
    - **Validates: Requirements 7.1, 7.5**

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement S3 scanner
  - [x] 5.1 Implement `scan_source_bucket(s3_client, bucket: str) -> list[dict]` — paginated `list_objects_v2`, filters via `is_mp4_file`, returns list of `{"key": str, "last_modified": datetime}` dicts capturing `LastModified` from each S3 object, logs total MP4 count and skipped count at INFO
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 6.1_

- [x] 6. Implement date extraction and transcription components
  - [x] 6.1 Implement `extract_video_date(local_path: str) -> str` — runs `ffprobe -v quiet -print_format json -show_format`, checks `format.tags` for `METADATA_DATE_FIELDS` in priority order, returns full date string or empty string on failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [ ]* 6.2 Write property test for `extract_video_date` with mocked ffprobe output
    - **Property 6: Date extraction respects field priority**
    - **Validates: Requirements 5.2, 5.3, 5.4**
  - [x] 6.3 Implement `transcribe_video(local_path: str, model) -> str` — runs Whisper transcription on local MP4 using the pre-loaded model, returns transcript text or empty string
    - _Requirements: 2.1, 2.2_
  - [x] 6.4 Implement `generate_metadata(s3_key: str, bucket: str, video_date: str, upload_date: str, transcript_language: str) -> dict` — builds Bedrock KB-compatible metadata dict wrapped in `metadataAttributes`, derives `video_id` and `title` from filename stem, sets `url` to `s3://{bucket}/{key}`, sets `playlists` and `description` to empty strings, sets `processed_timestamp` to current UTC ISO 8601, all values must be strings (no arrays/dicts)
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12_
  - [ ]* 6.5 Write property test for `generate_metadata`
    - **Property 5: Metadata generation structure and content**
    - **Validates: Requirements 4.3, 4.4, 4.5, 4.6, 4.7, 4.12, 6.2**

- [x] 7. Implement S3 I/O functions
  - [x] 7.1 Implement `download_from_s3(s3_client, bucket: str, key: str, local_path: str) -> None` — downloads S3 object to local file using `download_file`
    - _Requirements: 11.1_
  - [x] 7.2 Implement `upload_to_s3(s3_client, bucket: str, key: str, content: str, content_type: str) -> None` — uploads string content to S3 using `put_object`, encodes as UTF-8
    - _Requirements: 3.4, 4.14_

- [x] 8. Implement pipeline orchestrator
  - [x] 8.1 Implement `process_file(s3_key: str, last_modified: datetime, s3_client, bucket: str, temp_dir: str, model) -> dict | None` — download MP4 → ffprobe date → transcribe → generate metadata → upload `.md` (content type `text/markdown`) → upload `.md.metadata.json` (content type `application/json`) → cleanup in `finally` block. Returns progress record (`source_key`, `transcript_key`, `metadata_key`, `timestamp`) on success, `None` on failure. Logs warning and returns `None` for empty transcripts. Logs transcription duration.
    - _Requirements: 2.3, 2.4, 2.5, 3.1, 3.4, 4.1, 4.2, 4.14, 5.1, 6.2, 10.2, 11.1, 11.2, 11.3, 11.4, 11.5_
  - [x] 8.2 Implement `run_pipeline(args: argparse.Namespace) -> None` — loads Whisper "base" model once before the loop, scans bucket, loads progress, filters already-processed keys, handles `--dry-run` mode (scan/report/exit), applies `--limit`, iterates calling `process_file`, saves state after each success, logs `[N/Total]` progress, logs final summary (total found, transcribed, skipped, failed). Logs batch summary when limit reached.
    - _Requirements: 2.1, 7.2, 7.4, 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 10.1, 10.3, 10.4_
  - [ ]* 8.3 Write property test for already-processed filtering
    - **Property 8: Already-processed files are filtered out**
    - **Validates: Requirements 7.2**
  - [ ]* 8.4 Write property test for batch limit
    - **Property 9: Batch limit bounds actual processing count**
    - **Validates: Requirements 8.1, 8.2, 8.4**
  - [ ]* 8.5 Write property test for failed files never recorded
    - **Property 10: Failed files are never recorded as completed**
    - **Validates: Requirements 11.5**

- [x] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate the 10 correctness properties from the design document
- All code goes in `s3_video_transcribe.py`, all tests in `test_s3_video_transcribe.py`
- Python 3.13.12, openai-whisper, ffprobe 8.1, boto3 1.42.56, hypothesis 6.151.9 — all already in venv
- Whisper model loaded ONCE at pipeline start in `run_pipeline`, passed to `process_file`
- Scanner returns dicts with `LastModified` (not just keys) for `upload_date` metadata
- `upload_to_s3` uploads string content directly via `put_object` (not file upload)
- Dedicated error log file: `transcription_errors.log` for ERROR-level messages
