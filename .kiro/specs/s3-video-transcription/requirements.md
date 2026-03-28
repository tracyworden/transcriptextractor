# Requirements Document

## Introduction

This feature implements a batch video transcription pipeline (step 2 of the family video archive project). The pipeline scans the destination bucket (`s3://mw-family-videos-1/`) containing ~5,621 MP4 files organized by year folders (e.g., `2015/clip.mp4`, `unknown-year/clip.mp4`), downloads each video, runs Whisper (openai-whisper, "base" model) to generate a transcript, produces a Bedrock Knowledge Base-compatible metadata file, and uploads both the transcript (`.md`) and metadata (`.md.metadata.json`) back to the same S3 folder alongside the original MP4. The pipeline is designed to run on an EC2 g4dn.xlarge instance (T4 GPU) in us-east-1 for GPU-accelerated transcription, but can also run locally for testing. Progress is tracked in a local JSON state file (same pattern as the step 1 conversion pipeline) to support resumption after interruption.

## Glossary

- **Pipeline**: The Python script (`s3_video_transcribe.py`) that orchestrates scanning, downloading, transcribing, and uploading transcript and metadata files
- **Video_Bucket**: The S3 bucket `s3://mw-family-videos-1/` containing MP4 files organized by year folders — serves as both the source of videos and the destination for transcripts
- **Scanner**: The component that lists all `.mp4` objects in Video_Bucket recursively
- **Transcriber**: The component that uses the Whisper "base" model to generate a text transcript from an MP4 file's audio
- **Metadata_Generator**: The component that produces a Bedrock KB-compatible JSON metadata file for each transcribed video
- **Uploader**: The component that uploads transcript and metadata files to Video_Bucket in the same folder as the source MP4
- **Progress_Tracker**: The component that persists processing state to a local JSON state file to enable resumption after interruption
- **Transcript_File**: A markdown file named `{filename_stem}.md` containing a title header and the Whisper-generated transcript text
- **Metadata_File**: A JSON file named `{filename_stem}.md.metadata.json` containing video metadata wrapped in `metadataAttributes` for Bedrock KB compatibility
- **Filename_Stem**: The MP4 filename without extension (e.g., `VID_20150313_085854_924` from `VID_20150313_085854_924.mp4`), used as the `video_id`
- **Video_Date**: The full creation date extracted from the video file's metadata via ffprobe, or an empty string if unavailable
- **Batch_Limit**: The optional `--limit N` CLI argument that caps the number of videos transcribed in a single run
- **Date_Extractor**: The component that uses ffprobe to read the video file's embedded metadata and extract a full creation date

## Requirements

### Requirement 1: S3 Bucket Scanning for MP4 Files

**User Story:** As a user, I want the pipeline to scan the video bucket for all MP4 files, so that every video is discovered for transcription.

#### Acceptance Criteria

1. WHEN the Pipeline is started, THE Scanner SHALL list all objects in Video_Bucket recursively using paginated S3 API calls
2. THE Scanner SHALL identify objects with the `.mp4` extension (case-insensitive) as candidates for transcription
3. THE Scanner SHALL skip any object that does not have the `.mp4` extension
4. THE Scanner SHALL report the total count of MP4 files found in Video_Bucket

### Requirement 2: Whisper Transcription

**User Story:** As a user, I want each video transcribed using the Whisper "base" model, so that I get text transcripts of all family videos for search via Bedrock Knowledge Base.

#### Acceptance Criteria

1. WHEN an MP4 file is downloaded, THE Transcriber SHALL load the Whisper "base" model and transcribe the audio
2. THE Transcriber SHALL use GPU acceleration when a CUDA-capable GPU is available
3. WHEN Whisper produces a non-empty transcript, THE Pipeline SHALL save the transcript as a Transcript_File
4. IF Whisper produces an empty transcript for a video, THEN THE Pipeline SHALL log a warning with the S3 key and skip the file without uploading a Transcript_File or Metadata_File
5. IF Whisper transcription fails with an error, THEN THE Pipeline SHALL log the error with the S3 key and continue processing remaining files

### Requirement 3: Transcript File Format

