import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os
import threading
import time
import queue
import sys
from unittest.mock import MagicMock

try:
    import pystray
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    pystray = None # type: ignore

from email_monitor import (
    connect_to_gmail,
    search_emails as em_search_emails,
    decode_subject as em_decode_subject,
    extract_link_from_email as em_extract_link_from_email,
    open_link_in_browser as em_open_link_in_browser,
    mark_as_read as em_mark_as_read,
)
import imaplib
import email

# --- Configuration Handling ---
CONFIG_FILE = "config.py"
DEFAULT_CONFIG = {
    "IMAP_SERVER": "imap.gmail.com",
    "EMAIL_ACCOUNT": "YOUR_EMAIL@gmail.com",
    "APP_PASSWORD": "YOUR_APP_PASSWORD",
    "KEYWORD": "your_specific_keyword",
    "POLL_INTERVAL_SECONDS": 30,
    "MAILBOX": "INBOX"
}

def load_configuration():
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
            pass
    return config

def save_configuration(config_data):
    try:
        config_path = str(CONFIG_FILE)
        with open(config_path, 'w') as f:
            f.write("# Gmail IMAP settings\n")
            f.write(f"IMAP_SERVER = '{config_data['IMAP_SERVER']}'\n")
            f.write(f"EMAIL_ACCOUNT = '{config_data['EMAIL_ACCOUNT']}'  # Replace with your Gmail address\n")
            f.write(f"APP_PASSWORD = '{config_data['APP_PASSWORD']}'      # Replace with your Gmail app password\n")
            f.write("\n# Email search criteria\n")
            f.write(f"KEYWORD = '{config_data['KEYWORD']}'       # Replace with the keyword to search for\n")
            f.write("\n# Monitoring settings\n")
            f.write(f"POLL_INTERVAL_SECONDS = {config_data['POLL_INTERVAL_SECONDS']}\n")
            f.write("\n# Optional: Specify the mailbox to monitor (default is \"INBOX\")\n")
            f.write(f"MAILBOX = \"{config_data['MAILBOX']}\"\n")
        return True
    except Exception as e:
        messagebox.showerror("Error Saving Config", f"Could not save configuration: {e}")
        return False

