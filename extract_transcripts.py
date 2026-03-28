#!/usr/bin/env python3
"""
YouTube Transcript Extractor for @MachiningCloud channel.

Extracts transcripts and metadata from YouTube videos using yt-dlp,
with incremental processing and state tracking.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from typing import List, Set, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class S3Config:
    """Configuration for S3 storage"""
    bucket_name: str
    prefix: str = ""  # Optional S3 key prefix (folder path)
    region: str = "us-east-1"
    aws_profile: Optional[str] = None  # AWS SSO profile name


@dataclass
class StorageConfig:
    """Configuration for storage destinations"""
    local_dir: Optional[str] = None  # None = skip local storage
    s3_config: Optional[S3Config] = None  # None = skip S3 storage
    
    def should_save_local(self) -> bool:
        """Check if local storage is enabled"""
        return self.local_dir is not None
    
    def should_save_s3(self) -> bool:
        """Check if S3 storage is enabled"""
        return self.s3_config is not None


# Configuration: Playlists to ignore (videos exclusively in these playlists will be skipped)
IGNORED_PLAYLISTS = [
    "NOVO-WIDIA",
    "NOVO - Kennametal"
]


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def upload_to_s3(
    file_content: str,
    s3_key: str,
    bucket_name: str,
    content_type: str = "text/plain",
    aws_profile: Optional[str] = None
) -> bool:
    """
    Upload file content directly to S3 without creating local temp file.
    
    Args:
        file_content: String content to upload
        s3_key: S3 object key (path) for the file
        bucket_name: S3 bucket name
        content_type: MIME type for the content (default: "text/plain")
        aws_profile: AWS SSO profile name (optional)
    
    Returns:
        True if upload successful, False otherwise
    
    Preconditions:
        - file_content is non-empty string
        - s3_key is valid S3 key (non-empty, no leading slash)
        - bucket_name is valid S3 bucket name
        - AWS credentials are configured
    
    Postconditions:
        - Returns True if upload successful
        - Returns False if upload fails
        - File exists in S3 at s3://{bucket_name}/{s3_key} on success
        - No local side effects on failure
    """
    # Step 1: Validate inputs
    if not file_content:
        logger.error("Invalid input: file_content is empty")
        return False
    
    if not s3_key:
        logger.error("Invalid input: s3_key is empty")
        return False
    
    if not bucket_name:
        logger.error("Invalid input: bucket_name is empty")
        return False
    
    # Step 2: Initialize boto3 S3 client
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
        
        # Initialize session with profile support if provided
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            s3_client = session.client('s3')
            logger.debug(f"Initialized S3 client with AWS profile: {aws_profile}")
        else:
            s3_client = boto3.client('s3')
            logger.debug("Initialized S3 client with default credentials")
            
    except ImportError:
        logger.error("boto3 library is not installed. Install with: pip install boto3")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")
        return False
    
    # Step 3: Upload content to S3
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=file_content.encode('utf-8'),
            ContentType=content_type
        )
        
        s3_uri = f"s3://{bucket_name}/{s3_key}"
        logger.info(f"Successfully uploaded to {s3_uri}")
        return True
        
    except Exception as e:
        logger.error(f"S3 upload failed for {s3_key}: {e}")
        return False
def save_transcript_with_storage(
    video_id: str,
    title: str,
    transcript: str,
    storage_config: StorageConfig
) -> None:
    """
    Save transcript to all configured storage destinations.

    Args:
        video_id: YouTube video ID (11-character identifier)
        title: Video title for markdown header
        transcript: Transcript text
        storage_config: Configuration for storage destinations

    Raises:
        IOError: If all enabled storage operations fail

    Preconditions:
        - video_id is non-empty string (11-character YouTube ID)
        - title is non-empty string
        - transcript is non-empty string
        - storage_config has at least one destination enabled (local or S3)

    Postconditions:
        - If storage_config.should_save_local(): file saved to local directory
        - If storage_config.should_save_s3(): file uploaded to S3
        - Raises IOError if all enabled storage operations fail
        - At least one storage operation succeeds or exception raised
    """
    # Step 1: Format content as markdown with title header
    content = f"# {title}\n\n{transcript}\n"

    # Step 2: Generate filename using "{video_id}.md" format
    filename = f"{video_id}.md"

    # Step 3: Track success across storage destinations
    any_success = False

    # Step 4: Save to local storage if configured
    if storage_config.should_save_local():
        try:
            # Create local directory if it does not exist
            os.makedirs(storage_config.local_dir, exist_ok=True)

            filepath = os.path.join(storage_config.local_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Saved transcript locally: {filepath}")
            any_success = True

        except Exception as e:
            logger.error(f"Local save failed for {video_id}: {e}")

    # Step 5: Upload to S3 if configured
    if storage_config.should_save_s3():
        # Construct S3 key by combining prefix and filename
        # Remove leading slashes to ensure valid key format
        s3_key = f"{storage_config.s3_config.prefix}{filename}".lstrip('/')

        success = upload_to_s3(
            file_content=content,
            s3_key=s3_key,
            bucket_name=storage_config.s3_config.bucket_name,
            content_type="text/markdown",
            aws_profile=storage_config.s3_config.aws_profile
        )

        if success:
            any_success = True

    # Step 6: Raise IOError if all enabled destinations fail
    if not any_success:
        raise IOError(f"Failed to save transcript {video_id} to any destination")
def save_metadata_with_storage(
    video_id: str,
    metadata: dict,
    storage_config: StorageConfig
) -> None:
    """
    Save metadata JSON to all configured storage destinations.

    Args:
        video_id: YouTube video ID (11-character identifier)
        metadata: Dictionary containing video metadata
        storage_config: Configuration for storage destinations

    Raises:
        IOError: If all enabled storage operations fail

    Preconditions:
        - video_id is non-empty string (11-character YouTube ID)
        - metadata contains all required fields (video_id, title, url, upload_date,
          playlists, transcript_language, processed_timestamp)
        - storage_config has at least one destination enabled (local or S3)

    Postconditions:
        - If storage_config.should_save_local(): JSON file saved to local directory
        - If storage_config.should_save_s3(): JSON file uploaded to S3
        - Raises IOError if all enabled storage operations fail
        - At least one storage operation succeeds or exception raised
    """
    # Step 1: Generate filename using "{video_id}.md.metadata.json" format
    filename = f"{video_id}.md.metadata.json"

    # Step 2: Convert arrays to Bedrock-compatible format (strings, numbers, booleans only)
    # AWS Bedrock does not support array values in metadata
    bedrock_compatible_metadata = {}
    for key, value in metadata.items():
        if isinstance(value, list):
            if len(value) == 0:
                # Skip empty arrays entirely
                continue
            else:
                # Convert non-empty arrays to comma-separated strings
                bedrock_compatible_metadata[key] = ", ".join(str(v) for v in value)
        else:
            bedrock_compatible_metadata[key] = value

    # Step 3: Wrap metadata in metadataAttributes for AWS Bedrock Knowledge Base compatibility
    bedrock_metadata = {
        "metadataAttributes": bedrock_compatible_metadata
    }

    # Step 4: Serialize metadata to JSON with 2-space indentation and ensure_ascii=False
    content = json.dumps(bedrock_metadata, indent=2, ensure_ascii=False)

    # Step 3: Track success across storage destinations
    any_success = False

    # Step 4: Save to local storage if configured
    if storage_config.should_save_local():
        try:
            # Create local directory if it does not exist
            os.makedirs(storage_config.local_dir, exist_ok=True)

            filepath = os.path.join(storage_config.local_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Saved metadata locally: {filepath}")
            any_success = True

        except Exception as e:
            logger.error(f"Local metadata save failed for {video_id}: {e}")

    # Step 5: Upload to S3 if configured
    if storage_config.should_save_s3():
        # Construct S3 key by combining prefix and filename
        # Remove leading slashes to ensure valid key format
        s3_key = f"{storage_config.s3_config.prefix}{filename}".lstrip('/')

        success = upload_to_s3(
            file_content=content,
            s3_key=s3_key,
            bucket_name=storage_config.s3_config.bucket_name,
            content_type="application/json",
            aws_profile=storage_config.s3_config.aws_profile
        )

        if success:
            any_success = True

    # Step 6: Raise IOError if all enabled storage operations fail
    if not any_success:
        raise IOError(f"Failed to save metadata {video_id} to any destination")


def get_channel_playlists(channel_url: str) -> dict:
    """
    Fetches all playlists from a YouTube channel and maps video IDs to playlist names.
    
    Args:
        channel_url: The YouTube channel URL (e.g., '@MachiningCloud')
    
    Returns:
        Dictionary mapping video_id -> list of playlist names
    
    Raises:
        Exception: If yt-dlp fails to fetch playlist data
    """
    try:
        logger.info(f"Fetching playlists from channel: {channel_url}")
        
        # Construct the playlists URL
        if not channel_url.startswith('http'):
            playlists_url = f"https://www.youtube.com/{channel_url}/playlists"
        else:
            # Extract channel handle/ID and append /playlists
            playlists_url = channel_url.rstrip('/') + '/playlists'
        
        # Fetch all playlists
        result = subprocess.run(
            ['yt-dlp', '--flat-playlist', '--dump-json', playlists_url],
            capture_output=True,
            text=True,
            check=True
        )
        
        if not result.stdout.strip():
            logger.info("No playlists found for channel")
            return {}
        
        # Parse playlist metadata
        playlists = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                try:
                    playlist_data = json.loads(line)
                    playlists.append(playlist_data)
                except json.JSONDecodeError:
                    continue
        
        logger.info(f"Found {len(playlists)} playlists")
        
        # Build video_id -> playlist_names mapping
        video_to_playlists = {}
        
        for playlist in playlists:
            playlist_title = playlist.get('title', 'Unknown Playlist')
            playlist_url = playlist.get('url', '')
            
            if not playlist_url:
                continue
            
            logger.info(f"Fetching videos from playlist: {playlist_title}")
            
            try:
                # Fetch videos in this playlist
                playlist_result = subprocess.run(
                    ['yt-dlp', '--flat-playlist', '--dump-json', playlist_url],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Parse video IDs from playlist
                for video_line in playlist_result.stdout.strip().split('\n'):
                    if video_line.strip():
                        try:
                            video_data = json.loads(video_line)
                            video_id = video_data.get('id', '')
                            
                            if video_id:
                                if video_id not in video_to_playlists:
                                    video_to_playlists[video_id] = []
                                video_to_playlists[video_id].append(playlist_title)
                        except json.JSONDecodeError:
                            continue
                            
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to fetch videos from playlist '{playlist_title}': {e.stderr}")
                continue
        
        logger.info(f"Mapped {len(video_to_playlists)} videos to playlists")
        return video_to_playlists
        
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to fetch playlists: {e.stderr}")
        return {}
    except Exception as e:
        logger.warning(f"Error fetching playlists: {str(e)}")
        return {}




def get_channel_videos(channel_url: str) -> List[str]:
    """
    Fetches all video URLs from a YouTube channel using yt-dlp.
    
    Args:
        channel_url: The YouTube channel URL (e.g., '@MachiningCloud')
    
    Returns:
        List of video URLs
    
    Raises:
        Exception: If yt-dlp fails to fetch channel data
    """
    try:
        logger.info(f"Fetching video URLs from channel: {channel_url}")
        
        # Construct the full channel URL if only handle is provided
        if not channel_url.startswith('http'):
            full_url = f"https://www.youtube.com/{channel_url}"
        else:
            full_url = channel_url
        
        # Run yt-dlp with --flat-playlist and --get-url options
        result = subprocess.run(
            ['yt-dlp', '--flat-playlist', '--get-url', full_url],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the output - each line is a video URL
        video_urls = [url.strip() for url in result.stdout.strip().split('\n') if url.strip()]
        
        logger.info(f"Successfully fetched {len(video_urls)} video URLs from channel")
        return video_urls
        
    except subprocess.CalledProcessError as e:
        error_msg = f"yt-dlp failed to fetch channel data: {e.stderr}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except FileNotFoundError:
        error_msg = "yt-dlp not found. Please ensure yt-dlp is installed and in PATH"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error fetching channel videos: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def should_process_video(video_id: str, video_to_playlists: dict) -> bool:
    """
    Determines if a video should be processed based on its playlists.
    
    Videos are skipped if they are ONLY in ignored playlists.
    Videos in both ignored and non-ignored playlists are processed.
    Videos not in any playlist are processed.
    
    Args:
        video_id: The YouTube video ID
        video_to_playlists: Dictionary mapping video_id -> list of playlist names
    
    Returns:
        True if video should be processed, False if it should be skipped
    """
    # If video has no playlists, process it
    if video_id not in video_to_playlists:
        return True
    
    playlists = video_to_playlists[video_id]
    
    # If video has no playlists, process it
    if not playlists:
        return True
    
    # Check if video is in any non-ignored playlist
    has_non_ignored_playlist = any(
        playlist not in IGNORED_PLAYLISTS 
        for playlist in playlists
    )
    
    # Process if video is in at least one non-ignored playlist
    if has_non_ignored_playlist:
        return True
    
    # Skip if video is ONLY in ignored playlists
    logger.info(f"Skipping video {video_id} - only in ignored playlists: {', '.join(playlists)}")
    return False





def load_processed_records(filepath: str) -> Tuple[Set[str], Set[str], list[dict]]:
    """
    Loads processed records from processed.json, handling both legacy and new formats.

    Args:
        filepath: Path to processed.json

    Returns:
        Tuple of (url_set, filename_set, records_list).
        Returns empty sets and empty list if file doesn't exist or is corrupted.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.info(f"No processed.json found at {filepath}, starting fresh")
        return set(), set(), []
    except json.JSONDecodeError as e:
        logger.warning(f"Corrupted JSON in {filepath}: {e}. Treating as empty.")
        return set(), set(), []
    except Exception as e:
        logger.error(f"Unexpected error reading {filepath}: {e}. Treating as empty.")
        return set(), set(), []

    # New format
    if "processed" in data:
        records = data["processed"]
        url_set = {r["url"] for r in records if r.get("url")}
        filename_set = {r["filename"] for r in records if r.get("filename")}
        logger.info(f"Loaded {len(records)} processed records from {filepath}")
        return url_set, filename_set, records

    # Legacy format — migrate
    if "processed_urls" in data:
        video_id_pattern = re.compile(r'(?:v=|/)([a-zA-Z0-9_-]{11})(?:[&?]|$)')
        legacy_urls = data["processed_urls"]
        records = []
        for url in legacy_urls:
            match = video_id_pattern.search(url)
            if match:
                vid = match.group(1)
                records.append({"url": url, "filename": f"{vid}.md"})
            else:
                logger.warning(f"Legacy migration: could not extract Video_ID from URL, skipping: {url}")
        logger.info(f"Migrated {len(records)} of {len(legacy_urls)} legacy URLs to new format")
        save_processed_records(filepath, records)
        url_set = {r["url"] for r in records if r.get("url")}
        filename_set = {r["filename"] for r in records if r.get("filename")}
        return url_set, filename_set, records

    # File exists but has neither key — treat as empty
    logger.warning(f"Unrecognized format in {filepath}, treating as empty.")
    return set(), set(), []


