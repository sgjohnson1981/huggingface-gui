import os
from huggingface_hub import HfApi, hf_hub_download, snapshot_download
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

    def download_model(self, model_id, download_dir):
        """
        Downloads an entire model repository to a specified directory.
        """
        self.connect()
        try:
            # snapshot_download will download the whole repo and return the path
            path = snapshot_download(
                repo_id=model_id,
                local_dir=os.path.join(download_dir, model_id),
                local_dir_use_symlinks=False, # To avoid issues with symlinks on some systems
            )
            return True, f"Model downloaded successfully to {path}"
        except Exception as e:
            logger.error(f"Failed to download model {model_id}: {e}", exc_info=True)
            return False, f"Failed to download model: {e}"


# Global instance for easy access
hf_service = HuggingFaceService()