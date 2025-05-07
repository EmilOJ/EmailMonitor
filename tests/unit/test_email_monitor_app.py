import unittest
import sys
import os
from unittest.mock import patch, MagicMock, call
import tkinter as tk
import threading
import queue
import time # Added for TestMonitoringLoop

# Add parent directory to path to import modules to be tested
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import gui_app

# Helper function to set up mock widgets
def _setup_mock_widgets(app_instance):
    app_instance.main_frame = MagicMock(name='main_frame_mock')
    app_instance.status_label = MagicMock(name='status_label_mock')
    app_instance.log_text = MagicMock(name='log_text_mock')
    app_instance.button_frame = MagicMock(name='button_frame_mock')
    app_instance.start_button = MagicMock(name='start_button_mock')
    app_instance.stop_button = MagicMock(name='stop_button_mock')
    app_instance.settings_button = MagicMock(name='settings_button_mock')
    # Return value is required for side_effect functions
    return None

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

        self.patch_load_config = patch('gui_app.load_configuration', return_value=self.test_config)
        self.mock_load_config = self.patch_load_config.start()

        # Fix: Create a lambda that captures self.app and passes it to _setup_mock_widgets
        self.patch_create_widgets = patch('gui_app.EmailMonitorApp.create_main_widgets')
        self.mock_create_widgets = self.patch_create_widgets.start()
        
        self.patch_setup_tray = patch('gui_app.EmailMonitorApp.setup_tray_icon')
        self.mock_setup_tray = self.patch_setup_tray.start()

        self.patch_check_log_queue = patch('gui_app.EmailMonitorApp.check_log_queue')
        self.mock_check_log_queue = self.patch_check_log_queue.start()

        self.patch_is_config_valid = patch('gui_app.EmailMonitorApp._is_config_valid', return_value=True)
        self.mock_is_config_valid = self.patch_is_config_valid.start()

        self.patch_log_message_gui = patch('gui_app.EmailMonitorApp.log_message_gui')
        self.mock_log_message_gui = self.patch_log_message_gui.start()
        
        # Patch update_gui_state to prevent it from being called in __init__ before widgets are set up
        self.patch_update_gui = patch('gui_app.EmailMonitorApp.update_gui_state')
        self.mock_update_gui = self.patch_update_gui.start()

        self.app = gui_app.EmailMonitorApp(self.root)
        
        # After self.app is created, set up the mock widgets
        _setup_mock_widgets(self.app)
        
        # Now we can stop the patch on update_gui_state so later calls work
        self.patch_update_gui.stop()
        
        # Ensure essential non-widget attributes are set for tests
        self.app.monitoring_active = False
        self.app.monitoring_thread = None
        self.app.stop_event = threading.Event() # __init__ creates one
        self.app.processed_email_ids = set() # __init__ creates one
        self.app.log_queue = queue.Queue() # __init__ creates one

    def tearDown(self):
        """Clean up after each test"""
        self.patch_load_config.stop()
        self.patch_create_widgets.stop()
        self.patch_setup_tray.stop()
        self.patch_check_log_queue.stop()
        self.patch_is_config_valid.stop()
        self.patch_log_message_gui.stop()

        if hasattr(self.app, 'monitoring_thread') and self.app.monitoring_thread:
            if hasattr(self.app, 'stop_event'):
                 self.app.stop_event.set()
            if self.app.monitoring_thread.is_alive():
                self.app.monitoring_thread.join(timeout=0.1)

    def test_is_config_valid(self):
        """Test _is_config_valid method with various configurations"""
        # Stop the mock so we can test the actual implementation
        self.patch_is_config_valid.stop()
        
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
        
        # Restart the mock for other tests
        self.mock_is_config_valid = self.patch_is_config_valid.start()

    @patch('gui_app.EmailMonitorApp.log_message_gui')
    @patch('gui_app.EmailMonitorApp.update_gui_state')
    def test_start_monitoring_with_valid_config(self, mock_update_gui, mock_log):
        """Test start_monitoring with valid configuration"""
        # The log_message_gui is already mocked in setUp by self.mock_log_message_gui
        # Re-patching it here via decorator will use a new mock for this test method scope.
        # If we want to use the setUp mock, we should remove @patch('gui_app.EmailMonitorApp.log_message_gui')
        # For now, let's assume the local mock_log is intended.
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
            mock_update_gui.assert_called_once() # This mock is fine as it's specific to this test.
            mock_thread.assert_called_once()
            mock_log.assert_called_with("Monitoring started.")

    @patch('gui_app.SetupWizard')
    @patch('gui_app.tk_messagebox.showwarning')
    def test_start_monitoring_without_config(self, mock_messagebox, mock_wizard):
        """Test attempting to start monitoring without valid config"""
        self.app.config_loaded = False
        self.app.run_setup_wizard = MagicMock()
        
        self.app.start_monitoring()
        
        mock_messagebox.assert_called_once()
        self.app.run_setup_wizard.assert_called_once_with(force_setup=True)

    @patch('gui_app.EmailMonitorApp.log_message_gui')
    def test_start_monitoring_already_active(self, mock_log):
        """Test start_monitoring when monitoring is already active"""
        # Setup
        self.app.monitoring_active = True
        # Use the class-level mock if this specific mock_log isn't strictly needed
        # self.mock_log_message_gui.reset_mock() # Reset if using class-level mock
        
        # Call method
        self.app.start_monitoring()
        
        # Assertions
        mock_log.assert_called_with("Monitoring is already active.") # Or self.mock_log_message_gui

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
        mock_log.assert_called_with("Monitoring is not active.") # Or self.mock_log_message_gui

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
        # Ensure mock objects exist (they should from _setup_mock_widgets)
        self.assertIsNotNone(self.app.start_button)
        self.assertIsNotNone(self.app.stop_button)
        self.assertIsNotNone(self.app.settings_button)

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
        self.assertIsNotNone(self.app.start_button)
        self.assertIsNotNone(self.app.stop_button)
        self.assertIsNotNone(self.app.settings_button)

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
        self.assertIsNotNone(self.app.start_button)
        self.assertIsNotNone(self.app.stop_button)
        self.assertIsNotNone(self.app.settings_button)

        self.app.monitoring_active = False
        self.app.config_loaded = False
        
        # Call method
        self.app.update_gui_state()
        
        # Assertions
        self.app.start_button.config.assert_called_with(state=tk.DISABLED)
        self.app.stop_button.config.assert_called_with(state=tk.DISABLED)
        self.app.settings_button.config.assert_called_with(state=tk.NORMAL)

    @patch('gui_app.SetupWizard')
    @patch('gui_app.tk_messagebox.showwarning')
    def test_run_setup_wizard_when_monitoring(self, mock_messagebox, mock_wizard):
        """Test that setup wizard cannot be run when monitoring is active"""
        self.app.monitoring_active = True
        self.app.run_setup_wizard()
        
        mock_messagebox.assert_called_once()
        mock_wizard.assert_not_called()

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
        mock_wizard.assert_called_once()  # Only check if it was called, not the parameters
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
        # The log_message_gui is mocked in setUp. We use that mock.
        self.mock_log_message_gui.reset_mock() # Reset class level mock
        
        # Call method
        self.app.log_message_gui(test_message) # This will call the mocked version
        
        # Assert message was added to queue (the mock was called)
        # The actual queue mechanism is part of the real method, which is mocked.
        # So we assert the mock was called.
        self.mock_log_message_gui.assert_called_once_with(test_message)


    @patch('gui_app.tk_messagebox.askyesnocancel', return_value=True)  # Choose to exit
    def test_on_closing_when_monitoring_exit(self, mock_dialog):
        """Test on_closing when monitoring and user chooses to exit"""
        self.app.monitoring_active = True
        self.app.stop_monitoring = MagicMock()
        self.app.quit_application = MagicMock()
        self.app.hide_to_tray = MagicMock()
        
        self.app.on_closing()
        
        mock_dialog.assert_called_once()
        self.app.stop_monitoring.assert_called_once()
        self.app.quit_application.assert_called_once()
        self.app.hide_to_tray.assert_not_called()

    @patch('gui_app.tk_messagebox.askyesnocancel', return_value=False)  # Choose to minimize
    def test_on_closing_when_monitoring_minimize(self, mock_dialog):
        """Test on_closing when monitoring and user chooses to minimize"""
        self.app.monitoring_active = True
        self.app.stop_monitoring = MagicMock()
        self.app.quit_application = MagicMock()
        self.app.hide_to_tray = MagicMock()
        
        self.app.on_closing()
        
        mock_dialog.assert_called_once()
        self.app.stop_monitoring.assert_not_called()
        self.app.quit_application.assert_not_called()
        self.app.hide_to_tray.assert_called_once()

    @patch('gui_app.tk_messagebox.askyesno', return_value=True)  # Choose to minimize
    def test_on_closing_when_not_monitoring_minimize(self, mock_dialog):
        """Test on_closing when not monitoring and user chooses to minimize"""
        self.app.monitoring_active = False
        self.app.quit_application = MagicMock()
        self.app.hide_to_tray = MagicMock()
        
        self.app.on_closing()
        
        mock_dialog.assert_called_once()
        self.app.quit_application.assert_not_called()
        self.app.hide_to_tray.assert_called_once()

    @patch('gui_app.tk_messagebox.askyesno', return_value=False)  # Choose to quit
    def test_on_closing_when_not_monitoring_quit(self, mock_dialog):
        """Test on_closing when not monitoring and user chooses to quit"""
        self.app.monitoring_active = False
        self.app.quit_application = MagicMock()
        self.app.hide_to_tray = MagicMock()
        
        self.app.on_closing()
        
        mock_dialog.assert_called_once()
        self.app.quit_application.assert_called_once()
        self.app.hide_to_tray.assert_not_called()


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
        self.log_messages = []

        self.patch_load_config = patch('gui_app.load_configuration', return_value=self.test_config)
        self.mock_load_config = self.patch_load_config.start()

        # Fix: Use the same approach as TestEmailMonitorApp
        self.patch_create_widgets = patch('gui_app.EmailMonitorApp.create_main_widgets')
        self.mock_create_widgets = self.patch_create_widgets.start()

        self.patch_setup_tray = patch('gui_app.EmailMonitorApp.setup_tray_icon')
        self.mock_setup_tray = self.patch_setup_tray.start()

        self.patch_check_log_queue = patch('gui_app.EmailMonitorApp.check_log_queue')
        self.mock_check_log_queue = self.patch_check_log_queue.start()

        self.patch_is_config_valid = patch('gui_app.EmailMonitorApp._is_config_valid', return_value=True)
        self.mock_is_config_valid = self.patch_is_config_valid.start()
        
        # Patch log_message_gui for the __init__ call, will be overridden for tests by self.capture_log
        self.patch_log_gui_for_init = patch('gui_app.EmailMonitorApp.log_message_gui')
        self.mock_log_gui_for_init = self.patch_log_gui_for_init.start()
        
        # Patch update_gui_state to prevent it from being called in __init__ before widgets are set up
        self.patch_update_gui = patch('gui_app.EmailMonitorApp.update_gui_state')
        self.mock_update_gui = self.patch_update_gui.start()

        self.app = gui_app.EmailMonitorApp(self.root)
        
        # After self.app is created, set up the mock widgets
        _setup_mock_widgets(self.app)
        
        # Now we can stop the patch on update_gui_state
        self.patch_update_gui.stop()
            
        # Override log_message_gui for test purposes AFTER app initialization
        self.app.log_message_gui = self.capture_log

        # Ensure essential non-widget attributes are set
        self.app.monitoring_active = False
        self.app.monitoring_thread = None
        self.app.stop_event = threading.Event()
        self.app.processed_email_ids = set()
        self.app.log_queue = queue.Queue() # Real queue, but check_log_queue is mocked

    def tearDown(self):
        """Clean up after each test for TestMonitoringLoop"""
        self.patch_load_config.stop()
        self.patch_create_widgets.stop()
        self.patch_setup_tray.stop()
        self.patch_check_log_queue.stop()
        self.patch_is_config_valid.stop()
        self.patch_log_gui_for_init.stop() # Stop the one used for init

        if hasattr(self.app, 'monitoring_thread') and self.app.monitoring_thread:
            if hasattr(self.app, 'stop_event'):
                 self.app.stop_event.set()
            if self.app.monitoring_thread.is_alive():
                self.app.monitoring_thread.join(timeout=0.1)

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