import unittest
import sys
import os
from unittest.mock import patch, MagicMock, call
import tkinter as tk
import threading
import queue

# Add parent directory to path to import modules to be tested
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import gui_app


class TestEmailMonitorApp(unittest.TestCase):
    """Unit tests for EmailMonitorApp class"""

    def setUp(self):
        """Set up test fixtures before each test"""
        self.root = MagicMock()
        self.test_config = {
            "IMAP_SERVER": "imap.test.com",
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "test_password",
            "KEYWORD": "test_keyword",
            "POLL_INTERVAL_SECONDS": 60,
            "MAILBOX": "TestBox"
        }
        
        # Setup patches
        self.patch_load_config = patch('gui_app.load_configuration', return_value=self.test_config)
        self.mock_load_config = self.patch_load_config.start()

        # Create app instance with patched dependencies
        with patch('gui_app.EmailMonitorApp.create_main_widgets'), \
             patch('gui_app.EmailMonitorApp.setup_tray_icon'), \
             patch('gui_app.EmailMonitorApp.check_log_queue'), \
             patch('gui_app.EmailMonitorApp._is_config_valid', return_value=True), \
             patch('gui_app.EmailMonitorApp.log_message_gui'):
            self.app = gui_app.EmailMonitorApp(self.root)
            
            # Setup manually since we patched the constructor
            self.app.root = self.root
            self.app.current_config = self.test_config
            self.app.config_loaded = True
            self.app.monitoring_active = False
            self.app.monitoring_thread = None
            self.app.stop_event = threading.Event()
            self.app.processed_email_ids = set()
            self.app.log_queue = queue.Queue()
            
            # Mock GUI components
            self.app.status_label = MagicMock()
            self.app.start_button = MagicMock()
            self.app.stop_button = MagicMock()
            self.app.settings_button = MagicMock()

    def tearDown(self):
        """Clean up after each test"""
        self.patch_load_config.stop()
        if hasattr(self.app, 'monitoring_thread') and self.app.monitoring_thread:
            self.app.stop_event.set()
            if self.app.monitoring_thread.is_alive():
                self.app.monitoring_thread.join(timeout=0.1)

    def test_is_config_valid(self):
        """Test _is_config_valid method with various configurations"""
        # Valid config
        valid_config = {
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "password123",
            "KEYWORD": "test"
        }
        self.assertTrue(self.app._is_config_valid(valid_config))
        
        # Default email account
        invalid_config1 = {
            "EMAIL_ACCOUNT": gui_app.DEFAULT_CONFIG["EMAIL_ACCOUNT"],
            "APP_PASSWORD": "password123",
            "KEYWORD": "test"
        }
        self.assertFalse(self.app._is_config_valid(invalid_config1))
        
        # Missing app password
        invalid_config2 = {
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "",
            "KEYWORD": "test"
        }
        self.assertFalse(self.app._is_config_valid(invalid_config2))
        
        # Default keyword
        invalid_config3 = {
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "password123",
            "KEYWORD": gui_app.DEFAULT_CONFIG["KEYWORD"]
        }
        self.assertFalse(self.app._is_config_valid(invalid_config3))

    @patch('gui_app.EmailMonitorApp.log_message_gui')
    @patch('gui_app.EmailMonitorApp.update_gui_state')
    def test_start_monitoring_with_valid_config(self, mock_update_gui, mock_log):
        """Test start_monitoring with valid configuration"""
        with patch('threading.Thread') as mock_thread:
            # Setup
            self.app.config_loaded = True
            self.app.monitoring_active = False
            
            # Call method
            self.app.start_monitoring()
            
            # Assertions
            self.assertTrue(self.app.monitoring_active)
            self.assertFalse(self.app.stop_event.is_set())
            self.assertEqual(len(self.app.processed_email_ids), 0)
            self.app.status_label.config.assert_called_with(text="Status: Monitoring...")
            mock_update_gui.assert_called_once()
            mock_thread.assert_called_once()
            mock_log.assert_called_with("Monitoring started.")

    @patch('gui_app.EmailMonitorApp.log_message_gui')
    @patch('tkinter.messagebox.showwarning')
    @patch('gui_app.EmailMonitorApp.run_setup_wizard')
    def test_start_monitoring_without_config(self, mock_run_setup, mock_warning, mock_log):
        """Test start_monitoring without valid configuration"""
        # Setup
        self.app.config_loaded = False
        
        # Call method
        self.app.start_monitoring()
        
        # Assertions
        self.assertFalse(self.app.monitoring_active)
        mock_warning.assert_called_once()
        mock_run_setup.assert_called_once_with(force_setup=True)

    @patch('gui_app.EmailMonitorApp.log_message_gui')
    def test_start_monitoring_already_active(self, mock_log):
        """Test start_monitoring when monitoring is already active"""
        # Setup
        self.app.monitoring_active = True
        
        # Call method
        self.app.start_monitoring()
        
        # Assertions
        mock_log.assert_called_with("Monitoring is already active.")

    @patch('gui_app.EmailMonitorApp.log_message_gui')
    @patch('gui_app.EmailMonitorApp.update_gui_state')
    def test_stop_monitoring_when_active(self, mock_update_gui, mock_log):
        """Test stop_monitoring when monitoring is active"""
        # Setup
        self.app.monitoring_active = True
        self.app.monitoring_thread = MagicMock()
        self.app.monitoring_thread.is_alive.return_value = False
        
        # Call method
        self.app.stop_monitoring()
        
        # Assertions
        self.assertFalse(self.app.monitoring_active)
        self.assertTrue(self.app.stop_event.is_set())
        self.app.monitoring_thread.join.assert_called_once()
        self.app.status_label.config.assert_called_with(text="Status: Stopped")
        mock_update_gui.assert_called_once()
        mock_log.assert_any_call("Attempting to stop monitoring...")
        mock_log.assert_any_call("Monitoring stopped.")

    @patch('gui_app.EmailMonitorApp.log_message_gui')
    def test_stop_monitoring_not_active(self, mock_log):
        """Test stop_monitoring when monitoring is not active"""
        # Setup
        self.app.monitoring_active = False
        
        # Call method
        self.app.stop_monitoring()
        
        # Assertions
        mock_log.assert_called_with("Monitoring is not active.")

    @patch('gui_app.EmailMonitorApp.log_message_gui')
    @patch('gui_app.EmailMonitorApp.update_gui_state')
    def test_stop_monitoring_thread_stuck(self, mock_update_gui, mock_log):
        """Test stop_monitoring when thread is stuck"""
        # Setup
        self.app.monitoring_active = True
        self.app.monitoring_thread = MagicMock()
        self.app.monitoring_thread.is_alive.return_value = True
        
        # Call method
        self.app.stop_monitoring()
        
        # Assertions
        self.assertFalse(self.app.monitoring_active)
        self.assertTrue(self.app.stop_event.is_set())
        self.app.monitoring_thread.join.assert_called_once()
        mock_log.assert_any_call("Monitoring thread did not stop in time. It might be stuck.")

    def test_update_gui_state_when_monitoring(self):
        """Test update_gui_state when monitoring is active"""
        # Setup
        self.app.monitoring_active = True
        
        # Call method
        self.app.update_gui_state()
        
        # Assertions
        self.app.start_button.config.assert_called_with(state=tk.DISABLED)
        self.app.stop_button.config.assert_called_with(state=tk.NORMAL)
        self.app.settings_button.config.assert_called_with(state=tk.DISABLED)

    def test_update_gui_state_when_not_monitoring_config_loaded(self):
        """Test update_gui_state when monitoring is inactive and config is loaded"""
        # Setup
        self.app.monitoring_active = False
        self.app.config_loaded = True
        
        # Call method
        self.app.update_gui_state()
        
        # Assertions
        self.app.start_button.config.assert_called_with(state=tk.NORMAL)
        self.app.stop_button.config.assert_called_with(state=tk.DISABLED)
        self.app.settings_button.config.assert_called_with(state=tk.NORMAL)

    def test_update_gui_state_when_not_monitoring_no_config(self):
        """Test update_gui_state when monitoring is inactive and no config is loaded"""
        # Setup
        self.app.monitoring_active = False
        self.app.config_loaded = False
        
        # Call method
        self.app.update_gui_state()
        
        # Assertions
        self.app.start_button.config.assert_called_with(state=tk.DISABLED)
        self.app.stop_button.config.assert_called_with(state=tk.DISABLED)
        self.app.settings_button.config.assert_called_with(state=tk.NORMAL)

    @patch('gui_app.EmailMonitorApp.log_message_gui')
    @patch('tkinter.messagebox.showwarning')
    def test_run_setup_wizard_when_monitoring(self, mock_warning, mock_log):
        """Test run_setup_wizard when monitoring is active"""
        # Setup
        self.app.monitoring_active = True
        
        # Call method
        self.app.run_setup_wizard()
        
        # Assertions
        mock_warning.assert_called_once()
        self.root.focus_set.assert_not_called()

    @patch('gui_app.SetupWizard')
    @patch('gui_app.save_configuration')
    @patch('gui_app.EmailMonitorApp.log_message_gui')
    def test_run_setup_wizard_successful_save(self, mock_log, mock_save, mock_wizard):
        """Test run_setup_wizard with successful configuration save"""
        # Setup
        self.app.monitoring_active = False
        wizard_instance = MagicMock()
        wizard_instance.result_config = {"new": "config"}
        mock_wizard.return_value = wizard_instance
        mock_save.return_value = True
        
        # Call method
        self.app.run_setup_wizard()
        
        # Assertions
        mock_wizard.assert_called_once_with(self.root, initial_config=self.app.current_config)
        mock_save.assert_called_once_with({"new": "config"})
        self.assertEqual(self.app.current_config, {"new": "config"})
        mock_log.assert_any_call("Configuration saved successfully.")
        self.root.focus_set.assert_called_once()
        self.root.lift.assert_called_once()

    @patch('gui_app.SetupWizard')
    @patch('gui_app.save_configuration')
    @patch('gui_app.EmailMonitorApp.log_message_gui')
    def test_run_setup_wizard_save_failure(self, mock_log, mock_save, mock_wizard):
        """Test run_setup_wizard with configuration save failure"""
        # Setup
        self.app.monitoring_active = False
        wizard_instance = MagicMock()
        wizard_instance.result_config = {"new": "config"}
        mock_wizard.return_value = wizard_instance
        mock_save.return_value = False
        
        # Call method
        self.app.run_setup_wizard()
        
        # Assertions
        mock_save.assert_called_once()
        self.assertNotEqual(self.app.current_config, {"new": "config"})
        mock_log.assert_any_call("Failed to save configuration.")

    @patch('gui_app.SetupWizard')
    @patch('gui_app.EmailMonitorApp.log_message_gui')
    def test_run_setup_wizard_cancelled(self, mock_log, mock_wizard):
        """Test run_setup_wizard when wizard is cancelled"""
        # Setup
        self.app.monitoring_active = False
        wizard_instance = MagicMock()
        wizard_instance.result_config = None  # Cancelled
        mock_wizard.return_value = wizard_instance
        
        # Call method
        self.app.run_setup_wizard()
        
        # Assertions
        mock_log.assert_any_call("Setup wizard was cancelled.")

    def test_log_message_gui(self):
        """Test log_message_gui puts message in queue"""
        # Setup
        test_message = "Test log message"
        
        # Call method
        self.app.log_message_gui(test_message)
        
        # Assert message was added to queue
        self.assertEqual(self.app.log_queue.get(), test_message)
        self.assertTrue(self.app.log_queue.empty())

    @patch('tkinter.messagebox.askyesnocancel')
    @patch('gui_app.EmailMonitorApp.stop_monitoring')
    @patch('gui_app.EmailMonitorApp.quit_application')
    @patch('gui_app.EmailMonitorApp.hide_to_tray')
    def test_on_closing_when_monitoring_exit(self, mock_hide, mock_quit, mock_stop, mock_dialog):
        """Test on_closing when monitoring is active and user chooses to exit"""
        # Setup
        self.app.monitoring_active = True
        mock_dialog.return_value = True  # True = Stop and exit
        
        # Call method
        self.app.on_closing()
        
        # Assertions
        mock_dialog.assert_called_once()
        mock_stop.assert_called_once()
        mock_quit.assert_called_once()
        mock_hide.assert_not_called()

    @patch('tkinter.messagebox.askyesnocancel')
    @patch('gui_app.EmailMonitorApp.stop_monitoring')
    @patch('gui_app.EmailMonitorApp.quit_application')
    @patch('gui_app.EmailMonitorApp.hide_to_tray')
    def test_on_closing_when_monitoring_minimize(self, mock_hide, mock_quit, mock_stop, mock_dialog):
        """Test on_closing when monitoring is active and user chooses to minimize"""
        # Setup
        self.app.monitoring_active = True
        mock_dialog.return_value = False  # False = Minimize to tray
        
        # Call method
        self.app.on_closing()
        
        # Assertions
        mock_dialog.assert_called_once()
        mock_stop.assert_not_called()
        mock_quit.assert_not_called()
        mock_hide.assert_called_once()

    @patch('tkinter.messagebox.askyesno')
    @patch('gui_app.EmailMonitorApp.quit_application')
    @patch('gui_app.EmailMonitorApp.hide_to_tray')
    def test_on_closing_when_not_monitoring_minimize(self, mock_hide, mock_quit, mock_dialog):
        """Test on_closing when not monitoring and user chooses to minimize"""
        # Setup
        self.app.monitoring_active = False
        mock_dialog.return_value = True  # True = Minimize to tray
        
        # Call method
        self.app.on_closing()
        
        # Assertions
        mock_dialog.assert_called_once()
        mock_hide.assert_called_once()
        mock_quit.assert_not_called()

    @patch('tkinter.messagebox.askyesno')
    @patch('gui_app.EmailMonitorApp.quit_application')
    @patch('gui_app.EmailMonitorApp.hide_to_tray')
    def test_on_closing_when_not_monitoring_quit(self, mock_hide, mock_quit, mock_dialog):
        """Test on_closing when not monitoring and user chooses to quit"""
        # Setup
        self.app.monitoring_active = False
        mock_dialog.return_value = False  # False = Quit
        
        # Call method
        self.app.on_closing()
        
        # Assertions
        mock_dialog.assert_called_once()
        mock_hide.assert_not_called()
        mock_quit.assert_called_once()


