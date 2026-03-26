import os
import shutil
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from huggingface_hub.constants import HUGGINGFACE_HUB_CACHE
from huggingface_hub.utils import HfHubHTTPError
import requests
import threading
from .config_manager import config_manager
from .logging_config import logger

class HuggingFaceService:
    def __init__(self):
        self._api = None
        self._token = None
        self._lock = threading.Lock()
        self.connect()

    def connect(self):
        """
        Connects to the Hugging Face Hub API using the stored token.
        """
        with self._lock:
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

    def search_models(self, search_query=None, sort=None, limit=None, filters=None, full_text=False, strict=False, **kwargs):
        """
        Searches for models on the Hugging Face Hub.

        Args:
            search_query (str, optional): The search query. Defaults to None.
            sort (str, optional): The field to sort by (e.g., 'downloads', 'likes'). Defaults to None.
            limit (int, optional): The maximum number of results to return. Defaults to None.
            filters (list, optional): A list of filters to apply (e.g., 'text-generation'). Defaults to None.
            full_text (bool, optional): Whether to perform a full-text search (searching READMEs). Defaults to False.
            **kwargs: Additional arguments (like 'direction' which is ignored).

        Returns:
            list: A list of objects containing model information.
        """
        self.connect()  # Ensure the connection is up-to-date with the latest token

        if full_text and search_query:
            # Full-text search API endpoint (searches READMEs/model cards)
            url = "https://huggingface.co/api/search/full-text"
            config_limit = config_manager.get('search_limit', 100)
            # Combine filters into the query string for the API since it doesn't take a separate tags array
            api_query = search_query
            if filters:
                filter_str = " ".join([f'tags:"{f}"' for f in filters])
                api_query = f"{api_query} {filter_str}".strip()

            params = {
                "q": api_query,
                "type": "model",
                "limit": limit or (config_limit if config_limit > 0 else 10000) # Full-text API doesn't allow None limit reliably
            }
            try:
                logger.info(f"Performing full-text search for: {search_query}")
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                search_results = response.json()
                hits = search_results.get('hits', [])
                
                # Convert hits to ModelInfo-compatible objects
                from types import SimpleNamespace
                from datetime import datetime
                
                models = []
                for hit in hits:
                    repo_owner = hit.get('repoOwner')
                    repo_name = hit.get('repoName')
                    
                    # Apply strict filtering if requested or if filters were injected into the query (which causes OR matches on the backend)
                    if (strict or filters) and search_query:
                        if not self._is_hit_strict_match(search_query, hit):
                            continue

                    if repo_owner and repo_name:
                        repo_id = f"{repo_owner}/{repo_name}"
                    else:
                        repo_id = repo_name or hit.get('repoId', 'unknown')

                    updated_at = hit.get('updatedAt')
                    last_modified = None
                    if updated_at:
                        try:
                            last_modified = datetime.fromtimestamp(updated_at / 1000)
                        except Exception:
                            pass
                    
                    # Parse tags string (comma-separated)
                    tags_str = hit.get('tags', '')
                    tags_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                    
                    # Apply tag filters if requested
                    if filters:
                        if not all(f in tags_list for f in filters):
                            continue
                    
                    # Heuristic for pipeline_tag: often the first or contains known tasks
                    # We'll just take the first tag if available as a placeholder for pipeline_tag
                    pipeline_tag = 'N/A'
                    if tags_list:
                        pipeline_tag = tags_list[0]

                    # Create a mock ModelInfo object
                    model = SimpleNamespace(
                        id=repo_id,
                        author=hit.get('authorData', {}).get('fullname') or repo_owner or 'N/A',
                        pipeline_tag=pipeline_tag,
                        downloads=0, # Not available in full-text search API
                        likes=hit.get('likes', 0),
                        lastModified=last_modified,
                        tags=tags_list
                    )
                    models.append(model)
                logger.info(f"Full-text search returned {len(models)} results (estimated total API hits: {search_results.get('estimatedTotalHits')}).")
                
                # If we injected filters, the API's estimated hits represent an OR query and are wildly inaccurate for our AND requirement.
                estimated_total = search_results.get('estimatedTotalHits') if not filters else None
                return models, estimated_total
            except Exception as e:
                logger.error(f"Full-text search failed: {e}", exc_info=True)
                pass # Fallback to standard search

        try:
            config_limit = config_manager.get('search_limit', 100)
            models = self._api.list_models(
                search=search_query,
                sort=sort,
                limit=limit or (config_limit if config_limit > 0 else None),
                filter=filters,
                full=False,
            )
            results_list = list(models)
            return results_list, None # Standard API doesn't return total without full iteration
        except Exception as e:
            logger.error(f"An error occurred while searching for models: {e}", exc_info=True)
            return [], 0

    def get_model_tags(self):
        """
        Fetches the list of available model tags (tasks) from the Hub API.
        """
        self.connect()
        try:
            # Use the library's built-in method which handles auth and sessions correctly
            tags_dict = self._api.get_model_tags()
            if 'pipeline_tag' in tags_dict:
                # The data is a list of Namespace objects or dicts: {'id': 'text-classification', ...}
                tag_ids = [t['id'] for t in tags_dict['pipeline_tag'] if isinstance(t, dict) and 'id' in t]
                return sorted([str(tid) for tid in tag_ids if tid])
            
            logger.error("'pipeline_tag' not found in model tags.")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch model tags via HfApi: {e}")
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

    def get_model_relationships(self, model_id):
        """
        Fetches the relationships (base model, finetunes, adapters, quantizations) for a model.
        """
        self.connect()
        try:
            model_info = self._api.model_info(model_id)
            
            # Find base model in tags
            base_model_id = None
            for tag in model_info.tags:
                if tag.startswith("base_model:") and not tag.startswith("base_model:finetune:") and not tag.startswith("base_model:adapter:") and not tag.startswith("base_model:quantized:"):
                    base_model_id = tag.replace("base_model:", "")
                    break
            
            # If not found in tags, check 'base_model' attribute (sometimes present in newer versions of library)
            if not base_model_id:
                base_model_id = getattr(model_info, 'base_model', None)

            # Count finetunes, adapters, quantizations
            # We use a limit of 1 just to see if any exist, but the user wants the full count.
            # To get a full count without fetching all data, we could use the search API or just iterate.
            # For now, we'll iterate as it's the most reliable way to get an accurate count via HfApi.
            
            def count_filtered(filter_expr):
                try:
                    models = self._api.list_models(filter=filter_expr)
                    return sum(1 for _ in models)
                except Exception as e:
                    logger.warning(f"Error counting models with filter {filter_expr}: {e}")
                    return 0

            finetunes_count = count_filtered(f"base_model:finetune:{model_id}")
            adapters_count = count_filtered(f"base_model:adapter:{model_id}")
            quantizations_count = count_filtered(f"base_model:quantized:{model_id}")

            return {
                "base_model": base_model_id,
                "finetunes": finetunes_count,
                "adapters": adapters_count,
                "quantizations": quantizations_count,
                "this_model_is_finetune": any(tag.startswith("base_model:finetune:") for tag in model_info.tags)
            }
        except Exception as e:
            logger.error(f"Error fetching relationships for {model_id}: {e}", exc_info=True)
            return None

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


    def _is_hit_strict_match(self, query, hit):
        """
        Determines if a search hit matches a query strictly (without fuzzy matching).
        Supports boolean operators AND, OR, NOT and parentheses.
        """
        import re

        # Collect all text from metadata and snippets
        text_parts = [
            hit.get('repoName', '') or '',
            hit.get('repoOwner', '') or '',
            hit.get('tags', '') or '',
            hit.get('repoId', '') or ''
        ]
        
        formatted = hit.get('formatted', {})
        for field in formatted.values():
            if isinstance(field, list):
                for part in field:
                    if isinstance(part, dict) and 'text' in part:
                        text_parts.append(part['text'])
        
        full_text = " ".join(text_parts).lower()

        # Tokenize query, preserving boolean operators (case-insensitive), parentheses, and quoted strings
        tokens = re.findall(r'\(|\)|AND|OR|NOT|&|\||!|"[^"]+"|[^\s()]+', query, re.IGNORECASE)
        
        term_matches = {}
        for token in tokens:
            upper_token = token.upper()
            if upper_token in ('(', ')', 'AND', 'OR', 'NOT', '&', '|', '!'):
                continue
            
            term = token.strip('"').lower()
            if term not in term_matches:
                # Check if term is in any part of the text (literal match)
                term_matches[token] = term in full_text
        
        eval_tokens = []
        for token in tokens:
            upper_token = token.upper()
            if upper_token == 'AND' or token == '&': eval_tokens.append('and')
            elif upper_token == 'OR' or token == '|': eval_tokens.append('or')
            elif upper_token == 'NOT' or token == '!': eval_tokens.append('not')
            elif token in ('(', ')'): eval_tokens.append(token)
            else:
                eval_tokens.append(str(term_matches.get(token, False)))
        
        # Default behavior if no operators: AND all terms
        has_operator = any(t.upper() in ('AND', 'OR', 'NOT', '&', '|', '!') for t in tokens)
        if not has_operator:
            real_terms = [t for t in tokens if t not in ('(', ')')]
            if not real_terms: return True
            return all(term_matches.get(t, False) for t in real_terms)

        try:
            expr = " ".join(eval_tokens)
            # Safe evaluation of boolean literals and operators
            return eval(expr, {"__builtins__": None}, {"True": True, "False": False})
        except Exception as e:
            logger.warning(f"Failed to evaluate strict match expression: {e}")
            return True # Fallback to showing results if evaluation fails


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