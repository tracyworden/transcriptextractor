# Requirements Document: S3 Transcript Storage

## Introduction

This document specifies the requirements for adding S3 storage capability to the YouTube transcript extraction system. The system shall enable direct upload of transcript markdown files and metadata JSON files to AWS S3 buckets, providing flexible storage options including S3-only, local-only, or dual storage configurations.

## Glossary

- **System**: The YouTube transcript extraction and storage system (extract_transcripts.py)
- **Transcript_File**: A markdown (.md) file containing extracted YouTube video transcript text
- **Metadata_File**: A JSON file (.metadata.json) containing video metadata and processing information
- **S3_Storage**: AWS S3 bucket storage destination for transcript and metadata files
- **Local_Storage**: Local filesystem directory storage destination for transcript and metadata files
- **Storage_Configuration**: Configuration object specifying enabled storage destinations (local, S3, or both)
- **Video_ID**: 11-character YouTube video identifier
- **S3_Key**: Object key (path) for files stored in S3 bucket

## Requirements

### Requirement 1: S3 Upload Capability

**User Story:** As a system operator, I want to upload transcript files directly to S3, so that I can store transcripts in cloud storage without requiring local disk space.

#### Acceptance Criteria

1. WHEN valid file content and S3 configuration are provided, THE System SHALL upload the content to the specified S3 bucket and key
2. WHEN S3 upload succeeds, THE System SHALL return a success indicator
3. WHEN S3 upload fails, THE System SHALL return a failure indicator and log the error
4. WHEN uploading to S3, THE System SHALL encode content as UTF-8
5. WHEN uploading transcript files, THE System SHALL set content type to "text/markdown"
6. WHEN uploading metadata files, THE System SHALL set content type to "application/json"

### Requirement 2: Flexible Storage Configuration

**User Story:** As a system operator, I want to configure storage destinations independently, so that I can choose S3-only, local-only, or dual storage based on my needs.

#### Acceptance Criteria

1. WHERE local storage is configured, THE System SHALL save files to the local directory
2. WHERE S3 storage is configured, THE System SHALL upload files to the S3 bucket
3. WHERE both storage destinations are configured, THE System SHALL save files to both local and S3
4. WHERE neither storage destination is configured, THE System SHALL reject the operation
5. THE System SHALL provide configuration options for S3 bucket name, key prefix, and region

### Requirement 3: Transcript Storage

**User Story:** As a system operator, I want to save extracted transcripts to configured storage destinations, so that transcript data is persisted according to my storage strategy.

#### Acceptance Criteria

1. WHEN saving a transcript, THE System SHALL format it as markdown with video title as header
2. WHEN saving a transcript, THE System SHALL use filename format "{video_id}.md"
3. WHEN local storage is enabled, THE System SHALL create the local directory if it does not exist
4. WHEN S3 storage is enabled, THE System SHALL construct S3 keys by combining prefix and filename
5. WHEN constructing S3 keys, THE System SHALL remove leading slashes to ensure valid key format
6. IF all enabled storage operations fail, THEN THE System SHALL raise an IOError

### Requirement 4: Metadata Storage

**User Story:** As a system operator, I want to save video metadata alongside transcripts, so that I can track video information and processing details.

#### Acceptance Criteria

1. WHEN saving metadata, THE System SHALL serialize it as formatted JSON with 2-space indentation
2. WHEN saving metadata, THE System SHALL use filename format "{video_id}.md.metadata.json"
3. WHEN serializing metadata, THE System SHALL preserve non-ASCII characters (ensure_ascii=False)
4. WHEN local storage is enabled, THE System SHALL create the local directory if it does not exist
5. WHEN S3 storage is enabled, THE System SHALL construct S3 keys by combining prefix and filename
6. IF all enabled storage operations fail, THEN THE System SHALL raise an IOError

### Requirement 5: Storage Reliability

**User Story:** As a system operator, I want the system to ensure at least one storage operation succeeds, so that transcript data is not lost due to partial failures.

