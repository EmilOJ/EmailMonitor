\
import unittest
from unittest.mock import patch, mock_open, MagicMock
import os

# Add the parent directory to the Python path to allow importing gui_app
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from gui_app import (
    load_configuration,
    save_configuration,
    SetupWizard,
    EmailMonitorApp,
    DEFAULT_CONFIG,
    CONFIG_FILE
)

class TestConfigFunctions(unittest.TestCase):

    def setUp(self):
        # Make a copy of DEFAULT_CONFIG for modification in tests
        self.default_config_copy = DEFAULT_CONFIG.copy()
        self.test_config_data = {
            "IMAP_SERVER": "test.imap.com",
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "testpassword",
            "KEYWORD": "testkeyword",
            "POLL_INTERVAL_SECONDS": 60,
            "MAILBOX": "TestInbox"
        }

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_configuration_no_file(self, mock_file_open, mock_exists):
        mock_exists.return_value = False
        config = load_configuration()
        self.assertEqual(config, self.default_config_copy)
        mock_file_open.assert_not_called()

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='IMAP_SERVER = "custom.server.com"\\nPOLL_INTERVAL_SECONDS = 120')
    def test_load_configuration_file_exists_partial(self, mock_file_open, mock_exists):
        mock_exists.return_value = True
        config = load_configuration()
        expected_config = self.default_config_copy.copy()
        expected_config["IMAP_SERVER"] = "custom.server.com"
        expected_config["POLL_INTERVAL_SECONDS"] = 120
        self.assertEqual(config, expected_config)
        mock_file_open.assert_called_once_with(CONFIG_FILE, 'r')

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='INVALID_PYTHON_CODE')
    def test_load_configuration_file_error(self, mock_file_open, mock_exists):
        mock_exists.return_value = True
        # Silence print output during this test
        with patch('builtins.print') as mock_print:
            config = load_configuration()
        self.assertEqual(config, self.default_config_copy) # Should return default on error
        mock_file_open.assert_called_once_with(CONFIG_FILE, 'r')
        mock_print.assert_called() # Check that an error was printed

    @patch('builtins.open', new_callable=mock_open)
    @patch('tkinter.messagebox.showerror')
    def test_save_configuration_success(self, mock_showerror, mock_file_open):
        result = save_configuration(self.test_config_data)
        self.assertTrue(result)
        mock_file_open.assert_called_once_with(CONFIG_FILE, 'w')
        # Check if all parts of the config were written
        handle = mock_file_open()
        handle.write.assert_any_call(f"IMAP_SERVER = '{self.test_config_data['IMAP_SERVER']}'\\n")
        handle.write.assert_any_call(f"EMAIL_ACCOUNT = '{self.test_config_data['EMAIL_ACCOUNT']}'  # Replace with your Gmail address\\n")
        handle.write.assert_any_call(f"APP_PASSWORD = '{self.test_config_data['APP_PASSWORD']}'      # Replace with your Gmail app password\\n")
        handle.write.assert_any_call(f"KEYWORD = '{self.test_config_data['KEYWORD']}'       # Replace with the keyword to search for\\n")
        handle.write.assert_any_call(f"POLL_INTERVAL_SECONDS = {self.test_config_data['POLL_INTERVAL_SECONDS']}\\n")
        handle.write.assert_any_call(f"MAILBOX = \"{self.test_config_data['MAILBOX']}\"\\n")
        mock_showerror.assert_not_called()

    @patch('builtins.open', new_callable=mock_open)
    @patch('tkinter.messagebox.showerror')
    def test_save_configuration_error(self, mock_showerror, mock_file_open):
        mock_file_open.side_effect = IOError("Disk full")
        result = save_configuration(self.test_config_data)
        self.assertFalse(result)
        mock_showerror.assert_called_once()

