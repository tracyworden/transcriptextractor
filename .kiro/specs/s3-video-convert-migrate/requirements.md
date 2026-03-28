# Requirements Document

## Introduction

This feature implements a batch video conversion and migration pipeline. The pipeline scans an existing S3 archive bucket (`s3://wor-family-pics/`) containing mixed media (photos, videos, system files), identifies all video files, converts non-MP4 videos to MP4 (H.264/AAC) using ffmpeg, and uploads the resulting MP4 files to a clean destination bucket (`s3://mw-family-videos/`). Videos are organized into year-based folders when metadata allows. The source bucket is treated as read-only. Processing happens locally: download → convert → upload. The pipeline runs in a local Python venv (Python 3.13, ffmpeg/ffprobe 8.1, boto3). Docker containerization is out of scope for now but may be considered in the future.

## Glossary

- **Pipeline**: The Python script that orchestrates scanning, downloading, converting, and uploading video files
- **Source_Bucket**: The S3 bucket `s3://wor-family-pics/` containing the original mixed media archive (read-only)
- **Destination_Bucket**: The S3 bucket `s3://mw-family-videos/` where converted MP4 files are uploaded
- **Scanner**: The component that lists all objects in Source_Bucket recursively and classifies them as video or non-video
- **Converter**: The component that uses ffmpeg to transcode non-MP4 video files to MP4 (H.264 video, AAC audio)
- **Uploader**: The component that uploads MP4 files to Destination_Bucket
- **Progress_Tracker**: The component that persists processing state to enable resumption after interruption
- **Video_File**: A file with one of the recognized video extensions: `.mp4`, `.mov`, `.mts`, `.m2ts`, `.avi`, `.wmv`, `.mpg`, `.mpeg`, `.flv`, `.mkv`, `.3gp`, `.webm`, `.vob`, `.ts`
- **Non_Video_File**: A file that does not have a recognized video extension (e.g., `.jpg`, `.png`, `.zip`, `.db`)
- **Year_Folder**: A folder in Destination_Bucket named with a four-digit year (e.g., `2015/`) used to organize videos by creation year
- **Metadata_Extractor**: The component that uses ffprobe to read video file metadata and extract the creation year
- **Batch_Limit**: The optional `--limit N` CLI argument that caps the number of Video_File objects processed (downloaded/converted/uploaded) in a single run

## Requirements

### Requirement 1: Recursive S3 Bucket Scanning

**User Story:** As a user, I want the pipeline to scan the entire source bucket recursively, so that all video files across all folders are discovered.

#### Acceptance Criteria

1. WHEN the Pipeline is started, THE Scanner SHALL list all objects in Source_Bucket recursively, including all subdirectories
2. THE Scanner SHALL classify each object as a Video_File or Non_Video_File based on file extension (case-insensitive matching)
3. THE Scanner SHALL recognize the following extensions as Video_File: `.mp4`, `.mov`, `.mts`, `.m2ts`, `.avi`, `.wmv`, `.mpg`, `.mpeg`, `.flv`, `.mkv`, `.3gp`, `.webm`, `.vob`, `.ts`
4. WHEN a Non_Video_File is encountered, THE Scanner SHALL skip the file and log its key at DEBUG level
5. THE Scanner SHALL report the total count of Video_File objects found and the total count of Non_Video_File objects skipped

### Requirement 2: Video Conversion to MP4

**User Story:** As a user, I want all non-MP4 videos converted to MP4 format using H.264/AAC, so that I have a uniform collection of modern video files.

#### Acceptance Criteria

1. WHEN a Video_File has an extension other than `.mp4`, THE Converter SHALL transcode the file to MP4 format using H.264 video codec and AAC audio codec via ffmpeg
2. WHEN a Video_File already has the `.mp4` extension, THE Pipeline SHALL copy the file as-is without re-encoding
3. THE Converter SHALL preserve the original video resolution and frame rate during transcoding
4. IF ffmpeg returns a non-zero exit code during conversion, THEN THE Pipeline SHALL log the error with the source S3 key and continue processing remaining files
5. THE Converter SHALL name the output file using the original filename stem with the `.mp4` extension

### Requirement 3: Local Processing Workflow

**User Story:** As a user, I want files processed locally (download → convert → upload), so that I can use my local ffmpeg installation and verify files.

#### Acceptance Criteria