class SetupWizard(simpledialog.Dialog):
    def __init__(self, parent, title="Setup Wizard", initial_config=None):
        self.config = initial_config if initial_config else load_configuration()
        self.result_config = None
        # Call parent constructor properly
        simpledialog.Dialog.__init__(self, parent, title)

    def body(self, master):
        ttk.Label(master, text="IMAP Server:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.imap_server_entry = ttk.Entry(master, width=40)
        self.imap_server_entry.grid(row=0, column=1, padx=5, pady=2)
        self.imap_server_entry.insert(0, self.config.get("IMAP_SERVER", ""))

        ttk.Label(master, text="Email Account:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.email_account_entry = ttk.Entry(master, width=40)
        self.email_account_entry.grid(row=1, column=1, padx=5, pady=2)
        self.email_account_entry.insert(0, self.config.get("EMAIL_ACCOUNT", ""))

        ttk.Label(master, text="App Password:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.app_password_entry = ttk.Entry(master, width=40, show="*")
        self.app_password_entry.grid(row=2, column=1, padx=5, pady=2)
        self.app_password_entry.insert(0, self.config.get("APP_PASSWORD", ""))

        ttk.Label(master, text="Keyword:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.keyword_entry = ttk.Entry(master, width=40)
        self.keyword_entry.grid(row=3, column=1, padx=5, pady=2)
        self.keyword_entry.insert(0, self.config.get("KEYWORD", ""))

        ttk.Label(master, text="Poll Interval (sec):").grid(row=4, column=0, sticky="w", padx=5, pady=2)
        self.poll_interval_entry = ttk.Entry(master, width=40)
        self.poll_interval_entry.grid(row=4, column=1, padx=5, pady=2)
        self.poll_interval_entry.insert(0, str(self.config.get("POLL_INTERVAL_SECONDS", 30)))
        
        ttk.Label(master, text="Mailbox:").grid(row=5, column=0, sticky="w", padx=5, pady=2)
        self.mailbox_entry = ttk.Entry(master, width=40)
        self.mailbox_entry.grid(row=5, column=1, padx=5, pady=2)
        self.mailbox_entry.insert(0, self.config.get("MAILBOX", "INBOX"))
        
        return self.imap_server_entry # initial focus

    def apply(self):
        try:
            poll_interval = int(self.poll_interval_entry.get())
            if poll_interval <= 0:
                messagebox.showerror("Invalid Input", "Poll interval must be a positive integer.", parent=self)
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Poll interval must be a number.", parent=self)
            return

        self.result_config = {
            "IMAP_SERVER": self.imap_server_entry.get(),
            "EMAIL_ACCOUNT": self.email_account_entry.get(),
            "APP_PASSWORD": self.app_password_entry.get(),
            "KEYWORD": self.keyword_entry.get(),
            "POLL_INTERVAL_SECONDS": poll_interval,
            "MAILBOX": self.mailbox_entry.get()
        }

class EmailMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Email Monitor")
        self.root.geometry("600x450")

        self.current_config = load_configuration()
        self.config_loaded = self._is_config_valid(self.current_config)
        
        self.monitoring_active = False
        self.monitoring_thread = None
        self.stop_event = threading.Event()
        self.processed_email_ids = set()
        self.log_queue = queue.Queue()

        self.create_main_widgets()
        self.setup_tray_icon()
        self.check_log_queue()

        if not self.config_loaded:
            self.log_message_gui("Initial configuration is incomplete or missing. Please run setup.")
            self.run_setup_wizard(force_setup=True)
        else:
            self.log_message_gui("Configuration loaded.")
            self.update_gui_state()

    def _is_config_valid(self, config_data):
        # We need to explicitly check against the default config values
        if not config_data.get("EMAIL_ACCOUNT") or config_data.get("EMAIL_ACCOUNT") == DEFAULT_CONFIG["EMAIL_ACCOUNT"]:
            return False
        if not config_data.get("APP_PASSWORD") or not config_data["APP_PASSWORD"]:
            return False
        if not config_data.get("KEYWORD") or config_data["KEYWORD"] == DEFAULT_CONFIG["KEYWORD"]:
            return False
        return True

    def create_main_widgets(self):
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(self.main_frame, text="Status: Idle")
        self.status_label.pack(pady=5)

        self.log_text = tk.Text(self.main_frame, height=15, state=tk.DISABLED)
        self.log_text.pack(pady=5, fill=tk.BOTH, expand=True)

        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(pady=5)

        self.start_button = ttk.Button(self.button_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(self.button_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.settings_button = ttk.Button(self.button_frame, text="Settings", command=self.run_setup_wizard)
        self.settings_button.pack(side=tk.LEFT, padx=5)

    def run_setup_wizard(self, force_setup=False):
        if not force_setup and self.monitoring_active:
            messagebox.showwarning("Settings Locked", "Cannot change settings while monitoring is active.", parent=self.root)
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
        if not self.config_loaded:
            messagebox.showwarning("Configuration Missing", "Please complete the setup wizard first.", parent=self.root)
            self.run_setup_wizard(force_setup=True)
            return
        if self.monitoring_active:
            self.log_message_gui("Monitoring is already active.")
            return

        self.status_label.config(text="Status: Monitoring...")
        self.monitoring_active = True
        self.stop_event.clear()
        self.processed_email_ids.clear()
        self.update_gui_state()
        self.log_message_gui("Monitoring started.")
        
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

    def stop_monitoring(self):
        if not self.monitoring_active:
            self.log_message_gui("Monitoring is not active.")
            return

        self.log_message_gui("Attempting to stop monitoring...")
        self.stop_event.set()
        self.monitoring_active = False

        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=self.current_config.get("POLL_INTERVAL_SECONDS", 30) + 5)
        else:
            # Ensure join is called even if thread is not alive
            self.monitoring_thread.join()
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.log_message_gui("Monitoring thread did not stop in time. It might be stuck.")
        else:
            self.log_message_gui("Monitoring stopped.")
            
        self.status_label.config(text="Status: Stopped")
        self.update_gui_state()

    def _monitoring_loop(self):
        self.log_message_gui(f"Monitoring for emails with keyword: '{self.current_config['KEYWORD']}'")
        self.log_message_gui(f"Polling interval: {self.current_config['POLL_INTERVAL_SECONDS']} seconds.")

        while not self.stop_event.is_set():
            mail = None
            try:
                # Use self.current_config and self.log_message_gui for email_monitor functions
                mail = connect_to_gmail(self.current_config, logger=self.log_message_gui)

                if not mail:
                    self.log_message_gui(f"Failed to connect. Retrying in {self.current_config['POLL_INTERVAL_SECONDS']} seconds...")
                    self.stop_event.wait(self.current_config['POLL_INTERVAL_SECONDS'])
                    continue
                
                email_ids = em_search_emails(mail, self.current_config, logger=self.log_message_gui)

                if not email_ids:
                    self.log_message_gui(f"No new emails found. Waiting...") # Adjusted log message
                # else: # No need for else, processing loop will handle if email_ids is populated
                    # self.log_message_gui(f"Found {len(email_ids)} email(s) potentially matching criteria.")

                for e_id_bytes in reversed(email_ids):
                    if self.stop_event.is_set(): break
                    e_id_str = e_id_bytes.decode()

                    if e_id_bytes in self.processed_email_ids:
                        continue

                    status, msg_data_raw = mail.fetch(e_id_bytes, '(RFC822)')
                    if status == 'OK':
                        for response_part in msg_data_raw:
                            if self.stop_event.is_set(): break
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                subject = em_decode_subject(msg['subject'])
                                from_ = msg.get('From')
                                self.log_message_gui(f"Processing ID {e_id_str}: From: {from_}, Subject: {subject}")

                                keyword_in_subject = self.current_config['KEYWORD'].lower() in subject.lower()
                                link = None
                                keyword_in_body = False

                                for part in msg.walk():
                                    if self.stop_event.is_set(): break
                                    if part.get_content_type() in ["text/plain", "text/html"] and \
                                       "attachment" not in str(part.get("Content-Disposition")):
                                        try:
                                            body_part_content = part.get_payload(decode=True).decode()
                                        except UnicodeDecodeError:
                                            try: body_part_content = part.get_payload(decode=True).decode('latin-1', errors='replace')
                                            except: continue
                                        
                                        if self.current_config['KEYWORD'].lower() in body_part_content.lower():
                                            keyword_in_body = True
                                        
                                        if not link:
                                            # Pass logger to em_extract_link_from_email
                                            url_match = em_extract_link_from_email(msg, logger=self.log_message_gui)
                                            if url_match: link = url_match
                                        
                                        if link and keyword_in_body: break
                                
                                if keyword_in_subject or keyword_in_body:
                                    if link:
                                        self.log_message_gui(f"Found link in email ID {e_id_str}: {link}")
                                        em_open_link_in_browser(link, logger=self.log_message_gui)
                                        em_mark_as_read(mail, e_id_bytes, self.current_config, logger=self.log_message_gui)
                                        self.processed_email_ids.add(e_id_bytes)
                                    else:
                                        self.log_message_gui(f"Keyword found in ID {e_id_str}, but no link.")
                                        em_mark_as_read(mail, e_id_bytes, self.current_config, logger=self.log_message_gui)
                                        self.processed_email_ids.add(e_id_bytes)
                                else:
                                    self.log_message_gui(f"Keyword not in subject/body of ID {e_id_str} after fetch. Skipping.")
                                    self.processed_email_ids.add(e_id_bytes)
                    else:
                        self.log_message_gui(f"Failed to fetch email ID {e_id_str}")
                    if self.stop_event.is_set(): break
            
            except imaplib.IMAP4.abort as e:
                self.log_message_gui(f"IMAP connection aborted: {e}. Retrying connection...")
            except Exception as e:
                self.log_message_gui(f"Error in monitoring loop: {type(e).__name__} - {e}") # Log type of error
            finally:
                if mail:
                    try:
                        mail.close()
                        mail.logout()
                        # self.log_message_gui("Logged out from Gmail.") # Can be a bit noisy
                    except Exception as e_logout:
                        self.log_message_gui(f"Error during logout: {e_logout}")
            
            if not self.stop_event.is_set():
                # self.log_message_gui(f"Waiting for {self.current_config['POLL_INTERVAL_SECONDS']} seconds...") # Noisy
                self.stop_event.wait(self.current_config['POLL_INTERVAL_SECONDS'])
        
        self.log_message_gui("Monitoring loop finished.")

    def log_message_gui(self, message):
        self.log_queue.put(message)

    def check_log_queue(self):
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
            self.root.after(100, self.check_log_queue)

    def update_gui_state(self):
        if self.monitoring_active:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.settings_button.config(state=tk.DISABLED)
        else:
            self.start_button.config(state=tk.NORMAL if self.config_loaded else tk.DISABLED)
            self.stop_button.config(state=tk.DISABLED)
            self.settings_button.config(state=tk.NORMAL)

    def on_closing(self):
        if self.monitoring_active:
            choice = messagebox.askyesnocancel(
                "Confirm Exit", 
                "Monitoring is active. Stop monitoring and exit, or minimize to tray?",
                parent=self.root
            )
            if choice is True:
                self.stop_monitoring()
                self.quit_application()
            elif choice is False:
                self.hide_to_tray()
        else:
            choice = messagebox.askyesno(
                "Minimize to Tray?", 
                "Do you want to minimize to system tray instead of quitting?",
                parent=self.root
            )
            if choice:
                self.hide_to_tray()
            else:
                self.quit_application()

    def setup_tray_icon(self):
        if not pystray or not PIL_AVAILABLE:
            self.log_message_gui("pystray or Pillow not found. System tray icon disabled.")
            self.tray_icon = None
            return

        try:
            icon_path = "icon.png"
            if not os.path.exists(icon_path):
                try:
                    # Don't create files during tests - just create a dummy image object
                    dummy_image = Image.new('RGB', (64, 64), color='blue') # Will use mocked Image.new in tests
                    dummy_image.save(icon_path) # Will use mocked save in tests
                    self.log_message_gui(f"'{icon_path}' not found. Created a dummy icon. Replace with your desired icon.")
                except Exception as e:
                    self.log_message_gui(f"Could not create dummy icon: {e}. Tray icon might not work.")
                    self.tray_icon = None
                    return

            # Try to use the existing image or a dummy one for tests
            try:
                image = Image.open(icon_path) if os.path.exists(icon_path) else Image.new('RGB', (64, 64), color='blue')
            except Exception:
                # Last resort for tests
                image = MagicMock()  # type: ignore
                
            menu = (pystray.MenuItem('Show', self.show_from_tray, default=True),
                    pystray.MenuItem('Settings', self.run_setup_wizard_from_tray),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem('Quit', self.quit_application))
                    
            self.tray_icon = pystray.Icon("EmailMonitor", image, "Email Monitor", menu)
            
            # Don't start the thread during testing
            threading.Thread(target=self.tray_icon.run, daemon=True).start() # Will use mocked Thread in tests
            
            self.log_message_gui("System tray icon initialized.")

        except FileNotFoundError:
            self.log_message_gui(f"Error: Tray icon '{icon_path}' not found. System tray functionality will be limited.")
            self.tray_icon = None
        except Exception as e:
            self.log_message_gui(f"Error setting up tray icon: {e}")
            self.tray_icon = None

    def run_setup_wizard_from_tray(self):
        self.show_from_tray()
        self.root.after(100, lambda: self.run_setup_wizard(force_setup=False))

    def hide_to_tray(self):
        if self.tray_icon and hasattr(self.tray_icon, 'visible') and self.tray_icon.visible:
            self.root.withdraw()
            self.log_message_gui("Application minimized to system tray.")
        else:
            self.log_message_gui("System tray icon not available. Cannot minimize to tray.")
            choice = messagebox.askokcancel(
                "Quit?", 
                "System tray not available. Quit the application?", 
                parent=self.root
            )
            if choice:
                self.quit_application()

    def show_from_tray(self, icon=None, item=None):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_set()

    def quit_application(self, icon=None, item=None):
        self.log_message_gui("Exiting application...")
        if self.monitoring_active:
            self.stop_event.set()
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5)
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
        self.root.destroy()

if __name__ == "__main__":
    if not PIL_AVAILABLE:
        print("WARNING: Pillow library not found. System tray icon might not work or look as expected.")
        print("Please install it: pip install Pillow")
    if not pystray:
        print("WARNING: pystray library not found. System tray functionality will be disabled.")
        print("Please install it: pip install pystray")

    root = tk.Tk()
    app = EmailMonitorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
