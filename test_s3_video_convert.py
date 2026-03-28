"""Unit tests for is_video_file, resolve_dest_key, load_progress, save_progress,
scan_source_bucket, and extract_year_from_metadata."""

import json
import logging
import pytest
from unittest.mock import MagicMock, patch
from s3_video_convert import (
    is_video_file,
    resolve_dest_key,
    load_progress,
    save_progress,
    scan_source_bucket,
    extract_year_from_metadata,
    download_from_s3,
    upload_to_s3,
    convert_to_mp4,
    process_file,
)


# ---------------------------------------------------------------------------
# is_video_file
# ---------------------------------------------------------------------------

class TestIsVideoFile:
    """Tests for is_video_file."""

    @pytest.mark.parametrize("key", [
        "folder/clip.mp4",
        "folder/clip.mov",
        "folder/clip.mts",
        "folder/clip.m2ts",
        "folder/clip.avi",
        "folder/clip.wmv",
        "folder/clip.mpg",
        "folder/clip.mpeg",
        "folder/clip.flv",
        "folder/clip.mkv",
        "folder/clip.3gp",
        "folder/clip.webm",
        "folder/clip.vob",
        "folder/clip.ts",
    ])
    def test_known_video_extensions(self, key):
        assert is_video_file(key) is True

    @pytest.mark.parametrize("key", [
        "folder/photo.jpg",
        "folder/photo.png",
        "folder/doc.pdf",
        "folder/archive.zip",
        "folder/data.db",
        "folder/readme.txt",
    ])
    def test_non_video_extensions(self, key):
        assert is_video_file(key) is False

    def test_no_extension(self):
        assert is_video_file("folder/README") is False

    @pytest.mark.parametrize("key", [
        "folder/clip.MOV",
        "folder/clip.Mov",
        "folder/clip.MTS",
        "folder/clip.Mp4",
    ])
    def test_mixed_case(self, key):
        assert is_video_file(key) is True

    def test_multiple_dots(self):
        assert is_video_file("folder/file.backup.mov") is True
        assert is_video_file("folder/file.backup.jpg") is False


# ---------------------------------------------------------------------------
# resolve_dest_key
# ---------------------------------------------------------------------------

class TestResolveDestKey:
    """Tests for resolve_dest_key."""

    def test_basic_with_year(self):
        assert resolve_dest_key("2015", "clip", set()) == "2015/clip.mp4"

    def test_none_year(self):
        assert resolve_dest_key(None, "clip", set()) == "unknown-year/clip.mp4"

    def test_collision_one_existing(self):
        existing = {"2020/clip.mp4"}
        result = resolve_dest_key("2020", "clip", existing)
        assert result == "2020/clip_1.mp4"

    def test_collision_multiple_existing(self):
        existing = {"2020/clip.mp4", "2020/clip_1.mp4", "2020/clip_2.mp4"}
        result = resolve_dest_key("2020", "clip", existing)
        assert result == "2020/clip_3.mp4"

    def test_collision_logs_warning(self, caplog):
        existing = {"2020/clip.mp4"}
        with caplog.at_level(logging.WARNING):
            resolve_dest_key("2020", "clip", existing)
        assert "collision" in caplog.text.lower()


# ---------------------------------------------------------------------------
# load_progress
# ---------------------------------------------------------------------------

class TestLoadProgress:
    """Tests for load_progress."""

    def test_missing_file(self, tmp_path):
        result = load_progress(str(tmp_path / "nonexistent.json"))
        assert result == {"completed": []}

    def test_empty_file(self, tmp_path):
        state_file = tmp_path / "empty.json"
        state_file.write_text("")
        result = load_progress(str(state_file))
        assert result == {"completed": []}

    def test_corrupted_json(self, tmp_path, caplog):
        state_file = tmp_path / "bad.json"
        state_file.write_text("{not valid json!!!")
        with caplog.at_level(logging.WARNING):
            result = load_progress(str(state_file))
        assert result == {"completed": []}
        assert "corrupted" in caplog.text.lower()

    def test_valid_state_file(self, tmp_path):
        state_file = tmp_path / "state.json"
        data = {
            "completed": [
                {
                    "source_key": "Photos/2015/clip.MOV",
                    "dest_key": "2015/clip.mp4",
                    "timestamp": "2025-07-14T10:30:00Z",
                }
            ]
        }
        state_file.write_text(json.dumps(data))
        result = load_progress(str(state_file))
        assert result == data