**User Story:** As a user, I want transcripts saved as markdown files with a title header, so that Bedrock Knowledge Base can ingest them as documents.

#### Acceptance Criteria

1. THE Pipeline SHALL save each transcript as `{filename_stem}.md` in the same S3 folder as the source MP4
2. THE Transcript_File SHALL contain a markdown title header followed by the transcript text in the format: `# {title}\n\n{transcript}\n`
3. THE Pipeline SHALL derive the title by humanizing the Filename_Stem (replacing underscores with spaces)
4. THE Transcript_File SHALL be uploaded with content type `text/markdown`

### Requirement 4: Metadata Generation in Bedrock KB Format

**User Story:** As a user, I want a metadata JSON file generated for each transcript, so that Bedrock Knowledge Base can filter and search videos by attributes.

#### Acceptance Criteria

1. THE Metadata_Generator SHALL produce a Metadata_File named `{filename_stem}.md.metadata.json` for each transcribed video
2. THE Metadata_File SHALL be uploaded to the same S3 folder as the source MP4 and the Transcript_File
3. THE Metadata_File SHALL wrap all attributes inside a top-level `metadataAttributes` object
4. THE Metadata_File SHALL contain the following attributes: `video_id`, `title`, `url`, `video_date`, `upload_date`, `playlists`, `transcript_language`, `processed_timestamp`, `description`
5. THE Metadata_Generator SHALL set `video_id` to the Filename_Stem
6. THE Metadata_Generator SHALL set `title` to the humanized Filename_Stem
7. THE Metadata_Generator SHALL set `url` to the full S3 URI of the source MP4 (e.g., `s3://mw-family-videos-1/2015/clip.mp4`)
8. THE Metadata_Generator SHALL set `transcript_language` to `en`
9. THE Metadata_Generator SHALL set `processed_timestamp` to the current time in ISO 8601 format
10. THE Metadata_Generator SHALL set `playlists` to an empty string
11. THE Metadata_Generator SHALL set `description` to an empty string
12. THE Metadata_File SHALL contain only string, number, or boolean values — arrays are not permitted per Bedrock KB constraints
13. THE Metadata_File SHALL be serialized as JSON with 2-space indentation
14. THE Metadata_File SHALL be uploaded with content type `application/json`

### Requirement 5: Video Date Extraction

**User Story:** As a user, I want the creation date extracted from each video's embedded metadata, so that the metadata file contains accurate date information.

#### Acceptance Criteria

1. WHEN an MP4 file is downloaded, THE Date_Extractor SHALL run ffprobe to read the video file's format-level metadata tags
2. THE Date_Extractor SHALL check the following metadata fields in order: `creation_time`, `date`, `encoded_date`
3. WHEN a valid date is found in metadata, THE Metadata_Generator SHALL set `video_date` to the full date string
4. IF no valid date is found in any metadata field, THEN THE Metadata_Generator SHALL set `video_date` to an empty string

### Requirement 6: Upload Date from S3 Object Metadata

**User Story:** As a user, I want the upload date captured from the S3 object's LastModified timestamp, so that I know when each video was originally uploaded.

#### Acceptance Criteria

1. WHEN scanning MP4 files, THE Scanner SHALL capture the `LastModified` timestamp from the S3 object metadata for each file
2. THE Metadata_Generator SHALL set `upload_date` to the S3 object's `LastModified` date formatted as an ISO 8601 string
3. IF the `LastModified` timestamp is not available, THEN THE Metadata_Generator SHALL set `upload_date` to the processing timestamp

### Requirement 7: Progress Tracking and Resumption

**User Story:** As a user, I want the pipeline to track progress and resume from where it left off if interrupted, so that I do not re-transcribe files unnecessarily.

#### Acceptance Criteria

1. THE Progress_Tracker SHALL persist a record of each successfully transcribed and uploaded file to a local JSON state file
2. WHEN the Pipeline starts, THE Progress_Tracker SHALL load the state file and skip any MP4 file that has already been successfully processed
3. IF the state file does not exist, THEN THE Progress_Tracker SHALL treat all files as unprocessed
4. THE Progress_Tracker SHALL write the state file after each successful upload pair (Transcript_File and Metadata_File) to minimize data loss on interruption
5. THE Progress_Tracker SHALL record the source S3 key, transcript S3 key, metadata S3 key, and processing timestamp for each completed file

