import os
import json
from appdirs import user_cache_dir
from .logging_config import logger

APP_NAME = "HuggingFaceGUIExplorer"
APP_AUTHOR = "HuggingFaceGUIExplorer"

class CacheManager:
    def __init__(self, app_name=APP_NAME, app_author=APP_AUTHOR):
        self.cache_dir = user_cache_dir(app_name, app_author)
        self.filters_cache_path = os.path.join(self.cache_dir, "filters.json")
        self._ensure_cache_dir_exists()

    def _ensure_cache_dir_exists(self):
        """
        Ensures that the cache directory exists.
        """
        if not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir)
                logger.info(f"Created cache directory at: {self.cache_dir}")
            except OSError as e:
                logger.error(f"Failed to create cache directory at {self.cache_dir}: {e}")

    def load_filters(self):
        """
        Loads the filter tags from the JSON cache file.

        Returns:
            list: A list of tags if the cache file exists and is valid, otherwise None.
        """
        if not os.path.exists(self.filters_cache_path):
            logger.info("Filter cache file not found. Skipping cache load.")
            return None

        try:
            with open(self.filters_cache_path, 'r', encoding='utf-8') as f:
                tags = json.load(f)
                logger.info(f"Successfully loaded {len(tags)} filters from cache.")
                return tags
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load filters from cache: {e}")
            return None

    def save_filters(self, tags):
        """
        Saves the given list of filter tags to the JSON cache file.

        Args:
            tags (list): A list of strings representing the filter tags.
        """
        try:
            with open(self.filters_cache_path, 'w', encoding='utf-8') as f:
                json.dump(tags, f, indent=4)
            logger.info(f"Successfully saved {len(tags)} filters to cache.")
        except IOError as e:
            logger.error(f"Failed to save filters to cache: {e}")

# Global instance for easy access
cache_manager = CacheManager()