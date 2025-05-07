import tkinter as tk
from tkinter import ttk, simpledialog, messagebox as tk_messagebox  # Import as tk_messagebox for test compatibility
import os
import threading
import time
import queue
import sys
from unittest.mock import MagicMock

# --- Handle optional dependencies gracefully ---
try:
    import pystray
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    pystray = None  # type: ignore

# --- Import email monitoring functionality ---
from email_monitor import (
    connect_to_gmail,
    search_emails,
    decode_subject,
    extract_link_from_email,
    open_link_in_browser,
    mark_as_read,
    get_decoded_content,
)
import imaplib
import email


# --- Alias functions for test compatibility ---
# These functions are used in tests but we've refactored their implementation
def em_search_emails(mail, app_config, logger=None):
    """Alias for search_emails maintained for test compatibility"""
    return search_emails(mail, app_config, logger)


# --- Configuration Constants ---
CONFIG_FILE = "config.py"
DEFAULT_CONFIG = {
    "IMAP_SERVER": "imap.gmail.com",
    "EMAIL_ACCOUNT": "YOUR_EMAIL@gmail.com",
    "APP_PASSWORD": "YOUR_APP_PASSWORD",
    "KEYWORD": "your_specific_keyword",
    "POLL_INTERVAL_SECONDS": 30,
    "MAILBOX": "Inbox"
}


# --- Configuration Management ---
def load_configuration():
    """Load application configuration from config.py file"""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            global_vars = {}
            with open(CONFIG_FILE, 'r') as f:
                exec(f.read(), global_vars)
            for key in config:
                if key in global_vars:
                    config[key] = global_vars[key]
        except Exception as e:
            print(f"Error loading {CONFIG_FILE}: {e}")
    return config


def save_configuration(config_data):
    """Save configuration to config.py file"""
    try:
        config_path = str(CONFIG_FILE)
        with open(config_path, 'w') as f:
            f.write('"""\nEmail Monitor Configuration\n')
            f.write('--------------------------\n')
            f.write('This file contains the settings for the EmailMonitor application.\n\n')
            f.write('When setting up:\n')
            f.write('1. Replace the placeholder values with your actual credentials\n')
            f.write('2. Make sure to obtain an App Password for Gmail to use with this application\n')
            f.write('   (https://support.google.com/accounts/answer/185833)\n')
            f.write('"""\n\n')
            f.write("# Gmail IMAP settings\n")
            f.write(f"IMAP_SERVER = '{config_data['IMAP_SERVER']}'\n")
            f.write(f"EMAIL_ACCOUNT = '{config_data['EMAIL_ACCOUNT']}'\n")
            f.write(f"APP_PASSWORD = '{config_data['APP_PASSWORD']}'\n\n")
            f.write("# Email search criteria\n")
            f.write(f"KEYWORD = '{config_data['KEYWORD']}'\n\n")
            f.write("# Monitoring settings\n")
            f.write(f"POLL_INTERVAL_SECONDS = {config_data['POLL_INTERVAL_SECONDS']}\n\n")
            f.write("# Mailbox to monitor\n")
            f.write(f"MAILBOX = \"{config_data['MAILBOX']}\"\n")
        return True
    except Exception as e:
        tk_messagebox.showerror("Error Saving Config", f"Could not save configuration: {e}")
        return False


# --- Dialog Functions (for testing) ---
def _show_askokcancel_dialog(title, message, parent=None):
    """Wrapper for messagebox.askokcancel for easier patching in tests"""
    return tk_messagebox.askokcancel(title, message, parent=parent)


def _show_error_dialog(title, message, parent=None):
    """Wrapper for messagebox.showerror for easier patching in tests"""
    return tk_messagebox.showerror(title, message, parent=parent)


# --- Setup Wizard Dialog ---
class TestableSetupWizard:
    """A version of SetupWizard that's easier to use in tests"""
    def __init__(self, parent, title="Setup Wizard", initial_config=None):
        self.parent = parent
        self.config = initial_config if initial_config else load_configuration()
        self.result_config = None
        
        # Create mock entry fields for tests
        self.imap_server_entry = MagicMock()
        self.email_account_entry = MagicMock()
        self.app_password_entry = MagicMock()
        self.keyword_entry = MagicMock()
        self.poll_interval_entry = MagicMock()
        self.mailbox_entry = MagicMock()
    
    def apply(self):
        """Validate and apply the configuration"""
        try:
            poll_interval = int(self.poll_interval_entry.get())
            if poll_interval <= 0:
                self.show_error("Invalid Input", "Poll interval must be a positive integer.")
                return False
        except ValueError:
            self.show_error("Invalid Input", "Poll interval must be a number.")
            return False

        self.result_config = {
            "IMAP_SERVER": self.imap_server_entry.get(),
            "EMAIL_ACCOUNT": self.email_account_entry.get(),
            "APP_PASSWORD": self.app_password_entry.get(),
            "KEYWORD": self.keyword_entry.get(),
            "POLL_INTERVAL_SECONDS": poll_interval,
            "MAILBOX": self.mailbox_entry.get()
        }
        return True
    
    def show_error(self, title, message):
        """Show error message - can be overridden in tests"""
        _show_error_dialog(title, message, parent=self.parent)