1. THE Pipeline SHALL download each Video_File from Source_Bucket to a local temporary directory before processing
2. WHEN conversion is complete for a file, THE Uploader SHALL upload the resulting MP4 file to Destination_Bucket
3. WHEN upload is confirmed successful, THE Pipeline SHALL delete the local temporary files (source download and converted output) for that file
4. THE Pipeline SHALL process files one at a time to limit local disk usage

### Requirement 4: Year-Based Organization in Destination

**User Story:** As a user, I want videos organized into year folders in the destination bucket, so that I can browse videos by year.

#### Acceptance Criteria

1. WHEN a Video_File is processed, THE Metadata_Extractor SHALL attempt to read the creation year from the video file metadata using ffprobe
2. WHEN a valid four-digit year is extracted from metadata, THE Uploader SHALL upload the MP4 file under the path `{year}/{filename}.mp4` in Destination_Bucket
3. IF the Metadata_Extractor cannot determine a creation year from metadata, THEN THE Uploader SHALL upload the MP4 file under the path `unknown-year/{filename}.mp4` in Destination_Bucket
4. THE Metadata_Extractor SHALL check the following metadata fields in order: `creation_time`, `date`, `encoded_date`

### Requirement 5: Source Bucket Protection

**User Story:** As a user, I want the source archive bucket to remain completely untouched, so that original files are preserved.

#### Acceptance Criteria

1. THE Pipeline SHALL perform only read operations (GetObject, ListObjectsV2) against Source_Bucket
2. THE Pipeline SHALL perform no write, delete, or modify operations against Source_Bucket

### Requirement 6: Progress Tracking and Resumption

**User Story:** As a user, I want the pipeline to track progress and resume from where it left off if interrupted, so that I do not reprocess files unnecessarily.

#### Acceptance Criteria

1. THE Progress_Tracker SHALL persist a record of each successfully uploaded file to a local JSON state file
2. WHEN the Pipeline starts, THE Progress_Tracker SHALL load the state file and skip any Video_File that has already been successfully uploaded
3. IF the state file does not exist, THEN THE Progress_Tracker SHALL treat all files as unprocessed
4. THE Progress_Tracker SHALL write the state file after each successful upload to minimize data loss on interruption
5. THE Progress_Tracker SHALL record the source S3 key, destination S3 key, and processing timestamp for each completed file

### Requirement 7: Logging and Progress Reporting

**User Story:** As a user, I want clear logging and progress reporting, so that I can monitor the pipeline and diagnose issues.

#### Acceptance Criteria

1. THE Pipeline SHALL log each file being processed, including the source S3 key and the action taken (copy or convert)
2. THE Pipeline SHALL log a running progress count in the format `[N/Total]` for each file processed
3. WHEN the Pipeline completes, THE Pipeline SHALL log a summary including: total files found, files converted, files copied, files skipped (already processed), and files failed
4. THE Pipeline SHALL log all errors with sufficient detail to identify the failing file and the cause of failure

### Requirement 8: Filename Collision Handling

**User Story:** As a user, I want the pipeline to handle duplicate filenames across different source folders, so that no files are silently overwritten in the destination.

#### Acceptance Criteria

1. WHEN two or more Video_File objects from different source folders produce the same destination filename within the same year folder, THE Pipeline SHALL append a numeric suffix (e.g., `_1`, `_2`) to the duplicate filenames before uploading
2. THE Pipeline SHALL log a warning when a filename collision is detected

### Requirement 9: Dry Run Mode

**User Story:** As a user, I want a dry-run mode, so that I can preview what the pipeline will do before it processes any files.

#### Acceptance Criteria

1. WHERE the `--dry-run` flag is provided, THE Pipeline SHALL scan and classify all files, log the planned actions for each Video_File, and exit without downloading, converting, or uploading any files
2. WHERE the `--dry-run` flag is provided, THE Pipeline SHALL report the total number of files that would be converted, copied, and skipped

### Requirement 10: Batch Size Limiting

**User Story:** As a user, I want to limit how many files are processed in a single run using a `--limit N` flag, so that I can process the large bucket (~20k objects, ~576 GB) in manageable batches.

#### Acceptance Criteria

1. WHERE the `--limit N` flag is provided, THE Pipeline SHALL stop processing after N Video_File objects have been downloaded, converted, and uploaded successfully
2. THE Pipeline SHALL apply the limit only to files that are actually processed (downloaded/converted/uploaded), not to files that are scanned or skipped by the Progress_Tracker
3. WHEN the limit is reached, THE Pipeline SHALL log a summary of the batch and exit cleanly
4. IF the `--limit` flag is not provided, THEN THE Pipeline SHALL process all remaining unprocessed Video_File objects
