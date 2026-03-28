#!/usr/bin/env python3
"""
Test script to verify playlist filtering works correctly.
"""

from extract_transcripts import should_process_video, IGNORED_PLAYLISTS

print("Testing Playlist Filtering Logic")
print("=" * 60)
print(f"Ignored playlists: {IGNORED_PLAYLISTS}\n")

# Test cases
test_cases = [
    # (video_id, playlists, expected_result, description)
    ("video1", ["Chuck's corner"], True, "Video in non-ignored playlist"),
    ("video2", ["NOVO-WIDIA"], False, "Video ONLY in ignored playlist"),
    ("video3", ["NOVO - Kennametal"], False, "Video ONLY in other ignored playlist"),
    ("video4", ["NOVO-WIDIA", "NOVO - Kennametal"], False, "Video in multiple ignored playlists"),
    ("video5", ["Chuck's corner", "NOVO-WIDIA"], True, "Video in both ignored and non-ignored"),
    ("video6", ["Webinars", "NOVO - Kennametal"], True, "Video in non-ignored + ignored"),
    ("video7", [], True, "Video with no playlists"),
]

# Build test mapping
video_to_playlists = {}
for video_id, playlists, _, _ in test_cases:
    if playlists:
        video_to_playlists[video_id] = playlists

# Run tests
passed = 0
failed = 0

for video_id, playlists, expected, description in test_cases:
    result = should_process_video(video_id, video_to_playlists)
    status = "✓ PASS" if result == expected else "✗ FAIL"
    
    if result == expected:
        passed += 1
    else:
        failed += 1
    
    print(f"{status}: {description}")
    print(f"  Video: {video_id}")
    print(f"  Playlists: {playlists if playlists else '(none)'}")
    print(f"  Expected: {'Process' if expected else 'Skip'}")
    print(f"  Got: {'Process' if result else 'Skip'}")
    print()

print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 60)

if failed == 0:
    print("\n✅ All tests passed!")
else:
    print(f"\n❌ {failed} test(s) failed!")