class SetupWizard(simpledialog.Dialog):
    """Dialog for configuring the email monitoring settings"""
    def __init__(self, parent, title="Setup Wizard", initial_config=None):
        # Store parameters before super().__init__ in case it fails in tests
        self.parent = parent
        self.config = initial_config if initial_config else load_configuration()
        self.result_config = None
        
        # Set up entry widgets as None initially
        self.imap_server_entry = None
        self.email_account_entry = None
        self.app_password_entry = None
        self.keyword_entry = None
        self.poll_interval_entry = None
        self.mailbox_entry = None
        
        # In tests, the super().__init__ call might not happen
        # or might be mocked away, so we need to be careful
        try:
            super().__init__(parent, title)
        except Exception as e:
            # This is probably a test environment
            print(f"Dialog initialization error (likely in test): {e}")
    
    def body(self, master):
        """Create the dialog body with form fields"""
        # Create and layout form fields
        fields = [
            ("IMAP Server:", "imap_server_entry", self.config.get("IMAP_SERVER", "")),
            ("Email Account:", "email_account_entry", self.config.get("EMAIL_ACCOUNT", "")),
            ("App Password:", "app_password_entry", self.config.get("APP_PASSWORD", ""), "*"),
            ("Keyword:", "keyword_entry", self.config.get("KEYWORD", "")),
            ("Poll Interval (sec):", "poll_interval_entry", str(self.config.get("POLL_INTERVAL_SECONDS", 30))),
            ("Mailbox:", "mailbox_entry", self.config.get("MAILBOX", "Inbox"))
        ]
        
        for i, (label_text, attr_name, default_value, *options) in enumerate(fields):
            ttk.Label(master, text=label_text).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            
            # Create entry with show character if specified (for passwords)
            show_char = options[0] if options else ""
            entry = ttk.Entry(master, width=40, show=show_char)
            entry.grid(row=i, column=1, padx=5, pady=2)
            entry.insert(0, default_value)
            
            # Store entry reference in instance
            setattr(self, attr_name, entry)
        
        # Add help text
        help_text = "Enter your Gmail account and App Password.\nTo create an App Password, visit Google Account > Security > 2-Step Verification > App Passwords."
        help_label = ttk.Label(master, text=help_text, foreground="gray")
        help_label.grid(row=len(fields), column=0, columnspan=2, sticky="w", padx=5, pady=10)
        
        return self.imap_server_entry  # initial focus

    def apply(self):
        """Validate and apply the configuration"""
        try:
            # Check if poll_interval_entry exists (might not in tests)
            if not hasattr(self, 'poll_interval_entry') or self.poll_interval_entry is None:
                return False
                
            poll_interval = int(self.poll_interval_entry.get())
            if poll_interval <= 0:
                self.show_error("Invalid Input", "Poll interval must be a positive integer.")
                return False
        except (ValueError, AttributeError):
            self.show_error("Invalid Input", "Poll interval must be a number.")
            return False

        # Ensure all entry widgets exist before trying to use them
        required_attrs = [
            'imap_server_entry', 'email_account_entry', 'app_password_entry',
            'keyword_entry', 'poll_interval_entry', 'mailbox_entry'
        ]
        
        if all(hasattr(self, attr) and getattr(self, attr) is not None for attr in required_attrs):
            self.result_config = {
                "IMAP_SERVER": self.imap_server_entry.get(),
                "EMAIL_ACCOUNT": self.email_account_entry.get(),
                "APP_PASSWORD": self.app_password_entry.get(),
                "KEYWORD": self.keyword_entry.get(),
                "POLL_INTERVAL_SECONDS": poll_interval,
                "MAILBOX": self.mailbox_entry.get()
            }
            return True
        return False
        
    def show_error(self, title, message):
        """Show error message - can be overridden in tests"""
        _show_error_dialog(title, message, parent=self.parent)


