# Requirements Document

## Introduction

A YouTube transcript extractor for the @MachiningCloud channel that uses yt-dlp to extract transcripts and metadata. The system tracks processed videos to enable incremental updates.

## Glossary

- **Extractor**: The system that extracts video transcripts and metadata from YouTube
- **Video_ID**: The unique YouTube identifier for a video
- **processed.json**: File tracking successfully processed video URLs
- **Whisper**: OpenAI's speech-to-text model for generating transcripts from audio
- **Fallback_Transcript**: A transcript generated using Whisper when YouTube transcripts are unavailable

## Requirements

### Requirement 1: Get Channel Video URLs

**User Story:** As a user, I want to get all video URLs from the @MachiningCloud channel, so that I can process them.

#### Acceptance Criteria

1. WHEN the Extractor runs, THE Extractor SHALL use yt-dlp to get all video URLs from the @MachiningCloud channel
2. THE Extractor SHALL extract the complete list of video URLs from the channel

### Requirement 2: Filter Unprocessed Videos

**User Story:** As a user, I want to skip already processed videos, so that I don't waste time reprocessing them.

#### Acceptance Criteria

1. WHEN the Extractor has a list of video URLs, THE Extractor SHALL read processed.json
2. THE Extractor SHALL create a list of URLs that are NOT in processed.json
3. IF processed.json does not exist, THEN THE Extractor SHALL treat all videos as unprocessed and create an empty processed.json file for use as the videos are processed 

### Requirement 3: Extract Transcripts

**User Story:** As a user, I want transcripts saved as markdown files, so that I can read them easily.

#### Acceptance Criteria

1. WHEN processing a video URL, THE Extractor SHALL use yt-dlp to extract the transcript
2. THE Extractor SHALL save the transcript to {Video_ID}.md
3. IF a transcript is not available from YouTube, THEN THE Extractor SHALL attempt to generate a Fallback_Transcript using Whisper
4. IF Whisper fallback is enabled and transcript is unavailable, THE Extractor SHALL download the video audio using yt-dlp
5. IF Whisper fallback is enabled and transcript is unavailable, THE Extractor SHALL use Whisper to generate a transcript from the audio
6. IF Whisper fallback is enabled and transcript is unavailable, THE Extractor SHALL delete the downloaded audio file after transcript generation
7. IF both YouTube transcript and Whisper fallback fail, THEN THE Extractor SHALL log an error and skip to the next video

### Requirement 4: Extract Metadata with AWS Bedrock Naming

**User Story:** As a user, I want metadata saved with AWS Bedrock compatible naming, so that I can use it with AWS Bedrock.

#### Acceptance Criteria

1. WHEN processing a video URL, THE Extractor SHALL use yt-dlp to extract metadata
2. THE Extractor SHALL save metadata to {Video_ID}.md.metadata.json
3. THE metadata file SHALL include video_id as a field
4. THE metadata file SHALL include title as a field
5. THE metadata file SHALL include url as a field
6. THE metadata file SHALL include upload_date as a field
7. THE metadata file SHALL include playlists as an array field
8. THE metadata file SHALL include transcript_language as a field
9. THE metadata file SHALL include processed_timestamp as a field

### Requirement 5: Handle Errors Without Updating Tracker

**User Story:** As a user, I want failed extractions to not be marked as processed, so that I can retry them later.

#### Acceptance Criteria

1. IF yt-dlp fails to extract a transcript, THEN THE Extractor SHALL NOT update processed.json for that URL
2. IF yt-dlp fails to extract metadata, THEN THE Extractor SHALL NOT update processed.json for that URL
3. IF file writing fails, THEN THE Extractor SHALL NOT update processed.json for that URL
4. THE Extractor SHALL log all errors with the video URL and error details
5. THE Extractor SHALL continue processing remaining videos after an error

### Requirement 6: Update Tracker on Success

**User Story:** As a user, I want successfully processed videos tracked, so that I don't reprocess them.

#### Acceptance Criteria

1. WHEN both transcript and metadata are successfully extracted and saved, THE Extractor SHALL add the video URL to processed.json
2. THE Extractor SHALL append to processed.json without removing existing entries
3. IF processed.json does not exist, THEN THE Extractor SHALL create it before adding the first URL