def save_processed_records(filepath: str, records: list[dict]) -> None:
    """
    Writes processed records to disk in the new format.

    Args:
        filepath: Path to the processed JSON file
        records: List of Video_Record dicts (each with 'url' and 'filename' keys)
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({"processed": records}, f, indent=2, ensure_ascii=False)


def list_s3_files(s3_config: 'S3Config') -> Set[str]:
    """
    Lists all .md files under the configured prefix in S3, excluding .md.metadata.json files.

    Args:
        s3_config: S3Config dataclass with bucket_name, prefix, region, aws_profile

    Returns:
        Set of basenames (e.g., {"abc123.md", "def456.md"})

    Raises:
        Any boto3/botocore exception on S3 errors (network, permissions, etc.)
    """
    import boto3

    if s3_config.aws_profile:
        session = boto3.Session(profile_name=s3_config.aws_profile, region_name=s3_config.region)
        s3_client = session.client('s3')
    else:
        s3_client = boto3.client('s3', region_name=s3_config.region)

    md_files: Set[str] = set()
    params = {
        'Bucket': s3_config.bucket_name,
        'Prefix': s3_config.prefix,
    }

    while True:
        response = s3_client.list_objects_v2(**params)
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key.endswith('.md') and not key.endswith('.md.metadata.json'):
                md_files.add(os.path.basename(key))

        if response.get('IsTruncated'):
            params['ContinuationToken'] = response['NextContinuationToken']
        else:
            break

    return md_files


def reconcile_processed_file(processed_file_path: str, s3_config: 'S3Config') -> None:
    """
    Synchronizes processed.json against S3 contents.

    S3 is the source of truth:
    - Files in S3 but not in processed.json are added (with url="").
    - Records in processed.json with no corresponding S3 file are removed.

    Exceptions from list_s3_files are NOT caught here — they propagate to main().

    Args:
        processed_file_path: Path to the processed JSON file
        s3_config: S3Config dataclass with bucket_name, prefix, region, aws_profile
    """
    url_set, filename_set, records = load_processed_records(processed_file_path)
    s3_filenames = list_s3_files(s3_config)

    to_add = s3_filenames - filename_set
    to_remove = filename_set - s3_filenames

    updated_records = [r for r in records if r.get("filename") not in to_remove]

    for fname in sorted(to_add):
        updated_records.append({"url": "", "filename": fname})

    save_processed_records(processed_file_path, updated_records)

    logger.info(f"Reconciliation complete: {len(to_add)} added, {len(to_remove)} removed")


def _extract_transcript_with_whisper(video_url: str, video_id: str, temp_dir: str) -> Tuple[str, str, str]:
    """
    Extracts transcript using Whisper speech-to-text model.
    
    Args:
        video_url: The YouTube video URL
        video_id: The extracted video ID
        temp_dir: Temporary directory for audio file
    
    Returns:
        Tuple of (video_id, transcript_text, language_code)
    
    Raises:
        Exception: If Whisper transcription fails
    """
    import whisper
    
    audio_file = None
    try:
        logger.info(f"Downloading audio for {video_id} using yt-dlp")
        
        # Download audio using yt-dlp
        audio_file = os.path.join(temp_dir, f"{video_id}.mp3")
        result = subprocess.run(
            [
                'yt-dlp',
                '--extract-audio',
                '--audio-format', 'mp3',
                '-o', audio_file,
                video_url
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"Loading Whisper model (base) for {video_id}")
        # Load Whisper model (base model for balance of speed/accuracy)
        model = whisper.load_model("base")
        
        logger.info(f"Transcribing audio for {video_id} using Whisper")
        # Transcribe audio
        result = model.transcribe(audio_file)
        transcript_text = result["text"]
        
        if not transcript_text:
            raise Exception(f"Whisper generated empty transcript for video {video_id}")
        
        logger.info(f"Successfully generated Whisper transcript for {video_id} ({len(transcript_text)} characters)")
        
        return (video_id, transcript_text, 'en')
        
    except subprocess.CalledProcessError as e:
        error_msg = f"yt-dlp failed to download audio: {e.stderr}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Whisper transcription failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    finally:
        # Delete audio file after transcription
        if audio_file and os.path.exists(audio_file):
            try:
                #os.remove(audio_file)
                logger.info(f"can delete audio file: {audio_file}")
            except Exception as e:
                logger.warning(f"Failed to delete audio file {audio_file}: {str(e)}")




def extract_transcript(video_url: str, use_whisper_fallback: bool = False) -> Tuple[str, str, str]:
    """
    Extracts transcript from a YouTube video using yt-dlp.
    Falls back to Whisper speech-to-text if YouTube transcript is unavailable.
    
    Args:
        video_url: The YouTube video URL
        use_whisper_fallback: Whether to use Whisper if YouTube transcript unavailable
    
    Returns:
        Tuple of (video_id, transcript_text, language_code)
    
    Raises:
        Exception: If transcript extraction fails
    """
    try:
        logger.info(f"Extracting transcript from: {video_url}")
        
        # Extract video ID from URL
        video_id_match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})(?:[&?]|$)', video_url)
        if not video_id_match:
            raise Exception(f"Could not extract video ID from URL: {video_url}")
        video_id = video_id_match.group(1)
        
        # Create temporary directory for subtitle files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Try to download manual subtitles first, then auto-generated as fallback
            # Use --write-sub for manual, --write-auto-sub for auto-generated
            # --skip-download to avoid downloading video
            # --sub-lang en to prefer English
            # --sub-format vtt for easier parsing
            # -o to specify output template
            output_template = os.path.join(temp_dir, '%(id)s.%(ext)s')
            
            # First attempt: manual subtitles
            result = subprocess.run(
                [
                    'yt-dlp',
                    '--write-sub',
                    '--sub-lang', 'en',
                    '--sub-format', 'vtt',
                    '--skip-download',
                    '-o', output_template,
                    video_url
                ],
                capture_output=True,
                text=True
            )
            
            # Check if manual subtitle was downloaded
            vtt_file = os.path.join(temp_dir, f"{video_id}.en.vtt")
            is_auto_generated = False
            
            if not os.path.exists(vtt_file):
                # Try auto-generated subtitles
                logger.info(f"Manual subtitles not available, trying auto-generated for {video_id}")
                result = subprocess.run(
                    [
                        'yt-dlp',
                        '--write-auto-sub',
                        '--sub-lang', 'en',
                        '--sub-format', 'vtt',
                        '--skip-download',
                        '-o', output_template,
                        video_url
                    ],
                    capture_output=True,
                    text=True
                )
                is_auto_generated = True
                
                # Check again for auto-generated subtitle
                if not os.path.exists(vtt_file):
                    # No YouTube transcript available
                    if not use_whisper_fallback:
                        raise Exception(f"No transcript available for video {video_id}")
                    
                    # Use Whisper fallback
                    logger.info(f"No YouTube transcript available for {video_id}, using Whisper fallback")
                    return _extract_transcript_with_whisper(video_url, video_id, temp_dir)
            
            # Parse VTT file to extract transcript text
            with open(vtt_file, 'r', encoding='utf-8') as f:
                vtt_content = f.read()
            
            # Parse VTT format - remove timestamps and metadata
            # VTT format has lines like:
            # WEBVTT
            # 
            # 00:00:00.000 --> 00:00:02.000
            # Transcript text here
            transcript_lines = []
            for line in vtt_content.split('\n'):
                # Skip WEBVTT header, timestamps, and empty lines
                if line.strip() and not line.startswith('WEBVTT') and '-->' not in line and not re.match(r'^\d+$', line.strip()):
                    # Remove VTT tags like <c> or <v>
                    clean_line = re.sub(r'<[^>]+>', '', line)
                    clean_line = clean_line.strip()
                    
                    # Skip if this line is identical to the previous line (deduplication)
                    if not transcript_lines or transcript_lines[-1] != clean_line:
                        transcript_lines.append(clean_line)
            
            transcript_text = ' '.join(transcript_lines)
            
            if not transcript_text:
                raise Exception(f"Transcript file is empty for video {video_id}")
            
            language_code = 'en'
            logger.info(f"Successfully extracted {'auto-generated' if is_auto_generated else 'manual'} transcript for {video_id} ({len(transcript_text)} characters)")
            
            return (video_id, transcript_text, language_code)
            
    except subprocess.CalledProcessError as e:
        error_msg = f"yt-dlp failed to extract transcript: {e.stderr}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except FileNotFoundError as e:
        if 'yt-dlp' in str(e):
            error_msg = "yt-dlp not found. Please ensure yt-dlp is installed and in PATH"
        else:
            error_msg = f"File not found: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Error extracting transcript: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def extract_metadata(video_url: str, video_to_playlists: dict = None) -> dict:
    """
    Extracts metadata from a YouTube video using yt-dlp.
    
    Args:
        video_url: The YouTube video URL
        video_to_playlists: Optional dictionary mapping video_id -> list of playlist names
    
    Returns:
        Dictionary containing video metadata
    
    Raises:
        Exception: If metadata extraction fails
    """
    try:
        logger.info(f"Extracting metadata from: {video_url}")
        
        # Run yt-dlp with --dump-json to get metadata
        result = subprocess.run(
            ['yt-dlp', '--dump-json', '--skip-download', video_url],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse JSON output
        metadata_raw = json.loads(result.stdout)
        
        # Extract required fields
        video_id = metadata_raw.get('id', '')
        title = metadata_raw.get('title', '')
        url = metadata_raw.get('webpage_url', video_url)
        upload_date = metadata_raw.get('upload_date', '')
        
        # Get playlists from the mapping if provided
        playlists = []
        if video_to_playlists and video_id in video_to_playlists:
            playlists = video_to_playlists[video_id]
        
        # Build metadata dictionary with all required fields
        metadata = {
            'video_id': video_id,
            'title': title,
            'url': url,
            'upload_date': upload_date,
            'playlists': playlists,
            'transcript_language': 'en',
            'processed_timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        logger.info(f"Successfully extracted metadata for video {video_id}: {title}")
        if playlists:
            logger.info(f"  Playlists: {', '.join(playlists)}")
        return metadata
        
    except subprocess.CalledProcessError as e:
        error_msg = f"yt-dlp failed to extract metadata: {e.stderr}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse yt-dlp JSON output: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except FileNotFoundError:
        error_msg = "yt-dlp not found. Please ensure yt-dlp is installed and in PATH"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Error extracting metadata: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def save_transcript(video_id: str, title: str, transcript: str, output_dir: str) -> None:
    """
    Saves transcript to a markdown file.
    
    Args:
        video_id: YouTube video ID
        title: Video title for markdown header
        transcript: Transcript text
        output_dir: Directory to save the file
    
    Raises:
        IOError: If file writing fails
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Construct filename: {video_id}.md
        filename = f"{video_id}.md"
        filepath = os.path.join(output_dir, filename)
        
        # Format content with title as markdown header
        content = f"# {title}\n\n{transcript}\n"
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Successfully saved transcript to {filepath}")
        
    except OSError as e:
        error_msg = f"Failed to write transcript file {video_id}.md: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error saving transcript for {video_id}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


