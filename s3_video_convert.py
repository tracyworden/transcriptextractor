"""S3 Video Convert & Migrate Pipeline.

Scans a source S3 bucket for video files, converts non-MP4 videos to MP4
(H.264/AAC) using ffmpeg, and uploads the results to a destination bucket
organized by year-based folders. Progress is tracked in a local JSON state
file to support resumption after interruption.

Usage:
    python s3_video_convert.py [--dry-run] [--limit N] [--verbose]
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
import tempfile
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VIDEO_EXTENSIONS: set[str] = {
    '.mp4', '.mov', '.mts', '.m2ts', '.avi', '.wmv',
    '.mpg', '.mpeg', '.flv', '.mkv', '.3gp', '.webm', '.vob', '.ts'
}

SOURCE_BUCKET: str = "wor-family-pics"
DEST_BUCKET: str = "mw-family-videos-1"

METADATA_YEAR_FIELDS: list[str] = ["creation_time", "date", "encoded_date"]

DEFAULT_STATE_FILE: str = "video_convert_progress.json"
DEFAULT_TEMP_DIR: str = "video_convert_tmp"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure Utility Functions
# ---------------------------------------------------------------------------

def is_video_file(key: str) -> bool:
    """Return True if the S3 key's extension (case-insensitive) is in VIDEO_EXTENSIONS."""
    ext = pathlib.PurePosixPath(key).suffix.lower()
    return ext in VIDEO_EXTENSIONS


def resolve_dest_key(
    year: str | None,
    filename_stem: str,
    existing_dest_keys: set[str],
) -> str:
    """Build a destination S3 key, appending _1, _2, etc. on collision."""
    folder = year if year is not None else "unknown-year"
    candidate = f"{folder}/{filename_stem}.mp4"
    if candidate not in existing_dest_keys:
        return candidate

    n = 1
    while True:
        candidate = f"{folder}/{filename_stem}_{n}.mp4"
        if candidate not in existing_dest_keys:
            logger.warning(
                "Filename collision resolved: %s/%s.mp4 -> %s",
                folder,
                filename_stem,
                candidate,
            )
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Progress Tracking
# ---------------------------------------------------------------------------

def load_progress(state_file: str) -> dict:
    """Load the JSON state file. Return empty state if missing or corrupted."""
    if not os.path.exists(state_file):
        return {"completed": []}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Corrupted state file %s — starting fresh", state_file)
        return {"completed": []}


def save_progress(state_file: str, progress: dict) -> None:
    """Write the progress dict to the state file as JSON."""
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


