# Implementation Plan: YouTube Transcript Extractor

## Overview

This plan implements a Python script that extracts transcripts and metadata from the @MachiningCloud YouTube channel using yt-dlp. The implementation follows an incremental approach with state tracking, graceful error handling, and comprehensive testing including property-based tests.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create extract_transcripts.py in the project root
  - Create requirements.txt with yt-dlp and hypothesis dependencies
  - Create test_extract_transcripts.py for unit and property-based tests
  - Set up basic logging configuration
  - _Requirements: All (foundation for implementation)_

- [x] 2. Implement state management functions
  - [x] 2.1 Implement load_processed_urls() function
    - Read processed.json and return set of URLs
    - Handle missing file by returning empty set
    - Handle corrupted JSON gracefully
    - _Requirements: 2.1, 2.3_
  
  - [ ]* 2.2 Write property test for URL filtering
    - **Property 1: URL Filtering Set Difference**
    - **Validates: Requirements 2.2**
  
  - [x] 2.3 Implement update_processed_urls() function
    - Append video URL to processed.json
    - Create file if it doesn't exist
    - Preserve existing entries when appending
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [ ]* 2.4 Write property test for append preservation
    - **Property 8: Append Preserves Existing Entries**
    - **Validates: Requirements 6.2**

- [x] 3. Implement YouTube data extraction functions
  - [x] 3.1 Implement get_channel_videos() function
    - Use yt-dlp with --flat-playlist and --get-url options
    - Extract all video URLs from @MachiningCloud channel
    - Handle yt-dlp errors and log appropriately
    - _Requirements: 1.1, 1.2_
  
  - [x] 3.2 Implement extract_transcript() function
    - Use yt-dlp with --write-auto-sub or --write-sub
    - Return tuple of (video_id, transcript_text, language_code)
    - Prefer manual transcripts over auto-generated
    - Raise exception if transcript unavailable
    - _Requirements: 3.1_
  
  - [x] 3.3 Implement extract_metadata() function
    - Use yt-dlp with --dump-json option
    - Extract video_id, title, url, upload_date, playlists
    - Return dictionary with all required metadata fields
    - Add processed_timestamp field
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_
  
  - [ ]* 3.4 Write property test for metadata completeness
    - **Property 4: Metadata Completeness**
    - **Validates: Requirements 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9**

- [x] 4. Implement file writing functions
  - [x] 4.1 Implement save_transcript() function
    - Write transcript to {video_id}.md file
    - Include video title as markdown header
    - Handle file writing errors with exceptions
    - _Requirements: 3.2_
  
  - [ ]* 4.2 Write property test for transcript filename convention
    - **Property 2: Transcript Filename Convention**
    - **Validates: Requirements 3.2**
  
  - [x] 4.3 Implement save_metadata() function
    - Write metadata to {video_id}.md.metadata.json file
    - Ensure all required fields are included
    - Format JSON with proper indentation
    - Handle file writing errors with exceptions
    - _Requirements: 4.2_
  
  - [ ]* 4.4 Write property test for metadata filename convention
    - **Property 3: Metadata Filename Convention**
    - **Validates: Requirements 4.2**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement error handling and logging
  - [x] 6.1 Add error logging for transcript extraction failures
    - Log video URL, error type, and error details
    - Continue processing remaining videos after error
    - Do not update processed.json on failure
    - _Requirements: 3.3, 5.1, 5.4, 5.5_
  
  - [x] 6.2 Add error logging for metadata extraction failures
    - Log video URL, error type, and error details
    - Continue processing remaining videos after error
    - Do not update processed.json on failure
    - _Requirements: 5.2, 5.4, 5.5_
  
  - [x] 6.3 Add error logging for file writing failures
    - Log video URL, error type, and error details
    - Continue processing remaining videos after error
    - Do not update processed.json on failure
    - _Requirements: 5.3, 5.4, 5.5_
  
  - [ ]* 6.4 Write property test for state consistency on failure
    - **Property 5: State Consistency on Failure**
    - **Validates: Requirements 5.1, 5.2, 5.3**
  
  - [ ]* 6.5 Write property test for error resilience
    - **Property 6: Error Resilience**
    - **Validates: Requirements 3.3, 5.5**

- [x] 7. Implement main orchestration function
  - [x] 7.1 Implement main() function
    - Call get_channel_videos() to fetch all URLs
    - Call load_processed_urls() to get processed set
    - Filter unprocessed videos using set difference
    - Loop through unprocessed videos
    - For each video: extract transcript, extract metadata, save both files
    - Update processed.json only after both files saved successfully
    - Handle errors gracefully and continue processing
    - _Requirements: All (orchestrates entire workflow)_
  
  - [ ]* 7.2 Write property test for state update on success
    - **Property 7: State Update on Success**
    - **Validates: Requirements 6.1**

- [ ] 8. Add unit tests for edge cases
  - [ ]* 8.1 Write unit tests for file operations
    - Test reading existing processed.json
    - Test creating new processed.json when missing
    - Test handling corrupted processed.json
    - Test appending to processed.json
    - _Requirements: 2.1, 2.3, 6.2, 6.3_
  
  - [ ]* 8.2 Write unit tests for error scenarios
    - Test error logging format and content
    - Test empty channel (no videos)
    - Test all videos already processed
    - Test missing transcript for a video
    - Test invalid video URL
    - _Requirements: 3.3, 5.4, 5.5_

- [x] 9. Add command-line interface and configuration
  - [x] 9.1 Add command-line argument parsing
    - Add --channel argument for channel URL (default: @MachiningCloud)
    - Add --output-dir argument for output directory (default: current directory)
    - Add --processed-file argument for state file path (default: processed.json)
    - Add if __name__ == "__main__" block to call main()
    - _Requirements: All (makes script executable)_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
.\
- [x] 11. Add Whisper fallback for videos without transcripts
  - [x] 11.1 Add openai-whisper to requirements.txt
    - Add openai-whisper dependency
    - _Requirements: 3.3, 3.4, 3.5, 3.6_
  
  - [x] 11.2 Update extract_transcript() to support Whisper fallback
    - Add use_whisper_fallback parameter (default: False)
    - When YouTube transcript unavailable and fallback enabled:
      - Download audio using yt-dlp with --extract-audio --audio-format mp3
      - Load Whisper model (base model for balance of speed/accuracy)
      - Transcribe audio using Whisper
      - Delete downloaded audio file after transcription
      - Return generated transcript
    - _Requirements: 3.3, 3.4, 3.5, 3.6_
  
  - [x] 11.3 Add --use-whisper-fallback CLI argument
    - Add command-line flag to enable Whisper fallback
    - Pass flag to extract_transcript() function
    - Update help text with Whisper fallback information
    - _Requirements: 3.3, 3.4, 3.5, 3.6_
  
  - [x] 11.4 Add unit tests for Whisper fallback
    - Test Whisper fallback when YouTube transcript unavailable
    - Test audio file cleanup after transcription
    - Test fallback disabled by default
    - _Requirements: 3.3, 3.4, 3.5, 3.6_

- [ ] 12. Final checkpoint - Ensure all tests pass with Whisper
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property-based tests use hypothesis library with minimum 100 iterations
- All property tests include feature tags for documentation
- Unit tests focus on edge cases and integration points
- Error handling ensures no partial state updates (atomic operations)
