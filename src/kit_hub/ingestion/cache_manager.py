"""Cache management for downloaded Instagram posts.

``CacheManager`` provides a lightweight interface for checking whether a
given Instagram shortcode has already been downloaded and stored on disk,
and for pruning stale entries from the cache directory.

The expected directory layout is::

    ig_cache_dir/
        {shortcode}/
            video.mp4
            thumbnail.jpg
            ...

This mirrors the structure produced by ``MediaStorage`` when called with
``SourceType.INSTAGRAM`` and the shortcode as the ``source_id``.
"""

from pathlib import Path
import shutil
import time

from loguru import logger as lg
from media_downloader.core.models import DownloadedMedia

_SECONDS_PER_DAY: int = 86400


class CacheManager:
    """Manage cached Instagram post data on disk.

    Files are organised as ``{ig_cache_dir}/{shortcode}/``. A post is
    considered cached when the directory exists and contains at least one
    file.

    Attributes:
        _cache_dir: Root directory containing per-shortcode subdirectories.
    """

    def __init__(self, ig_cache_dir: Path) -> None:
        """Initialise the cache manager.

        Args:
            ig_cache_dir: Directory that holds one subdirectory per
                downloaded Instagram shortcode. Does not need to exist
                yet - all methods check existence before operating.
        """
        self._cache_dir = ig_cache_dir

    def has_post(self, shortcode: str) -> bool:
        """Return True if a non-empty cache directory exists for this shortcode.

        Args:
            shortcode: Instagram shortcode (the alphanumeric ID in the URL).

        Returns:
            True when ``{ig_cache_dir}/{shortcode}/`` exists and contains
            at least one file.
        """
        post_dir = self._cache_dir / shortcode
        return post_dir.is_dir() and any(post_dir.iterdir())

    def get_cached_media(self, shortcode: str) -> DownloadedMedia | None:
        """Return cached media for the shortcode, or None if unavailable.

        Currently always returns ``None``. Reconstructing a full
        ``DownloadedMedia`` from downloaded files requires the original
        metadata (caption, transcription text, etc.) which is not stored
        separately by the cache. Use ``has_post()`` for deduplication
        checks instead.

        Args:
            shortcode: Instagram shortcode.

        Returns:
            ``None`` in all cases.
        """
        if not self.has_post(shortcode):
            return None
        return None

    def clear_old_cache(self, max_age_days: int = 30) -> int:
        """Remove cached post directories older than ``max_age_days``.

        Removes the entire directory tree for each stale shortcode. Age
        is determined by the directory's modification time (``st_mtime``).

        Args:
            max_age_days: Maximum age in days before a cached post is
                considered stale and eligible for deletion.

        Returns:
            Number of shortcode directories deleted.
        """
        if not self._cache_dir.is_dir():
            return 0
        cutoff = time.time() - max_age_days * _SECONDS_PER_DAY
        deleted = 0
        for post_dir in self._cache_dir.iterdir():
            if not post_dir.is_dir():
                continue
            if post_dir.stat().st_mtime < cutoff:
                lg.info(f"Removing stale cache directory: {post_dir}")
                shutil.rmtree(post_dir)
                deleted += 1
        return deleted
