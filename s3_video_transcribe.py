"""S3 Video Transcription Pipeline.

Scans the video bucket for MP4 files, downloads each one locally, runs
Whisper ("base" model) to generate a text transcript, produces a Bedrock
Knowledge Base-compatible metadata JSON file, and uploads both the
transcript (.md) and metadata (.md.metadata.json) back to the same S3
folder alongside the original MP4. Progress is tracked in a local JSON
state file to support resumption after interruption.

Usage:
    python s3_video_transcribe.py [--dry-run] [--limit N] [--verbose]
"""

import argparse
import boto3
import json
import logging
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BUCKET: str = "mw-family-videos-1"

METADATA_DATE_FIELDS: list[str] = ["creation_time", "date", "encoded_date"]

DEFAULT_STATE_FILE: str = "transcribe_progress.json"
DEFAULT_TEMP_DIR: str = "transcribe_tmp"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure Utility Functions
# ---------------------------------------------------------------------------

def is_mp4_file(key: str) -> bool:
    """Return True if the S3 key's file extension, lowercased, is .mp4."""
    return pathlib.PurePosixPath(key).suffix.lower() == ".mp4"


def derive_output_keys(s3_key: str) -> tuple[str, str]:
    """Derive transcript and metadata S3 keys from an MP4 S3 key.

    Given e.g. '2015/clip.mp4', returns ('2015/clip.md', '2015/clip.md.metadata.json').
    """
    p = pathlib.PurePosixPath(s3_key)
    base = str(p.with_suffix(".md"))
    return (base, base + ".metadata.json")


def humanize_title(filename_stem: str) -> str:
    """Replace underscores with spaces in a filename stem."""
    return filename_stem.replace("_", " ")


def format_transcript(title: str, transcript: str) -> str:
    """Format a transcript as markdown with a title header.

    Returns: '# {title}\\n\\n{transcript}\\n'
    """
    return f"# {title}\n\n{transcript}\n"


# ---------------------------------------------------------------------------
# Progress Tracking
# ---------------------------------------------------------------------------

def load_progress(state_file: str) -> dict:
    """Load progress state from a JSON file.

    Returns {"completed": []} if the file is missing or corrupted.
    """
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"completed": []}
    except (json.JSONDecodeError, ValueError):
        logger.warning("Corrupted state file %s — starting fresh", state_file)
        return {"completed": []}


def save_progress(state_file: str, progress: dict) -> None:
    """Write progress dict to a JSON state file with 2-space indentation."""
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


# ---------------------------------------------------------------------------
# S3 Scanner
# ---------------------------------------------------------------------------

def scan_source_bucket(s3_client, bucket: str) -> list[dict]:
    """Scan an S3 bucket for MP4 files using paginated list_objects_v2.

    Returns a list of dicts: [{"key": str, "last_modified": datetime}, ...].
    Logs total MP4 count and skipped count at INFO.
    """
    mp4_files: list[dict] = []
    skipped = 0

    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if is_mp4_file(key):
                mp4_files.append({
                    "key": key,
                    "last_modified": obj["LastModified"],
                })
            else:
                skipped += 1

    logger.info("Found %d MP4 files, skipped %d non-MP4 objects", len(mp4_files), skipped)
    return mp4_files


# ---------------------------------------------------------------------------
# Date Extraction and Transcription Components
# ---------------------------------------------------------------------------

def extract_video_date(local_path: str) -> str:
    """Extract the video creation date from embedded metadata via ffprobe.

    Runs ffprobe, checks format.tags for METADATA_DATE_FIELDS in priority
    order. Returns the full date string from the first field found, or
    empty string on failure.
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", local_path],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        tags = data.get("format", {}).get("tags", {})
        for field in METADATA_DATE_FIELDS:
            if field in tags and tags[field]:
                return tags[field]
        return ""
    except subprocess.CalledProcessError:
        logger.warning("ffprobe failed for %s", local_path)
        return ""
    except (json.JSONDecodeError, ValueError):
        logger.warning("Invalid ffprobe JSON output for %s", local_path)
        return ""
    except Exception:
        logger.warning("Unexpected error extracting date from %s", local_path)
        return ""


def transcribe_video(local_path: str, model) -> str:
    """Transcribe a video file using a pre-loaded Whisper model.

    Returns the transcript text, or empty string on failure.
    """
    try:
        result = model.transcribe(local_path, language="en")
        return result.get("text", "") or ""
    except Exception:
        logger.error("Whisper transcription failed for %s", local_path)
        return ""


def generate_metadata(
    s3_key: str,
    bucket: str,
    video_date: str,
    upload_date: str,
    transcript_language: str,
) -> dict:
    """Build a Bedrock KB-compatible metadata dict.

    All values inside metadataAttributes are strings.
    """
    stem = pathlib.PurePosixPath(s3_key).stem
    return {
        "metadataAttributes": {
            "video_id": stem,
            "title": humanize_title(stem),
            "url": f"s3://{bucket}/{s3_key}",
            "video_date": video_date,
            "upload_date": upload_date,
            "playlists": "",
            "description": "",
            "transcript_language": transcript_language,
            "processed_timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }


# ---------------------------------------------------------------------------
# S3 I/O Functions
# ---------------------------------------------------------------------------

def download_from_s3(s3_client, bucket: str, key: str, local_path: str) -> None:
    """Download an S3 object to a local file path."""
    s3_client.download_file(bucket, key, local_path)


def upload_file_to_s3(s3_client, bucket: str, key: str, local_path: str, content_type: str) -> None:
    """Upload a local file to S3 with a specified content type."""
    s3_client.upload_file(
        local_path, bucket, key,
        ExtraArgs={"ContentType": content_type},
    )


def upload_to_s3(s3_client, bucket: str, key: str, content: str, content_type: str) -> None:
    """Upload string content to S3 as UTF-8 bytes."""
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType=content_type,
    )


# ---------------------------------------------------------------------------
# Thumbnail Generation
# ---------------------------------------------------------------------------

def get_video_duration(local_path: str) -> float | None:
    """Get video duration in seconds via ffprobe. Returns None on failure."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", local_path],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        logger.warning("Could not get duration for %s", local_path)
        return None