# ---------------------------------------------------------------------------
# save_progress
# ---------------------------------------------------------------------------

class TestSaveProgress:
    """Tests for save_progress."""

    def test_write_and_read_back(self, tmp_path):
        state_file = str(tmp_path / "state.json")
        data = {
            "completed": [
                {
                    "source_key": "Videos/trip.avi",
                    "dest_key": "2020/trip.mp4",
                    "timestamp": "2025-07-14T12:00:00Z",
                }
            ]
        }
        save_progress(state_file, data)
        with open(state_file, "r", encoding="utf-8") as f:
            written = json.load(f)
        assert written == data

    def test_round_trip(self, tmp_path):
        state_file = str(tmp_path / "rt.json")
        data = {"completed": []}
        save_progress(state_file, data)
        loaded = load_progress(state_file)
        assert loaded == data


# ---------------------------------------------------------------------------
# scan_source_bucket
# ---------------------------------------------------------------------------

class TestScanSourceBucket:
    """Tests for scan_source_bucket."""

    def _make_paginator(self, pages):
        """Build a mock S3 client whose get_paginator returns pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = pages
        mock_client.get_paginator.return_value = mock_paginator
        return mock_client

    def test_mixed_video_and_non_video(self):
        pages = [
            {
                "Contents": [
                    {"Key": "photos/pic.jpg"},
                    {"Key": "videos/clip.mp4"},
                    {"Key": "videos/clip.MOV"},
                    {"Key": "docs/readme.txt"},
                ]
            }
        ]
        client = self._make_paginator(pages)
        result = scan_source_bucket(client, "my-bucket")
        assert result == ["videos/clip.mp4", "videos/clip.MOV"]
        client.get_paginator.assert_called_once_with("list_objects_v2")

    def test_empty_bucket(self):
        pages = [{}]  # no Contents key
        client = self._make_paginator(pages)
        result = scan_source_bucket(client, "my-bucket")
        assert result == []

    def test_all_non_video(self):
        pages = [
            {
                "Contents": [
                    {"Key": "photo.jpg"},
                    {"Key": "doc.pdf"},
                    {"Key": "archive.zip"},
                ]
            }
        ]
        client = self._make_paginator(pages)
        result = scan_source_bucket(client, "my-bucket")
        assert result == []

    def test_multiple_pages(self):
        pages = [
            {"Contents": [{"Key": "a/clip.avi"}]},
            {"Contents": [{"Key": "b/photo.png"}, {"Key": "b/movie.mkv"}]},
        ]
        client = self._make_paginator(pages)
        result = scan_source_bucket(client, "my-bucket")
        assert result == ["a/clip.avi", "b/movie.mkv"]

    def test_logs_totals_at_info(self, caplog):
        pages = [
            {
                "Contents": [
                    {"Key": "vid.mp4"},
                    {"Key": "pic.jpg"},
                    {"Key": "vid2.mov"},
                ]
            }
        ]
        client = self._make_paginator(pages)
        with caplog.at_level(logging.INFO):
            scan_source_bucket(client, "my-bucket")
        assert "2 video files found" in caplog.text
        assert "1 non-video files skipped" in caplog.text

    def test_logs_skipped_at_debug(self, caplog):
        pages = [{"Contents": [{"Key": "pic.jpg"}]}]
        client = self._make_paginator(pages)
        with caplog.at_level(logging.DEBUG):
            scan_source_bucket(client, "my-bucket")
        assert "Skipping non-video file: pic.jpg" in caplog.text


# ---------------------------------------------------------------------------
# extract_year_from_metadata
# ---------------------------------------------------------------------------

class TestExtractYearFromMetadata:
    """Tests for extract_year_from_metadata."""

    def _ffprobe_result(self, tags):
        """Build a mock subprocess.CompletedProcess with ffprobe JSON output."""
        probe_output = json.dumps({"format": {"tags": tags}})
        return MagicMock(stdout=probe_output, returncode=0)

    @patch("s3_video_convert.subprocess.run")
    def test_creation_time(self, mock_run):
        mock_run.return_value = self._ffprobe_result(
            {"creation_time": "2015-06-20T14:30:00.000000Z"}
        )
        assert extract_year_from_metadata("/tmp/clip.mp4") == "2015"

    @patch("s3_video_convert.subprocess.run")
    def test_date_field_only(self, mock_run):
        mock_run.return_value = self._ffprobe_result({"date": "2018"})
        assert extract_year_from_metadata("/tmp/clip.mp4") == "2018"

    @patch("s3_video_convert.subprocess.run")
    def test_no_tags(self, mock_run):
        probe_output = json.dumps({"format": {}})
        mock_run.return_value = MagicMock(stdout=probe_output, returncode=0)
        assert extract_year_from_metadata("/tmp/clip.mp4") is None

    @patch("s3_video_convert.subprocess.run")
    def test_ffprobe_failure(self, mock_run):
        import subprocess as sp
        mock_run.side_effect = sp.CalledProcessError(1, "ffprobe")
        assert extract_year_from_metadata("/tmp/clip.mp4") is None

    @patch("s3_video_convert.subprocess.run")
    def test_invalid_json(self, mock_run):
        mock_run.return_value = MagicMock(stdout="not json at all", returncode=0)
        assert extract_year_from_metadata("/tmp/clip.mp4") is None

    @patch("s3_video_convert.subprocess.run")
    def test_field_priority_creation_time_over_date(self, mock_run):
        mock_run.return_value = self._ffprobe_result(
            {
                "creation_time": "2015-06-20T14:30:00Z",
                "date": "2020",
                "encoded_date": "UTC 2019-01-01 00:00:00",
            }
        )
        assert extract_year_from_metadata("/tmp/clip.mp4") == "2015"

    @patch("s3_video_convert.subprocess.run")
    def test_encoded_date_fallback(self, mock_run):
        mock_run.return_value = self._ffprobe_result(
            {"encoded_date": "UTC 2019-01-01 00:00:00"}
        )
        assert extract_year_from_metadata("/tmp/clip.mp4") == "2019"

    @patch("s3_video_convert.subprocess.run")
    def test_no_valid_year_in_tags(self, mock_run):
        mock_run.return_value = self._ffprobe_result(
            {"creation_time": "no-year-here", "date": "abc"}
        )
        assert extract_year_from_metadata("/tmp/clip.mp4") is None


# ---------------------------------------------------------------------------
# download_from_s3
# ---------------------------------------------------------------------------

class TestDownloadFromS3:
    """Tests for download_from_s3."""

    def test_calls_download_file_with_correct_args(self):
        mock_client = MagicMock()
        download_from_s3(mock_client, "my-bucket", "videos/clip.mov", "/tmp/clip.mov")
        mock_client.download_file.assert_called_once_with(
            "my-bucket", "videos/clip.mov", "/tmp/clip.mov"
        )


# ---------------------------------------------------------------------------
# upload_to_s3
# ---------------------------------------------------------------------------

class TestUploadToS3:
    """Tests for upload_to_s3."""

    def test_calls_upload_file_with_correct_args(self):
        mock_client = MagicMock()
        upload_to_s3(mock_client, "dest-bucket", "2015/clip.mp4", "/tmp/clip.mp4")
        mock_client.upload_file.assert_called_once_with(
            "/tmp/clip.mp4", "dest-bucket", "2015/clip.mp4"
        )


# ---------------------------------------------------------------------------
# convert_to_mp4
# ---------------------------------------------------------------------------

class TestConvertToMp4:
    """Tests for convert_to_mp4."""

    @patch("s3_video_convert.subprocess.run")
    def test_success_returns_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = convert_to_mp4("/tmp/input.mov", "/tmp/output.mp4")
        assert result is True
        mock_run.assert_called_once_with(
            [
                "ffmpeg", "-i", "/tmp/input.mov",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-movflags", "+faststart",
                "-y", "/tmp/output.mp4",
            ],
            capture_output=True,
            text=True,
        )

    @patch("s3_video_convert.subprocess.run")
    def test_failure_returns_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="some ffmpeg error")
        result = convert_to_mp4("/tmp/input.mov", "/tmp/output.mp4")
        assert result is False

    @patch("s3_video_convert.subprocess.run")
    def test_failure_logs_error(self, mock_run, caplog):
        mock_run.return_value = MagicMock(returncode=1, stderr="codec not found")
        with caplog.at_level(logging.ERROR):
            convert_to_mp4("/tmp/input.mov", "/tmp/output.mp4")
        assert "ffmpeg conversion failed" in caplog.text
        assert "codec not found" in caplog.text


# ---------------------------------------------------------------------------
# process_file
# ---------------------------------------------------------------------------

class TestProcessFile:
    """Tests for process_file."""

    @patch("s3_video_convert.upload_to_s3")
    @patch("s3_video_convert.convert_to_mp4", return_value=True)
    @patch("s3_video_convert.extract_year_from_metadata", return_value="2015")
    @patch("s3_video_convert.download_from_s3")
    @patch("s3_video_convert.os.remove")
    @patch("s3_video_convert.os.path.exists", return_value=True)
    def test_successful_conversion_flow(
        self, mock_exists, mock_remove, mock_download, mock_probe, mock_convert, mock_upload, tmp_path
    ):
        """Non-mp4 file: downloads, probes, converts, uploads, returns record."""
        s3_src = MagicMock()
        s3_dst = MagicMock()
        existing = set()
        temp_dir = str(tmp_path / "temp")

        result = process_file(
            source_key="videos/clip.mov",
            s3_source=s3_src,
            s3_dest=s3_dst,
            temp_dir=temp_dir,
            dest_bucket="dest-bucket",
            existing_dest_keys=existing,
            source_bucket="src-bucket",
        )

        assert result is not None
        assert result["source_key"] == "videos/clip.mov"
        assert result["dest_key"] == "2015/clip.mp4"
        assert "timestamp" in result

        mock_download.assert_called_once()
        mock_probe.assert_called_once()
        mock_convert.assert_called_once()
        mock_upload.assert_called_once_with(s3_dst, "dest-bucket", "2015/clip.mp4", mock_upload.call_args[0][3])
        assert "2015/clip.mp4" in existing

    @patch("s3_video_convert.upload_to_s3")
    @patch("s3_video_convert.convert_to_mp4")
    @patch("s3_video_convert.extract_year_from_metadata", return_value="2020")
    @patch("s3_video_convert.download_from_s3")
    @patch("s3_video_convert.os.remove")
    @patch("s3_video_convert.os.path.exists", return_value=True)
    def test_successful_copy_flow(
        self, mock_exists, mock_remove, mock_download, mock_probe, mock_convert, mock_upload, tmp_path
    ):
        """Mp4 file: downloads, probes, uploads (no conversion), returns record."""
        s3_src = MagicMock()
        s3_dst = MagicMock()
        existing = set()
        temp_dir = str(tmp_path / "temp")

        result = process_file(
            source_key="videos/clip.mp4",
            s3_source=s3_src,
            s3_dest=s3_dst,
            temp_dir=temp_dir,
            dest_bucket="dest-bucket",
            existing_dest_keys=existing,
            source_bucket="src-bucket",
        )

        assert result is not None
        assert result["source_key"] == "videos/clip.mp4"
        assert result["dest_key"] == "2020/clip.mp4"
        mock_convert.assert_not_called()
        mock_upload.assert_called_once()
        assert "2020/clip.mp4" in existing

    @patch("s3_video_convert.download_from_s3", side_effect=Exception("S3 download error"))
    @patch("s3_video_convert.os.remove")
    @patch("s3_video_convert.os.path.exists", return_value=False)
    def test_download_failure_returns_none(self, mock_exists, mock_remove, mock_download, tmp_path, caplog):
        """Download failure: returns None, logs error."""
        s3_src = MagicMock()
        s3_dst = MagicMock()
        temp_dir = str(tmp_path / "temp")

        with caplog.at_level(logging.ERROR):
            result = process_file(
                source_key="videos/clip.mov",
                s3_source=s3_src,
                s3_dest=s3_dst,
                temp_dir=temp_dir,
                dest_bucket="dest-bucket",
                existing_dest_keys=set(),
                source_bucket="src-bucket",
            )

        assert result is None
        assert "videos/clip.mov" in caplog.text

    @patch("s3_video_convert.upload_to_s3")
    @patch("s3_video_convert.convert_to_mp4", return_value=False)
    @patch("s3_video_convert.extract_year_from_metadata", return_value="2015")
    @patch("s3_video_convert.download_from_s3")
    @patch("s3_video_convert.os.remove")
    @patch("s3_video_convert.os.path.exists", return_value=True)
    def test_conversion_failure_returns_none(
        self, mock_exists, mock_remove, mock_download, mock_probe, mock_convert, mock_upload, tmp_path
    ):
        """Conversion failure: returns None, no upload."""
        s3_src = MagicMock()
        s3_dst = MagicMock()
        temp_dir = str(tmp_path / "temp")

        result = process_file(
            source_key="videos/clip.mov",
            s3_source=s3_src,
            s3_dest=s3_dst,
            temp_dir=temp_dir,
            dest_bucket="dest-bucket",
            existing_dest_keys=set(),
            source_bucket="src-bucket",
        )

        assert result is None
        mock_upload.assert_not_called()
