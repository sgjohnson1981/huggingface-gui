import os
import shutil
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from huggingface_hub.constants import HUGGINGFACE_HUB_CACHE
from huggingface_hub.utils import HfHubHTTPError
from .config_manager import config_manager
from .logging_config import logger

class HuggingFaceService:
    def __init__(self):
        self._api = None
        self._token = None
        self.connect()

    def connect(self):
        """
        Connects to the Hugging Face Hub API using the stored token.
        """
        token = config_manager.get('hf_token')
        if token and token != self._token:
            self._token = token
            self._api = HfApi(token=self._token)
        elif not token and self._token is not None:
            # Token was removed
            self._token = None
            self._api = HfApi()
        elif self._api is None:
            # First time connection
            self._api = HfApi()

    def search_models(self, search_query=None, sort=None, direction=None, limit=None, filters=None):
        """
        Searches for models on the Hugging Face Hub.

        Args:
            search_query (str, optional): The search query. Defaults to None.
            sort (str, optional): The field to sort by (e.g., 'downloads', 'likes'). Defaults to None.
            direction (int, optional): Sort direction (-1 for descending, 1 for ascending). Defaults to None.
            limit (int, optional): The maximum number of results to return. Defaults to None.
            filters (list, optional): A list of filters to apply (e.g., 'text-generation'). Defaults to None.

        Returns:
            list: A list of ModelInfo objects.
        """
        self.connect()  # Ensure the connection is up-to-date with the latest token

        # The HfApi().list_models uses 'search' for the query, and 'filter' for tags.
        # It's a bit confusing. 'filter' is a list of tags. 'search' is a string query.

        try:
            models = self._api.list_models(
                search=search_query,
                sort=sort,
                direction=direction,
                limit=limit,
                filter=filters,
                full=False,  # We don't need full model info for the list view
            )
            return list(models)
        except Exception as e:
            logger.error(f"An error occurred while searching for models: {e}", exc_info=True)
            return []

    def get_model_tags(self):
        """
        Fetches the list of available model tags (tasks) from the Hub API.
        """
        self.connect()
        try:
            url = "https://huggingface.co/api/models-tags"
            # Use the session from the HfApi client for connection pooling and auth
            response = self._api._session.get(url)
            response.raise_for_status()
            tags_data = response.json()
            if 'pipeline_tag' in tags_data and isinstance(tags_data['pipeline_tag'], list):
                # Sort for consistent ordering in the UI
                return sorted(tags_data['pipeline_tag'])
            else:
                logger.error("'pipeline_tag' not found or not a list in API response.")
                return []
        except Exception as e:
            # Catching a broad exception because the underlying library could raise anything
            logger.error(f"An unexpected error occurred while fetching model tags: {e}", exc_info=True)
            return []

    def get_model_readme(self, model_id):
        """
        Downloads the README.md file for a given model.
        """
        self.connect()
        try:
            readme_path = hf_hub_download(repo_id=model_id, filename="README.md", repo_type="model")
            with open(readme_path, 'r', encoding='utf-8') as f:
                return f.read()
        except HfHubHTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"No README.md found for model: {model_id}")
                return "No README.md file found for this model."
            logger.error(f"HTTP error fetching README for {model_id}: {e}", exc_info=True)
            return f"Error fetching README: {e}"
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching README for {model_id}: {e}", exc_info=True)
            return f"An unexpected error occurred: {e}"

    def download_model(self, model_id, download_dir, progress_callback=None):
        """
        Downloads an entire model repository to a specified directory.
        Accepts an optional callback for progress reporting (current, total).
        """
        self.connect()

        # Helper class that mimics tqdm's interface to capture progress updates
        # from snapshot_download and forward them to our Qt signal.
        class ProgressCallbackTqdm:
            def __init__(self, *args, **kwargs):
                self.callback = progress_callback
                # snapshot_download provides the total number of files in kwargs
                self.total = kwargs.get("total", 0)
                self.current = 0
                if self.callback:
                    # Initial call to set up the progress bar (e.g., set max value)
                    self.callback(self.current, self.total)

            def update(self, n=1):
                self.current += n
                if self.callback:
                    self.callback(self.current, self.total)

            def close(self):
                # Ensure the progress bar reaches 100% if it was started
                if self.callback and self.total > 0 and self.current < self.total:
                    self.callback(self.total, self.total)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.close()

        try:
            # snapshot_download will download the whole repo and return the path
            path = snapshot_download(
                repo_id=model_id,
                local_dir=os.path.join(download_dir, model_id),
                local_dir_use_symlinks=False,  # To avoid issues with symlinks
                tqdm_class=ProgressCallbackTqdm if progress_callback else None,
            )
            return True, f"Model downloaded successfully to {path}"
        except Exception as e:
            logger.error(f"Failed to download model {model_id}: {e}", exc_info=True)
            return False, f"Failed to download model: {e}"

    def delete_model_cache(self, model_id: str):
        """
        Deletes the cache directory for a given model ID.
        This is used to clean up partial downloads upon cancellation.
        """
        try:
            # Construct the path to the model's cache directory
            # e.g., "bert-base-uncased" -> "models--bert-base-uncased"
            model_cache_dir_name = f"models--{model_id.replace('/', '--')}"
            cache_path = Path(HUGGINGFACE_HUB_CACHE) / model_cache_dir_name

            if cache_path.exists() and cache_path.is_dir():
                logger.info(f"Deleting cache directory: {cache_path}")
                shutil.rmtree(cache_path)
                logger.info(f"Successfully deleted cache for model {model_id}.")
                return True, f"Cache for {model_id} deleted."
            else:
                logger.warning(f"Cache directory not found for model {model_id} at {cache_path}. No action taken.")
                return True, "Cache directory not found, no cleanup needed."

        except Exception as e:
            logger.error(f"Error deleting cache for model {model_id}: {e}", exc_info=True)
            return False, f"Error deleting cache: {e}"


# Global instance for easy access
hf_service = HuggingFaceService()


def run_download_in_process(queue, model_id, download_dir):
    """
    A top-level function to be run in a separate process for downloading a model.
    It creates its own HuggingFaceService instance and communicates progress,
    results, and errors back through a queue.

    Args:
        queue (multiprocessing.Queue): The queue to send messages back to the main thread.
        model_id (str): The ID of the model to download.
        download_dir (str): The directory to download the model to.
    """
    # This function runs in a separate process, so it needs its own imports and setup.
    import sys
    import traceback

    try:
        service = HuggingFaceService()

        # Define a callback that puts progress updates into the queue
        def progress_callback(current, total):
            queue.put(('progress', (current, total)))

        # Call the download method with the process-safe callback
        success, message = service.download_model(
            model_id,
            download_dir,
            progress_callback=progress_callback
        )
        queue.put(('result', (success, message)))

    except Exception as e:
        exctype, value = sys.exc_info()[:2]
        tb = traceback.format_exc()
        logger.error(f"Error in download process for {model_id}: {e}", exc_info=(exctype, value, tb))
        queue.put(('error', (exctype, str(value), tb)))


def run_search_in_process(queue, search_params):
    """
    A top-level function to be run in a separate process for searching models.
    It communicates results or errors back through a queue.
    """
    import sys
    import traceback

    try:
        service = HuggingFaceService()
        results = service.search_models(**search_params)
        queue.put(('result', results))
    except Exception as e:
        exctype, value = sys.exc_info()[:2]
        tb = traceback.format_exc()
        logger.error(f"Error in search process: {e}", exc_info=(exctype, value, tb))
        queue.put(('error', (exctype, str(value), tb)))