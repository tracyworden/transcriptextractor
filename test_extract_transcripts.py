"""
Unit and property-based tests for YouTube Transcript Extractor.

Tests verify correctness properties and edge cases for the extraction system.
"""

import pytest
from hypothesis import given, strategies as st
import json
import os
from extract_transcripts import (
    get_channel_videos,
    load_processed_records,
    save_processed_records,
    extract_transcript,
    extract_metadata,
    save_transcript,
    save_metadata,
    update_processed_records,
    save_transcript_with_storage,
    StorageConfig,
    S3Config
)


# Unit tests will be added in later tasks


# Unit tests for extract_transcript() function
class TestExtractTranscript:
    """Tests for extract_transcript() function."""
    
    def test_extract_video_id_from_url(self):
        """Test that video ID is correctly extracted from URL."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually with a real video URL that has transcripts:
        # video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # video_id, transcript_text, language_code = extract_transcript(video_url)
        # assert video_id == "dQw4w9WgXcQ"
        # assert isinstance(transcript_text, str)
        # assert len(transcript_text) > 0
        # assert language_code == "en"
        pass
    
    def test_extract_transcript_returns_tuple(self):
        """Test that extract_transcript returns a tuple of three elements."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually:
        # video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # result = extract_transcript(video_url)
        # assert isinstance(result, tuple)
        # assert len(result) == 3
        # video_id, transcript_text, language_code = result
        # assert isinstance(video_id, str)
        # assert isinstance(transcript_text, str)
        # assert isinstance(language_code, str)
        pass
    
    def test_extract_transcript_raises_on_invalid_url(self):
        """Test that extract_transcript raises exception for invalid URL."""
        # This test can be run without network access
        with pytest.raises(Exception) as exc_info:
            extract_transcript("https://www.youtube.com/watch?v=INVALID")
        assert "Could not extract video ID" in str(exc_info.value) or "transcript" in str(exc_info.value).lower()
    
    def test_extract_transcript_raises_on_no_transcript(self):
        """Test that extract_transcript raises exception when transcript unavailable."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually with a video URL that has no transcripts:
        # video_url = "https://www.youtube.com/watch?v=NOTRANSCRIPT"
        # with pytest.raises(Exception) as exc_info:
        #     extract_transcript(video_url)
        # assert "No transcript available" in str(exc_info.value)
        pass


# Unit tests for get_channel_videos() function
class TestGetChannelVideos:
    """Tests for get_channel_videos() function."""
    
    def test_channel_url_with_handle(self):
        """Test that channel handle is converted to full URL."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually:
        # channel_url = "@MachiningCloud"
        # videos = get_channel_videos(channel_url)
        # assert isinstance(videos, list)
        # assert len(videos) > 0
        # assert all(url.startswith('https://') for url in videos)
        pass
    
    def test_channel_url_with_full_url(self):
        """Test that full URL is handled correctly."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually:
        # channel_url = "https://www.youtube.com/@MachiningCloud"
        # videos = get_channel_videos(channel_url)
        # assert isinstance(videos, list)
        # assert len(videos) > 0
        pass


# Unit tests for update_processed_records() function
class TestUpdateProcessedRecords:
    """Tests for update_processed_records() function."""
    
    def test_create_file_if_not_exists(self, tmp_path):
        """Test that processed.json is created if it doesn't exist."""
        filepath = tmp_path / "processed.json"
        video_url = "https://www.youtube.com/watch?v=TEST1234567"
        video_id = "TEST1234567"
        
        assert not filepath.exists()
        update_processed_records(str(filepath), video_url, video_id)
        assert filepath.exists()
        
        with open(filepath, 'r') as f:
            data = json.load(f)
            assert len(data['processed']) == 1
            assert data['processed'][0] == {'url': video_url, 'filename': f'{video_id}.md'}
    
    def test_append_to_existing_file(self, tmp_path):
        """Test that new record is appended to existing processed.json."""
        filepath = tmp_path / "processed.json"
        existing = [{"url": "https://www.youtube.com/watch?v=EXISTING1234", "filename": "EXISTING1234.md"}]
        save_processed_records(str(filepath), existing)
        
        new_url = "https://www.youtube.com/watch?v=NEW12345678"
        update_processed_records(str(filepath), new_url, "NEW12345678")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
            assert len(data['processed']) == 2
    
    def test_preserve_existing_entries(self, tmp_path):
        """Test that existing entries are preserved when appending."""
        filepath = tmp_path / "processed.json"
        existing = [
            {"url": "https://www.youtube.com/watch?v=VIDEO1_____", "filename": "VIDEO1_____.md"},
            {"url": "https://www.youtube.com/watch?v=VIDEO2_____", "filename": "VIDEO2_____.md"},
        ]
        save_processed_records(str(filepath), existing)
        
        update_processed_records(str(filepath), "https://www.youtube.com/watch?v=VIDEO3_____", "VIDEO3_____")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
            assert len(data['processed']) == 3
            filenames = [r['filename'] for r in data['processed']]
            assert "VIDEO1_____.md" in filenames
            assert "VIDEO2_____.md" in filenames
            assert "VIDEO3_____.md" in filenames
    
    def test_empty_url_raises_valueerror(self, tmp_path):
        """Test that empty URL raises ValueError."""
        filepath = tmp_path / "processed.json"
        save_processed_records(str(filepath), [])
        
        with pytest.raises(ValueError):
            update_processed_records(str(filepath), "", "somevideoid")
    
    def test_handle_corrupted_json(self, tmp_path):
        """Test that corrupted JSON is handled gracefully."""
        filepath = tmp_path / "processed.json"
        with open(filepath, 'w') as f:
            f.write("{invalid json content")
        
        update_processed_records(str(filepath), "https://www.youtube.com/watch?v=NEW12345678", "NEW12345678")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
            assert len(data['processed']) == 1