def save_metadata(video_id: str, metadata: dict, output_dir: str) -> None:
    """
    Saves metadata to a JSON file with AWS Bedrock naming convention.
    
    Args:
        video_id: YouTube video ID
        metadata: Metadata dictionary
        output_dir: Directory to save the file
    
    Raises:
        IOError: If file writing fails
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Construct filename: {video_id}.md.metadata.json (AWS Bedrock naming)
        filename = f"{video_id}.md.metadata.json"
        filepath = os.path.join(output_dir, filename)
        
        # Validate that all required fields are present
        required_fields = [
            'video_id', 'title', 'url', 'upload_date', 
            'playlists', 'transcript_language', 'processed_timestamp'
        ]
        missing_fields = [field for field in required_fields if field not in metadata]
        if missing_fields:
            raise ValueError(f"Missing required metadata fields: {', '.join(missing_fields)}")
        
        # Ensure playlists is an array
        if not isinstance(metadata.get('playlists'), list):
            raise ValueError("playlists field must be an array")
        
        # Write to file with proper indentation (2 spaces)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully saved metadata to {filepath}")
        
    except OSError as e:
        error_msg = f"Failed to write metadata file {video_id}.md.metadata.json: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)
    except ValueError as e:
        error_msg = f"Invalid metadata for {video_id}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error saving metadata for {video_id}: {str(e)}"
        logger.error(error_msg)
        raise IOError(error_msg)


def update_processed_records(filepath: str, video_url: str, video_id: str) -> None:
    """
    Appends a processed video record to processed.json.
    
    Args:
        filepath: Path to processed.json
        video_url: The video URL (must be non-empty)
        video_id: The video ID used to construct the filename
    
    Raises:
        ValueError: If video_url is an empty string
    """
    if video_url == "":
        raise ValueError("video_url must not be empty")

    _, _, records = load_processed_records(filepath)
    records.append({"url": video_url, "filename": f"{video_id}.md"})
    save_processed_records(filepath, records)
    logger.info(f"Appended record for {video_id} to {filepath} ({len(records)} total records)")


def main(channel: str = "@MachiningCloud", output_dir: str = ".", processed_file: str = "processed.json", use_whisper_fallback: bool = False, storage_config: Optional[StorageConfig] = None) -> None:
    """
    Main execution function that orchestrates the extraction process.
    
    Args:
        channel: YouTube channel URL or handle (default: @MachiningCloud)
        output_dir: Directory to save transcript and metadata files (default: current directory)
        processed_file: Path to the state file tracking processed videos (default: processed.json)
        use_whisper_fallback: Whether to use Whisper fallback for videos without transcripts (default: False)
        storage_config: Configuration for storage destinations (default: None, uses output_dir for local storage)
    """
    logger.info("YouTube Transcript Extractor started")
    logger.info(f"Channel: {channel}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Processed file: {processed_file}")
    logger.info(f"Whisper fallback: {'enabled' if use_whisper_fallback else 'disabled'}")
    
    # If storage_config is not provided, create default config using output_dir for local storage
    if storage_config is None:
        storage_config = StorageConfig(local_dir=output_dir, s3_config=None)
        logger.info("Using default storage configuration: local storage only")
    else:
        # Log storage configuration
        if storage_config.should_save_local():
            logger.info(f"Local storage enabled: {storage_config.local_dir}")
        if storage_config.should_save_s3():
            logger.info(f"S3 storage enabled: s3://{storage_config.s3_config.bucket_name}/{storage_config.s3_config.prefix}")
    
    # S3 is required — abort if not configured
    if storage_config.s3_config is None:
        logger.error("S3 storage is required. Provide --s3-bucket.")
        sys.exit(1)
    
    try:
        # Step 1: Get all video URLs from channel
        all_video_urls = get_channel_videos(channel)
        logger.info(f"Found {len(all_video_urls)} total videos in channel")
        
        # Step 2: Fetch playlist information for the channel
        video_to_playlists = get_channel_playlists(channel)
        logger.info(f"Fetched playlist information for {len(video_to_playlists)} videos")
        
        # Step 3: Load processed URLs from processed.json
        processed_urls, _, _ = load_processed_records(processed_file)
        logger.info(f"Found {len(processed_urls)} already processed videos")
        
        # Step 3b: Reconcile processed.json against S3
        try:
            reconcile_processed_file(processed_file, storage_config.s3_config)
        except Exception as e:
            logger.error(f"S3 reconciliation failed: {e}")
            sys.exit(1)
        
        # Step 3c: Re-load after reconciliation
        processed_urls, processed_filenames, _ = load_processed_records(processed_file)
        logger.info(f"After reconciliation: {len(processed_urls)} URLs, {len(processed_filenames)} filenames tracked")
        
        # Step 4: Filter unprocessed videos using both URL and filename checks
        video_id_pattern = re.compile(r'(?:v=|/)([a-zA-Z0-9_-]{11})(?:[&?]|$)')
        unprocessed_urls = []
        for url in all_video_urls:
            if url in processed_urls:
                continue
            match = video_id_pattern.search(url)
            if match and f"{match.group(1)}.md" in processed_filenames:
                continue
            unprocessed_urls.append(url)
        logger.info(f"Found {len(unprocessed_urls)} unprocessed videos to extract")
        
        if not unprocessed_urls:
            logger.info("No new videos to process. All videos are up to date.")
            return
        
        # Track statistics
        successful_count = 0
        failed_count = 0
        skipped_count = 0
        
        # Step 5: Loop through unprocessed videos
        for idx, video_url in enumerate(unprocessed_urls, 1):
            logger.info(f"Processing video {idx}/{len(unprocessed_urls)}: {video_url}")
            
            try:
                # Step 6a: Extract transcript
                video_id, transcript_text, language_code = extract_transcript(video_url, use_whisper_fallback)
                
                # Step 6b: Check if video should be processed based on playlists
                if not should_process_video(video_id, video_to_playlists):
                    skipped_count += 1
                    # Mark as processed so we don't try again
                    update_processed_records(processed_file, video_url, video_id)
                    continue
                
                # Step 6c: Extract metadata with playlist information
                metadata = extract_metadata(video_url, video_to_playlists)
                
                # Update transcript_language in metadata from actual extraction
                metadata['transcript_language'] = language_code
                
                # Step 6d: Save transcript file using unified storage
                save_transcript_with_storage(video_id, metadata['title'], transcript_text, storage_config)
                
                # Step 6e: Save metadata file using unified storage
                save_metadata_with_storage(video_id, metadata, storage_config)
                
                # Step 7: Update processed.json only after both files saved successfully
                update_processed_records(processed_file, video_url, video_id)
                
                successful_count += 1
                logger.info(f"Successfully processed video {video_id}: {metadata['title']}")
                
            except IOError as e:
                # Step 8a: Handle storage errors (IOError from storage functions)
                failed_count += 1
                logger.error(f"Failed to save files for video {video_url}: {str(e)}")
                logger.info("Continuing to next video...")
                continue
            except Exception as e:
                # Step 8b: Handle other errors gracefully and continue processing
                failed_count += 1
                logger.error(f"Failed to process video {video_url}: {str(e)}")
                logger.info("Continuing to next video...")
                continue
        
        # Print summary
        logger.info("=" * 60)
        logger.info("Extraction complete!")
        logger.info(f"Total videos in channel: {len(all_video_urls)}")
        logger.info(f"Previously processed: {len(processed_urls)}")
        logger.info(f"Newly processed: {successful_count}")
        logger.info(f"Skipped (ignored playlists): {skipped_count}")
        logger.info(f"Failed: {failed_count}")
        logger.info(f"Total processed: {len(processed_urls) + successful_count + skipped_count}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Fatal error in main execution: {str(e)}")
        raise


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Extract transcripts and metadata from YouTube channel videos using yt-dlp.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local storage only (default behavior)
  python extract_transcripts.py
  python extract_transcripts.py --channel @MachiningCloud
  python extract_transcripts.py --channel @MachiningCloud --output-dir ./transcripts --processed-file ./processed.json
  python extract_transcripts.py --use-whisper-fallback
  
  # S3 storage with local backup (dual storage)
  python extract_transcripts.py --s3-bucket my-bucket --output-dir ./transcripts
  python extract_transcripts.py --s3-bucket my-bucket --s3-prefix youtube/transcripts/
  
  # S3-only storage (no local files)
  python extract_transcripts.py --s3-bucket my-bucket --no-local-save
  python extract_transcripts.py --s3-bucket my-bucket --s3-prefix youtube/ --no-local-save
  
  # S3 with AWS SSO profile
  python extract_transcripts.py --s3-bucket my-bucket --aws-profile my-profile
  python extract_transcripts.py --s3-bucket my-bucket --s3-region us-west-2 --aws-profile my-profile
        """
    )
    
    parser.add_argument(
        '--channel',
        type=str,
        default='@MachiningCloud',
        help='YouTube channel URL or handle (default: @MachiningCloud)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='.',
        help='Directory to save transcript and metadata files (default: current directory)'
    )
    
    parser.add_argument(
        '--processed-file',
        type=str,
        default='processed.json',
        help='Path to the state file tracking processed videos (default: processed.json)'
    )
    
    parser.add_argument(
        '--use-whisper-fallback',
        action='store_true',
        help='Use Whisper to generate transcripts for videos without YouTube transcripts (requires openai-whisper)'
    )
    
    parser.add_argument(
        '--s3-bucket',
        type=str,
        default=None,
        help='S3 bucket name for storing transcripts and metadata (enables S3 storage)'
    )
    
    parser.add_argument(
        '--s3-prefix',
        type=str,
        default='',
        help='S3 key prefix (folder path) for organizing files in the bucket (default: empty string)'
    )
    
    parser.add_argument(
        '--s3-region',
        type=str,
        default='us-east-1',
        help='AWS region for S3 bucket (default: us-east-1)'
    )
    
    parser.add_argument(
        '--aws-profile',
        type=str,
        default=None,
        help='AWS SSO profile name for authentication (uses default credentials if not specified)'
    )
    
    parser.add_argument(
        '--no-local-save',
        action='store_true',
        help='Disable local file storage (only save to S3, requires --s3-bucket)'
    )
    
    args = parser.parse_args()
    
    # Create StorageConfig from command-line arguments
    # Step 1: Determine local storage configuration
    if args.no_local_save:
        local_dir = None
        logger.info("Local storage disabled (--no-local-save)")
    else:
        local_dir = args.output_dir
        logger.info(f"Local storage enabled: {local_dir}")
    
    # Step 2: Determine S3 storage configuration
    if args.s3_bucket:
        s3_config = S3Config(
            bucket_name=args.s3_bucket,
            prefix=args.s3_prefix,
            region=args.s3_region,
            aws_profile=args.aws_profile
        )
        logger.info(f"S3 storage enabled: s3://{args.s3_bucket}/{args.s3_prefix}")
    else:
        s3_config = None
        logger.info("S3 storage disabled (no --s3-bucket provided)")
    
    # Step 3: Validate that S3 is configured (required — S3 is source of truth)
    if s3_config is None:
        logger.error("Error: --s3-bucket is required. S3 is the source of truth for processed state.")
        parser.exit(1, "Error: --s3-bucket is required.\n")
    
    # Step 4: Create StorageConfig object
    storage_config = StorageConfig(local_dir=local_dir, s3_config=s3_config)
    
    # Call main with parsed arguments
    main(
        channel=args.channel,
        output_dir=args.output_dir,
        processed_file=args.processed_file,
        use_whisper_fallback=args.use_whisper_fallback,
        storage_config=storage_config
    )
