# Email Monitor GUI Tool

This application monitors a Gmail account for emails matching a specific keyword, extracts the first link found in the email, and opens it in your default web browser. It features a graphical user interface (GUI) for easy configuration and control.

## Features

-   Connects to Gmail via IMAP using an App Password.
-   User-friendly GUI for managing settings, starting, and stopping the monitor.
-   Setup wizard for initial configuration of email account, password, keyword, and other settings.
-   Monitors for incoming emails with a specific keyword in the subject or body (case-insensitive).
-   Extracts the first HTTP/HTTPS link from the email body.
-   Opens the extracted link in the default web browser.
-   Marks processed emails as read.
-   Polls for new emails at a configurable interval.
-   Logs actions and errors to a text area within the GUI.
-   System tray icon for minimizing the application and quick access to actions (Show, Settings, Quit).
-   Configuration is saved to a `config.py` file.

## Prerequisites

-   Python 3.x
-   An active Gmail account with IMAP enabled.
-   A Gmail App Password.
-   The following Python libraries (install via pip):
    *   `Pillow` (for the system tray icon image)
    *   `pystray` (for system tray functionality)

    You can install them using:
    ```bash
    pip install Pillow pystray
    ```

## Setup Instructions

1.  **Enable IMAP in Gmail:**
    *   Go to your Gmail account settings.
    *   Click on the "Forwarding and POP/IMAP" tab.
    *   In the "IMAP access" section, select "Enable IMAP".
    *   Click "Save Changes".

2.  **Generate a Gmail App Password:**
    *   Go to your Google Account settings: [https://myaccount.google.com/](https://myaccount.google.com/)
    *   Navigate to "Security".
    *   Under "Signing in to Google", if "2-Step Verification" is off, you need to turn it on first.
    *   Once 2-Step Verification is on, click on "App passwords". You might need to sign in again.
    *   Under "Select app", choose "Mail".
    *   Under "Select device", choose "Other (Custom name)" and give it a name (e.g., "EmailMonitorApp").
    *   Click "Generate".
    *   A 16-character password will be displayed. **Copy this password.** This is your App Password.
    *   Click "Done".

3.  **Initial Application Setup:**
    *   When you first run `gui_app.py`, if a valid `config.py` is not found or is incomplete, a setup wizard will automatically appear.
    *   Enter your IMAP server (default is `imap.gmail.com`), Email Account, the App Password you generated, the keyword to search for, the desired poll interval, and the mailbox to monitor.
    *   Click "OK" to save the configuration. This will create or update the `config.py` file in the same directory as the application.
    *   You can access the settings/setup wizard again anytime via the "Settings" button in the main window or the tray icon menu (if monitoring is not active).

## Running the Application

1.  Open a terminal or command prompt.
2.  Navigate to the directory where `gui_app.py` and other files are located.
    ```bash
    cd path/to/EmailMonitor
    ```
3.  Run the application using Python:
    ```bash
    python gui_app.py
    ```
4.  The Email Monitor GUI window will appear.
    *   If configuration is needed, the setup wizard will guide you.
    *   Once configured, click "Start Monitoring".
    *   Log messages will appear in the text area.

## Using the Application

-   **Start Monitoring:** Begins checking your email account based on the current settings.
-   **Stop Monitoring:** Stops the email checking process.
-   **Settings:** Opens the setup wizard to modify configuration (only available when monitoring is stopped).
-   **Log Area:** Displays status messages, errors, and information about processed emails.
-   **Closing the Window:**
    *   If monitoring is active, you'll be asked if you want to stop monitoring and exit, or minimize to the system tray.
    *   If monitoring is not active, you'll be asked if you want to minimize to the system tray or quit.
-   **System Tray Icon:**
    *   Right-click the icon for a menu: Show, Settings, Quit.
    *   Left-click (or default action) shows the application window.
    *   If `Pillow` or `pystray` are not installed, tray functionality will be disabled or limited. A dummy icon might be created if `icon.png` is missing.

## How it Works

1.  **Configuration:** The application loads settings from `config.py`. If the file doesn't exist or is invalid, the GUI prompts for setup.
2.  **GUI Interaction:** The user controls the monitoring process (start/stop) and settings via the Tkinter-based GUI.
3.  **Monitoring Thread:** When "Start Monitoring" is clicked, a separate thread begins:
    *   **Login:** Connects to the Gmail IMAP server using credentials from the configuration.
    *   **Search:** Periodically searches the specified mailbox for unread emails or emails matching the `KEYWORD` in the subject or body.
    *   **Fetch & Parse:** If matching emails are found, they are fetched.
    *   **Keyword Verification & Link Extraction:** The script re-verifies the keyword in the subject/body and extracts the first HTTP/HTTPS link.
    *   **Open Link:** If a link is found, it's opened in the default web browser.
    *   **Mark as Read:** Processed emails are marked as read (\\Seen flag).
    *   **Loop:** The process repeats after the `POLL_INTERVAL_SECONDS`.
4.  **Logging:** All actions, found emails, and errors are logged to the GUI's text area.
5.  **Tray Icon:** Provides background operation and quick access.

## Troubleshooting

*   **Login Failed / Connection Issues:**
    *   Verify your Email Account, App Password, and IMAP Server in the Settings.
    *   Ensure IMAP is enabled in your Gmail settings.
    *   Check your internet connection.
    *   The GUI log area will display error messages from the email connection attempts.
*   **No Emails Found:**
    *   Double-check the `KEYWORD` and `MAILBOX` in Settings.
    *   Ensure target emails are not already marked as read if testing.
*   **Link Not Opening:**
    *   The script extracts the *first* valid link.
*   **System Tray Icon Issues:**
    *   Ensure `Pillow` and `pystray` are installed (`pip install Pillow pystray`).
    *   An `icon.png` file is recommended in the application's directory for the tray icon. If not found, a dummy blue icon will be created.
*   **Character Encoding Issues:**
    *   The script attempts to decode emails using common encodings. Issues with specific emails might require code adjustments in `email_monitor.py`.

## Security Considerations

*   **App Password:** Using a Gmail App Password is more secure than your main password.
*   **Local Storage:** Credentials (App Password) are stored in `config.py` on your local machine.
*   **Keyword Specificity:** Use a distinct keyword to avoid unintended actions.

## Platform Compatibility

-   **Windows:** Tested and works.
-   **macOS:** Tested and works.
-   **Linux:** Should work. `webbrowser.open()` and system tray behavior might vary slightly with desktop environments.

## Disclaimer

This tool is provided as-is. Be cautious when running scripts that access your email. Understand the script's function before use.
