"""
Resource Catalog Service.

Provides cached, fast access to shaders, videos, and other resources
with metadata support. Improves performance when browsing large numbers
of resources in the web frontend.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import time
from datetime import datetime


@dataclass
class ResourceInfo:
    """Information about a resource (shader or video)."""
    name: str
    path: str
    full_path: str
    category: str  # Directory name
    file_type: str  # 'shader' or 'video'
    size_bytes: int
    modified: str
    extension: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class ResourceCatalog:
    """
    Cached catalog of visualization resources (shaders and videos).

    Provides fast resource discovery with caching to avoid repeated
    filesystem scans. Essential for responsive web frontend with
    many resources.

    Features:
    - Cached resource listings
    - Automatic cache invalidation (TTL-based)
    - Search and filtering
    - Category organization
    - Metadata extraction
    """

    def __init__(
        self,
        shaders_dir: Path,
        videos_dir: Path,
        cache_ttl: int = 60  # Cache time-to-live in seconds
    ):
        """
        Initialize resource catalog.

        Args:
            shaders_dir: Path to shaders directory
            videos_dir: Path to videos directory
            cache_ttl: Cache TTL in seconds (default: 60)
        """
        self.shaders_dir = Path(shaders_dir)
        self.videos_dir = Path(videos_dir)
        self.cache_ttl = cache_ttl

        # Cache storage
        self._shader_cache: List[ResourceInfo] = []
        self._video_cache: List[ResourceInfo] = []
        self._shader_cache_time: float = 0
        self._video_cache_time: float = 0

        # Category cache (shaders by directory, videos by directory)
        self._shader_categories: Dict[str, List[ResourceInfo]] = {}
        self._video_categories: Dict[str, List[ResourceInfo]] = {}

    def get_shaders(
        self,
        category: Optional[str] = None,
        force_refresh: bool = False
    ) -> List[ResourceInfo]:
        """
        Get all shader resources, optionally filtered by category.

        Args:
            category: Optional category (directory name) to filter by
            force_refresh: Force cache refresh even if not expired

        Returns:
            List of ResourceInfo objects for shaders
        """
        # Check cache
        if force_refresh or self._is_cache_expired(self._shader_cache_time):
            self._refresh_shaders()

        # Filter by category if specified
        if category:
            return [s for s in self._shader_cache if s.category == category]

        return self._shader_cache

    def get_videos(
        self,
        category: Optional[str] = None,
        force_refresh: bool = False
    ) -> List[ResourceInfo]:
        """
        Get all video resources, optionally filtered by category.

        Args:
            category: Optional category (directory name) to filter by
            force_refresh: Force cache refresh even if not expired

        Returns:
            List of ResourceInfo objects for videos
        """
        # Check cache
        if force_refresh or self._is_cache_expired(self._video_cache_time):
            self._refresh_videos()

        # Filter by category if specified
        if category:
            return [v for v in self._video_cache if v.category == category]

        return self._video_cache

    def get_shader_categories(self, force_refresh: bool = False) -> Dict[str, List[ResourceInfo]]:
        """
        Get shaders organized by category (directory).

        Args:
            force_refresh: Force cache refresh

        Returns:
            Dictionary mapping category name to list of shaders
        """
        if force_refresh or self._is_cache_expired(self._shader_cache_time):
            self._refresh_shaders()

        return dict(self._shader_categories)

    def get_video_categories(self, force_refresh: bool = False) -> Dict[str, List[ResourceInfo]]:
        """
        Get videos organized by category (directory).

        Args:
            force_refresh: Force cache refresh

        Returns:
            Dictionary mapping category name to list of videos
        """
        if force_refresh or self._is_cache_expired(self._video_cache_time):
            self._refresh_videos()

        return dict(self._video_categories)

    def search_shaders(self, query: str) -> List[ResourceInfo]:
        """
        Search shaders by name or path.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching ResourceInfo objects
        """
        # Ensure cache is fresh
        if self._is_cache_expired(self._shader_cache_time):
            self._refresh_shaders()

        query_lower = query.lower()
        return [
            s for s in self._shader_cache
            if query_lower in s.name.lower() or query_lower in s.path.lower()
        ]

    def search_videos(self, query: str) -> List[ResourceInfo]:
        """
        Search videos by name or path.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching ResourceInfo objects
        """
        # Ensure cache is fresh
        if self._is_cache_expired(self._video_cache_time):
            self._refresh_videos()

        query_lower = query.lower()
        return [
            v for v in self._video_cache
            if query_lower in v.name.lower() or query_lower in v.path.lower()
        ]

    def get_all_categories(self) -> List[str]:
        """
        Get list of all unique categories (shader and video).

        Returns:
            Sorted list of category names
        """
        categories = set()

        if self._is_cache_expired(self._shader_cache_time):
            self._refresh_shaders()
        if self._is_cache_expired(self._video_cache_time):
            self._refresh_videos()

        categories.update(self._shader_categories.keys())
        categories.update(self._video_categories.keys())

        return sorted(categories)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get catalog statistics.

        Returns:
            Dictionary with counts and cache info
        """
        return {
            'shader_count': len(self._shader_cache),
            'video_count': len(self._video_cache),
            'shader_categories': len(self._shader_categories),
            'video_categories': len(self._video_categories),
            'shader_cache_age': time.time() - self._shader_cache_time if self._shader_cache_time > 0 else None,
            'video_cache_age': time.time() - self._video_cache_time if self._video_cache_time > 0 else None,
            'cache_ttl': self.cache_ttl
        }

    def refresh_cache(self):
        """Force refresh of all caches."""
        self._refresh_shaders()
        self._refresh_videos()
        print(f"[ResourceCatalog] Cache refreshed ({len(self._shader_cache)} shaders, {len(self._video_cache)} videos)")

    def _is_cache_expired(self, cache_time: float) -> bool:
        """Check if cache has expired."""
        if cache_time == 0:
            return True
        return (time.time() - cache_time) > self.cache_ttl

    def _refresh_shaders(self):
        """Refresh shader cache."""
        self._shader_cache.clear()
        self._shader_categories.clear()

        if not self.shaders_dir.exists():
            print(f"[ResourceCatalog] Shaders directory not found: {self.shaders_dir}")
            return

        try:
            for subdir in sorted(self.shaders_dir.iterdir()):
                if not subdir.is_dir():
                    continue

                category = subdir.name
                category_shaders = []

                for glsl_file in sorted(subdir.glob('*.glsl')):
                    try:
                        stat = glsl_file.stat()
                        resource = ResourceInfo(
                            name=glsl_file.stem,
                            path=str(glsl_file.relative_to(self.shaders_dir.parent)),
                            full_path=str(glsl_file),
                            category=category,
                            file_type='shader',
                            size_bytes=stat.st_size,
                            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            extension='.glsl'
                        )
                        self._shader_cache.append(resource)
                        category_shaders.append(resource)
                    except Exception as e:
                        print(f"[ResourceCatalog] Error reading shader {glsl_file}: {e}")

                if category_shaders:
                    self._shader_categories[category] = category_shaders

            self._shader_cache_time = time.time()
            print(f"[ResourceCatalog] Loaded {len(self._shader_cache)} shaders from {len(self._shader_categories)} categories")

        except Exception as e:
            print(f"[ResourceCatalog] Error refreshing shaders: {e}")

    def _refresh_videos(self):
        """Refresh video cache."""
        self._video_cache.clear()
        self._video_categories.clear()

        if not self.videos_dir.exists():
            print(f"[ResourceCatalog] Videos directory not found: {self.videos_dir}")
            return

        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v']

        try:
            for subdir in sorted(self.videos_dir.iterdir()):
                if not subdir.is_dir():
                    continue

                category = subdir.name
                category_videos = []

                for ext in video_extensions:
                    for video_file in sorted(subdir.glob(f'*{ext}')):
                        try:
                            stat = video_file.stat()
                            resource = ResourceInfo(
                                name=video_file.stem,
                                path=str(video_file.relative_to(self.videos_dir.parent)),
                                full_path=str(video_file),
                                category=category,
                                file_type='video',
                                size_bytes=stat.st_size,
                                modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                extension=video_file.suffix
                            )
                            self._video_cache.append(resource)
                            category_videos.append(resource)
                        except Exception as e:
                            print(f"[ResourceCatalog] Error reading video {video_file}: {e}")

                if category_videos:
                    self._video_categories[category] = category_videos

            self._video_cache_time = time.time()
            print(f"[ResourceCatalog] Loaded {len(self._video_cache)} videos from {len(self._video_categories)} categories")

        except Exception as e:
            print(f"[ResourceCatalog] Error refreshing videos: {e}")

    def __repr__(self) -> str:
        return f"ResourceCatalog({len(self._shader_cache)} shaders, {len(self._video_cache)} videos)"
