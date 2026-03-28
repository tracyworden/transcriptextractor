# Implementation Plan: S3 Transcript Storage

## Overview

This implementation adds S3 storage capability to the YouTube transcript extraction system. The approach follows a modular design with configuration dataclasses, dedicated storage functions, and flexible command-line interface. Implementation will be incremental, starting with core S3 functionality, then adding storage abstraction, and finally integrating with the main extraction workflow.

## Tasks

- [x] 1. Add boto3 dependency and create configuration dataclasses
  - Add boto3 to requirements.txt
  - Create S3Config dataclass with bucket_name, prefix, region, and aws_profile fields
  - Create StorageConfig dataclass with local_dir and s3_config fields
  - Implement should_save_local() and should_save_s3() helper methods
  - _Requirements: 2.5, 6.2, 6.3_

- [ ] 2. Implement S3 upload functionality
  - [x] 2.1 Implement upload_to_s3() function
    - Add input validation for file_content, s3_key, and bucket_name
    - Initialize boto3 S3 client with profile support (if aws_profile provided)
    - Implement put_object call with UTF-8 encoding and content type
    - Add error handling and logging for upload success/failure
    - Return boolean success indicator
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 6.1, 6.3, 6.4, 6.5, 6.6, 8.2, 8.3, 9.3, 9.4_
  
  - [ ]* 2.2 Write property test for S3 key format
    - **Property 2: S3 keys must not have leading slashes**
    - **Validates: Requirements 3.5**
  
  - [ ]* 2.3 Write property test for content integrity
    - **Property 3: Content uploaded to S3 matches source content**
    - **Validates: Requirements 10.1, 10.2, 10.3**

- [ ] 3. Implement unified transcript storage function
  - [x] 3.1 Implement save_transcript_with_storage() function
    - Format transcript content as markdown with title header
    - Generate filename using "{video_id}.md" format
    - Implement local storage logic with directory creation
    - Implement S3 storage logic with prefix handling and leading slash removal
    - Track success across storage destinations
    - Raise IOError if all enabled destinations fail
    - Add logging for each storage operation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 5.1, 5.2, 5.3, 5.4, 5.5, 8.4, 8.5, 9.1, 9.2, 9.3, 10.5_
  
  - [ ]* 3.2 Write property test for storage reliability
    - **Property 1: At least one storage destination must succeed**
    - **Validates: Requirements 5.1, 5.2, 5.3**

- [ ] 4. Implement unified metadata storage function
  - [x] 4.1 Implement save_metadata_with_storage() function
    - Generate filename using "{video_id}.md.metadata.json" format
    - Serialize metadata to JSON with 2-space indentation and ensure_ascii=False
    - Implement local storage logic with directory creation
    - Implement S3 storage logic with prefix handling and leading slash removal
    - Track success across storage destinations
    - Raise IOError if all enabled destinations fail
    - Add logging for each storage operation
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 8.6, 9.1, 9.2, 9.3, 10.4_
  
  - [ ]* 4.2 Write property test for metadata JSON validity
    - **Property 4: Metadata JSON is valid after serialization**
    - **Validates: Requirements 4.3, 10.4**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Add command-line arguments to extract_transcripts.py
  - Add --s3-bucket argument for S3 bucket name
  - Add --s3-prefix argument for S3 key prefix (optional, default empty string)
  - Add --s3-region argument for AWS region (optional, default "us-east-1")
  - Add --aws-profile argument for AWS SSO profile name (optional)
  - Add --no-local-save flag to disable local storage
  - Update argument parser help text for all new arguments
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [ ] 7. Integrate storage functions into main extraction workflow
  - [x] 7.1 Create StorageConfig from command-line arguments
    - Build S3Config if --s3-bucket is provided
    - Set local_dir to None if --no-local-save is specified
    - Validate that at least one storage destination is configured
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 7.7_
  
  - [x] 7.2 Replace existing save calls with unified storage functions
    - Replace transcript file write with save_transcript_with_storage()
    - Replace metadata file write with save_metadata_with_storage()
    - Update error handling to catch IOError from storage functions
    - Preserve existing processed.json update logic
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 5.1, 5.2, 5.3_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The implementation assumes AWS credentials are configured via `aws sso login` before running the script
- boto3 session initialization with profile parameter enables AWS SSO profile support
