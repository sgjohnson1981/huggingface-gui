import json
import os

class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return self._get_default_config()
        return self._get_default_config()

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value

    def _get_default_config(self):
        return {
            'hf_token': '',
            'download_dir': os.path.expanduser('~/huggingface_downloads'),
            'prompt_for_download': True,
            'view_details_in_new_window': False,
            'search_limit': 100
        }

    def ensure_download_dir_exists(self):
        download_dir = self.get('download_dir')
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

# Create a global instance for easy access
config_manager = ConfigManager()