import unittest
from unittest.mock import MagicMock, patch, call
import tkinter as tk
import queue
import threading
import time

# Add the parent directory to the Python path to allow importing gui_app
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from gui_app import EmailMonitorApp, DEFAULT_CONFIG, SetupWizard

# Minimal valid config for testing app startup when config is considered loaded
MINIMAL_VALID_CONFIG = {
    "IMAP_SERVER": "imap.gmail.com",
    "EMAIL_ACCOUNT": "test@example.com",
    "APP_PASSWORD": "password",
    "KEYWORD": "testkeyword",
    "POLL_INTERVAL_SECONDS": 1, # Short for testing
    "MAILBOX": "INBOX"
}

class TestEmailMonitorApp(unittest.TestCase):

    def setUp(self):
        # Create a root window for the app, but we won't call mainloop
        self.root = tk.Tk()
        self.root.withdraw() # Hide the window during tests

        # Patch external dependencies and lengthy operations
        self.mock_load_config = patch('gui_app.load_configuration').start()
        self.mock_save_config = patch('gui_app.save_configuration').start()
        self.mock_setup_wizard_class = patch('gui_app.SetupWizard').start()
        self.mock_connect_gmail = patch('email_monitor.connect_to_gmail').start()
        self.mock_search_emails = patch('email_monitor.search_emails').start()
        self.mock_decode_subject = patch('email_monitor.decode_subject').start()
        self.mock_extract_link = patch('email_monitor.extract_link_from_email').start()
        self.mock_open_link = patch('email_monitor.open_link_in_browser').start()
        self.mock_mark_as_read = patch('email_monitor.mark_as_read').start()
        self.mock_pystray_icon = patch('pystray.Icon').start()
        self.mock_pil_image = patch('PIL.Image.open').start()
        self.mock_os_path_exists = patch('os.path.exists').start()

        # Default behavior for mocks
        self.mock_load_config.return_value = MINIMAL_VALID_CONFIG.copy()
        self.mock_os_path_exists.return_value = True # Assume icon.png exists by default
        self.mock_setup_wizard_instance = MagicMock()
        self.mock_setup_wizard_class.return_value = self.mock_setup_wizard_instance
        self.mock_setup_wizard_instance.result_config = None # Default to wizard cancelled

        # Instantiate the app
        self.app = EmailMonitorApp(self.root)
        # Ensure log queue is processed at least once for initial messages
        self.app.check_log_queue() 

    def tearDown(self):
        # Stop all patches
        patch.stopall()
        # Destroy the root window if it still exists
        if self.root:
            self.root.destroy()
            self.root = None
        # Clean up any threads that might have been started
        if hasattr(self.app, 'monitoring_thread') and self.app.monitoring_thread and self.app.monitoring_thread.is_alive():
            self.app.stop_event.set()
            self.app.monitoring_thread.join(timeout=1)

    def test_app_initialization_config_loaded(self):
        self.mock_load_config.assert_called_once()
        self.assertTrue(self.app.config_loaded)
        self.assertEqual(self.app.current_config, MINIMAL_VALID_CONFIG)
        self.assertIn("Configuration loaded.", self.app.log_text.get("1.0", tk.END))
        self.app.start_button.config('state')[-1] == tk.NORMAL
        self.app.settings_button.config('state')[-1] == tk.NORMAL
        self.mock_setup_wizard_class.assert_not_called() # Should not run wizard if config is valid

    def test_app_initialization_config_invalid(self):
        self.mock_load_config.return_value = DEFAULT_CONFIG.copy() # Invalid config
        # Re-initialize app for this specific test case
        self.app = EmailMonitorApp(self.root)
        self.app.check_log_queue()

        self.assertFalse(self.app.config_loaded)
        self.assertIn("Initial configuration is incomplete or missing.", self.app.log_text.get("1.0", tk.END))
        self.mock_setup_wizard_class.assert_called_once_with(self.root, initial_config=DEFAULT_CONFIG.copy())
        self.app.start_button.config('state')[-1] == tk.DISABLED

    def test_run_setup_wizard_monitoring_active(self):
        self.app.monitoring_active = True
        with patch('tkinter.messagebox.showwarning') as mock_showwarning:
            self.app.run_setup_wizard()
            mock_showwarning.assert_called_once_with("Settings Locked", "Cannot change settings while monitoring is active.", parent=self.app.root)
            self.mock_setup_wizard_class.assert_not_called() # Wizard should not open

    def test_run_setup_wizard_save_config(self):
        new_config_data = {"KEYWORD": "new_keyword", **MINIMAL_VALID_CONFIG}
        del new_config_data['POLL_INTERVAL_SECONDS'] # remove to ensure it is added by wizard
        new_config_data['POLL_INTERVAL_SECONDS'] = 99 # Make sure it is an int

        self.mock_setup_wizard_instance.result_config = new_config_data
        self.mock_save_config.return_value = True

        self.app.run_setup_wizard()

        self.mock_setup_wizard_class.assert_called_once_with(self.root, initial_config=self.app.current_config)
        self.mock_save_config.assert_called_once_with(new_config_data)
        self.assertEqual(self.app.current_config, new_config_data)
        self.assertTrue(self.app.config_loaded)
        self.assertIn("Configuration saved successfully.", self.app.log_text.get("1.0", tk.END))
        # Check if GUI state is updated (e.g. start button enabled)
        self.assertEqual(self.app.start_button.cget('state'), tk.NORMAL)

    def test_run_setup_wizard_save_fail(self):
        self.mock_setup_wizard_instance.result_config = MINIMAL_VALID_CONFIG.copy()
        self.mock_save_config.return_value = False # Simulate save failure

        initial_config_before_wizard = self.app.current_config.copy()
        self.app.run_setup_wizard()

        self.mock_save_config.assert_called_once_with(MINIMAL_VALID_CONFIG.copy())
        self.assertEqual(self.app.current_config, initial_config_before_wizard) # Config should not change
        self.assertIn("Failed to save configuration.", self.app.log_text.get("1.0", tk.END))

    def test_run_setup_wizard_cancelled(self):
        self.mock_setup_wizard_instance.result_config = None # Wizard cancelled
        initial_config_before_wizard = self.app.current_config.copy()

        self.app.run_setup_wizard()

        self.mock_save_config.assert_not_called()
        self.assertEqual(self.app.current_config, initial_config_before_wizard)
        self.assertIn("Setup wizard was cancelled.", self.app.log_text.get("1.0", tk.END))

    def test_start_monitoring_config_not_loaded(self):
        self.app.config_loaded = False
        self.app.update_gui_state() # Ensure button is disabled
        with patch('tkinter.messagebox.showwarning') as mock_showwarning:
            self.app.start_button.invoke()
            mock_showwarning.assert_called_once_with("Configuration Missing", "Please complete the setup wizard first.", parent=self.app.root)
            self.mock_setup_wizard_class.assert_called_with(self.app.root, initial_config=self.app.current_config) # force_setup=True is implied by this call path
            self.assertFalse(self.app.monitoring_active)

    def test_start_monitoring_already_active(self):
        self.app.monitoring_active = True
        self.app.update_gui_state()
        self.app.start_button.invoke() # Try to start again
        self.assertIn("Monitoring is already active.", self.app.log_text.get("1.0", tk.END))
        self.assertTrue(self.app.monitoring_active) # Should remain true
        # Check that thread was not started again (hard to check directly without more mocks)

    @patch('threading.Thread')
    def test_start_monitoring_success(self, mock_thread_class):
        self.app.config_loaded = True
        self.app.update_gui_state()

        mock_thread_instance = MagicMock()
        mock_thread_class.return_value = mock_thread_instance

        self.app.start_button.invoke()

        self.assertTrue(self.app.monitoring_active)
        self.assertEqual(self.app.status_label.cget("text"), "Status: Monitoring...")
        self.assertIn("Monitoring started.", self.app.log_text.get("1.0", tk.END))
        self.assertEqual(self.app.start_button.cget('state'), tk.DISABLED)
        self.assertEqual(self.app.stop_button.cget('state'), tk.NORMAL)
        self.assertEqual(self.app.settings_button.cget('state'), tk.DISABLED)
        mock_thread_class.assert_called_once_with(target=self.app._monitoring_loop, daemon=True)
        mock_thread_instance.start.assert_called_once()
        self.assertFalse(self.app.stop_event.is_set())
        self.assertEqual(len(self.app.processed_email_ids), 0)

    def test_stop_monitoring_not_active(self):
        self.app.monitoring_active = False
        self.app.update_gui_state()
        self.app.stop_button.invoke()
        self.assertIn("Monitoring is not active.", self.app.log_text.get("1.0", tk.END))
        self.assertFalse(self.app.monitoring_active)

    def test_stop_monitoring_success(self):
        # Start monitoring first (simplified)
        self.app.monitoring_active = True
        self.app.monitoring_thread = MagicMock(spec=threading.Thread)
        self.app.monitoring_thread.is_alive.return_value = True # Initially alive
        self.app.update_gui_state()

        # Define a side effect for join to simulate thread stopping
        def stop_thread_effect(*args, **kwargs):
            self.app.monitoring_thread.is_alive.return_value = False
        self.app.monitoring_thread.join.side_effect = stop_thread_effect

        self.app.stop_button.invoke()

        self.assertTrue(self.app.stop_event.is_set())
        self.assertFalse(self.app.monitoring_active)
        self.app.monitoring_thread.join.assert_called_once()
        self.assertIn("Monitoring stopped.", self.app.log_text.get("1.0", tk.END))
        self.assertEqual(self.app.status_label.cget("text"), "Status: Stopped")
        self.assertEqual(self.app.start_button.cget('state'), tk.NORMAL)
        self.assertEqual(self.app.stop_button.cget('state'), tk.DISABLED)
        self.assertEqual(self.app.settings_button.cget('state'), tk.NORMAL)

    def test_stop_monitoring_thread_timeout(self):
        self.app.monitoring_active = True
        self.app.monitoring_thread = MagicMock(spec=threading.Thread)
        self.app.monitoring_thread.is_alive.return_value = True # Stays alive
        self.app.update_gui_state()

        self.app.stop_button.invoke()

        self.assertTrue(self.app.stop_event.is_set())
        self.assertFalse(self.app.monitoring_active) # App state changes regardless of thread
        self.app.monitoring_thread.join.assert_called_once()
        self.assertIn("Monitoring thread did not stop in time.", self.app.log_text.get("1.0", tk.END))
        self.assertEqual(self.app.status_label.cget("text"), "Status: Stopped")

    def test_log_message_gui(self):
        self.app.log_message_gui("Test log message")
        # Process the queue
        self.app.check_log_queue()
        self.assertIn("Test log message", self.app.log_text.get("1.0", tk.END))

    def test_check_log_queue_empty(self):
        # Ensure queue is empty
        while not self.app.log_queue.empty():
            self.app.log_queue.get_nowait()
        
        initial_log_content = self.app.log_text.get("1.0", tk.END)
        self.app.check_log_queue() # Should do nothing and not error
        self.assertEqual(initial_log_content, self.app.log_text.get("1.0", tk.END))

    def test_update_gui_state_monitoring_active(self):
        self.app.monitoring_active = True
        self.app.config_loaded = True # Assume config is fine
        self.app.update_gui_state()
        self.assertEqual(self.app.start_button.cget('state'), tk.DISABLED)
        self.assertEqual(self.app.stop_button.cget('state'), tk.NORMAL)
        self.assertEqual(self.app.settings_button.cget('state'), tk.DISABLED)

    def test_update_gui_state_monitoring_inactive_config_loaded(self):
        self.app.monitoring_active = False
        self.app.config_loaded = True
        self.app.update_gui_state()
        self.assertEqual(self.app.start_button.cget('state'), tk.NORMAL)
        self.assertEqual(self.app.stop_button.cget('state'), tk.DISABLED)
        self.assertEqual(self.app.settings_button.cget('state'), tk.NORMAL)

    def test_update_gui_state_monitoring_inactive_config_not_loaded(self):
        self.app.monitoring_active = False
        self.app.config_loaded = False
        self.app.update_gui_state()
        self.assertEqual(self.app.start_button.cget('state'), tk.DISABLED)
        self.assertEqual(self.app.stop_button.cget('state'), tk.DISABLED)
        self.assertEqual(self.app.settings_button.cget('state'), tk.NORMAL) # Settings always available

    @patch('tkinter.messagebox.askyesnocancel')
    @patch('gui_app.EmailMonitorApp.quit_application')
    @patch('gui_app.EmailMonitorApp.hide_to_tray')
    def test_on_closing_monitoring_active_stop_and_exit(self, mock_hide_to_tray, mock_quit_app, mock_askync):
        self.app.monitoring_active = True
        mock_askync.return_value = True # User chooses to stop and exit
        
        # Mock stop_monitoring to check it's called
        self.app.stop_monitoring = MagicMock()

        self.app.on_closing()

        mock_askync.assert_called_once()
        self.app.stop_monitoring.assert_called_once()
        mock_quit_app.assert_called_once()
        mock_hide_to_tray.assert_not_called()

    @patch('tkinter.messagebox.askyesnocancel')
    @patch('gui_app.EmailMonitorApp.quit_application')
    @patch('gui_app.EmailMonitorApp.hide_to_tray')
    def test_on_closing_monitoring_active_minimize(self, mock_hide_to_tray, mock_quit_app, mock_askync):
        self.app.monitoring_active = True
        mock_askync.return_value = False # User chooses to minimize
        self.app.stop_monitoring = MagicMock()

        self.app.on_closing()

        mock_askync.assert_called_once()
        self.app.stop_monitoring.assert_not_called()
        mock_quit_app.assert_not_called()
        mock_hide_to_tray.assert_called_once()

    @patch('tkinter.messagebox.askyesnocancel')
    @patch('gui_app.EmailMonitorApp.quit_application')
    @patch('gui_app.EmailMonitorApp.hide_to_tray')
    def test_on_closing_monitoring_active_cancel(self, mock_hide_to_tray, mock_quit_app, mock_askync):
        self.app.monitoring_active = True
        mock_askync.return_value = None # User cancels
        self.app.stop_monitoring = MagicMock()

        self.app.on_closing()

        mock_askync.assert_called_once()
        self.app.stop_monitoring.assert_not_called()
        mock_quit_app.assert_not_called()
        mock_hide_to_tray.assert_not_called()

    @patch('tkinter.messagebox.askyesno')
    @patch('gui_app.EmailMonitorApp.quit_application')
    @patch('gui_app.EmailMonitorApp.hide_to_tray')
    def test_on_closing_monitoring_inactive_minimize(self, mock_hide_to_tray, mock_quit_app, mock_askyn):
        self.app.monitoring_active = False
        mock_askyn.return_value = True # User chooses to minimize

        self.app.on_closing()
        mock_askyn.assert_called_once()
        mock_hide_to_tray.assert_called_once()
        mock_quit_app.assert_not_called()

    @patch('tkinter.messagebox.askyesno')
    @patch('gui_app.EmailMonitorApp.quit_application')
    @patch('gui_app.EmailMonitorApp.hide_to_tray')
    def test_on_closing_monitoring_inactive_quit(self, mock_hide_to_tray, mock_quit_app, mock_askyn):
        self.app.monitoring_active = False
        mock_askyn.return_value = False # User chooses to quit

        self.app.on_closing()
        mock_askyn.assert_called_once()
        mock_hide_to_tray.assert_not_called()
        mock_quit_app.assert_called_once()

    def test_setup_tray_icon_pystray_not_available(self):
        with patch('gui_app.pystray', None): # Simulate pystray not imported
            self.app.tray_icon = None # Reset from initial setup
            self.app.setup_tray_icon()
            self.assertIsNone(self.app.tray_icon)
            self.assertIn("pystray or Pillow not found", self.app.log_text.get("1.0", tk.END))

    def test_setup_tray_icon_icon_file_not_found_creates_dummy(self):
        self.mock_os_path_exists.return_value = False # icon.png does not exist
        mock_dummy_image_save = MagicMock()
        self.mock_pil_image.new.return_value.save = mock_dummy_image_save
        
        # Reset tray_icon and re-run setup_tray_icon
        self.app.tray_icon = None 
        with patch('threading.Thread') as mock_tray_thread: # Prevent actual thread start
            self.app.setup_tray_icon()

        self.assertIsNotNone(self.app.tray_icon)
        self.mock_pil_image.new.assert_called_once_with('RGB', (64, 64), color='blue')
        mock_dummy_image_save.assert_called_once_with("icon.png")
        self.assertIn("Created a dummy icon", self.app.log_text.get("1.0", tk.END))
        self.mock_pystray_icon.assert_called()
        mock_tray_thread.assert_called_once() # Check that thread for tray was started

    def test_hide_to_tray_success(self):
        self.app.tray_icon = MagicMock() # Assume tray icon exists and is visible
        self.app.tray_icon.visible = True
        self.app.root.withdraw = MagicMock()
        self.app.hide_to_tray()
        self.app.root.withdraw.assert_called_once()
        self.assertIn("Application minimized to system tray.", self.app.log_text.get("1.0", tk.END))

    def test_hide_to_tray_no_icon(self):
        self.app.tray_icon = None
        self.app.root.withdraw = MagicMock()
        with patch('tkinter.messagebox.askokcancel') as mock_askokcancel:
            mock_askokcancel.return_value = False # User chooses not to quit
            self.app.hide_to_tray()
            self.app.root.withdraw.assert_not_called()
            self.assertIn("System tray icon not available.", self.app.log_text.get("1.0", tk.END))
            mock_askokcancel.assert_called_once()

    def test_show_from_tray(self):
        self.app.root.deiconify = MagicMock()
        self.app.root.lift = MagicMock()
        self.app.root.focus_set = MagicMock()
        self.app.show_from_tray()
        self.app.root.deiconify.assert_called_once()
        self.app.root.lift.assert_called_once()
        self.app.root.focus_set.assert_called_once()

    def test_quit_application(self):
        self.app.monitoring_active = True
        self.app.stop_event = MagicMock(spec=threading.Event)
        self.app.monitoring_thread = MagicMock(spec=threading.Thread)
        self.app.monitoring_thread.is_alive.return_value = True
        self.app.tray_icon = MagicMock()
        self.app.tray_icon.stop = MagicMock()
        self.app.root.quit = MagicMock()
        self.app.root.destroy = MagicMock()

        self.app.quit_application()

        self.app.stop_event.set.assert_called_once()
        self.app.monitoring_thread.join.assert_called_once_with(timeout=5)
        self.app.tray_icon.stop.assert_called_once()
        self.app.root.quit.assert_called_once()
        self.app.root.destroy.assert_called_once()
        self.assertIn("Exiting application...", self.app.log_text.get("1.0", tk.END))

    # --- Test _monitoring_loop (simplified) ---
    # These tests are more like integration tests for the loop's logic flow
    # Full _monitoring_loop test is complex due to its tight coupling with external calls and state

    def run_monitoring_loop_once(self):
        """Helper to run the monitoring loop for one iteration."""
        # Set stop_event after one pass through the main try-except block in the loop
        # This is tricky because the loop is designed to run continuously.
        # We'll mock wait to set the stop_event.
        original_wait = self.app.stop_event.wait
        def wait_and_stop(timeout):
            original_wait(0.01) # Wait a very short time to allow one pass
            self.app.stop_event.set() # Then stop the loop
            return True # Indicate event was set (though not strictly necessary for mock)
        
        self.app.stop_event.wait = MagicMock(side_effect=wait_and_stop)
        self.app._monitoring_loop()
        self.app.stop_event.wait = original_wait # Restore original wait

    def test_monitoring_loop_connect_fail(self):
        self.mock_connect_gmail.return_value = None # Simulate connection failure
        self.app.current_config['POLL_INTERVAL_SECONDS'] = 0.01 # Fast retry for test

        self.run_monitoring_loop_once()

        self.mock_connect_gmail.assert_called_once_with(self.app.current_config, logger=self.app.log_message_gui)
        self.assertIn("Failed to connect. Retrying in 0.01 seconds...", self.app.log_text.get("1.0", tk.END))
        self.mock_search_emails.assert_not_called()

    def test_monitoring_loop_no_emails_found(self):
        mock_mail_instance = MagicMock()
        self.mock_connect_gmail.return_value = mock_mail_instance
        self.mock_search_emails.return_value = [] # No emails

        self.run_monitoring_loop_once()

        self.mock_search_emails.assert_called_once_with(mock_mail_instance, self.app.current_config, logger=self.app.log_message_gui)
        self.assertIn("No new emails found. Waiting...", self.app.log_text.get("1.0", tk.END))
        mock_mail_instance.fetch.assert_not_called()
        mock_mail_instance.close.assert_called_once()
        mock_mail_instance.logout.assert_called_once()

    def test_monitoring_loop_processes_email_with_link(self):
        mock_mail_instance = MagicMock()
        self.mock_connect_gmail.return_value = mock_mail_instance
        email_id_bytes = b'123'
        self.mock_search_emails.return_value = [email_id_bytes]
        
        mock_msg_data = email.message.Message()
        mock_msg_data['subject'] = "Test Subject with keyword"
        mock_msg_data['From'] = "sender@example.com"
        # Simulate a simple text part with a link and keyword
        text_part_content = "This body contains the keyword and a link: http://example.com/found"
        mock_msg_data.set_payload(text_part_content, charset='utf-8')
        mock_msg_data.set_content_type('text/plain')

        self.mock_decode_subject.return_value = "Test Subject with keyword"
        # Simulate fetch returning the message data
        mock_mail_instance.fetch.return_value = ('OK', [(b'RFC822', mock_msg_data.as_bytes())])
        self.mock_extract_link.return_value = "http://example.com/found"
        self.app.current_config["KEYWORD"] = "keyword"

        self.run_monitoring_loop_once()

        self.mock_search_emails.assert_called_once()
        mock_mail_instance.fetch.assert_called_once_with(email_id_bytes, '(RFC822)')
        self.mock_decode_subject.assert_called_once_with("Test Subject with keyword")
        self.mock_extract_link.assert_called()
        self.mock_open_link.assert_called_once_with("http://example.com/found", logger=self.app.log_message_gui)
        self.mock_mark_as_read.assert_called_once_with(mock_mail_instance, email_id_bytes, self.app.current_config, logger=self.app.log_message_gui)
        self.assertIn(email_id_bytes, self.app.processed_email_ids)
        self.assertIn(f"Found link in email ID {email_id_bytes.decode()}: http://example.com/found", self.app.log_text.get("1.0", tk.END))
        mock_mail_instance.close.assert_called_once()
        mock_mail_instance.logout.assert_called_once()

    def test_monitoring_loop_email_no_link_keyword_in_subject(self):
        mock_mail_instance = MagicMock()
        self.mock_connect_gmail.return_value = mock_mail_instance
        email_id_bytes = b'456'
        self.mock_search_emails.return_value = [email_id_bytes]

        mock_msg_data = email.message.Message()
        mock_msg_data['subject'] = "Subject has the KEYWORD"
        mock_msg_data['From'] = "another@example.com"
        mock_msg_data.set_payload("Body has no link.", charset='utf-8')
        mock_msg_data.set_content_type('text/plain')

        self.mock_decode_subject.return_value = "Subject has the KEYWORD"
        mock_mail_instance.fetch.return_value = ('OK', [(b'RFC822', mock_msg_data.as_bytes())])
        self.mock_extract_link.return_value = None # No link found
        self.app.current_config["KEYWORD"] = "KEYWORD"

        self.run_monitoring_loop_once()

        self.mock_open_link.assert_not_called()
        self.mock_mark_as_read.assert_called_once_with(mock_mail_instance, email_id_bytes, self.app.current_config, logger=self.app.log_message_gui)
        self.assertIn(email_id_bytes, self.app.processed_email_ids)
        self.assertIn(f"Keyword found in ID {email_id_bytes.decode()}, but no link.", self.app.log_text.get("1.0", tk.END))

    def test_monitoring_loop_keyword_not_found_skips(self):
        mock_mail_instance = MagicMock()
        self.mock_connect_gmail.return_value = mock_mail_instance
        email_id_bytes = b'789'
        self.mock_search_emails.return_value = [email_id_bytes]

        mock_msg_data = email.message.Message()
        mock_msg_data['subject'] = "Another subject"
        mock_msg_data['From'] = "noreply@example.com"
        mock_msg_data.set_payload("Body content here.", charset='utf-8')
        mock_msg_data.set_content_type('text/plain')

        self.mock_decode_subject.return_value = "Another subject"
        mock_mail_instance.fetch.return_value = ('OK', [(b'RFC822', mock_msg_data.as_bytes())])
        self.app.current_config["KEYWORD"] = "UNIQUE_KEYWORD_NOT_PRESENT"

        self.run_monitoring_loop_once()

        self.mock_extract_link.assert_called() # It will try to extract link before full keyword check
        self.mock_open_link.assert_not_called()
        self.mock_mark_as_read.assert_not_called() # Not marked as read if keyword not found for action
        self.assertIn(email_id_bytes, self.app.processed_email_ids) # Added to processed to avoid re-fetch
        self.assertIn(f"Keyword not in subject/body of ID {email_id_bytes.decode()} after fetch. Skipping.", self.app.log_text.get("1.0", tk.END))

    def test_monitoring_loop_fetch_fail(self):
        mock_mail_instance = MagicMock()
        self.mock_connect_gmail.return_value = mock_mail_instance
        email_id_bytes = b'000'
        self.mock_search_emails.return_value = [email_id_bytes]
        mock_mail_instance.fetch.return_value = ('NO', [b'Fetch error'])

        self.run_monitoring_loop_once()

        self.assertNotIn(email_id_bytes, self.app.processed_email_ids) # Not processed if fetch fails
        self.assertIn(f"Failed to fetch email ID {email_id_bytes.decode()}", self.app.log_text.get("1.0", tk.END))

    def test_monitoring_loop_imap_abort_exception(self):
        # Simulate IMAP4.abort during connect_to_gmail or search_emails
        self.mock_connect_gmail.side_effect = imaplib.IMAP4.abort("Connection reset by peer")
        self.app.current_config['POLL_INTERVAL_SECONDS'] = 0.01

        self.run_monitoring_loop_once()

        self.assertIn("IMAP connection aborted: Connection reset by peer. Retrying connection...", self.app.log_text.get("1.0", tk.END))
        # Ensure it tries to wait and retry
        self.app.stop_event.wait.assert_called_once_with(0.01)

    def test_monitoring_loop_general_exception(self):
        self.mock_connect_gmail.side_effect = Exception("Generic unexpected error")
        self.app.current_config['POLL_INTERVAL_SECONDS'] = 0.01

        self.run_monitoring_loop_once()

        self.assertIn("Error in monitoring loop: Exception - Generic unexpected error", self.app.log_text.get("1.0", tk.END))
        self.app.stop_event.wait.assert_called_once_with(0.01)

if __name__ == '__main__':
    # Need to ensure Tkinter root is properly managed if tests are run directly
    # For safety, when running tests, it's better to use a test runner that handles setup/teardown
    # If running this file directly, ensure that Tk().mainloop() is not called in the main app code.
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestEmailMonitorApp))
    runner = unittest.TextTestRunner()
    # runner.run(suite)
    # Instead of runner.run(suite) to avoid issues with Tkinter in some test environments,
    # we can use the standard unittest.main(), but ensure it doesn't exit prematurely
    # when running multiple test files via a discovery mechanism.
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