#### Acceptance Criteria

1. WHEN multiple storage destinations are configured, THE System SHALL attempt all enabled storage operations
2. WHEN at least one storage operation succeeds, THE System SHALL complete successfully
3. IF all enabled storage operations fail, THEN THE System SHALL raise an IOError with descriptive message
4. WHEN a storage operation fails, THE System SHALL log the error and continue attempting remaining destinations
5. WHEN S3 upload fails, THE System SHALL not affect local storage operations

### Requirement 6: AWS Credentials and Permissions

**User Story:** As a system operator, I want to use AWS SSO profiles for authentication, so that I can securely access the correct AWS account after running aws sso login.

#### Acceptance Criteria

1. WHEN initializing S3 client, THE System SHALL support AWS SSO profile-based authentication
2. THE System SHALL accept --aws-profile argument to specify which AWS profile to use
3. WHEN --aws-profile is provided, THE System SHALL initialize boto3 session with the specified profile
4. WHEN --aws-profile is not provided, THE System SHALL use boto3 default credential resolution
5. IF boto3 library is not installed, THEN THE System SHALL log an error and return failure
6. IF AWS credentials are not configured or SSO session is expired, THEN THE System SHALL log an error and return failure
7. WHEN uploading to S3, THE System SHALL require PutObject permission on the target bucket

### Requirement 7: Command-Line Interface

**User Story:** As a system operator, I want to configure storage options via command-line arguments, so that I can easily control storage behavior when running the script.

#### Acceptance Criteria

1. THE System SHALL accept --s3-bucket argument to specify S3 bucket name
2. THE System SHALL accept --s3-prefix argument to specify S3 key prefix (optional)
3. THE System SHALL accept --s3-region argument to specify AWS region (default: us-east-1)
4. THE System SHALL accept --aws-profile argument to specify AWS SSO profile name
5. THE System SHALL accept --no-local-save flag to disable local storage
6. THE System SHALL accept --output-dir argument to specify local storage directory
7. WHERE --s3-bucket is provided without --no-local-save, THE System SHALL enable dual storage

### Requirement 8: Input Validation

**User Story:** As a system operator, I want the system to validate inputs before attempting storage operations, so that I receive clear error messages for invalid configurations.

#### Acceptance Criteria

1. WHEN validating S3 upload inputs, THE System SHALL reject empty file content
2. WHEN validating S3 upload inputs, THE System SHALL reject empty S3 keys
3. WHEN validating S3 upload inputs, THE System SHALL reject empty bucket names
4. WHEN validating transcript save inputs, THE System SHALL require non-empty video ID
5. WHEN validating transcript save inputs, THE System SHALL require non-empty title and transcript text
6. WHEN validating metadata save inputs, THE System SHALL require all mandatory metadata fields

### Requirement 9: Logging and Observability

**User Story:** As a system operator, I want detailed logging of storage operations, so that I can troubleshoot issues and monitor system behavior.

#### Acceptance Criteria

1. WHEN a local save succeeds, THE System SHALL log the local file path
2. WHEN an S3 upload succeeds, THE System SHALL log the S3 URI (s3://bucket/key)
3. WHEN a storage operation fails, THE System SHALL log the error with video ID and destination
4. WHEN initializing S3 client fails, THE System SHALL log the specific error reason
5. WHEN input validation fails, THE System SHALL log the validation error

### Requirement 10: Content Integrity

**User Story:** As a system operator, I want to ensure uploaded content matches source content exactly, so that transcript data is not corrupted during storage operations.

#### Acceptance Criteria

1. WHEN uploading content to S3, THE System SHALL encode content as UTF-8 bytes
2. WHEN uploading content to S3, THE System SHALL use atomic put_object operation
3. IF S3 upload fails, THEN THE System SHALL not create partial uploads
4. WHEN serializing metadata to JSON, THE System SHALL preserve all field values exactly
5. WHEN formatting transcript markdown, THE System SHALL preserve all transcript text exactly
