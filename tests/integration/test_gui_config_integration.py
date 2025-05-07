import sys
import os
import unittest
from unittest import mock
import tkinter as tk
import tempfile
import shutil
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Import application modules
# We need to mock Tk to avoid GUI initialization during tests
with mock.patch('tkinter.Tk'):
    from gui_app import EmailMonitorApp, load_configuration, save_configuration

class TestGuiConfigIntegration(unittest.TestCase):
    """Integration tests for GUI and configuration integration"""

    def setUp(self):
        # Create a temporary directory for test configuration files
        self.test_dir = tempfile.mkdtemp()
        self.config_file_path = os.path.join(self.test_dir, "config.py")
        
        # Save original config file path
        self.original_config_file_path = "config.py"
        
        # Create test configuration
        self.test_config = {
            "IMAP_SERVER": "imap.test.com",
            "EMAIL_ACCOUNT": "test_integration@example.com",
            "APP_PASSWORD": "test_integration_password",
            "KEYWORD": "integration_test",
            "POLL_INTERVAL_SECONDS": 45,
            "MAILBOX": "TEST_INBOX"
        }
        
        # Mock tkinter root
        self.mock_root = mock.MagicMock(spec=tk.Tk)

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)

    @mock.patch('gui_app.CONFIG_FILE')
    def test_save_load_configuration(self, mock_config_file):
        """Test saving and loading configuration file from GUI app"""
        # Set the mocked CONFIG_FILE to our temporary file
        mock_config_file.__str__.return_value = self.config_file_path
        mock_config_file.__eq__.side_effect = lambda x: str(mock_config_file) == x
        
        # Test saving configuration
        save_result = save_configuration(self.test_config)
        self.assertTrue(save_result)
        self.assertTrue(os.path.exists(self.config_file_path))
        
        # Test loading configuration
        with mock.patch('gui_app.CONFIG_FILE', self.config_file_path):
            loaded_config = load_configuration()
            
            # Verify the loaded configuration matches what we saved
            self.assertEqual(loaded_config["IMAP_SERVER"], self.test_config["IMAP_SERVER"])
            self.assertEqual(loaded_config["EMAIL_ACCOUNT"], self.test_config["EMAIL_ACCOUNT"])
            self.assertEqual(loaded_config["APP_PASSWORD"], self.test_config["APP_PASSWORD"])
            self.assertEqual(loaded_config["KEYWORD"], self.test_config["KEYWORD"])
            self.assertEqual(loaded_config["POLL_INTERVAL_SECONDS"], self.test_config["POLL_INTERVAL_SECONDS"])
            self.assertEqual(loaded_config["MAILBOX"], self.test_config["MAILBOX"])

    @mock.patch('gui_app.CONFIG_FILE')
    @mock.patch('gui_app.tk.Tk')
    @mock.patch('gui_app.threading.Thread')
    @mock.patch('gui_app.pystray')
    @mock.patch('gui_app.Image')
    def test_app_initialization_with_config(self, mock_image, mock_pystray, mock_thread, mock_tk, mock_config_file):
        """Test app initialization with configuration"""
        # Setup mocks
        mock_tk.return_value = self.mock_root
        mock_config_file.__str__.return_value = self.config_file_path
        
        # Create the test config file
        with open(self.config_file_path, 'w') as f:
            f.write(f"IMAP_SERVER = '{self.test_config['IMAP_SERVER']}'\n")
            f.write(f"EMAIL_ACCOUNT = '{self.test_config['EMAIL_ACCOUNT']}'\n")
            f.write(f"APP_PASSWORD = '{self.test_config['APP_PASSWORD']}'\n")
            f.write(f"KEYWORD = '{self.test_config['KEYWORD']}'\n")
            f.write(f"POLL_INTERVAL_SECONDS = {self.test_config['POLL_INTERVAL_SECONDS']}\n")
            f.write(f"MAILBOX = '{self.test_config['MAILBOX']}'\n")
        
        # Patch open to return our test file content
        with mock.patch('gui_app.open', mock.mock_open(read_data="")) as mock_open:
            # Patch os.path.exists to return True for our test config file
            with mock.patch('os.path.exists', return_value=True):
                # Create the EmailMonitorApp
                with mock.patch('gui_app.load_configuration', return_value=self.test_config):
                    app = EmailMonitorApp(self.mock_root)
                    
                    # Check if config was loaded properly
                    self.assertEqual(app.current_config, self.test_config)
                    self.assertTrue(app.config_loaded)
    
    @mock.patch('gui_app.CONFIG_FILE')
    @mock.patch('gui_app.connect_to_gmail')
    def test_monitoring_with_config(self, mock_connect_to_gmail, mock_config_file):
        """Test monitoring functionality with configuration"""
        # Setup mocks
        mock_config_file.__str__.return_value = self.config_file_path
        mock_mail = mock.MagicMock()
        mock_connect_to_gmail.return_value = mock_mail
        
        # Mock TK
        with mock.patch('tkinter.Tk'):
            # Create app with monitoring enabled
            with mock.patch('gui_app.EmailMonitorApp._monitoring_loop') as mock_monitoring_loop:
                with mock.patch('gui_app.load_configuration', return_value=self.test_config):
                    app = EmailMonitorApp(mock.MagicMock())
                    
                    # Start monitoring
                    app.start_monitoring()
                    
                    # Check that monitoring thread was started with proper config
                    self.assertEqual(app.current_config, self.test_config)
                    self.assertTrue(app.monitoring_active)
                    self.assertFalse(app.stop_event.is_set())

if __name__ == '__main__':
    unittest.main()