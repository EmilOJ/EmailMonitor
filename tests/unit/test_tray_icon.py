import unittest
import sys
import os
from unittest.mock import patch, MagicMock, call
import tkinter as tk

# Add parent directory to path to import modules to be tested
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import gui_app

# Helper function to set up mock widgets - copied from test_email_monitor_app.py for consistency
def _setup_mock_widgets(app_instance):
    app_instance.main_frame = MagicMock(name='main_frame_mock')
    app_instance.status_label = MagicMock(name='status_label_mock')
    app_instance.log_text = MagicMock(name='log_text_mock')
    app_instance.button_frame = MagicMock(name='button_frame_mock')
    app_instance.start_button = MagicMock(name='start_button_mock')
    app_instance.stop_button = MagicMock(name='stop_button_mock')
    app_instance.settings_button = MagicMock(name='settings_button_mock')
    return None

class TestTrayIconFunctionality(unittest.TestCase):
    """Unit tests for system tray functionality"""
    
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
        
        # Create app instance with patched dependencies
        with patch('gui_app.load_configuration', return_value=self.test_config), \
             patch('gui_app.EmailMonitorApp.create_main_widgets'), \
             patch('gui_app.EmailMonitorApp.setup_tray_icon'), \
             patch('gui_app.EmailMonitorApp.check_log_queue'), \
             patch('gui_app.EmailMonitorApp._is_config_valid', return_value=True), \
             patch('gui_app.EmailMonitorApp.log_message_gui'), \
             patch('gui_app.EmailMonitorApp.update_gui_state'):  # Patch update_gui_state during initialization
            self.app = gui_app.EmailMonitorApp(self.root)
            
            # Setup manually since we patched the constructor
            self.app.root = self.root
            self.app.current_config = self.test_config
            self.app.log_message_gui = MagicMock()
            
            # Add mock widgets that would normally be created by create_main_widgets
            _setup_mock_widgets(self.app)
            
    @patch('gui_app.PIL_AVAILABLE', True)
    @patch('gui_app.pystray', spec=True)
    @patch('gui_app.Image')
    @patch('os.path.exists', return_value=True)
    @patch('threading.Thread')
    def test_setup_tray_icon_success(self, mock_thread, mock_exists, mock_image, mock_pystray):
        """Test successful setup of system tray icon"""
        # Setup
        mock_image_instance = MagicMock()
        mock_image.open.return_value = mock_image_instance
        mock_icon = MagicMock()
        mock_pystray.Icon.return_value = mock_icon
        mock_pystray.MenuItem.side_effect = lambda text, action, default=False: (text, action, default)
        mock_pystray.Menu.SEPARATOR = "---"
        
        # Make the thread.start method a no-op to prevent hanging
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Call method
        self.app.setup_tray_icon()
        
        # Assertions
        mock_image.open.assert_called_once_with("icon.png")
        mock_pystray.Icon.assert_called_once()
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()  # Verify start was called on the thread
        self.app.log_message_gui.assert_called_with("System tray icon initialized.")
        self.assertEqual(self.app.tray_icon, mock_icon)
            
    @patch('gui_app.PIL_AVAILABLE', True)
    @patch('gui_app.pystray', spec=True)
    @patch('gui_app.Image')
    @patch('os.path.exists', return_value=False)
    @patch('threading.Thread')
    def test_setup_tray_icon_create_dummy(self, mock_thread, mock_exists, mock_image, mock_pystray):
        """Test creating dummy icon when icon file doesn't exist"""
        # Setup
        mock_image_instance = MagicMock()
        mock_image.new.return_value = mock_image_instance
        mock_image.open.return_value = mock_image_instance
        
        # Make the thread.start method a no-op
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Call method
        self.app.setup_tray_icon()
        
        # Assertions
        mock_image.new.assert_called_once()
        mock_image_instance.save.assert_called_once_with("icon.png")
        self.app.log_message_gui.assert_any_call("'icon.png' not found. Created a dummy icon. Replace with your desired icon.")
    
    @patch('gui_app.PIL_AVAILABLE', False)
    def test_setup_tray_icon_no_pil(self):
        """Test handling when PIL is not available"""
        # Call method
        self.app.setup_tray_icon()
        
        # Assertions
        self.app.log_message_gui.assert_any_call("pystray or Pillow not found. System tray icon disabled.")
        self.assertIsNone(self.app.tray_icon)
    
    @patch('gui_app.PIL_AVAILABLE', True)
    @patch('gui_app.pystray', None)
    def test_setup_tray_icon_no_pystray(self):
        """Test handling when pystray is not available"""
        # Call method
        self.app.setup_tray_icon()
        
        # Assertions
        self.app.log_message_gui.assert_any_call("pystray or Pillow not found. System tray icon disabled.")
        self.assertIsNone(self.app.tray_icon)
    
    def test_hide_to_tray_success(self):
        """Test hiding to tray when tray icon is available"""
        # Setup
        self.app.tray_icon = MagicMock()
        self.app.tray_icon.visible = True
        
        # Call method
        self.app.hide_to_tray()
        
        # Assertions
        self.root.withdraw.assert_called_once()
        self.app.log_message_gui.assert_called_with("Application minimized to system tray.")
    
    @patch('tkinter.messagebox.askokcancel', return_value=True)
    def test_hide_to_tray_no_icon_quit(self, mock_dialog):
        """Test hiding to tray when no tray icon is available - user chooses to quit"""
        # Setup
        self.app.tray_icon = None
        self.app.quit_application = MagicMock()
        
        # Call method
        self.app.hide_to_tray()
        
        # Assertions
        self.app.log_message_gui.assert_called_with("System tray icon not available. Cannot minimize to tray.")
        mock_dialog.assert_called_once()
        self.app.quit_application.assert_called_once()
    
    @patch('tkinter.messagebox.askokcancel', return_value=False)
    def test_hide_to_tray_no_icon_stay(self, mock_dialog):
        """Test hiding to tray when no tray icon is available - user chooses to stay"""
        # Setup
        self.app.tray_icon = None
        self.app.quit_application = MagicMock()
        
        # Call method
        self.app.hide_to_tray()
        
        # Assertions
        mock_dialog.assert_called_once()
        self.app.quit_application.assert_not_called()
    
    def test_show_from_tray(self):
        """Test showing window from tray"""
        # Call method
        self.app.show_from_tray()
        
        # Assertions
        self.root.deiconify.assert_called_once()
        self.root.lift.assert_called_once()
        self.root.focus_set.assert_called_once()
    
    def test_run_setup_wizard_from_tray(self):
        """Test running setup wizard from tray"""
        # Setup
        self.app.show_from_tray = MagicMock()
        self.app.run_setup_wizard = MagicMock()
        
        # Need to patch root.after to call the lambda function immediately
        def execute_after_func(ms, func):
            func()
        self.root.after.side_effect = execute_after_func
        
        # Call method
        self.app.run_setup_wizard_from_tray()
        
        # Assertions
        self.app.show_from_tray.assert_called_once()
        self.root.after.assert_called_once()
        self.app.run_setup_wizard.assert_called_once_with(force_setup=False)
    
    def test_quit_application(self):
        """Test quitting the application"""
        # Setup
        self.app.monitoring_active = False
        self.app.tray_icon = MagicMock()
        
        # Call method
        self.app.quit_application()
        
        # Assertions
        self.app.log_message_gui.assert_called_with("Exiting application...")
        self.app.tray_icon.stop.assert_called_once()
        self.root.quit.assert_called_once()
        self.root.destroy.assert_called_once()
    
    def test_quit_application_when_monitoring(self):
        """Test quitting the application when monitoring is active"""
        # Setup
        self.app.monitoring_active = True
        self.app.stop_event = MagicMock()
        self.app.monitoring_thread = MagicMock()
        self.app.monitoring_thread.is_alive.return_value = True
        self.app.tray_icon = MagicMock()
        
        # Call method
        self.app.quit_application()
        
        # Assertions
        self.app.stop_event.set.assert_called_once()
        self.app.monitoring_thread.join.assert_called_once()
        self.app.tray_icon.stop.assert_called_once()
        self.root.quit.assert_called_once()
        self.root.destroy.assert_called_once()


if __name__ == '__main__':
    unittest.main()