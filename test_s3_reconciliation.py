"""
Property-based and unit tests for S3 reconciliation features in extract_transcripts.py.
Uses hypothesis for property-based testing and pytest as the test runner.
"""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from extract_transcripts import (
    load_processed_records,
    save_processed_records,
    update_processed_records,
    list_s3_files,
    reconcile_processed_file,
    S3Config,
)

# ---------------------------------------------------------------------------
# Shared Hypothesis Strategies
# ---------------------------------------------------------------------------

_VIDEO_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"


@st.composite
def video_id(draw):
    """Generates an 11-character YouTube video ID from [a-zA-Z0-9_-]."""
    return draw(st.text(alphabet=_VIDEO_ID_ALPHABET, min_size=11, max_size=11))


@st.composite
def youtube_url(draw, vid=None):
    """Generates a valid YouTube watch URL like https://www.youtube.com/watch?v={video_id}.
    If vid is provided, uses it; otherwise generates one."""
    if vid is None:
        vid = draw(video_id())
    return f"https://www.youtube.com/watch?v={vid}"


@st.composite
def video_record(draw):
    """Generates a Video_Record dict: {"url": <youtube_url_or_empty>, "filename": "<video_id>.md"}.
    ~80% have non-empty URLs, ~20% have empty URLs (simulating reconciled entries)."""
    vid = draw(video_id())
    has_url = draw(st.floats(min_value=0.0, max_value=1.0)) < 0.8
    if has_url:
        url = draw(youtube_url(vid=vid))
    else:
        url = ""
    return {"url": url, "filename": f"{vid}.md"}


@st.composite
def s3_key_set(draw):
    """Generates a set of S3 object keys mixing .md and .md.metadata.json files
    under a transcripts/ prefix."""
    vids = draw(st.lists(video_id(), min_size=0, max_size=20, unique=True))
    keys = set()
    for vid in vids:
        keys.add(f"transcripts/{vid}.md")
        keys.add(f"transcripts/{vid}.md.metadata.json")
    return keys