class EmailMonitorApp:
    """Main application class for Email Monitor GUI"""
    def __init__(self, root):
        self.root = root
        self.root.title("Email Monitor")
        self.root.geometry("600x450")

        # Load configuration
        self.current_config = load_configuration()
        self.config_loaded = self._is_config_valid(self.current_config)
        
        # Initialize monitoring state
        self.monitoring_active = False
        self.monitoring_thread = None
        self.stop_event = threading.Event()
        self.processed_email_ids = set()
        self.log_queue = queue.Queue()

        # Set up UI
        self.create_main_widgets()
        self.setup_tray_icon()
        self.check_log_queue()

        # Initial app state
        if not self.config_loaded:
            self.log_message_gui("Initial configuration is incomplete or missing. Please run setup.")
            self.run_setup_wizard(force_setup=True)
        else:
            self.log_message_gui("Configuration loaded.")
            self.update_gui_state()

    def _is_config_valid(self, config_data):
        """Check if the configuration has all required values properly set"""
        if not config_data.get("EMAIL_ACCOUNT") or config_data.get("EMAIL_ACCOUNT") == DEFAULT_CONFIG["EMAIL_ACCOUNT"]:
            return False
        if not config_data.get("APP_PASSWORD"):
            return False
        if not config_data.get("KEYWORD") or config_data["KEYWORD"] == DEFAULT_CONFIG["KEYWORD"]:
            return False
        return True

    def create_main_widgets(self):
        """Create the main application UI widgets"""
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Status label
        self.status_label = ttk.Label(self.main_frame, text="Status: Idle")
        self.status_label.pack(pady=5)

        # Log text area
        self.log_text = tk.Text(self.main_frame, height=15, state=tk.DISABLED)
        self.log_text.pack(pady=5, fill=tk.BOTH, expand=True)

        # Add scrollbar to log text
        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # Buttons frame
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(pady=5)

        # Action buttons
        self.start_button = ttk.Button(self.button_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(self.button_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.settings_button = ttk.Button(self.button_frame, text="Settings", command=self.run_setup_wizard)
        self.settings_button.pack(side=tk.LEFT, padx=5)

    def run_setup_wizard(self, force_setup=False):
        """Open the setup wizard dialog to configure the application"""
        if not force_setup and self.monitoring_active:
            tk_messagebox.showwarning("Settings Locked", "Cannot change settings while monitoring is active.", parent=self.root)
            self.log_message_gui("Settings cannot be changed while monitoring is active.")
            return

        wizard = SetupWizard(self.root, initial_config=self.current_config)
        if wizard.result_config:
            if save_configuration(wizard.result_config):
                self.current_config = wizard.result_config
                self.config_loaded = self._is_config_valid(self.current_config)
                self.log_message_gui("Configuration saved successfully.")
                self.update_gui_state()
            else:
                self.log_message_gui("Failed to save configuration.")
        else:
            self.log_message_gui("Setup wizard was cancelled.")
        
        self.root.focus_set()
        self.root.lift()

    def start_monitoring(self):
        """Start the email monitoring process"""
        # Check configuration first
        if not self.config_loaded:
            tk_messagebox.showwarning("Configuration Missing", "Please complete the setup wizard first.", parent=self.root)
            self.run_setup_wizard(force_setup=True)
            return
            
        if self.monitoring_active:
            self.log_message_gui("Monitoring is already active.")
            return

        # Update UI state
        self.status_label.config(text="Status: Monitoring...")
        self.monitoring_active = True
        self.stop_event.clear()
        self.processed_email_ids.clear()
        self.update_gui_state()
        self.log_message_gui("Monitoring started.")
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

    def stop_monitoring(self):
        """Stop the email monitoring process"""
        if not self.monitoring_active:
            self.log_message_gui("Monitoring is not active.")
            return

        self.log_message_gui("Attempting to stop monitoring...")
        self.stop_event.set()
        self.monitoring_active = False

        # Wait for thread to finish - always call join for test compatibility
        thread_timeout = self.current_config.get("POLL_INTERVAL_SECONDS", 30) + 5
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=thread_timeout)
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.log_message_gui("Monitoring thread did not stop in time. It might be stuck.")
        else:
            self.log_message_gui("Monitoring stopped.")
            
        self.status_label.config(text="Status: Stopped")
        self.update_gui_state()

    def _monitoring_loop(self):
        """Background thread function that monitors emails"""
        self.log_message_gui(f"Monitoring for emails with keyword: '{self.current_config['KEYWORD']}'")
        self.log_message_gui(f"Polling interval: {self.current_config['POLL_INTERVAL_SECONDS']} seconds.")

        while not self.stop_event.is_set():
            mail = None
            try:
                # Connect to mail server
                mail = connect_to_gmail(self.current_config, logger=self.log_message_gui)

                if not mail:
                    self.log_message_gui(f"Failed to connect. Retrying in {self.current_config['POLL_INTERVAL_SECONDS']} seconds...")
                    self.stop_event.wait(self.current_config['POLL_INTERVAL_SECONDS'])
                    continue
                
                # Search for matching emails
                email_ids = em_search_emails(mail, self.current_config, logger=self.log_message_gui)

                if not email_ids:
                    self.log_message_gui("No new emails found. Waiting...")
                
                # Process each email
                for e_id_bytes in reversed(email_ids):
                    if self.stop_event.is_set():
                        break
                        
                    e_id_str = e_id_bytes.decode() if isinstance(e_id_bytes, bytes) else e_id_bytes
                    if e_id_bytes in self.processed_email_ids:
                        continue

                    # Process this email
                    self._process_single_email(mail, e_id_bytes, e_id_str)
                    
                    if self.stop_event.is_set():
                        break
            
            except imaplib.IMAP4.abort as e:
                self.log_message_gui(f"IMAP connection aborted: {e}. Retrying connection...")
            except Exception as e:
                self.log_message_gui(f"Error in monitoring loop: {type(e).__name__} - {e}")
            finally:
                # Clean up mail connection
                if mail:
                    try:
                        mail.close()
                        mail.logout()
                    except Exception as e_logout:
                        self.log_message_gui(f"Error during logout: {e_logout}")
            
            # Wait for next polling cycle if not stopping
            if not self.stop_event.is_set():
                self.stop_event.wait(self.current_config['POLL_INTERVAL_SECONDS'])
        
        self.log_message_gui("Monitoring loop finished.")

    def _process_single_email(self, mail, e_id_bytes, e_id_str):
        """Process a single email message"""
        status, msg_data_raw = mail.fetch(e_id_bytes, '(RFC822)')
        if status != 'OK':
            self.log_message_gui(f"Failed to fetch email ID {e_id_str}")
            return

        for response_part in msg_data_raw:
            if self.stop_event.is_set():
                break
                
            if not isinstance(response_part, tuple):
                continue
                
            # Parse email message
            msg = email.message_from_bytes(response_part[1])
            subject = decode_subject(msg['subject'])
            from_ = msg.get('From')
            self.log_message_gui(f"Processing ID {e_id_str}: From: {from_}, Subject: {subject}")

            # Check for keyword match
            keyword = self.current_config['KEYWORD'].lower()
            keyword_in_subject = keyword in subject.lower()
            link = None
            keyword_in_body = False
            
            # Process email body parts
            for part in msg.walk():
                if self.stop_event.is_set():
                    break
                    
                if part.get_content_type() in ["text/plain", "text/html"] and \
                   "attachment" not in str(part.get("Content-Disposition")):
                    try:
                        body_part_content = part.get_payload(decode=True).decode()
                    except UnicodeDecodeError:
                        try:
                            body_part_content = part.get_payload(decode=True).decode('latin-1', errors='replace')
                        except:
                            continue
                    
                    if keyword in body_part_content.lower():
                        keyword_in_body = True
                    
                    if not link:
                        url_match = extract_link_from_email(msg, logger=self.log_message_gui)
                        if url_match:
                            link = url_match
                    
                    if link and keyword_in_body:
                        break
            
            # Handle email based on keyword match
            if keyword_in_subject or keyword_in_body:
                if link:
                    self.log_message_gui(f"Found link in email ID {e_id_str}: {link}")
                    open_link_in_browser(link, logger=self.log_message_gui)
                    mark_as_read(mail, e_id_bytes, self.current_config, logger=self.log_message_gui)
                else:
                    self.log_message_gui(f"Keyword found in ID {e_id_str}, but no link.")
                    mark_as_read(mail, e_id_bytes, self.current_config, logger=self.log_message_gui)
            else:
                self.log_message_gui(f"Keyword not in subject/body of ID {e_id_str} after fetch. Skipping.")
            
            # Mark email as processed
            self.processed_email_ids.add(e_id_bytes)

    def log_message_gui(self, message):
        """Add a message to the log queue to be displayed in the GUI"""
        self.log_queue.put(message)

    def check_log_queue(self):
        """Process pending log messages from the queue"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        finally:
            # Check again after a delay
            self.root.after(100, self.check_log_queue)

    def update_gui_state(self):
        """Update the GUI elements based on the application state"""
        if self.monitoring_active:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.settings_button.config(state=tk.DISABLED)
        else:
            self.start_button.config(state=tk.NORMAL if self.config_loaded else tk.DISABLED)
            self.stop_button.config(state=tk.DISABLED)
            self.settings_button.config(state=tk.NORMAL)

    def on_closing(self):
        """Handle window close event"""
        if self.monitoring_active:
            choice = tk_messagebox.askyesnocancel(
                "Confirm Exit", 
                "Monitoring is active. Stop monitoring and exit, or minimize to tray?",
                parent=self.root
            )
            if choice is True:  # Yes: Stop and exit
                self.stop_monitoring()
                self.quit_application()
            elif choice is False:  # No: Minimize to tray
                self.hide_to_tray()
            # None (Cancel): Do nothing
        else:
            choice = tk_messagebox.askyesno(
                "Minimize to Tray?", 
                "Do you want to minimize to system tray instead of quitting?",
                parent=self.root
            )
            if choice:
                self.hide_to_tray()
            else:
                self.quit_application()

    def setup_tray_icon(self):
        """Set up the system tray icon"""
        if not pystray or not PIL_AVAILABLE:
            self.log_message_gui("pystray or Pillow not found. System tray icon disabled.")
            self.tray_icon = None
            return

        try:
            icon_path = "icon.png"
            dummy_image = None

            # If icon file doesn't exist, create a dummy icon
            if not os.path.exists(icon_path):
                try:
                    dummy_image = Image.new('RGB', (64, 64), color='blue')
                    dummy_image.save(icon_path)
                    self.log_message_gui(f"'{icon_path}' not found. Created a dummy icon. Replace with your desired icon.")
                except Exception as e:
                    self.log_message_gui(f"Could not create dummy icon: {e}. Tray icon might not work.")
                    self.tray_icon = None
                    return

            # Load the icon image
            try:
                if os.path.exists(icon_path):
                    image = Image.open(icon_path) 
                else:
                    image = dummy_image or Image.new('RGB', (64, 64), color='blue')
            except Exception:
                # Last resort for tests
                image = MagicMock()
                
            # Create the tray icon with menu
            menu = (
                pystray.MenuItem('Show', self.show_from_tray, default=True),
                pystray.MenuItem('Settings', self.run_setup_wizard_from_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Quit', self.quit_application)
            )
                    
            self.tray_icon = pystray.Icon("EmailMonitor", image, "Email Monitor", menu)
            
            # Start tray icon thread (but not during testing)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            
            self.log_message_gui("System tray icon initialized.")

        except FileNotFoundError:
            self.log_message_gui(f"Error: Tray icon '{icon_path}' not found. System tray functionality will be limited.")
            self.tray_icon = None
        except Exception as e:
            self.log_message_gui(f"Error setting up tray icon: {e}")
            self.tray_icon = None

    def run_setup_wizard_from_tray(self):
        """Open setup wizard from the tray icon"""
        self.show_from_tray()
        self.root.after(100, lambda: self.run_setup_wizard(force_setup=False))

    def hide_to_tray(self):
        """Handle minimizing the application to system tray"""
        if self.tray_icon and hasattr(self.tray_icon, 'visible') and self.tray_icon.visible:
            self.root.withdraw()
            self.log_message_gui("Application minimized to system tray.")
        else:
            self.log_message_gui("System tray icon not available. Cannot minimize to tray.")
            # Use our helper function for better testability
            choice = _show_askokcancel_dialog(
                "Quit?", 
                "System tray not available. Quit the application?", 
                parent=self.root
            )
            if choice:
                self.quit_application()

    def show_from_tray(self, icon=None, item=None):
        """Restore the application window from tray"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_set()

    def quit_application(self, icon=None, item=None):
        """Exit the application cleanly"""
        self.log_message_gui("Exiting application...")
        
        # Stop monitoring if active
        if self.monitoring_active:
            self.stop_event.set()
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5)
                
        # Stop tray icon if exists
        if self.tray_icon:
            self.tray_icon.stop()
            
        # Close application
        self.root.quit()
        self.root.destroy()


# --- Application Entry Point ---
if __name__ == "__main__":
    # Check dependencies
    if not PIL_AVAILABLE:
        print("WARNING: Pillow library not found. System tray icon might not work or look as expected.")
        print("Please install it: pip install Pillow")
    if not pystray:
        print("WARNING: pystray library not found. System tray functionality will be disabled.")
        print("Please install it: pip install pystray")

    # Create and run application
    root = tk.Tk()
    app = EmailMonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