# Unit tests for extract_metadata() function
class TestExtractMetadata:
    """Tests for extract_metadata() function."""
    
    def test_extract_metadata_returns_dict(self):
        """Test that extract_metadata returns a dictionary with required fields."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually with a real video URL:
        # video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # metadata = extract_metadata(video_url)
        # assert isinstance(metadata, dict)
        # assert 'video_id' in metadata
        # assert 'title' in metadata
        # assert 'url' in metadata
        # assert 'upload_date' in metadata
        # assert 'playlists' in metadata
        # assert 'transcript_language' in metadata
        # assert 'processed_timestamp' in metadata
        pass
    
    def test_extract_metadata_has_all_required_fields(self):
        """Test that metadata contains all required fields."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually:
        # video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # metadata = extract_metadata(video_url)
        # required_fields = ['video_id', 'title', 'url', 'upload_date', 'playlists', 'transcript_language', 'processed_timestamp']
        # for field in required_fields:
        #     assert field in metadata, f"Missing required field: {field}"
        pass
    
    def test_extract_metadata_playlists_is_list(self):
        """Test that playlists field is a list."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually:
        # video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # metadata = extract_metadata(video_url)
        # assert isinstance(metadata['playlists'], list)
        pass
    
    def test_extract_metadata_transcript_language_default(self):
        """Test that transcript_language defaults to 'en'."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually:
        # video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # metadata = extract_metadata(video_url)
        # assert metadata['transcript_language'] == 'en'
        pass
    
    def test_extract_metadata_processed_timestamp_format(self):
        """Test that processed_timestamp is in ISO 8601 format."""
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually:
        # from datetime import datetime
        # video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        # metadata = extract_metadata(video_url)
        # timestamp = metadata['processed_timestamp']
        # assert timestamp.endswith('Z'), "Timestamp should end with 'Z' for UTC"
        # # Verify it can be parsed as ISO 8601
        # datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        pass
    
    def test_extract_metadata_raises_on_invalid_url(self):
        """Test that extract_metadata raises exception for invalid URL."""
        # This test can be run without network access
        with pytest.raises(Exception) as exc_info:
            extract_metadata("https://www.youtube.com/watch?v=INVALID")
        assert "metadata" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


# Property-based tests will be added in later tasks


# Unit tests for save_transcript() function
class TestSaveTranscript:
    """Tests for save_transcript() function."""
    
    def test_save_transcript_creates_file(self, tmp_path):
        """Test that save_transcript creates a markdown file."""
        video_id = "TEST123"
        title = "Test Video Title"
        transcript = "This is a test transcript."
        output_dir = str(tmp_path)
        
        # Call function
        save_transcript(video_id, title, transcript, output_dir)
        
        # Verify file exists
        filepath = tmp_path / f"{video_id}.md"
        assert filepath.exists()
    
    def test_save_transcript_correct_format(self, tmp_path):
        """Test that transcript file has correct markdown format."""
        video_id = "TEST456"
        title = "My Test Video"
        transcript = "This is the transcript content."
        output_dir = str(tmp_path)
        
        # Call function
        save_transcript(video_id, title, transcript, output_dir)
        
        # Read and verify content
        filepath = tmp_path / f"{video_id}.md"
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        expected = f"# {title}\n\n{transcript}\n"
        assert content == expected
    
    def test_save_transcript_creates_directory(self, tmp_path):
        """Test that save_transcript creates output directory if it doesn't exist."""
        video_id = "TEST789"
        title = "Another Test"
        transcript = "More transcript content."
        output_dir = str(tmp_path / "subdir" / "nested")
        
        # Directory should not exist initially
        assert not os.path.exists(output_dir)
        
        # Call function
        save_transcript(video_id, title, transcript, output_dir)
        
        # Directory and file should now exist
        assert os.path.exists(output_dir)
        filepath = os.path.join(output_dir, f"{video_id}.md")
        assert os.path.exists(filepath)
    
    def test_save_transcript_handles_special_characters(self, tmp_path):
        """Test that save_transcript handles special characters in title and transcript."""
        video_id = "SPECIAL123"
        title = "Test & Title with <special> characters!"
        transcript = "Transcript with \"quotes\" and 'apostrophes' and unicode: \u00e9\u00e8\u00ea"
        output_dir = str(tmp_path)
        
        # Call function
        save_transcript(video_id, title, transcript, output_dir)
        
        # Read and verify content
        filepath = tmp_path / f"{video_id}.md"
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert title in content
        assert transcript in content
    
    def test_save_transcript_raises_ioerror_on_invalid_path(self, tmp_path):
        """Test that save_transcript raises IOError for invalid paths."""
        video_id = "ERROR123"
        title = "Error Test"
        transcript = "This should fail."
        # Create a file, then try to use it as a directory (should fail)
        invalid_file = tmp_path / "file.txt"
        invalid_file.write_text("existing file")
        output_dir = str(invalid_file / "subdir")  # Try to create directory inside a file
        
        with pytest.raises(IOError) as exc_info:
            save_transcript(video_id, title, transcript, output_dir)
        assert "Failed to write transcript file" in str(exc_info.value) or "Unexpected error" in str(exc_info.value)
    
    def test_save_transcript_overwrites_existing_file(self, tmp_path):
        """Test that save_transcript overwrites existing file."""
        video_id = "OVERWRITE123"
        title = "Original Title"
        transcript = "Original transcript."
        output_dir = str(tmp_path)
        
        # Create initial file
        save_transcript(video_id, title, transcript, output_dir)
        
        # Overwrite with new content
        new_title = "Updated Title"
        new_transcript = "Updated transcript content."
        save_transcript(video_id, new_title, new_transcript, output_dir)
        
        # Verify new content
        filepath = tmp_path / f"{video_id}.md"
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert new_title in content
        assert new_transcript in content
        assert title not in content
        assert transcript not in content


