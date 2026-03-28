"""Unit tests for s3_video_transcribe.py utility functions and progress tracking."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from s3_video_transcribe import (
    derive_output_keys,
    download_from_s3,
    extract_video_date,
    format_transcript,
    generate_metadata,
    humanize_title,
    is_mp4_file,
    load_progress,
    process_file,
    save_progress,
    scan_source_bucket,
    transcribe_video,
    upload_to_s3,
)


# ---------------------------------------------------------------------------
# is_mp4_file
# ---------------------------------------------------------------------------

class TestIsMp4File:
    def test_lowercase_mp4(self):
        assert is_mp4_file("folder/video.mp4") is True

    def test_uppercase_mp4(self):
        assert is_mp4_file("folder/video.MP4") is True

    def test_mixed_case_mp4(self):
        assert is_mp4_file("folder/video.Mp4") is True

    def test_mov_extension(self):
        assert is_mp4_file("folder/video.mov") is False

    def test_txt_extension(self):
        assert is_mp4_file("folder/notes.txt") is False

    def test_no_extension(self):
        assert is_mp4_file("folder/README") is False

    def test_multiple_dots(self):
        assert is_mp4_file("folder/my.video.clip.mp4") is True

    def test_multiple_dots_non_mp4(self):
        assert is_mp4_file("folder/my.mp4.bak") is False


# ---------------------------------------------------------------------------
# derive_output_keys
# ---------------------------------------------------------------------------

class TestDeriveOutputKeys:
    def test_basic_case(self):
        md, meta = derive_output_keys("2015/clip.mp4")
        assert md == "2015/clip.md"
        assert meta == "2015/clip.md.metadata.json"

    def test_nested_folders(self):
        md, meta = derive_output_keys("a/b/c/video.mp4")
        assert md == "a/b/c/video.md"
        assert meta == "a/b/c/video.md.metadata.json"

    def test_root_level_file(self):
        md, meta = derive_output_keys("clip.mp4")
        assert md == "clip.md"
        assert meta == "clip.md.metadata.json"


# ---------------------------------------------------------------------------
# humanize_title
# ---------------------------------------------------------------------------

class TestHumanizeTitle:
    def test_underscores(self):
        assert humanize_title("VID_20150313_085854") == "VID 20150313 085854"

    def test_no_underscores(self):
        assert humanize_title("myvideo") == "myvideo"

    def test_multiple_consecutive_underscores(self):
        assert humanize_title("a___b") == "a   b"

    def test_empty_string(self):
        assert humanize_title("") == ""


# ---------------------------------------------------------------------------
# format_transcript
# ---------------------------------------------------------------------------

class TestFormatTranscript:
    def test_basic_case(self):
        result = format_transcript("My Title", "Hello world.")
        assert result == "# My Title\n\nHello world.\n"

    def test_exact_format(self):
        result = format_transcript("T", "Body text here")
        assert result.startswith("# T\n\n")
        assert result.endswith("Body text here\n")
        assert result.count("\n") == 3


# ---------------------------------------------------------------------------
# load_progress
# ---------------------------------------------------------------------------

class TestLoadProgress:
    def test_missing_file(self, tmp_path):
        result = load_progress(str(tmp_path / "nonexistent.json"))
        assert result == {"completed": []}

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("")
        result = load_progress(str(f))
        assert result == {"completed": []}

    def test_corrupted_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json!!")
        result = load_progress(str(f))
        assert result == {"completed": []}

    def test_valid_state(self, tmp_path):
        state = {"completed": [{"source_key": "a.mp4", "transcript_key": "a.md",
                                 "metadata_key": "a.md.metadata.json",
                                 "timestamp": "2025-01-01T00:00:00+00:00"}]}
        f = tmp_path / "state.json"
        f.write_text(json.dumps(state))
        result = load_progress(str(f))
        assert result == state


# ---------------------------------------------------------------------------
# save_progress
# ---------------------------------------------------------------------------

class TestSaveProgress:
    def test_write_and_read_back(self, tmp_path):
        state = {"completed": [{"source_key": "x.mp4"}]}
        path = str(tmp_path / "progress.json")
        save_progress(path, state)
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == state

    def test_round_trip(self, tmp_path):
        state = {"completed": [
            {"source_key": "2015/clip.mp4", "transcript_key": "2015/clip.md",
             "metadata_key": "2015/clip.md.metadata.json",
             "timestamp": "2025-07-14T10:00:00+00:00"},
        ]}
        path = str(tmp_path / "rt.json")
        save_progress(path, state)
        loaded = load_progress(path)
        assert loaded == state

    def test_two_space_indentation(self, tmp_path):
        state = {"completed": []}
        path = str(tmp_path / "indent.json")
        save_progress(path, state)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        # 2-space indent means the key is indented by 2 spaces
        assert '  "completed"' in raw


# ---------------------------------------------------------------------------
# scan_source_bucket
# ---------------------------------------------------------------------------

class TestScanSourceBucket:
    def _make_paginator(self, pages):
        """Build a mock s3_client whose paginator yields the given pages."""
        client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = pages
        client.get_paginator.return_value = paginator
        return client

    def test_mixed_mp4_and_non_mp4(self):
        dt1 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        dt2 = datetime(2025, 6, 15, tzinfo=timezone.utc)
        pages = [
            {
                "Contents": [
                    {"Key": "2015/clip.mp4", "LastModified": dt1},
                    {"Key": "2015/notes.txt", "LastModified": dt2},
                    {"Key": "2015/video.MP4", "LastModified": dt2},
                ]
            }
        ]
        client = self._make_paginator(pages)
        result = scan_source_bucket(client, "my-bucket")
        assert len(result) == 2
        assert result[0] == {"key": "2015/clip.mp4", "last_modified": dt1}
        assert result[1] == {"key": "2015/video.MP4", "last_modified": dt2}

    def test_empty_bucket(self):
        pages = [{"Contents": []}]
        client = self._make_paginator(pages)
        result = scan_source_bucket(client, "my-bucket")
        assert result == []

    def test_empty_bucket_no_contents_key(self):
        pages = [{}]
        client = self._make_paginator(pages)
        result = scan_source_bucket(client, "my-bucket")
        assert result == []

    def test_multiple_pages(self):
        dt = datetime(2025, 3, 1, tzinfo=timezone.utc)
        pages = [
            {"Contents": [{"Key": "a/one.mp4", "LastModified": dt}]},
            {"Contents": [{"Key": "b/two.mp4", "LastModified": dt}]},
        ]
        client = self._make_paginator(pages)
        result = scan_source_bucket(client, "bucket")
        assert len(result) == 2
        assert result[0]["key"] == "a/one.mp4"
        assert result[1]["key"] == "b/two.mp4"

    def test_last_modified_captured(self):
        dt = datetime(2024, 12, 25, 10, 30, 0, tzinfo=timezone.utc)
        pages = [{"Contents": [{"Key": "vid.mp4", "LastModified": dt}]}]
        client = self._make_paginator(pages)
        result = scan_source_bucket(client, "bucket")
        assert result[0]["last_modified"] == dt

    def test_logging_counts(self, caplog):
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        pages = [
            {
                "Contents": [
                    {"Key": "a.mp4", "LastModified": dt},
                    {"Key": "b.txt", "LastModified": dt},
                    {"Key": "c.mov", "LastModified": dt},
                ]
            }
        ]
        client = self._make_paginator(pages)
        with caplog.at_level(logging.INFO):
            scan_source_bucket(client, "bucket")
        assert "1 MP4" in caplog.text
        assert "2 non-MP4" in caplog.text


# ---------------------------------------------------------------------------
# extract_video_date
# ---------------------------------------------------------------------------

class TestExtractVideoDate:
    def _mock_ffprobe(self, tags):
        """Return a mock subprocess.run result with the given tags dict."""
        output = json.dumps({"format": {"tags": tags}})
        return MagicMock(stdout=output, returncode=0)

    @patch("s3_video_transcribe.subprocess.run")
    def test_creation_time(self, mock_run):
        mock_run.return_value = self._mock_ffprobe(
            {"creation_time": "2015-03-13T08:58:54.000000Z"}
        )
        assert extract_video_date("/tmp/vid.mp4") == "2015-03-13T08:58:54.000000Z"

    @patch("s3_video_transcribe.subprocess.run")
    def test_date_only(self, mock_run):
        mock_run.return_value = self._mock_ffprobe({"date": "2015-03-13"})
        assert extract_video_date("/tmp/vid.mp4") == "2015-03-13"

    @patch("s3_video_transcribe.subprocess.run")
    def test_encoded_date(self, mock_run):
        mock_run.return_value = self._mock_ffprobe(
            {"encoded_date": "UTC 2015-03-13 08:58:54"}
        )
        assert extract_video_date("/tmp/vid.mp4") == "UTC 2015-03-13 08:58:54"

    @patch("s3_video_transcribe.subprocess.run")
    def test_field_priority(self, mock_run):
        """creation_time wins over date and encoded_date."""
        mock_run.return_value = self._mock_ffprobe({
            "encoded_date": "UTC 2015-03-13",
            "creation_time": "2015-03-13T09:00:00Z",
            "date": "2015-03-13",
        })
        assert extract_video_date("/tmp/vid.mp4") == "2015-03-13T09:00:00Z"

    @patch("s3_video_transcribe.subprocess.run")
    def test_no_tags(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"format": {}}), returncode=0
        )
        assert extract_video_date("/tmp/vid.mp4") == ""

    @patch("s3_video_transcribe.subprocess.run")
    def test_ffprobe_failure(self, mock_run):
        import subprocess as sp
        mock_run.side_effect = sp.CalledProcessError(1, "ffprobe")
        assert extract_video_date("/tmp/vid.mp4") == ""

    @patch("s3_video_transcribe.subprocess.run")
    def test_invalid_json(self, mock_run):
        mock_run.return_value = MagicMock(stdout="not json{{{", returncode=0)
        assert extract_video_date("/tmp/vid.mp4") == ""


# ---------------------------------------------------------------------------
# transcribe_video
# ---------------------------------------------------------------------------

class TestTranscribeVideo:
    def test_success(self):
        model = MagicMock()
        model.transcribe.return_value = {"text": "Hello world"}
        assert transcribe_video("/tmp/vid.mp4", model) == "Hello world"

    def test_empty_text(self):
        model = MagicMock()
        model.transcribe.return_value = {"text": ""}
        assert transcribe_video("/tmp/vid.mp4", model) == ""

    def test_no_text_key(self):
        model = MagicMock()
        model.transcribe.return_value = {}
        assert transcribe_video("/tmp/vid.mp4", model) == ""

    def test_exception(self):
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("GPU OOM")
        assert transcribe_video("/tmp/vid.mp4", model) == ""


# ---------------------------------------------------------------------------
# generate_metadata
# ---------------------------------------------------------------------------

class TestGenerateMetadata:
    def test_known_inputs(self):
        result = generate_metadata(
            s3_key="2015/VID_20150313_085854_924.mp4",
            bucket="mw-family-videos-1",
            video_date="2015-03-13T08:58:54.000000Z",
            upload_date="2026-03-24T20:04:58+00:00",
            transcript_language="en",
        )
        attrs = result["metadataAttributes"]
        assert attrs["video_id"] == "VID_20150313_085854_924"
        assert attrs["title"] == "VID 20150313 085854 924"
        assert attrs["url"] == "s3://mw-family-videos-1/2015/VID_20150313_085854_924.mp4"
        assert attrs["video_date"] == "2015-03-13T08:58:54.000000Z"
        assert attrs["upload_date"] == "2026-03-24T20:04:58+00:00"
        assert attrs["transcript_language"] == "en"
        assert attrs["playlists"] == ""
        assert attrs["description"] == ""

    def test_metadata_attributes_wrapper(self):
        result = generate_metadata("clip.mp4", "b", "", "", "en")
        assert list(result.keys()) == ["metadataAttributes"]

    def test_all_values_are_strings(self):
        result = generate_metadata("clip.mp4", "b", "", "", "en")
        for key, val in result["metadataAttributes"].items():
            assert isinstance(val, str), f"{key} should be str, got {type(val)}"

    def test_no_arrays_in_values(self):
        result = generate_metadata("clip.mp4", "b", "", "", "en")
        for key, val in result["metadataAttributes"].items():
            assert not isinstance(val, (list, dict)), f"{key} must not be list/dict"

    def test_processed_timestamp_is_iso(self):
        result = generate_metadata("clip.mp4", "b", "", "", "en")
        ts = result["metadataAttributes"]["processed_timestamp"]
        # Should parse without error
        datetime.fromisoformat(ts)


# ---------------------------------------------------------------------------
# download_from_s3
# ---------------------------------------------------------------------------

class TestDownloadFromS3:
    def test_calls_download_file(self):
        client = MagicMock()
        download_from_s3(client, "my-bucket", "2015/clip.mp4", "/tmp/clip.mp4")
        client.download_file.assert_called_once_with(
            "my-bucket", "2015/clip.mp4", "/tmp/clip.mp4"
        )


# ---------------------------------------------------------------------------
# upload_to_s3
# ---------------------------------------------------------------------------

class TestUploadToS3:
    def test_calls_put_object(self):
        client = MagicMock()
        upload_to_s3(client, "my-bucket", "2015/clip.md", "# Title\n\nText\n", "text/markdown")
        client.put_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="2015/clip.md",
            Body="# Title\n\nText\n".encode("utf-8"),
            ContentType="text/markdown",
        )

    def test_utf8_encoding(self):
        client = MagicMock()
        content = "Héllo wörld — ñ"
        upload_to_s3(client, "b", "k", content, "text/plain")
        call_args = client.put_object.call_args
        assert call_args.kwargs["Body"] == content.encode("utf-8")

    def test_content_type_json(self):
        client = MagicMock()
        upload_to_s3(client, "b", "k.json", '{"a":1}', "application/json")
        call_args = client.put_object.call_args
        assert call_args.kwargs["ContentType"] == "application/json"


# ---------------------------------------------------------------------------
# process_file
# ---------------------------------------------------------------------------

class TestProcessFile:
    """Unit tests for process_file orchestration."""

    def _make_mocks(self):
        """Return (s3_client, model) mocks with sensible defaults."""
        s3_client = MagicMock()
        model = MagicMock()
        model.transcribe.return_value = {"text": "Hello world transcript"}
        return s3_client, model

    @patch("s3_video_transcribe.extract_video_date", return_value="2015-03-13T08:58:54Z")
    def test_successful_transcription_flow(self, mock_date, tmp_path):
        """Full success path: downloads, probes, transcribes, uploads .md and .md.metadata.json, returns record."""
        s3_client, model = self._make_mocks()
        temp_dir = str(tmp_path / "tmp")

        result = process_file(
            s3_key="2015/VID_20150313.mp4",
            last_modified=datetime(2025, 3, 24, 20, 0, 0, tzinfo=timezone.utc),
            s3_client=s3_client,
            bucket="mw-family-videos-1",
            temp_dir=temp_dir,
            model=model,
        )

        # Should return a progress record
        assert result is not None
        assert result["source_key"] == "2015/VID_20150313.mp4"
        assert result["transcript_key"] == "2015/VID_20150313.md"
        assert result["metadata_key"] == "2015/VID_20150313.md.metadata.json"
        assert "timestamp" in result

        # Should have downloaded the file
        s3_client.download_file.assert_called_once_with(
            "mw-family-videos-1", "2015/VID_20150313.mp4",
            os.path.join(temp_dir, "VID_20150313.mp4"),
        )

        # Should have transcribed
        model.transcribe.assert_called_once()

        # Should have uploaded two files (transcript .md and metadata .json)
        assert s3_client.put_object.call_count == 2
        upload_calls = s3_client.put_object.call_args_list

        # First upload: transcript .md
        md_call = upload_calls[0]
        assert md_call.kwargs["Key"] == "2015/VID_20150313.md"
        assert md_call.kwargs["ContentType"] == "text/markdown"

        # Second upload: metadata .md.metadata.json
        meta_call = upload_calls[1]
        assert meta_call.kwargs["Key"] == "2015/VID_20150313.md.metadata.json"
        assert meta_call.kwargs["ContentType"] == "application/json"

    @patch("s3_video_transcribe.extract_video_date", return_value="")
    def test_successful_flow_mp4_already_mp4(self, mock_date, tmp_path):
        """Verify the flow works for a plain mp4 file at root level."""
        s3_client, model = self._make_mocks()
        temp_dir = str(tmp_path / "tmp")

        result = process_file(
            s3_key="clip.mp4",
            last_modified=datetime(2025, 1, 1, tzinfo=timezone.utc),
            s3_client=s3_client,
            bucket="bucket",
            temp_dir=temp_dir,
            model=model,
        )

        assert result is not None
        assert result["source_key"] == "clip.mp4"
        assert result["transcript_key"] == "clip.md"
        assert result["metadata_key"] == "clip.md.metadata.json"
        assert s3_client.put_object.call_count == 2

    @patch("s3_video_transcribe.extract_video_date", return_value="")
    def test_empty_transcript_returns_none(self, mock_date, tmp_path):
        """When Whisper returns empty text, process_file returns None and does no uploads."""
        s3_client = MagicMock()
        model = MagicMock()
        model.transcribe.return_value = {"text": ""}
        temp_dir = str(tmp_path / "tmp")

        result = process_file(
            s3_key="2015/silent.mp4",
            last_modified=datetime(2025, 1, 1, tzinfo=timezone.utc),
            s3_client=s3_client,
            bucket="bucket",
            temp_dir=temp_dir,
            model=model,
        )

        assert result is None
        # No uploads should have happened
        s3_client.put_object.assert_not_called()

    def test_download_failure_returns_none(self, tmp_path, caplog):
        """When S3 download fails, process_file returns None and logs error."""
        s3_client = MagicMock()
        s3_client.download_file.side_effect = Exception("Network error")
        model = MagicMock()
        temp_dir = str(tmp_path / "tmp")

        with caplog.at_level(logging.ERROR):
            result = process_file(
                s3_key="2015/broken.mp4",
                last_modified=datetime(2025, 1, 1, tzinfo=timezone.utc),
                s3_client=s3_client,
                bucket="bucket",
                temp_dir=temp_dir,
                model=model,
            )

        assert result is None
        assert "2015/broken.mp4" in caplog.text
        # Transcription should not have been attempted
        model.transcribe.assert_not_called()

    @patch("s3_video_transcribe.extract_video_date", return_value="")
    def test_transcription_exception_returns_none(self, mock_date, tmp_path, caplog):
        """When Whisper raises an exception, process_file returns None."""
        s3_client = MagicMock()
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("GPU OOM")
        temp_dir = str(tmp_path / "tmp")

        with caplog.at_level(logging.ERROR):
            result = process_file(
                s3_key="2015/oom.mp4",
                last_modified=datetime(2025, 1, 1, tzinfo=timezone.utc),
                s3_client=s3_client,
                bucket="bucket",
                temp_dir=temp_dir,
                model=model,
            )

        assert result is None
        # No uploads should have happened
        s3_client.put_object.assert_not_called()
