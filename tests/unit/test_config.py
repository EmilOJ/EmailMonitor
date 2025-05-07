import unittest
import sys
import os
from unittest.mock import patch, mock_open, MagicMock
import tkinter as tk

# Add parent directory to path to import modules to be tested
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import gui_app

class TestConfigFunctions(unittest.TestCase):
    """Unit tests for configuration handling functions in gui_app.py"""

    def setUp(self):
        self.default_config = {
            "IMAP_SERVER": "imap.gmail.com",
            "EMAIL_ACCOUNT": "YOUR_EMAIL@gmail.com",
            "APP_PASSWORD": "YOUR_APP_PASSWORD",
            "KEYWORD": "your_specific_keyword",
            "POLL_INTERVAL_SECONDS": 30,
            "MAILBOX": "INBOX"
        }
        
        self.test_config = {
            "IMAP_SERVER": "imap.test.com",
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "test_password",
            "KEYWORD": "test_keyword",
            "POLL_INTERVAL_SECONDS": 60,
            "MAILBOX": "Inbox"
        }
        
        # Sample config file content
        self.config_file_content = '''# Gmail IMAP settings
IMAP_SERVER = 'imap.test.com'
EMAIL_ACCOUNT = 'test@example.com'  # Replace with your Gmail address
APP_PASSWORD = 'test_password'      # Replace with your Gmail app password

# Email search criteria
KEYWORD = 'test_keyword'       # Replace with the keyword to search for

# Monitoring settings
POLL_INTERVAL_SECONDS = 60

# Optional: Specify the mailbox to monitor (default is "INBOX")
MAILBOX = "TestBox"
'''

    def test_load_configuration_default_if_no_file(self):
        """Test that default configuration is returned if config file does not exist"""
        with patch('os.path.exists', return_value=False):
            config = gui_app.load_configuration()
            self.assertEqual(config, gui_app.DEFAULT_CONFIG)

    def test_load_configuration_from_file(self):
        """Test loading configuration from existing config file"""
        m = mock_open(read_data=self.config_file_content)
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', m), \
             patch('builtins.exec') as mock_exec:
            
            # Mock exec to set values in globals dict
            def side_effect(content, globals_dict):
                globals_dict.update({
                    'IMAP_SERVER': 'imap.test.com',
                    'EMAIL_ACCOUNT': 'test@example.com',
                    'APP_PASSWORD': 'test_password',
                    'KEYWORD': 'test_keyword',
                    'POLL_INTERVAL_SECONDS': 60,
                    'MAILBOX': 'TestBox'
                })
            mock_exec.side_effect = side_effect
            
            config = gui_app.load_configuration()
            
            # Verify file was opened
            m.assert_called_once_with(gui_app.CONFIG_FILE, 'r')
            # Verify exec was called
            self.assertTrue(mock_exec.called)
            # Verify config values were loaded correctly
            self.assertEqual(config['IMAP_SERVER'], 'imap.test.com')
            self.assertEqual(config['EMAIL_ACCOUNT'], 'test@example.com')
            self.assertEqual(config['APP_PASSWORD'], 'test_password')
            self.assertEqual(config['KEYWORD'], 'test_keyword')
            self.assertEqual(config['POLL_INTERVAL_SECONDS'], 60)
            self.assertEqual(config['MAILBOX'], 'TestBox')

    def test_load_configuration_handles_exception(self):
        """Test that load_configuration handles exceptions and returns default config"""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data="invalid python code")), \
             patch('builtins.exec', side_effect=Exception("Syntax error")), \
             patch('builtins.print') as mock_print:
            
            config = gui_app.load_configuration()
            
            # Verify default config is returned on error
            self.assertEqual(config, gui_app.DEFAULT_CONFIG)
            # Verify error is printed
            mock_print.assert_called()

    def test_save_configuration_success(self):
        """Test successful saving of configuration"""
        m = mock_open()
        
        with patch('builtins.open', m):
            result = gui_app.save_configuration(self.test_config)
            
            # Verify file was opened for writing
            m.assert_called_once_with(gui_app.CONFIG_FILE, 'w')
            # Verify all config values were written
            handle = m()
            self.assertIn(f"IMAP_SERVER = '{self.test_config['IMAP_SERVER']}'", 
                         ''.join(call_args[0][0] for call_args in handle.write.call_args_list))
            self.assertIn(f"EMAIL_ACCOUNT = '{self.test_config['EMAIL_ACCOUNT']}'", 
                         ''.join(call_args[0][0] for call_args in handle.write.call_args_list))
            self.assertIn(f"APP_PASSWORD = '{self.test_config['APP_PASSWORD']}'", 
                         ''.join(call_args[0][0] for call_args in handle.write.call_args_list))
            self.assertIn(f"KEYWORD = '{self.test_config['KEYWORD']}'", 
                         ''.join(call_args[0][0] for call_args in handle.write.call_args_list))
            self.assertIn(f"POLL_INTERVAL_SECONDS = {self.test_config['POLL_INTERVAL_SECONDS']}", 
                         ''.join(call_args[0][0] for call_args in handle.write.call_args_list))
            self.assertIn(f"MAILBOX = \"{self.test_config['MAILBOX']}\"", 
                         ''.join(call_args[0][0] for call_args in handle.write.call_args_list))
            # Verify function returned True on success
            self.assertTrue(result)

    def test_save_configuration_failure(self):
        """Test handling of failure to save configuration"""
        with patch('builtins.open', side_effect=Exception("Permission denied")), \
             patch('gui_app.tk_messagebox.showerror') as mock_showerror: # Changed patch target
            
            result = gui_app.save_configuration(self.test_config)
            
            # Verify error dialog was shown
            mock_showerror.assert_called_once()
            # Verify function returned False on failure
            self.assertFalse(result)


