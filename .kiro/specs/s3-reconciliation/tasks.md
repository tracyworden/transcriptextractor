# Implementation Plan: S3 Reconciliation

## Overview

Upgrade `processed.json` from a flat URL list to a record-based format and add S3 reconciliation. All code changes in `extract_transcripts.py`, all tests in `test_s3_reconciliation.py`. Ordered: data model → load/save → reconciliation → main() integration → CLI → tests.

## Tasks

- [x] 1. Implement new data model and save/load functions
  - [x] 1.1 Create `save_processed_records` function
    - Add `save_processed_records(filepath: str, records: list[dict]) -> None` that writes `{"processed": [records...]}` JSON to disk with 2-space indent
    - _Requirements: 1.1, 5.1_

  - [x] 1.2 Rewrite `load_processed_urls` as `load_processed_records`
    - Rename `load_processed_urls` to `load_processed_records(filepath: str) -> Tuple[Set[str], Set[str], list[dict]]`
    - Return `(url_set, filename_set, records_list)`
    - If file contains `"processed_urls"` key (legacy format): migrate each URL to a Video_Record by extracting Video_ID via regex `(?:v=|/)([a-zA-Z0-9_-]{11})(?:[&?]|$)`, log warning and skip URLs where extraction fails, write migrated format to disk immediately via `save_processed_records`
    - If file contains `"processed"` key (new format): load directly
    - If file doesn't exist or JSON is corrupted: return empty sets and empty list
    - _Requirements: 1.1, 1.3, 1.4, 1.5_

  - [x] 1.3 Rewrite `update_processed_urls` as `update_processed_records`
    - Rename `update_processed_urls` to `update_processed_records(filepath: str, video_url: str, video_id: str) -> None`
    - Append `{"url": video_url, "filename": "{video_id}.md"}` record
    - Raise `ValueError` if `video_url` is empty string (enforces non-empty URL during YouTube processing)
    - Use `save_processed_records` to write back
    - _Requirements: 1.2_

- [x] 2. Checkpoint - Verify data model functions
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement S3 listing and reconciliation
  - [x] 3.1 Create `list_s3_files` function
    - Add `list_s3_files(s3_config: S3Config) -> Set[str]` that lists all `.md` files under the configured prefix in S3
    - Use `list_objects_v2` with pagination (`NextContinuationToken` / `IsTruncated`)
    - Exclude `.md.metadata.json` files (only `.md` basenames)
    - Create boto3 session using `s3_config.aws_profile` if provided, otherwise default credential chain
    - Raise exception on any S3 error (network, permissions, etc.)
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3_

  - [x] 3.2 Create `reconcile_processed_file` function
    - Add `reconcile_processed_file(processed_file_path: str, s3_config: S3Config) -> None`
    - Call `load_processed_records` to get current records
    - Call `list_s3_files` to get S3 filenames
    - Compute diff: add records for S3 filenames not in any record's `filename` (with `url=""`), remove records whose `filename` is not in S3
    - Write updated records via `save_processed_records`
    - Log counts of added/removed entries
    - _Requirements: 2.3, 2.4, 2.5, 2.6_

- [x] 4. Checkpoint - Verify reconciliation logic
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Integrate into main() and CLI
  - [x] 5.1 Modify `main()` startup sequence
    - After parsing args, check that `s3_config` is not None; if None, log error and `sys.exit(1)`
    - Call `load_processed_records` (handles legacy migration)
    - Call `reconcile_processed_file` wrapped in try/except; any failure logs error and aborts via `sys.exit(1)`
    - Re-load records after reconciliation to get updated state
    - Filter unprocessed videos using both `url_set` and `filename_set` (video is processed if URL in `url_set` OR `{Video_ID}.md` in `filename_set`)
    - Replace all calls to `update_processed_urls` with `update_processed_records` in the extraction loop
    - _Requirements: 2.7, 4.1, 4.2, 4.3_

  - [x] 5.2 Update CLI `__main__` block validation
    - Change validation: instead of requiring "at least one storage destination," require `--s3-bucket` to be provided
    - If `--s3-bucket` is not provided, log error and exit with message that S3 is required
    - `--no-local-save` remains valid (S3-only mode)
    - _Requirements: 2.8_

- [x] 6. Checkpoint - Verify end-to-end integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Write property-based and unit tests
  - [x] 7.1 Set up test file with hypothesis generators
    - Create `test_s3_reconciliation.py` with imports and shared hypothesis strategies: `video_id()` (11-char `[a-zA-Z0-9_-]`), `youtube_url()`, `video_record()`, `s3_key_set()`
    - _Requirements: all_

  - [ ]* 7.2 Write property test: Processed file round trip
    - **Property 1: Processed file round trip**
    - For any valid list of Video_Records, `save_processed_records` then `load_processed_records` produces equivalent records
    - **Validates: Requirements 1.1, 5.1**

  - [ ]* 7.3 Write property test: Legacy migration preserves all valid URLs
    - **Property 2: Legacy migration preserves all valid URLs**
    - For any list of valid YouTube URLs, creating a legacy file and loading via `load_processed_records` yields one record per URL with correct `url` and `filename`
    - **Validates: Requirements 1.4, 5.2**

  - [ ]* 7.4 Write property test: update_processed_records enforces non-empty URL
    - **Property 3: update_processed_records enforces non-empty URL and correct filename**
    - Non-empty URL appends correct record; empty URL raises `ValueError`
    - **Validates: Requirements 1.2**

  - [ ]* 7.5 Write property test: URL membership identifies processed videos
    - **Property 4: URL membership identifies processed videos**
    - A video URL is "already processed" iff it appears in at least one record's `url` field
    - **Validates: Requirements 1.3, 4.1**

  - [ ]* 7.6 Write property test: Filename membership identifies processed videos
    - **Property 5: Filename membership identifies processed videos**
    - A video is "already processed" if any record's `filename` equals `"{Video_ID}.md"`, even with empty `url`
    - **Validates: Requirements 4.2**

  - [ ]* 7.7 Write property test: S3 file listing returns only .md basenames
    - **Property 6: S3 file listing returns only .md basenames**
    - Mock boto3; for any set of S3 keys, `list_s3_files` returns exactly basenames ending `.md` but not `.md.metadata.json`
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 7.8 Write property test: Reconciliation aligns processed records with S3
    - **Property 7: Reconciliation aligns processed records with S3**
    - Mock boto3; after reconciliation, records' filename set equals S3 filename set; retained records keep original URL; new records have `url=""`
    - **Validates: Requirements 2.3, 2.4**

  - [ ]* 7.9 Write unit tests for edge cases
    - Legacy migration with invalid URLs (skipped with warning)
    - Empty processed file returns empty sets
    - S3 abort on missing `--s3-bucket` arg
    - S3 abort on connection failure propagates exception
    - Reconciliation logging shows correct added/removed counts
    - Pagination: `list_s3_files` handles multi-page S3 responses
    - _Requirements: 1.5, 2.6, 2.7, 2.8_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` with `@given` decorators, mocking boto3 for S3 interactions
- All code changes are in `extract_transcripts.py`; all tests in `test_s3_reconciliation.py`