# Unit tests for save_metadata() function
class TestSaveMetadata:
    """Tests for save_metadata() function."""
    
    def test_save_metadata_creates_file(self, tmp_path):
        """Test that save_metadata creates a JSON file with AWS Bedrock naming."""
        video_id = "TEST123"
        metadata = {
            'video_id': video_id,
            'title': 'Test Video',
            'url': 'https://www.youtube.com/watch?v=TEST123',
            'upload_date': '20240115',
            'playlists': ['Playlist 1'],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-15T10:30:00Z'
        }
        output_dir = str(tmp_path)
        
        # Call function
        save_metadata(video_id, metadata, output_dir)
        
        # Verify file exists with correct naming: {video_id}.md.metadata.json
        filepath = tmp_path / f"{video_id}.md.metadata.json"
        assert filepath.exists()
    
    def test_save_metadata_correct_format(self, tmp_path):
        """Test that metadata file has correct JSON format with indentation."""
        video_id = "TEST456"
        metadata = {
            'video_id': video_id,
            'title': 'My Test Video',
            'url': 'https://www.youtube.com/watch?v=TEST456',
            'upload_date': '20240116',
            'playlists': ['Playlist A', 'Playlist B'],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-16T12:00:00Z'
        }
        output_dir = str(tmp_path)
        
        # Call function
        save_metadata(video_id, metadata, output_dir)
        
        # Read and verify content
        filepath = tmp_path / f"{video_id}.md.metadata.json"
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            loaded_metadata = json.loads(content)
        
        # Verify all fields are present and correct
        assert loaded_metadata == metadata
        
        # Verify indentation (should have 2 spaces)
        assert '  "video_id"' in content or '  "title"' in content
    
    def test_save_metadata_all_required_fields(self, tmp_path):
        """Test that all required fields are included in metadata file."""
        video_id = "REQUIRED123"
        metadata = {
            'video_id': video_id,
            'title': 'Complete Metadata Test',
            'url': 'https://www.youtube.com/watch?v=REQUIRED123',
            'upload_date': '20240117',
            'playlists': [],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-17T14:30:00Z'
        }
        output_dir = str(tmp_path)
        
        # Call function
        save_metadata(video_id, metadata, output_dir)
        
        # Read and verify all required fields
        filepath = tmp_path / f"{video_id}.md.metadata.json"
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_metadata = json.load(f)
        
        required_fields = ['video_id', 'title', 'url', 'upload_date', 'playlists', 'transcript_language', 'processed_timestamp']
        for field in required_fields:
            assert field in loaded_metadata, f"Missing required field: {field}"
    
    def test_save_metadata_playlists_is_array(self, tmp_path):
        """Test that playlists field is an array."""
        video_id = "ARRAY123"
        metadata = {
            'video_id': video_id,
            'title': 'Array Test',
            'url': 'https://www.youtube.com/watch?v=ARRAY123',
            'upload_date': '20240118',
            'playlists': ['Playlist 1', 'Playlist 2', 'Playlist 3'],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-18T16:00:00Z'
        }
        output_dir = str(tmp_path)
        
        # Call function
        save_metadata(video_id, metadata, output_dir)
        
        # Read and verify playlists is an array
        filepath = tmp_path / f"{video_id}.md.metadata.json"
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_metadata = json.load(f)
        
        assert isinstance(loaded_metadata['playlists'], list)
        assert len(loaded_metadata['playlists']) == 3
    
    def test_save_metadata_creates_directory(self, tmp_path):
        """Test that save_metadata creates output directory if it doesn't exist."""
        video_id = "DIR123"
        metadata = {
            'video_id': video_id,
            'title': 'Directory Test',
            'url': 'https://www.youtube.com/watch?v=DIR123',
            'upload_date': '20240119',
            'playlists': [],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-19T18:00:00Z'
        }
        output_dir = str(tmp_path / "subdir" / "nested")
        
        # Directory should not exist initially
        assert not os.path.exists(output_dir)
        
        # Call function
        save_metadata(video_id, metadata, output_dir)
        
        # Directory and file should now exist
        assert os.path.exists(output_dir)
        filepath = os.path.join(output_dir, f"{video_id}.md.metadata.json")
        assert os.path.exists(filepath)
    
    def test_save_metadata_handles_unicode(self, tmp_path):
        """Test that save_metadata handles unicode characters correctly."""
        video_id = "UNICODE123"
        metadata = {
            'video_id': video_id,
            'title': 'Test with unicode: \u00e9\u00e8\u00ea \u4e2d\u6587 \u0440\u0443\u0441\u0441\u043a\u0438\u0439',
            'url': 'https://www.youtube.com/watch?v=UNICODE123',
            'upload_date': '20240120',
            'playlists': ['Playlist \u00e9'],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-20T20:00:00Z'
        }
        output_dir = str(tmp_path)
        
        # Call function
        save_metadata(video_id, metadata, output_dir)
        
        # Read and verify unicode is preserved
        filepath = tmp_path / f"{video_id}.md.metadata.json"
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_metadata = json.load(f)
        
        assert loaded_metadata['title'] == metadata['title']
        assert loaded_metadata['playlists'][0] == metadata['playlists'][0]
    
    def test_save_metadata_raises_ioerror_on_missing_fields(self, tmp_path):
        """Test that save_metadata raises IOError when required fields are missing."""
        video_id = "MISSING123"
        # Missing 'title' field
        metadata = {
            'video_id': video_id,
            'url': 'https://www.youtube.com/watch?v=MISSING123',
            'upload_date': '20240121',
            'playlists': [],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-21T22:00:00Z'
        }
        output_dir = str(tmp_path)
        
        with pytest.raises(IOError) as exc_info:
            save_metadata(video_id, metadata, output_dir)
        assert "Missing required metadata fields" in str(exc_info.value) or "Invalid metadata" in str(exc_info.value)
    
    def test_save_metadata_raises_ioerror_on_invalid_playlists(self, tmp_path):
        """Test that save_metadata raises IOError when playlists is not an array."""
        video_id = "INVALID123"
        metadata = {
            'video_id': video_id,
            'title': 'Invalid Playlists Test',
            'url': 'https://www.youtube.com/watch?v=INVALID123',
            'upload_date': '20240122',
            'playlists': 'not an array',  # Should be a list
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-22T23:00:00Z'
        }
        output_dir = str(tmp_path)
        
        with pytest.raises(IOError) as exc_info:
            save_metadata(video_id, metadata, output_dir)
        assert "playlists field must be an array" in str(exc_info.value) or "Invalid metadata" in str(exc_info.value)
    
    def test_save_metadata_raises_ioerror_on_invalid_path(self, tmp_path):
        """Test that save_metadata raises IOError for invalid paths."""
        video_id = "ERROR123"
        metadata = {
            'video_id': video_id,
            'title': 'Error Test',
            'url': 'https://www.youtube.com/watch?v=ERROR123',
            'upload_date': '20240123',
            'playlists': [],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-23T10:00:00Z'
        }
        # Create a file, then try to use it as a directory (should fail)
        invalid_file = tmp_path / "file.txt"
        invalid_file.write_text("existing file")
        output_dir = str(invalid_file / "subdir")  # Try to create directory inside a file
        
        with pytest.raises(IOError) as exc_info:
            save_metadata(video_id, metadata, output_dir)
        assert "Failed to write metadata file" in str(exc_info.value) or "Unexpected error" in str(exc_info.value)
    
    def test_save_metadata_overwrites_existing_file(self, tmp_path):
        """Test that save_metadata overwrites existing file."""
        video_id = "OVERWRITE123"
        metadata = {
            'video_id': video_id,
            'title': 'Original Title',
            'url': 'https://www.youtube.com/watch?v=OVERWRITE123',
            'upload_date': '20240124',
            'playlists': ['Original Playlist'],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-24T11:00:00Z'
        }
        output_dir = str(tmp_path)
        
        # Create initial file
        save_metadata(video_id, metadata, output_dir)
        
        # Overwrite with new content
        new_metadata = {
            'video_id': video_id,
            'title': 'Updated Title',
            'url': 'https://www.youtube.com/watch?v=OVERWRITE123',
            'upload_date': '20240125',
            'playlists': ['Updated Playlist'],
            'transcript_language': 'en',
            'processed_timestamp': '2024-01-25T12:00:00Z'
        }
        save_metadata(video_id, new_metadata, output_dir)
        
        # Verify new content
        filepath = tmp_path / f"{video_id}.md.metadata.json"
        with open(filepath, 'r', encoding='utf-8') as f:
            loaded_metadata = json.load(f)
        
        assert loaded_metadata['title'] == 'Updated Title'
        assert loaded_metadata['upload_date'] == '20240125'
        assert loaded_metadata['playlists'] == ['Updated Playlist']