class TestSetupWizard(unittest.TestCase):
    def setUp(self):
        self.mock_parent = MagicMock() # Mock the parent tkinter widget
        self.initial_config = DEFAULT_CONFIG.copy()

    @patch('gui_app.load_configuration') # Mock load_configuration within gui_app module
    def test_setup_wizard_initialization_with_config(self, mock_load_config):
        test_config = {"KEYWORD": "specific"}
        wizard = SetupWizard(self.mock_parent, initial_config=test_config)
        self.assertEqual(wizard.config, test_config)
        mock_load_config.assert_not_called() # Should not call load_configuration if initial_config is provided

    @patch('gui_app.load_configuration')
    def test_setup_wizard_initialization_without_config(self, mock_load_config):
        mock_load_config.return_value = self.initial_config
        wizard = SetupWizard(self.mock_parent)
        self.assertEqual(wizard.config, self.initial_config)
        mock_load_config.assert_called_once()

    # We need to mock tkinter elements for the body and apply methods
    @patch('tkinter.ttk.Label')
    @patch('tkinter.ttk.Entry')
    @patch('tkinter.messagebox.showerror')
    def test_setup_wizard_apply_valid(self, mock_showerror, mock_entry, mock_label):
        # Mock the entry widgets and their get methods
        mock_imap_entry = MagicMock()
        mock_imap_entry.get.return_value = "imap.test.com"
        mock_email_entry = MagicMock()
        mock_email_entry.get.return_value = "user@test.com"
        mock_password_entry = MagicMock()
        mock_password_entry.get.return_value = "password"
        mock_keyword_entry = MagicMock()
        mock_keyword_entry.get.return_value = "testkey"
        mock_poll_entry = MagicMock()
        mock_poll_entry.get.return_value = "45"
        mock_mailbox_entry = MagicMock()
        mock_mailbox_entry.get.return_value = "TestBox"

        # Simulate the creation of these entries within the wizard
        wizard = SetupWizard(self.mock_parent, initial_config=self.initial_config)
        wizard.imap_server_entry = mock_imap_entry
        wizard.email_account_entry = mock_email_entry
        wizard.app_password_entry = mock_password_entry
        wizard.keyword_entry = mock_keyword_entry
        wizard.poll_interval_entry = mock_poll_entry
        wizard.mailbox_entry = mock_mailbox_entry

        wizard.apply()

        self.assertIsNotNone(wizard.result_config)
        self.assertEqual(wizard.result_config["IMAP_SERVER"], "imap.test.com")
        self.assertEqual(wizard.result_config["EMAIL_ACCOUNT"], "user@test.com")
        self.assertEqual(wizard.result_config["APP_PASSWORD"], "password")
        self.assertEqual(wizard.result_config["KEYWORD"], "testkey")
        self.assertEqual(wizard.result_config["POLL_INTERVAL_SECONDS"], 45)
        self.assertEqual(wizard.result_config["MAILBOX"], "TestBox")
        mock_showerror.assert_not_called()

    @patch('tkinter.ttk.Label')
    @patch('tkinter.ttk.Entry')
    @patch('tkinter.messagebox.showerror')
    def test_setup_wizard_apply_invalid_poll_interval_value(self, mock_showerror, mock_entry, mock_label):
        mock_poll_entry = MagicMock()
        mock_poll_entry.get.return_value = "not_a_number" # Invalid poll interval

        wizard = SetupWizard(self.mock_parent, initial_config=self.initial_config)
        # Only need to mock the problematic entry for this test
        wizard.poll_interval_entry = mock_poll_entry
        # Mock other entries to avoid AttributeError if apply tries to access them before erroring
        wizard.imap_server_entry = MagicMock()
        wizard.email_account_entry = MagicMock()
        wizard.app_password_entry = MagicMock()
        wizard.keyword_entry = MagicMock()
        wizard.mailbox_entry = MagicMock()


        wizard.apply()
        self.assertIsNone(wizard.result_config)
        mock_showerror.assert_called_once_with("Invalid Input", "Poll interval must be a number.", parent=wizard)

    @patch('tkinter.ttk.Label')
    @patch('tkinter.ttk.Entry')
    @patch('tkinter.messagebox.showerror')
    def test_setup_wizard_apply_invalid_poll_interval_negative(self, mock_showerror, mock_entry, mock_label):
        mock_poll_entry = MagicMock()
        mock_poll_entry.get.return_value = "-10" # Invalid poll interval

        wizard = SetupWizard(self.mock_parent, initial_config=self.initial_config)
        wizard.poll_interval_entry = mock_poll_entry
        wizard.imap_server_entry = MagicMock()
        wizard.email_account_entry = MagicMock()
        wizard.app_password_entry = MagicMock()
        wizard.keyword_entry = MagicMock()
        wizard.mailbox_entry = MagicMock()

        wizard.apply()
        self.assertIsNone(wizard.result_config)
        mock_showerror.assert_called_once_with("Invalid Input", "Poll interval must be a positive integer.", parent=wizard)