class TestSetupWizard(unittest.TestCase):
    """Unit tests for SetupWizard dialog class"""

    def setUp(self):
        self.test_config = {
            "IMAP_SERVER": "imap.test.com",
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "test_password",
            "KEYWORD": "test_keyword",
            "POLL_INTERVAL_SECONDS": 60,
            "MAILBOX": "Inbox"
        }

    @patch('gui_app._show_error_dialog')
    def test_setup_wizard_apply_invalid_poll_interval(self, mock_showerror):
        """Test SetupWizard.apply() with invalid poll interval"""
        parent = MagicMock()
        
        # Use TestableSetupWizard instead
        wizard = gui_app.TestableSetupWizard(parent, initial_config=self.test_config)
        wizard.poll_interval_entry.get.return_value = "invalid"
        
        # Apply method will check showerror
        result = wizard.apply()
        
        # Verify showerror was called
        mock_showerror.assert_called_once()
        # Verify result is False
        self.assertFalse(result)
        # Verify result_config was not set
        self.assertIsNone(wizard.result_config)

    @patch('gui_app._show_error_dialog')
    def test_setup_wizard_apply_negative_poll_interval(self, mock_showerror):
        """Test SetupWizard.apply() with negative poll interval"""
        parent = MagicMock()
        
        # Use TestableSetupWizard instead
        wizard = gui_app.TestableSetupWizard(parent, initial_config=self.test_config)
        wizard.poll_interval_entry.get.return_value = "-10"
        
        # Apply method will check showerror
        result = wizard.apply()
        
        # Verify showerror was called
        mock_showerror.assert_called_once()
        # Verify result is False
        self.assertFalse(result)
        # Verify result_config was not set
        self.assertIsNone(wizard.result_config)

    def test_setup_wizard_apply_valid_inputs(self):
        """Test SetupWizard.apply() with valid inputs"""
        parent = MagicMock()
        
        # Use TestableSetupWizard instead
        wizard = gui_app.TestableSetupWizard(parent, initial_config=self.test_config)
        
        # Configure mock entry widgets return values
        wizard.imap_server_entry.get.return_value = "imap.example.com"
        wizard.email_account_entry.get.return_value = "user@example.com"
        wizard.app_password_entry.get.return_value = "app_password"
        wizard.keyword_entry.get.return_value = "search_keyword" 
        wizard.poll_interval_entry.get.return_value = "120"
        wizard.mailbox_entry.get.return_value = "INBOX"
        
        # Execute apply method
        result = wizard.apply()
        
        # Verify result is True
        self.assertTrue(result)
        # Verify result_config contains expected values
        self.assertIsNotNone(wizard.result_config)
        self.assertEqual(wizard.result_config["IMAP_SERVER"], "imap.example.com")
        self.assertEqual(wizard.result_config["EMAIL_ACCOUNT"], "user@example.com")
        self.assertEqual(wizard.result_config["APP_PASSWORD"], "app_password")
        self.assertEqual(wizard.result_config["KEYWORD"], "search_keyword")
        self.assertEqual(wizard.result_config["POLL_INTERVAL_SECONDS"], 120)
        self.assertEqual(wizard.result_config["MAILBOX"], "INBOX")

    @patch('gui_app.load_configuration')
    def test_setup_wizard_init_with_initial_config(self, mock_load_config):
        """Test initialization of SetupWizard with initial config"""
        parent = MagicMock()
        
        # Use TestableSetupWizard instead
        wizard = gui_app.TestableSetupWizard(parent, initial_config=self.test_config)
        
        # Verify load_configuration was not called
        mock_load_config.assert_not_called()
        # Verify config is set to initial_config
        self.assertEqual(wizard.config, self.test_config)

    @patch('gui_app.load_configuration', return_value={"IMAP_SERVER": "imap.default.com"})
    def test_setup_wizard_init_without_initial_config(self, mock_load_config):
        """Test initialization of SetupWizard without initial config"""
        parent = MagicMock()
        
        # Use TestableSetupWizard instead
        wizard = gui_app.TestableSetupWizard(parent)
        
        # Verify load_configuration was called
        mock_load_config.assert_called_once()
        # Verify config is set to return value of load_configuration
        self.assertEqual(wizard.config, {"IMAP_SERVER": "imap.default.com"})

if __name__ == '__main__':
    unittest.main()