# Unit tests for main() function with command-line arguments
class TestMainFunction:
    """Tests for main() function with command-line arguments."""
    
    def test_main_accepts_channel_parameter(self):
        """Test that main() accepts channel parameter."""
        from extract_transcripts import main
        import inspect
        
        # Check that main() has the expected parameters
        sig = inspect.signature(main)
        params = list(sig.parameters.keys())
        
        assert 'channel' in params
        assert 'output_dir' in params
        assert 'processed_file' in params
        
        # Check default values
        assert sig.parameters['channel'].default == "@MachiningCloud"
        assert sig.parameters['output_dir'].default == "."
        assert sig.parameters['processed_file'].default == "processed.json"
    
    def test_main_parameters_have_correct_types(self):
        """Test that main() parameters have correct type annotations."""
        from extract_transcripts import main
        import inspect
        
        sig = inspect.signature(main)
        
        # Check type annotations
        assert sig.parameters['channel'].annotation == str
        assert sig.parameters['output_dir'].annotation == str
        assert sig.parameters['processed_file'].annotation == str


# Unit tests for Whisper fallback functionality
class TestWhisperFallback:
    """Tests for Whisper fallback functionality."""
    
    def test_whisper_fallback_disabled_by_default(self):
        """Test that Whisper fallback is disabled by default."""
        # This test verifies that when use_whisper_fallback is False (default),
        # an exception is raised when no YouTube transcript is available
        # This is a manual integration test - requires yt-dlp and network access
        # Uncomment to run manually with a video URL that has no transcripts:
        # video_url = "https://www.youtube.com/watch?v=NOTRANSCRIPT"
        # with pytest.raises(Exception) as exc_info:
        #     extract_transcript(video_url, use_whisper_fallback=False)
        # assert "No transcript available" in str(exc_info.value)
        pass
    
    def test_whisper_fallback_when_youtube_transcript_unavailable(self, tmp_path, monkeypatch):
        """Test that Whisper fallback is used when YouTube transcript is unavailable."""
        import subprocess
        from unittest.mock import Mock, patch, MagicMock
        
        # Mock video URL and ID
        video_url = "https://www.youtube.com/watch?v=TEST123"
        video_id = "TEST123"
        
        # Track whether Whisper was called
        whisper_called = False
        audio_file_path = None
        
        def mock_subprocess_run(*args, **kwargs):
            """Mock subprocess.run to simulate yt-dlp behavior."""
            nonlocal whisper_called, audio_file_path
            
            cmd = args[0] if args else kwargs.get('command', [])
            
            # Mock yt-dlp subtitle download (no subtitles available)
            if '--write-sub' in cmd or '--write-auto-sub' in cmd:
                # Return success but don't create subtitle file
                return Mock(stdout='', stderr='', returncode=0)
            
            # Mock yt-dlp audio download
            if '--extract-audio' in cmd:
                # Find the output path from -o argument
                try:
                    o_index = cmd.index('-o')
                    audio_file_path = cmd[o_index + 1]
                    # Create a dummy audio file
                    with open(audio_file_path, 'w') as f:
                        f.write('dummy audio')
                except (ValueError, IndexError):
                    pass
                return Mock(stdout='', stderr='', returncode=0, check=True)
            
            return Mock(stdout='', stderr='', returncode=0)
        
        def mock_whisper_load_model(model_name):
            """Mock Whisper model loading."""
            mock_model = Mock()
            
            def mock_transcribe(audio_path):
                """Mock Whisper transcription."""
                nonlocal whisper_called
                whisper_called = True
                return {"text": "This is a Whisper-generated transcript."}
            
            mock_model.transcribe = mock_transcribe
            return mock_model
        
        # Apply mocks - patch at the module level where whisper is imported
        with patch('extract_transcripts.subprocess.run', side_effect=mock_subprocess_run):
            with patch('extract_transcripts.whisper.load_model', side_effect=mock_whisper_load_model):
                with patch('extract_transcripts.tempfile.TemporaryDirectory') as mock_temp_dir:
                    # Set up temporary directory mock
                    temp_path = str(tmp_path / "temp")
                    os.makedirs(temp_path, exist_ok=True)
                    mock_temp_dir.return_value.__enter__.return_value = temp_path
                    
                    # Call extract_transcript with Whisper fallback enabled
                    result_video_id, transcript_text, language_code = extract_transcript(
                        video_url, 
                        use_whisper_fallback=True
                    )
                    
                    # Verify Whisper was called
                    assert whisper_called, "Whisper should have been called as fallback"
                    
                    # Verify result
                    assert result_video_id == video_id
                    assert "Whisper-generated transcript" in transcript_text
                    assert language_code == 'en'
    
    def test_audio_file_cleanup_after_transcription(self, tmp_path):
        """Test that audio file is deleted after Whisper transcription."""
        from unittest.mock import Mock, patch
        
        video_url = "https://www.youtube.com/watch?v=CLEANUP123"
        audio_file_created = False
        audio_file_deleted = False
        audio_file_path = None
        
        def mock_subprocess_run(*args, **kwargs):
            """Mock subprocess.run to simulate yt-dlp behavior."""
            nonlocal audio_file_created, audio_file_path
            
            cmd = args[0] if args else kwargs.get('command', [])
            
            # Mock yt-dlp subtitle download (no subtitles available)
            if '--write-sub' in cmd or '--write-auto-sub' in cmd:
                return Mock(stdout='', stderr='', returncode=0)
            
            # Mock yt-dlp audio download
            if '--extract-audio' in cmd:
                try:
                    o_index = cmd.index('-o')
                    audio_file_path = cmd[o_index + 1]
                    # Create a dummy audio file
                    with open(audio_file_path, 'w') as f:
                        f.write('dummy audio')
                    audio_file_created = True
                except (ValueError, IndexError):
                    pass
                return Mock(stdout='', stderr='', returncode=0, check=True)
            
            return Mock(stdout='', stderr='', returncode=0)
        
        def mock_whisper_load_model(model_name):
            """Mock Whisper model loading."""
            mock_model = Mock()
            mock_model.transcribe = lambda audio_path: {"text": "Transcribed text"}
            return mock_model
        
        original_os_remove = os.remove
        
        def mock_os_remove(path):
            """Mock os.remove to track file deletion."""
            nonlocal audio_file_deleted, audio_file_path
            if path == audio_file_path:
                audio_file_deleted = True
            # Actually remove the file
            original_os_remove(path)
        
        # Apply mocks
        with patch('subprocess.run', side_effect=mock_subprocess_run):
            with patch('whisper.load_model', side_effect=mock_whisper_load_model):
                with patch('os.remove', side_effect=mock_os_remove):
                    with patch('tempfile.TemporaryDirectory') as mock_temp_dir:
                        # Set up temporary directory mock
                        temp_path = str(tmp_path / "temp")
                        os.makedirs(temp_path, exist_ok=True)
                        mock_temp_dir.return_value.__enter__.return_value = temp_path
                        
                        # Call extract_transcript with Whisper fallback enabled
                        extract_transcript(video_url, use_whisper_fallback=True)
                        
                        # Verify audio file was created and then deleted
                        assert audio_file_created, "Audio file should have been created"
                        assert audio_file_deleted, "Audio file should have been deleted after transcription"
    
    def test_whisper_fallback_raises_on_empty_transcript(self, tmp_path):
        """Test that Whisper fallback raises exception when transcript is empty."""
        from unittest.mock import Mock, patch
        
        video_url = "https://www.youtube.com/watch?v=EMPTY123"
        
        def mock_subprocess_run(*args, **kwargs):
            """Mock subprocess.run to simulate yt-dlp behavior."""
            cmd = args[0] if args else kwargs.get('command', [])
            
            # Mock yt-dlp subtitle download (no subtitles available)
            if '--write-sub' in cmd or '--write-auto-sub' in cmd:
                return Mock(stdout='', stderr='', returncode=0)
            
            # Mock yt-dlp audio download
            if '--extract-audio' in cmd:
                try:
                    o_index = cmd.index('-o')
                    audio_file_path = cmd[o_index + 1]
                    # Create a dummy audio file
                    with open(audio_file_path, 'w') as f:
                        f.write('dummy audio')
                except (ValueError, IndexError):
                    pass
                return Mock(stdout='', stderr='', returncode=0, check=True)
            
            return Mock(stdout='', stderr='', returncode=0)
        
        def mock_whisper_load_model(model_name):
            """Mock Whisper model loading."""
            mock_model = Mock()
            # Return empty transcript
            mock_model.transcribe = lambda audio_path: {"text": ""}
            return mock_model
        
        # Apply mocks
        with patch('subprocess.run', side_effect=mock_subprocess_run):
            with patch('whisper.load_model', side_effect=mock_whisper_load_model):
                with patch('tempfile.TemporaryDirectory') as mock_temp_dir:
                    # Set up temporary directory mock
                    temp_path = str(tmp_path / "temp")
                    os.makedirs(temp_path, exist_ok=True)
                    mock_temp_dir.return_value.__enter__.return_value = temp_path
                    
                    # Call extract_transcript with Whisper fallback enabled
                    with pytest.raises(Exception) as exc_info:
                        extract_transcript(video_url, use_whisper_fallback=True)
                    
                    assert "empty transcript" in str(exc_info.value).lower()
    
    def test_main_function_accepts_use_whisper_fallback_parameter(self):
        """Test that main() function accepts use_whisper_fallback parameter."""
        from extract_transcripts import main
        import inspect
        
        # Check that main() has the use_whisper_fallback parameter
        sig = inspect.signature(main)
        params = list(sig.parameters.keys())
        
        assert 'use_whisper_fallback' in params
        
        # Check default value is False
        assert sig.parameters['use_whisper_fallback'].default == False
        
        # Check type annotation
        assert sig.parameters['use_whisper_fallback'].annotation == bool



