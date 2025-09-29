import unittest
from unittest.mock import patch, MagicMock
from src.huggingface_service import HuggingFaceService
from src.config_manager import ConfigManager

class TestHuggingFaceService(unittest.TestCase):

    def setUp(self):
        """Set up mocks used by the service."""
        self.config_manager_patch = patch('src.huggingface_service.config_manager', spec=ConfigManager)
        self.mock_config_manager = self.config_manager_patch.start()
        self.mock_config_manager.get.return_value = 'fake-token'

    def tearDown(self):
        self.config_manager_patch.stop()

    @patch('src.huggingface_service.HfApi')
    def test_search_models_success(self, mock_hf_api):
        """Test that search_models calls the API correctly and returns data."""
        mock_api_instance = mock_hf_api.return_value
        mock_model = MagicMock()
        mock_model.id = 'test/model'
        mock_api_instance.list_models.return_value = [mock_model]

        service = HuggingFaceService()
        results = service.search_models(search_query="test", limit=1)

        mock_hf_api.assert_called_with(token='fake-token')
        mock_api_instance.list_models.assert_called_once_with(
            search="test",
            sort=None,
            direction=None,
            limit=1,
            filter=None,
            full=False
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 'test/model')

    @patch('src.huggingface_service.HfApi')
    def test_search_models_api_error(self, mock_hf_api):
        """Test that search_models returns an empty list on API error."""
        mock_api_instance = mock_hf_api.return_value
        mock_api_instance.list_models.side_effect = Exception("API Failure")

        service = HuggingFaceService()
        results = service.search_models(search_query="test")

        self.assertEqual(results, [])

    @patch('src.huggingface_service.hf_hub_download')
    @patch('builtins.open')
    def test_get_model_readme_success(self, mock_open, mock_hf_hub_download):
        """Test successfully fetching and reading a README."""
        mock_hf_hub_download.return_value = '/fake/path/README.md'
        mock_open.return_value.__enter__.return_value.read.return_value = "# Model Readme"

        service = HuggingFaceService()
        readme = service.get_model_readme('test/model')

        mock_hf_hub_download.assert_called_once_with(repo_id='test/model', filename='README.md', repo_type='model')
        mock_open.assert_called_once_with('/fake/path/README.md', 'r', encoding='utf-8')
        self.assertEqual(readme, "# Model Readme")

    @patch('src.huggingface_service.snapshot_download')
    def test_download_model_success(self, mock_snapshot_download):
        """Test a successful model download."""
        mock_snapshot_download.return_value = '/fake/path/test/model'

        service = HuggingFaceService()
        success, message = service.download_model('test/model', '/downloads')

        mock_snapshot_download.assert_called_once_with(
            repo_id='test/model',
            local_dir='/downloads/test/model',
            local_dir_use_symlinks=False
        )
        self.assertTrue(success)
        self.assertIn("successfully", message)

if __name__ == '__main__':
    unittest.main()