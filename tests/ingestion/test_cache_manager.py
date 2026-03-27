"""Tests for CacheManager.

Uses ``tmp_path`` for filesystem isolation; no real Instagram data is needed.
"""

import os
from pathlib import Path
import time

from kit_hub.ingestion.cache_manager import CacheManager


class TestHasPost:
    """Tests for CacheManager.has_post."""

    def test_returns_false_when_shortcode_dir_absent(self, tmp_path: Path) -> None:
        """has_post is False when no directory exists for the shortcode."""
        cm = CacheManager(ig_cache_dir=tmp_path)
        assert cm.has_post("abc123") is False

    def test_returns_false_when_dir_exists_but_empty(self, tmp_path: Path) -> None:
        """has_post is False when the directory exists but contains no files."""
        (tmp_path / "abc123").mkdir()
        cm = CacheManager(ig_cache_dir=tmp_path)
        assert cm.has_post("abc123") is False

    def test_returns_true_when_files_present(self, tmp_path: Path) -> None:
        """has_post is True when the shortcode directory contains at least one file."""
        post_dir = tmp_path / "abc123"
        post_dir.mkdir()
        (post_dir / "video.mp4").write_bytes(b"fake")
        cm = CacheManager(ig_cache_dir=tmp_path)
        assert cm.has_post("abc123") is True

    def test_different_shortcodes_are_independent(self, tmp_path: Path) -> None:
        """has_post checks only the directory for the given shortcode."""
        present = tmp_path / "present123"
        present.mkdir()
        (present / "video.mp4").write_bytes(b"fake")
        cm = CacheManager(ig_cache_dir=tmp_path)
        assert cm.has_post("present123") is True
        assert cm.has_post("absent456") is False


class TestGetCachedMedia:
    """Tests for CacheManager.get_cached_media."""

    def test_returns_none_when_not_cached(self, tmp_path: Path) -> None:
        """get_cached_media returns None when the shortcode is unknown."""
        cm = CacheManager(ig_cache_dir=tmp_path)
        assert cm.get_cached_media("abc123") is None

    def test_returns_none_even_when_files_exist(self, tmp_path: Path) -> None:
        """get_cached_media returns None even when files exist.

        Metadata (caption, etc.) is not stored separately, so the full
        DownloadedMedia cannot be reconstructed from disk alone.
        """
        post_dir = tmp_path / "abc123"
        post_dir.mkdir()
        (post_dir / "video.mp4").write_bytes(b"fake")
        cm = CacheManager(ig_cache_dir=tmp_path)
        assert cm.get_cached_media("abc123") is None


class TestClearOldCache:
    """Tests for CacheManager.clear_old_cache."""

    def test_returns_zero_for_nonexistent_cache_dir(self, tmp_path: Path) -> None:
        """clear_old_cache returns 0 when the cache root does not exist."""
        cm = CacheManager(ig_cache_dir=tmp_path / "nonexistent")
        assert cm.clear_old_cache() == 0

    def test_returns_zero_when_no_entries(self, tmp_path: Path) -> None:
        """clear_old_cache returns 0 when the cache is empty."""
        cm = CacheManager(ig_cache_dir=tmp_path)
        assert cm.clear_old_cache() == 0

    def test_removes_stale_directories(self, tmp_path: Path) -> None:
        """Directories older than max_age_days are removed."""
        old_dir = tmp_path / "old123"
        old_dir.mkdir()
        (old_dir / "video.mp4").write_bytes(b"fake")
        old_time = time.time() - 31 * 86400
        os.utime(old_dir, (old_time, old_time))

        cm = CacheManager(ig_cache_dir=tmp_path)
        deleted = cm.clear_old_cache(max_age_days=30)

        assert deleted == 1
        assert not old_dir.exists()

    def test_keeps_recent_directories(self, tmp_path: Path) -> None:
        """Directories newer than max_age_days are left intact."""
        new_dir = tmp_path / "new123"
        new_dir.mkdir()
        (new_dir / "video.mp4").write_bytes(b"fake")

        cm = CacheManager(ig_cache_dir=tmp_path)
        deleted = cm.clear_old_cache(max_age_days=30)

        assert deleted == 0
        assert new_dir.exists()

    def test_mixes_old_and_new(self, tmp_path: Path) -> None:
        """Only stale directories are removed; recent ones survive."""
        old_dir = tmp_path / "old"
        old_dir.mkdir()
        (old_dir / "clip.mp4").write_bytes(b"x")
        old_time = time.time() - 40 * 86400
        os.utime(old_dir, (old_time, old_time))

        new_dir = tmp_path / "new"
        new_dir.mkdir()
        (new_dir / "clip.mp4").write_bytes(b"x")

        cm = CacheManager(ig_cache_dir=tmp_path)
        deleted = cm.clear_old_cache(max_age_days=30)

        assert deleted == 1
        assert not old_dir.exists()
        assert new_dir.exists()

    def test_ignores_files_in_cache_root(self, tmp_path: Path) -> None:
        """Loose files at the cache root level are skipped."""
        (tmp_path / "stray_file.txt").write_text("ignore me")

        cm = CacheManager(ig_cache_dir=tmp_path)
        assert cm.clear_old_cache() == 0

    def test_returns_count_of_deleted_entries(self, tmp_path: Path) -> None:
        """Return value equals the number of directories deleted."""
        old_time = time.time() - 35 * 86400
        for name in ("a", "b", "c"):
            d = tmp_path / name
            d.mkdir()
            (d / "f").write_bytes(b"x")
            os.utime(d, (old_time, old_time))

        cm = CacheManager(ig_cache_dir=tmp_path)
        assert cm.clear_old_cache(max_age_days=30) == 3