class TestSaveTranscriptWithStorage:
    """Tests for save_transcript_with_storage() function."""
    
    def test_save_to_local_only(self, tmp_path):
        """Test saving transcript to local storage only."""
        output_dir = str(tmp_path / "transcripts")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=None)
        
        video_id = "dQw4w9WgXcQ"
        title = "Test Video"
        transcript = "This is a test transcript."
        
        # Should not raise any exception
        save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        # Verify file was created
        expected_file = os.path.join(output_dir, f"{video_id}.md")
        assert os.path.exists(expected_file)
        
        # Verify content
        with open(expected_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert content == f"# {title}\n\n{transcript}\n"
    
    def test_save_creates_directory_if_not_exists(self, tmp_path):
        """Test that local directory is created if it doesn't exist."""
        output_dir = str(tmp_path / "new_dir" / "transcripts")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=None)
        
        video_id = "test123"
        title = "Test"
        transcript = "Content"
        
        # Directory should not exist yet
        assert not os.path.exists(output_dir)
        
        save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        # Directory should now exist
        assert os.path.exists(output_dir)
        assert os.path.exists(os.path.join(output_dir, f"{video_id}.md"))
    
    def test_save_formats_content_correctly(self, tmp_path):
        """Test that content is formatted as markdown with title header."""
        output_dir = str(tmp_path / "transcripts")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=None)
        
        video_id = "abc123"
        title = "My Video Title"
        transcript = "Line 1\nLine 2\nLine 3"
        
        save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        expected_file = os.path.join(output_dir, f"{video_id}.md")
        with open(expected_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should have title as header, blank line, then transcript, then newline
        assert content.startswith(f"# {title}\n\n")
        assert content.endswith("\n")
        assert transcript in content
    
    def test_save_uses_correct_filename_format(self, tmp_path):
        """Test that filename follows {video_id}.md format."""
        output_dir = str(tmp_path / "transcripts")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=None)
        
        video_id = "xyz789"
        title = "Test"
        transcript = "Content"
        
        save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        # Check exact filename
        expected_filename = f"{video_id}.md"
        expected_path = os.path.join(output_dir, expected_filename)
        assert os.path.exists(expected_path)
    
    def test_save_raises_ioerror_when_all_destinations_fail(self, tmp_path, monkeypatch):
        """Test that IOError is raised when all enabled storage operations fail."""
        # Mock os.makedirs to raise an exception
        def mock_makedirs(path, exist_ok=False):
            raise PermissionError("Permission denied")
        
        import extract_transcripts
        monkeypatch.setattr(extract_transcripts.os, 'makedirs', mock_makedirs)
        
        output_dir = str(tmp_path / "transcripts")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=None)
        
        video_id = "test123"
        title = "Test"
        transcript = "Content"
        
        with pytest.raises(IOError) as exc_info:
            save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        assert "Failed to save transcript" in str(exc_info.value)
        assert video_id in str(exc_info.value)
    
    def test_save_handles_special_characters_in_title(self, tmp_path):
        """Test that special characters in title are preserved."""
        output_dir = str(tmp_path / "transcripts")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=None)
        
        video_id = "test123"
        title = "Test: Special & Characters <>"
        transcript = "Content"
        
        save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        expected_file = os.path.join(output_dir, f"{video_id}.md")
        with open(expected_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert title in content
    
    def test_save_handles_unicode_content(self, tmp_path):
        """Test that unicode characters are properly saved."""
        output_dir = str(tmp_path / "transcripts")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=None)
        
        video_id = "test123"
        title = "Test 日本語"
        transcript = "Content with émojis 🎉 and 中文"
        
        save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        expected_file = os.path.join(output_dir, f"{video_id}.md")
        with open(expected_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert title in content
        assert transcript in content
    
    def test_save_overwrites_existing_file(self, tmp_path):
        """Test that existing file is overwritten."""
        output_dir = str(tmp_path / "transcripts")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=None)
        
        video_id = "test123"
        title1 = "First Title"
        transcript1 = "First content"
        
        # Save first version
        save_transcript_with_storage(video_id, title1, transcript1, storage_config)
        
        # Save second version with different content
        title2 = "Second Title"
        transcript2 = "Second content"
        save_transcript_with_storage(video_id, title2, transcript2, storage_config)
        
        # Verify only second version exists
        expected_file = os.path.join(output_dir, f"{video_id}.md")
        with open(expected_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert title2 in content
        assert transcript2 in content
        assert title1 not in content
        assert transcript1 not in content
    
    def test_save_with_mock_s3_success(self, tmp_path, monkeypatch):
        """Test saving to S3 when upload succeeds."""
        # Mock upload_to_s3 to return True
        upload_called = []
        
        def mock_upload(file_content, s3_key, bucket_name, content_type, aws_profile):
            upload_called.append({
                'file_content': file_content,
                's3_key': s3_key,
                'bucket_name': bucket_name,
                'content_type': content_type,
                'aws_profile': aws_profile
            })
            return True
        
        import extract_transcripts
        monkeypatch.setattr(extract_transcripts, 'upload_to_s3', mock_upload)
        
        s3_config = S3Config(bucket_name="test-bucket", prefix="transcripts/", region="us-east-1")
        storage_config = StorageConfig(local_dir=None, s3_config=s3_config)
        
        video_id = "test123"
        title = "Test Video"
        transcript = "Test content"
        
        # Should not raise exception
        save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        # Verify upload was called
        assert len(upload_called) == 1
        assert upload_called[0]['bucket_name'] == "test-bucket"
        assert upload_called[0]['s3_key'] == "transcripts/test123.md"
        assert upload_called[0]['content_type'] == "text/markdown"
        assert f"# {title}\n\n{transcript}\n" == upload_called[0]['file_content']
    
    def test_save_with_mock_s3_removes_leading_slash(self, tmp_path, monkeypatch):
        """Test that leading slashes are removed from S3 keys."""
        upload_called = []
        
        def mock_upload(file_content, s3_key, bucket_name, content_type, aws_profile):
            upload_called.append({'s3_key': s3_key})
            return True
        
        import extract_transcripts
        monkeypatch.setattr(extract_transcripts, 'upload_to_s3', mock_upload)
        
        # Test with prefix that has leading slash
        s3_config = S3Config(bucket_name="test-bucket", prefix="/transcripts/", region="us-east-1")
        storage_config = StorageConfig(local_dir=None, s3_config=s3_config)
        
        video_id = "test123"
        save_transcript_with_storage(video_id, "Title", "Content", storage_config)
        
        # S3 key should not have leading slash
        assert not upload_called[0]['s3_key'].startswith('/')
        assert upload_called[0]['s3_key'] == "transcripts/test123.md"
    
    def test_save_with_mock_s3_empty_prefix(self, tmp_path, monkeypatch):
        """Test S3 upload with empty prefix."""
        upload_called = []
        
        def mock_upload(file_content, s3_key, bucket_name, content_type, aws_profile):
            upload_called.append({'s3_key': s3_key})
            return True
        
        import extract_transcripts
        monkeypatch.setattr(extract_transcripts, 'upload_to_s3', mock_upload)
        
        s3_config = S3Config(bucket_name="test-bucket", prefix="", region="us-east-1")
        storage_config = StorageConfig(local_dir=None, s3_config=s3_config)
        
        video_id = "test123"
        save_transcript_with_storage(video_id, "Title", "Content", storage_config)
        
        # S3 key should just be the filename
        assert upload_called[0]['s3_key'] == "test123.md"
    
    def test_save_with_mock_s3_failure_raises_ioerror(self, tmp_path, monkeypatch):
        """Test that IOError is raised when S3 upload fails."""
        def mock_upload(file_content, s3_key, bucket_name, content_type, aws_profile):
            return False
        
        import extract_transcripts
        monkeypatch.setattr(extract_transcripts, 'upload_to_s3', mock_upload)
        
        s3_config = S3Config(bucket_name="test-bucket", prefix="", region="us-east-1")
        storage_config = StorageConfig(local_dir=None, s3_config=s3_config)
        
        video_id = "test123"
        
        with pytest.raises(IOError) as exc_info:
            save_transcript_with_storage(video_id, "Title", "Content", storage_config)
        
        assert "Failed to save transcript" in str(exc_info.value)
        assert video_id in str(exc_info.value)
    
    def test_save_with_dual_storage_both_succeed(self, tmp_path, monkeypatch):
        """Test saving to both local and S3 when both succeed."""
        upload_called = []
        
        def mock_upload(file_content, s3_key, bucket_name, content_type, aws_profile):
            upload_called.append(True)
            return True
        
        import extract_transcripts
        monkeypatch.setattr(extract_transcripts, 'upload_to_s3', mock_upload)
        
        output_dir = str(tmp_path / "transcripts")
        s3_config = S3Config(bucket_name="test-bucket", prefix="", region="us-east-1")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=s3_config)
        
        video_id = "test123"
        title = "Test"
        transcript = "Content"
        
        # Should not raise exception
        save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        # Verify local file was created
        expected_file = os.path.join(output_dir, f"{video_id}.md")
        assert os.path.exists(expected_file)
        
        # Verify S3 upload was called
        assert len(upload_called) == 1
    
    def test_save_with_dual_storage_local_fails_s3_succeeds(self, tmp_path, monkeypatch):
        """Test that operation succeeds if local fails but S3 succeeds."""
        upload_called = []
        
        def mock_upload(file_content, s3_key, bucket_name, content_type, aws_profile):
            upload_called.append(True)
            return True
        
        import extract_transcripts
        monkeypatch.setattr(extract_transcripts, 'upload_to_s3', mock_upload)
        
        # Use invalid local path
        invalid_dir = "/invalid/path"
        s3_config = S3Config(bucket_name="test-bucket", prefix="", region="us-east-1")
        storage_config = StorageConfig(local_dir=invalid_dir, s3_config=s3_config)
        
        video_id = "test123"
        
        # Should not raise exception because S3 succeeds
        save_transcript_with_storage(video_id, "Title", "Content", storage_config)
        
        # Verify S3 upload was called
        assert len(upload_called) == 1
    
    def test_save_with_dual_storage_s3_fails_local_succeeds(self, tmp_path, monkeypatch):
        """Test that operation succeeds if S3 fails but local succeeds."""
        def mock_upload(file_content, s3_key, bucket_name, content_type, aws_profile):
            return False
        
        import extract_transcripts
        monkeypatch.setattr(extract_transcripts, 'upload_to_s3', mock_upload)
        
        output_dir = str(tmp_path / "transcripts")
        s3_config = S3Config(bucket_name="test-bucket", prefix="", region="us-east-1")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=s3_config)
        
        video_id = "test123"
        title = "Test"
        transcript = "Content"
        
        # Should not raise exception because local succeeds
        save_transcript_with_storage(video_id, title, transcript, storage_config)
        
        # Verify local file was created
        expected_file = os.path.join(output_dir, f"{video_id}.md")
        assert os.path.exists(expected_file)
    
    def test_save_with_dual_storage_both_fail_raises_ioerror(self, tmp_path, monkeypatch):
        """Test that IOError is raised when both local and S3 fail."""
        def mock_upload(file_content, s3_key, bucket_name, content_type, aws_profile):
            return False
        
        def mock_makedirs(path, exist_ok=False):
            raise PermissionError("Permission denied")
        
        import extract_transcripts
        monkeypatch.setattr(extract_transcripts, 'upload_to_s3', mock_upload)
        monkeypatch.setattr(extract_transcripts.os, 'makedirs', mock_makedirs)
        
        output_dir = str(tmp_path / "transcripts")
        s3_config = S3Config(bucket_name="test-bucket", prefix="", region="us-east-1")
        storage_config = StorageConfig(local_dir=output_dir, s3_config=s3_config)
        
        video_id = "test123"
        
        with pytest.raises(IOError) as exc_info:
            save_transcript_with_storage(video_id, "Title", "Content", storage_config)
        
        assert "Failed to save transcript" in str(exc_info.value)
        assert video_id in str(exc_info.value)
