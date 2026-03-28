# Implementation Plan: S3 Video Convert & Migrate

## Overview

Build `s3_video_convert.py` as a standalone Python CLI script. Implement bottom-up: pure utility functions first (testable in isolation), then I/O components, then the pipeline orchestrator, then wire CLI. Property-based tests validate each layer before moving up. All code in one file, all tests in `test_s3_video_convert.py`.

## Tasks

- [x] 1. Create script skeleton with constants, imports, and CLI parsing
  - [x] 1.1 Create `s3_video_convert.py` with module docstring, imports (`argparse`, `boto3`, `json`, `logging`, `os`, `pathlib`, `re`, `subprocess`, `sys`, `tempfile`, `datetime`), and constants (`VIDEO_EXTENSIONS`, `SOURCE_BUCKET`, `DEST_BUCKET`, `METADATA_YEAR_FIELDS`, `DEFAULT_STATE_FILE`, `DEFAULT_TEMP_DIR`)
    - _Requirements: 1.3, 2.1_
  - [x] 1.2 Implement `parse_args() -> argparse.Namespace` with flags: `--dry-run`, `--limit N`, `--state-file`, `--temp-dir`, `--source-bucket`, `--dest-bucket`, `--aws-profile`, `--verbose`
    - _Requirements: 9.1, 10.1_
  - [x] 1.3 Implement `main()` entry point that parses args, configures logging (DEBUG if `--verbose`, else INFO), and calls `run_pipeline`
    - Stub `run_pipeline` as a pass for now
    - _Requirements: 7.1_

- [x] 2. Implement pure utility functions and their tests
  - [x] 2.1 Implement `is_video_file(key: str) -> bool` — case-insensitive extension check against `VIDEO_EXTENSIONS`
    - _Requirements: 1.2, 1.3_
  - [ ]* 2.2 Write property test for `is_video_file`
    - **Property 1: Video file classification is extension-based and case-insensitive**
    - **Validates: Requirements 1.2, 1.3**
  - [x] 2.3 Implement `resolve_dest_key(year: str | None, filename_stem: str, existing_dest_keys: set[str]) -> str` — builds `{year}/{stem}.mp4` or `unknown-year/{stem}.mp4`, appends `_1`, `_2` etc. on collision, logs warning on collision
    - _Requirements: 2.5, 4.2, 4.3, 8.1, 8.2_
  - [ ]* 2.4 Write property test for `resolve_dest_key` — destination key construction
    - **Property 3: Destination key construction**
    - **Validates: Requirements 2.5, 4.2, 4.3**
  - [ ]* 2.5 Write property test for `resolve_dest_key` — collision resolution uniqueness
    - **Property 7: Filename collision resolution produces unique keys**
    - **Validates: Requirements 8.1**

- [x] 3. Implement progress tracking
  - [x] 3.1 Implement `load_progress(state_file: str) -> dict` — loads JSON state file, returns empty `{"completed": []}` if missing or corrupted
    - _Requirements: 6.2, 6.3_
  - [x] 3.2 Implement `save_progress(state_file: str, progress: dict) -> None` — writes progress dict as JSON
    - _Requirements: 6.1, 6.4, 6.5_
  - [ ]* 3.3 Write property test for progress round-trip
    - **Property 5: Progress state round-trip**
    - **Validates: Requirements 6.1, 6.5**

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement S3 scanner and metadata extractor
  - [x] 5.1 Implement `scan_source_bucket(s3_client, bucket: str) -> list[str]` — paginated `list_objects_v2`, classifies via `is_video_file`, logs skipped files at DEBUG, logs totals at INFO
    - _Requirements: 1.1, 1.2, 1.4, 1.5_
  - [x] 5.2 Implement `extract_year_from_metadata(local_path: str) -> str | None` — runs `ffprobe -v quiet -print_format json -show_format`, parses JSON, checks `METADATA_YEAR_FIELDS` in priority order, extracts 4-digit year via regex `r'\b(19|20)\d{2}\b'`, returns `None` on failure
    - _Requirements: 4.1, 4.4_
  - [ ]* 5.3 Write property test for `extract_year_from_metadata` with mocked ffprobe output
    - **Property 4: Metadata year extraction respects field priority**
    - **Validates: Requirements 4.4**

- [x] 6. Implement file I/O components
  - [x] 6.1 Implement `download_from_s3(s3_client, bucket: str, key: str, local_path: str) -> None` — downloads S3 object to local file
    - _Requirements: 3.1_
  - [x] 6.2 Implement `upload_to_s3(s3_client, bucket: str, key: str, local_path: str) -> None` — uploads local file to S3
    - _Requirements: 3.2_
  - [x] 6.3 Implement `convert_to_mp4(input_path: str, output_path: str) -> bool` — runs ffmpeg with `-c:v libx264 -c:a aac -movflags +faststart`, returns `True`/`False`, logs stderr on failure
    - _Requirements: 2.1, 2.3_
  - [ ]* 6.4 Write property test for MP4 passthrough decision logic
    - **Property 2: MP4 files never trigger conversion**
    - **Validates: Requirements 2.2**

- [x] 7. Implement pipeline orchestrator
  - [x] 7.1 Implement `process_file(source_key, s3_source, s3_dest, temp_dir, dest_bucket, existing_dest_keys) -> dict | None` — download → probe → convert (if needed) → upload → cleanup in `finally` block. Returns progress record on success, `None` on failure. Logs errors with source key per Req 2.4.
    - _Requirements: 2.1, 2.2, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 5.1, 5.2_
  - [x] 7.2 Implement `run_pipeline(args: argparse.Namespace) -> None` — scans bucket, loads progress, filters already-processed keys, applies `--limit`, iterates calling `process_file`, saves state after each success, logs `[N/Total]` progress, logs final summary (found/converted/copied/skipped/failed). In `--dry-run` mode: scan, classify, log planned actions, report totals, exit without side effects.
    - _Requirements: 6.2, 6.4, 7.1, 7.2, 7.3, 7.4, 9.1, 9.2, 10.1, 10.2, 10.3, 10.4_
  - [ ]* 7.3 Write property test for already-processed filtering
    - **Property 6: Already-processed files are filtered out**
    - **Validates: Requirements 6.2**
  - [ ]* 7.4 Write property test for batch limit
    - **Property 8: Batch limit bounds actual processing count**
    - **Validates: Requirements 10.1, 10.2, 10.4**

- [x] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate the 8 correctness properties from the design document
- All code goes in `s3_video_convert.py`, all tests in `test_s3_video_convert.py`
- Python 3.13, ffmpeg/ffprobe 8.1, boto3 1.42.56, hypothesis 6.151.9 — all already in venv