# ---------------------------------------------------------------------------
# CLI Parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="S3 Video Convert & Migrate Pipeline"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview mode — scan and report only, no downloads/conversions/uploads",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of files to process (applied to actual processing, not scanning)",
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
        help=f"Local temp directory for downloads/conversions (default: {DEFAULT_TEMP_DIR})",
    )
    parser.add_argument(
        "--source-bucket",
        type=str,
        default=SOURCE_BUCKET,
        help=f"Source S3 bucket name (default: {SOURCE_BUCKET})",
    )
    parser.add_argument(
        "--dest-bucket",
        type=str,
        default=DEST_BUCKET,
        help=f"Destination S3 bucket name (default: {DEST_BUCKET})",
    )
    parser.add_argument(
        "--aws-profile",
        type=str,
        default=None,
        help="AWS SSO profile name (optional)",
    )
    parser.add_argument(
        "--keep-local",
        action="store_true",
        default=False,
        help="Keep local temp files after upload (useful for reviewing conversions)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Set log level to DEBUG",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# S3 Scanner & Metadata Extractor
# ---------------------------------------------------------------------------

def scan_source_bucket(s3_client, bucket: str) -> list[str]:
    """Paginated scan of an S3 bucket. Returns list of video S3 keys."""
    video_keys: list[str] = []
    skipped = 0

    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if is_video_file(key):
                video_keys.append(key)
            else:
                logger.debug("Skipping non-video file: %s", key)
                skipped += 1

    logger.info(
        "Scan complete: %d video files found, %d non-video files skipped",
        len(video_keys),
        skipped,
    )
    return video_keys


def extract_year_from_metadata(local_path: str) -> str | None:
    """Run ffprobe on a local file and extract a 4-digit creation year.

    Checks format.tags for fields in METADATA_YEAR_FIELDS order.
    Returns the year string or None on any failure.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                local_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("ffprobe failed for %s: %s", local_path, exc)
        return None

    try:
        probe = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        logger.warning("ffprobe returned invalid JSON for %s", local_path)
        return None

    tags = probe.get("format", {}).get("tags", {})
    year_re = re.compile(r"\b((?:19|20)\d{2})\b")

    for field in METADATA_YEAR_FIELDS:
        value = tags.get(field)
        if value is not None:
            m = year_re.search(str(value))
            if m:
                return m.group(1)

    return None


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def download_from_s3(s3_client, bucket: str, key: str, local_path: str) -> None:
    """Download an S3 object to a local file."""
    s3_client.download_file(bucket, key, local_path)


def upload_to_s3(s3_client, bucket: str, key: str, local_path: str) -> None:
    """Upload a local file to S3."""
    s3_client.upload_file(local_path, bucket, key)


def convert_to_mp4(input_path: str, output_path: str) -> bool:
    """Convert a video file to MP4 using ffmpeg.

    Returns True on success (exit code 0), False on failure.
    Logs stderr on failure.
    """
    result = subprocess.run(
        [
            "ffmpeg", "-i", input_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-movflags", "+faststart",
            "-y", output_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(
            "ffmpeg conversion failed for %s (exit code %d): %s",
            input_path,
            result.returncode,
            result.stderr,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def process_file(
    source_key: str,
    s3_source,
    s3_dest,
    temp_dir: str,
    dest_bucket: str,
    existing_dest_keys: set[str],
    source_bucket: str,
    keep_local: bool = False,
) -> dict | None:
    """Orchestrate single-file processing: download → probe → convert → upload.

    Returns a progress record dict on success, None on failure.
    Cleans up local temp files in a finally block.
    """
    basename = os.path.basename(source_key)
    download_path = os.path.join(temp_dir, basename)
    output_path = download_path  # may change if conversion needed

    try:
        os.makedirs(temp_dir, exist_ok=True)

        # Download
        download_from_s3(s3_source, source_bucket, source_key, download_path)

        # Extract year
        year = extract_year_from_metadata(download_path)

        # Determine if conversion is needed
        ext = pathlib.PurePosixPath(source_key).suffix.lower()
        needs_conversion = ext != ".mp4"

        if needs_conversion:
            stem = pathlib.PurePosixPath(source_key).stem
            output_path = os.path.join(temp_dir, f"{stem}.mp4")
            if not convert_to_mp4(download_path, output_path):
                return None
        # else: output_path stays as download_path (already mp4)

        # Resolve destination key
        stem = pathlib.PurePosixPath(source_key).stem
        dest_key = resolve_dest_key(year, stem, existing_dest_keys)

        # Upload
        upload_to_s3(s3_dest, dest_bucket, dest_key, output_path)

        # Track the new dest key for collision detection
        existing_dest_keys.add(dest_key)

        return {
            "source_key": source_key,
            "dest_key": dest_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        logger.error("Failed to process %s", source_key, exc_info=True)
        return None

    finally:
        # Clean up local temp files (unless --keep-local)
        if not keep_local:
            for path in {download_path, output_path}:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        logger.warning("Failed to clean up temp file: %s", path)
        else:
            logger.info("Keeping local file: %s", output_path)


def run_pipeline(args: argparse.Namespace) -> None:
    """Main pipeline orchestrator."""
    # Create boto3 session
    session_kwargs = {}
    if args.aws_profile:
        session_kwargs["profile_name"] = args.aws_profile
    session = boto3.Session(**session_kwargs)

    s3_source = session.client("s3")
    s3_dest = session.client("s3")

    # Scan source bucket
    video_keys = scan_source_bucket(s3_source, args.source_bucket)

    # Load progress
    progress = load_progress(args.state_file)

    # Build set of already-completed source keys
    completed_source_keys = {r["source_key"] for r in progress["completed"]}

    # Filter to unprocessed only
    unprocessed = [k for k in video_keys if k not in completed_source_keys]
    skipped = len(video_keys) - len(unprocessed)
    logger.info("Skipping %d already-processed files", skipped)

    # Dry-run mode
    if args.dry_run:
        would_convert = 0
        would_copy = 0
        for key in unprocessed:
            ext = pathlib.PurePosixPath(key).suffix.lower()
            if ext != ".mp4":
                logger.info("[DRY-RUN] Would convert: %s", key)
                would_convert += 1
            else:
                logger.info("[DRY-RUN] Would copy: %s", key)
                would_copy += 1
        logger.info(
            "Dry-run summary: would convert %d, would copy %d, skipped %d",
            would_convert,
            would_copy,
            skipped,
        )
        return

    # Apply limit
    if args.limit is not None:
        unprocessed = unprocessed[: args.limit]

    # Build set of existing destination keys for collision detection
    existing_dest_keys = {r["dest_key"] for r in progress["completed"]}

    # Create temp dir
    os.makedirs(args.temp_dir, exist_ok=True)

    # Counters
    converted = 0
    copied = 0
    failed = 0
    total = len(unprocessed)

    for i, key in enumerate(unprocessed, start=1):
        logger.info("[%d/%d] Processing: %s", i, total, key)

        record = process_file(
            source_key=key,
            s3_source=s3_source,
            s3_dest=s3_dest,
            temp_dir=args.temp_dir,
            dest_bucket=args.dest_bucket,
            existing_dest_keys=existing_dest_keys,
            source_bucket=args.source_bucket,
            keep_local=args.keep_local,
        )

        if record is not None:
            ext = pathlib.PurePosixPath(key).suffix.lower()
            if ext != ".mp4":
                converted += 1
            else:
                copied += 1
            progress["completed"].append(record)
            save_progress(args.state_file, progress)
        else:
            failed += 1

    logger.info(
        "Summary: %d found, %d converted, %d copied, %d skipped, %d failed",
        len(video_keys),
        converted,
        copied,
        skipped,
        failed,
    )

    # Clean up temp dir if empty
    try:
        os.rmdir(args.temp_dir)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point: parse args, configure logging, run pipeline."""
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    run_pipeline(args)


if __name__ == "__main__":
    main()
