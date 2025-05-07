"""
Global pytest configuration to ensure tests don't hang due to GUI or network operations.
"""
import sys
from unittest.mock import MagicMock


# Create proper mock classes instead of just MagicMock instances
class MockTk:
    """Mock class for tkinter.Tk"""
    def __init__(self, *args, **kwargs):
        pass

    def title(self, *args, **kwargs):
        pass

    def geometry(self, *args, **kwargs):
        pass

    def protocol(self, *args, **kwargs):
        pass

    def withdraw(self, *args, **kwargs):
        pass

    def deiconify(self, *args, **kwargs):
        pass

    def lift(self, *args, **kwargs):
        pass

    def focus_set(self, *args, **kwargs):
        pass

    def quit(self, *args, **kwargs):
        pass

    def destroy(self, *args, **kwargs):
        pass

    def mainloop(self, *args, **kwargs):
        pass

    def after(self, *args, **kwargs):
        pass


class MockDialog:
    """Mock class for tkinter.simpledialog.Dialog"""
    def __init__(self, parent, title=None, **kwargs):
        self.parent = parent
        self.title = title
        self.result = None

    def body(self, master):
        pass

    def apply(self):
        pass


class MockIMAP4:
    """Mock class for imaplib.IMAP4"""
    class error(Exception):
        """IMAP4 error class"""
        pass

    def __init__(self):
        pass


class MockIMAP4_SSL(MagicMock):
    """Mock class for imaplib.IMAP4_SSL"""
    pass


def mock_messagebox_function(*args, **kwargs):
    """Mock for messagebox functions - always return True for easy testing"""
    return True


# Mock problematic modules before any tests or modules using them are imported
def pytest_configure(config):
    """Configure pytest environment before collection starts"""
    # Mock GUI modules
    mock_pystray = MagicMock()
    mock_pystray.Icon = MagicMock()
    mock_pystray.Menu = MagicMock()
    mock_pystray.MenuItem = MagicMock()
    sys.modules['pystray'] = mock_pystray
    
    mock_pil = MagicMock()
    mock_pil_image = MagicMock()
    mock_pil_image.open = MagicMock(return_value=MagicMock())
    mock_pil.Image = mock_pil_image
    sys.modules['PIL'] = mock_pil
    sys.modules['PIL.Image'] = mock_pil_image
    
    # Mock tkinter with proper class implementation
    mock_tk = MagicMock()
    mock_tk.Tk = MockTk
    mock_tk.Frame = MagicMock()
    mock_tk.Label = MagicMock()
    mock_tk.Button = MagicMock()
    mock_tk.Text = MagicMock()
    mock_tk.Entry = MagicMock()
    mock_tk.NORMAL = "normal"
    mock_tk.DISABLED = "disabled"
    mock_tk.END = "end"
    mock_tk.LEFT = "left"
    mock_tk.BOTH = "both"
    
    mock_ttk = MagicMock()
    mock_ttk.Frame = MagicMock()
    mock_ttk.Label = MagicMock()
    mock_ttk.Button = MagicMock()
    mock_ttk.Entry = MagicMock()
    
    mock_messagebox = MagicMock()
    # Setup messagebox functions to return True for simplicity
    mock_messagebox.showinfo = mock_messagebox_function
    mock_messagebox.showerror = mock_messagebox_function
    mock_messagebox.showwarning = mock_messagebox_function
    mock_messagebox.askyesno = mock_messagebox_function
    mock_messagebox.askokcancel = mock_messagebox_function
    mock_messagebox.askyesnocancel = mock_messagebox_function
    
    mock_simpledialog = MagicMock()
    mock_simpledialog.Dialog = MockDialog
    
    sys.modules['tkinter'] = mock_tk
    sys.modules['tkinter.ttk'] = mock_ttk
    sys.modules['tkinter.messagebox'] = mock_messagebox
    sys.modules['tkinter.simpledialog'] = mock_simpledialog
    
    # Mock network modules with proper error classes
    mock_socket = MagicMock()
    mock_socket.gaierror = type('gaierror', (Exception,), {})
    
    mock_imaplib = MagicMock()
    mock_imaplib.IMAP4 = MockIMAP4
    mock_imaplib.IMAP4_SSL = MockIMAP4_SSL
    mock_imaplib.socket = mock_socket
    
    sys.modules['socket'] = mock_socket
    sys.modules['imaplib'] = mock_imaplib
    
    # Prevent browser opening
    mock_webbrowser = MagicMock()
    mock_webbrowser.open = MagicMock(return_value=True)
    sys.modules['webbrowser'] = mock_webbrowser