class TestEmailMonitorAppConfigValidation(unittest.TestCase):

    def setUp(self):
        # Mock the root Tkinter window and other dependencies for EmailMonitorApp
        self.mock_root = MagicMock()
        # Patch dependencies that are called during EmailMonitorApp.__init__
        patches = {
            'gui_app.load_configuration': MagicMock(return_value=DEFAULT_CONFIG.copy()),
            'gui_app.EmailMonitorApp.create_main_widgets': MagicMock(),
            'gui_app.EmailMonitorApp.setup_tray_icon': MagicMock(),
            'gui_app.EmailMonitorApp.check_log_queue': MagicMock(),
            'gui_app.EmailMonitorApp.run_setup_wizard': MagicMock(),
            'gui_app.EmailMonitorApp.log_message_gui': MagicMock(),
            'gui_app.EmailMonitorApp.update_gui_state': MagicMock(),
            'tkinter.Tk': self.mock_root # if EmailMonitorApp creates its own root
        }
        self.patchers = [patch(target, mock) for target, mock in patches.items()]
        for p in self.patchers:
            p.start()

        # Instantiate EmailMonitorApp after patches are active
        # We pass a mock root, but EmailMonitorApp might create its own if not careful.
        # For this test, we only care about _is_config_valid, so __init__ just needs to run.
        with patch('tkinter.Tk', return_value=self.mock_root): # Ensure Tk() calls use mock_root
             self.app = EmailMonitorApp(self.mock_root)


    def tearDown(self):
        for p in self.patchers:
            p.stop()

    def test_is_config_valid_all_defaults(self):
        config = DEFAULT_CONFIG.copy()
        self.assertFalse(self.app._is_config_valid(config))

    def test_is_config_valid_missing_email(self):
        config = DEFAULT_CONFIG.copy()
        config["EMAIL_ACCOUNT"] = "" # Missing
        config["APP_PASSWORD"] = "some_password"
        config["KEYWORD"] = "some_keyword"
        self.assertFalse(self.app._is_config_valid(config))

    def test_is_config_valid_default_email(self):
        config = DEFAULT_CONFIG.copy()
        config["EMAIL_ACCOUNT"] = DEFAULT_CONFIG["EMAIL_ACCOUNT"] # Still default
        config["APP_PASSWORD"] = "some_password"
        config["KEYWORD"] = "some_keyword"
        self.assertFalse(self.app._is_config_valid(config))

    def test_is_config_valid_missing_password(self):
        config = DEFAULT_CONFIG.copy()
        config["EMAIL_ACCOUNT"] = "user@example.com"
        config["APP_PASSWORD"] = "" # Missing
        config["KEYWORD"] = "some_keyword"
        self.assertFalse(self.app._is_config_valid(config))

    def test_is_config_valid_default_password(self):
        config = DEFAULT_CONFIG.copy()
        config["EMAIL_ACCOUNT"] = "user@example.com"
        config["APP_PASSWORD"] = DEFAULT_CONFIG["APP_PASSWORD"] # Still default
        config["KEYWORD"] = "some_keyword"
        self.assertFalse(self.app._is_config_valid(config))

    def test_is_config_valid_missing_keyword(self):
        config = DEFAULT_CONFIG.copy()
        config["EMAIL_ACCOUNT"] = "user@example.com"
        config["APP_PASSWORD"] = "some_password"
        config["KEYWORD"] = "" # Missing
        self.assertFalse(self.app._is_config_valid(config))

    def test_is_config_valid_default_keyword(self):
        config = DEFAULT_CONFIG.copy()
        config["EMAIL_ACCOUNT"] = "user@example.com"
        config["APP_PASSWORD"] = "some_password"
        config["KEYWORD"] = DEFAULT_CONFIG["KEYWORD"] # Still default
        self.assertFalse(self.app._is_config_valid(config))

    def test_is_config_valid_all_set_correctly(self):
        config = {
            "IMAP_SERVER": "imap.gmail.com",
            "EMAIL_ACCOUNT": "myemail@gmail.com",
            "APP_PASSWORD": "mypassword",
            "KEYWORD": "important_stuff",
            "POLL_INTERVAL_SECONDS": 30,
            "MAILBOX": "INBOX"
        }
        self.assertTrue(self.app._is_config_valid(config))

    def test_is_config_valid_only_required_set(self):
        config = DEFAULT_CONFIG.copy()
        config["EMAIL_ACCOUNT"] = "myemail@gmail.com"
        config["APP_PASSWORD"] = "mypassword"
        config["KEYWORD"] = "important_stuff"
        # IMAP_SERVER, POLL_INTERVAL_SECONDS, MAILBOX can remain default or be different
        self.assertTrue(self.app._is_config_valid(config))

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