class TestMonitoringLoop(unittest.TestCase):
    """Unit tests for the monitoring loop functionality"""

    def setUp(self):
        """Set up test fixtures before each test"""
        self.root = MagicMock()
        self.test_config = {
            "IMAP_SERVER": "imap.test.com",
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "test_password",
            "KEYWORD": "test_keyword",
            "POLL_INTERVAL_SECONDS": 0.01,  # Short interval for testing
            "MAILBOX": "TestBox"
        }
        
        # Create app with mocked components
        with patch('gui_app.load_configuration', return_value=self.test_config), \
             patch('gui_app.EmailMonitorApp.create_main_widgets'), \
             patch('gui_app.EmailMonitorApp.setup_tray_icon'), \
             patch('gui_app.EmailMonitorApp.check_log_queue'), \
             patch('gui_app.EmailMonitorApp._is_config_valid', return_value=True), \
             patch('gui_app.EmailMonitorApp.log_message_gui'):
            self.app = gui_app.EmailMonitorApp(self.root)
            
            # Setup manually since we patched the constructor
            self.app.root = self.root
            self.app.current_config = self.test_config
            self.app.config_loaded = True
            self.app.monitoring_active = False
            self.app.monitoring_thread = None
            self.app.stop_event = threading.Event()
            self.app.processed_email_ids = set()
            self.app.log_queue = queue.Queue()
            
            # Create a real logger for capturing messages
            self.app.log_message_gui = self.capture_log

        self.log_messages = []

    def capture_log(self, message):
        """Capture log messages for testing"""
        self.log_messages.append(message)

    @patch('gui_app.connect_to_gmail')
    def test_monitoring_loop_connect_failure(self, mock_connect):
        """Test monitoring loop when connection fails"""
        # Setup
        mock_connect.return_value = None  # Connection failed
        
        # Run monitoring loop for a short time
        self.app.stop_event.clear()
        thread = threading.Thread(target=self.app._monitoring_loop)
        thread.daemon = True
        thread.start()
        
        # Let it run briefly
        time.sleep(0.05)
        self.app.stop_event.set()
        thread.join(timeout=0.1)
        
        # Assertions
        mock_connect.assert_called_with(self.test_config, logger=self.app.log_message_gui)
        self.assertIn("Failed to connect", " ".join(self.log_messages))

    @patch('gui_app.connect_to_gmail')
    @patch('gui_app.em_search_emails')
    def test_monitoring_loop_no_emails(self, mock_search, mock_connect):
        """Test monitoring loop when no emails are found"""
        # Setup
        mock_mail = MagicMock()
        mock_connect.return_value = mock_mail
        mock_search.return_value = []  # No emails
        
        # Run monitoring loop for a short time
        self.app.stop_event.clear()
        thread = threading.Thread(target=self.app._monitoring_loop)
        thread.daemon = True
        thread.start()
        
        # Let it run briefly
        time.sleep(0.05)
        self.app.stop_event.set()
        thread.join(timeout=0.1)
        
        # Assertions
        mock_connect.assert_called_with(self.test_config, logger=self.app.log_message_gui)
        mock_search.assert_called_with(mock_mail, self.test_config, logger=self.app.log_message_gui)
        self.assertIn("No new emails found", " ".join(self.log_messages))

    @patch('gui_app.connect_to_gmail')
    @patch('gui_app.em_search_emails')
    def test_monitoring_loop_with_emails_already_processed(self, mock_search, mock_connect):
        """Test monitoring loop with emails that have already been processed"""
        # Setup
        mock_mail = MagicMock()
        mock_connect.return_value = mock_mail
        email_id = b'1'
        mock_search.return_value = [email_id]
        
        # Mark email as already processed
        self.app.processed_email_ids.add(email_id)
        
        # Run monitoring loop for a short time
        self.app.stop_event.clear()
        thread = threading.Thread(target=self.app._monitoring_loop)
        thread.daemon = True
        thread.start()
        
        # Let it run briefly
        time.sleep(0.05)
        self.app.stop_event.set()
        thread.join(timeout=0.1)
        
        # Assertions
        mock_connect.assert_called_with(self.test_config, logger=self.app.log_message_gui)
        mock_search.assert_called_with(mock_mail, self.test_config, logger=self.app.log_message_gui)
        # Verify email was not fetched (since it was already processed)
        mock_mail.fetch.assert_not_called()

if __name__ == '__main__':
    unittest.main()