def generate_thumbnail(local_path: str, output_path: str) -> bool:
    """Generate a 320x180 JPEG thumbnail at 10% into the video.

    Returns True on success, False on failure.
    """
    duration = get_video_duration(local_path)
    if duration is None or duration <= 0:
        timestamp = "00:00:01"
    else:
        seek_seconds = duration * 0.10
        timestamp = f"{int(seek_seconds // 3600):02d}:{int((seek_seconds % 3600) // 60):02d}:{seek_seconds % 60:06.3f}"

    result = subprocess.run(
        [
            "ffmpeg", "-ss", timestamp, "-i", local_path,
            "-vframes", "1", "-vf", "scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2",
            "-y", output_path,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.warning("Thumbnail generation failed for %s: %s", local_path, result.stderr[:200])
        return False
    return True


# ---------------------------------------------------------------------------
# CLI Parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="S3 Video Transcription Pipeline"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview mode — scan and report only, no downloads/transcriptions/uploads",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of files to process (applied to actual processing, not scanning)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Set log level to DEBUG",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=DEFAULT_BUCKET,
        help=f"S3 bucket name (default: {DEFAULT_BUCKET})",
    )
    parser.add_argument(
        "--aws-profile",
        type=str,
        default=None,
        help="AWS SSO profile name (optional)",
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default=DEFAULT_STATE_FILE,
        help=f"Path to progress state file (default: {DEFAULT_STATE_FILE})",
    )
    parser.add_argument(
        "--temp-dir",
        type=str,
        default=DEFAULT_TEMP_DIR,
        help=f"Local temp directory for downloads (default: {DEFAULT_TEMP_DIR})",
    )
    parser.add_argument(
        "--keep-local",
        action="store_true",
        default=False,
        help="Save copies of .md and .md.metadata.json files locally in temp dir for review",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="base",
        help="Whisper model size: tiny, base, small, medium, large (default: base)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def process_file(
    s3_key: str,
    last_modified: datetime,
    s3_client,
    bucket: str,
    temp_dir: str,
    model,
    keep_local: bool = False,
) -> dict | None:
    """Orchestrate single-file processing.

    Downloads MP4 from S3, extracts video date via ffprobe, transcribes
    with Whisper, generates metadata, uploads transcript .md and metadata
    .md.metadata.json back to S3. Returns a progress record dict on
    success, None on failure or empty transcript.
    """
    local_path = os.path.join(temp_dir, os.path.basename(s3_key))
    try:
        os.makedirs(temp_dir, exist_ok=True)

        # Download
        download_from_s3(s3_client, bucket, s3_key, local_path)

        # Extract video date
        video_date = extract_video_date(local_path)

        # Transcribe
        start_time = datetime.now(timezone.utc)
        transcript = transcribe_video(local_path, model)
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        logger.info("Transcription took %.1fs for %s", duration, s3_key)

        # Empty transcript → skip
        if not transcript:
            logger.warning("Empty transcript for %s — skipping", s3_key)
            return None

        # Derive output keys
        transcript_key, metadata_key = derive_output_keys(s3_key)

        # Format transcript content
        stem = pathlib.PurePosixPath(s3_key).stem
        title = humanize_title(stem)
        transcript_content = format_transcript(title, transcript)

        # Generate metadata
        metadata = generate_metadata(
            s3_key=s3_key,
            bucket=bucket,
            video_date=video_date,
            upload_date=last_modified.isoformat(),
            transcript_language="en",
        )
        metadata_json = json.dumps(metadata, indent=2, ensure_ascii=False)

        # Upload transcript and metadata
        upload_to_s3(s3_client, bucket, transcript_key, transcript_content, "text/markdown")
        upload_to_s3(s3_client, bucket, metadata_key, metadata_json, "application/json")

        # Generate and upload thumbnail
        thumb_filename = f"{stem}.jpg"
        thumb_local = os.path.join(temp_dir, thumb_filename)
        thumb_key = str(pathlib.PurePosixPath(s3_key).with_name(thumb_filename))
        if generate_thumbnail(local_path, thumb_local):
            upload_file_to_s3(s3_client, bucket, thumb_key, thumb_local, "image/jpeg")
            logger.info("Uploaded thumbnail: %s", thumb_key)
            if not keep_local and os.path.exists(thumb_local):
                os.remove(thumb_local)
        else:
            logger.warning("Skipped thumbnail for %s", s3_key)

        # Save local copies if requested
        if keep_local:
            local_md = os.path.join(temp_dir, os.path.basename(transcript_key))
            local_meta = os.path.join(temp_dir, os.path.basename(metadata_key))
            with open(local_md, "w", encoding="utf-8") as f:
                f.write(transcript_content)
            with open(local_meta, "w", encoding="utf-8") as f:
                f.write(metadata_json)
            logger.info("Saved local copies: %s, %s", local_md, local_meta)

        # Return progress record
        return {
            "source_key": s3_key,
            "transcript_key": transcript_key,
            "metadata_key": metadata_key,
            "thumbnail_key": thumb_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        logger.error("Failed to process %s", s3_key, exc_info=True)
        return None
    finally:
        # Clean up local temp file (unless --keep-local)
        if not keep_local:
            try:
                if os.path.exists(local_path):
                    os.remove(local_path)
            except Exception:
                logger.warning("Failed to clean up temp file %s", local_path)
        else:
            logger.info("Keeping local video: %s", local_path)


def run_pipeline(args: argparse.Namespace) -> None:
    """Main pipeline orchestrator."""
    import whisper

    logger.info("Loading Whisper model '%s'...", args.model)
    model = whisper.load_model(args.model)
    logger.info("Whisper model '%s' loaded", args.model)

    # Create boto3 session
    if args.aws_profile:
        session = boto3.Session(profile_name=args.aws_profile)
    else:
        session = boto3.Session()
    s3_client = session.client("s3")

    # Scan bucket for MP4 files
    all_mp4s = scan_source_bucket(s3_client, args.bucket)

    # Load progress and determine already-completed keys
    progress = load_progress(args.state_file)
    completed_keys = {rec["source_key"] for rec in progress["completed"]}

    # Filter to unprocessed files
    unprocessed = [f for f in all_mp4s if f["key"] not in completed_keys]
    skipped = len(all_mp4s) - len(unprocessed)
    logger.info("Skipping %d already-processed files", skipped)

    # Dry-run mode
    if args.dry_run:
        for f in unprocessed:
            logger.info("Would transcribe: %s", f["key"])
        logger.info(
            "Dry run summary: would transcribe %d, skipped %d",
            len(unprocessed),
            skipped,
        )
        return

    # Apply limit
    to_process = unprocessed
    if args.limit is not None:
        to_process = unprocessed[: args.limit]

    # Create temp dir
    os.makedirs(args.temp_dir, exist_ok=True)

    # Process files
    transcribed = 0
    failed = 0
    total = len(to_process)

    for i, file_info in enumerate(to_process, start=1):
        key = file_info["key"]
        logger.info("[%d/%d] Processing: %s", i, total, key)

        record = process_file(
            s3_key=key,
            last_modified=file_info["last_modified"],
            s3_client=s3_client,
            bucket=args.bucket,
            temp_dir=args.temp_dir,
            model=model,
            keep_local=args.keep_local,
        )

        if record is not None:
            transcribed += 1
            progress["completed"].append(record)
            save_progress(args.state_file, progress)
        else:
            failed += 1

    # Final summary
    logger.info(
        "Summary: total found=%d, transcribed=%d, skipped=%d, failed=%d",
        len(all_mp4s),
        transcribed,
        skipped,
        failed,
    )

    # Clean up temp dir if empty
    try:
        if os.path.isdir(args.temp_dir) and not os.listdir(args.temp_dir):
            os.rmdir(args.temp_dir)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point: parse args, configure logging, run pipeline."""
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    log_datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=log_datefmt,
    )

    # Dedicated file handler for ERROR-level messages
    error_handler = logging.FileHandler("transcription_errors.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(log_format, datefmt=log_datefmt))
    logging.getLogger().addHandler(error_handler)

    run_pipeline(args)


if __name__ == "__main__":
    main()