### Requirement 8: Batch Size Limiting

**User Story:** As a user, I want to limit how many files are transcribed in a single run using `--limit N`, so that I can process the ~5,621 videos in manageable batches and control costs.

#### Acceptance Criteria

1. WHERE the `--limit N` flag is provided, THE Pipeline SHALL stop processing after N MP4 files have been successfully transcribed and uploaded
2. THE Pipeline SHALL apply the limit only to files that are actually processed (transcribed and uploaded), not to files that are scanned or skipped
3. WHEN the limit is reached, THE Pipeline SHALL log a summary of the batch and exit cleanly
4. IF the `--limit` flag is not provided, THEN THE Pipeline SHALL process all remaining untranscribed MP4 files

### Requirement 9: Dry Run Mode

**User Story:** As a user, I want a dry-run mode, so that I can preview what the pipeline will do before it transcribes any files.

#### Acceptance Criteria

1. WHERE the `--dry-run` flag is provided, THE Pipeline SHALL scan and list all MP4 files that would be transcribed, and exit without downloading, transcribing, or uploading any files
2. WHERE the `--dry-run` flag is provided, THE Pipeline SHALL report the total number of files that would be transcribed and the number that would be skipped (already processed)

### Requirement 10: Logging and Progress Reporting

**User Story:** As a user, I want clear logging and progress reporting, so that I can monitor the pipeline during long transcription runs on EC2.

#### Acceptance Criteria

1. THE Pipeline SHALL log each file being processed, including the S3 key and a running progress count in the format `[N/Total]`
2. THE Pipeline SHALL log the Whisper transcription duration for each file
3. WHEN the Pipeline completes, THE Pipeline SHALL log a summary including: total MP4 files found, files transcribed, files skipped (already processed), and files failed
4. THE Pipeline SHALL log all errors with sufficient detail to identify the failing file and the cause of failure
5. WHERE the `--verbose` flag is provided, THE Pipeline SHALL set the log level to DEBUG
6. THE Pipeline SHALL write all file processing failures to a dedicated error log file (`transcription_errors.log`) containing the S3 key and the error details, so that failures can be reviewed after a run

### Requirement 11: Error Handling and Fault Tolerance

**User Story:** As a user, I want the pipeline to skip failed files and continue processing, so that one bad video does not halt the entire batch.

#### Acceptance Criteria

1. IF a download from S3 fails for a file, THEN THE Pipeline SHALL log the error and continue to the next file
2. IF Whisper transcription fails for a file, THEN THE Pipeline SHALL log the error and continue to the next file
3. IF an upload to S3 fails for a file, THEN THE Pipeline SHALL log the error and continue to the next file
4. THE Pipeline SHALL clean up local temporary files (downloaded MP4) after each file is processed, regardless of success or failure
5. THE Pipeline SHALL NOT record a failed file as completed in the Progress_Tracker

### Requirement 12: CLI Interface

**User Story:** As a user, I want a CLI with relevant flags, so that I can configure the pipeline for different environments (EC2 production vs. local testing).

#### Acceptance Criteria

1. THE Pipeline SHALL accept a `--dry-run` flag to enable preview mode
2. THE Pipeline SHALL accept a `--limit N` flag to cap the number of files processed
3. THE Pipeline SHALL accept a `--verbose` flag to enable DEBUG-level logging
4. THE Pipeline SHALL accept a `--bucket` flag to override the default Video_Bucket name (default: `mw-family-videos-1`)
5. THE Pipeline SHALL accept a `--aws-profile` flag to specify an AWS SSO profile name
6. THE Pipeline SHALL accept a `--state-file` flag to specify the path to the progress state file (default: `transcribe_progress.json`)
7. THE Pipeline SHALL accept a `--temp-dir` flag to specify the local temporary directory for downloaded files (default: `transcribe_tmp`)
