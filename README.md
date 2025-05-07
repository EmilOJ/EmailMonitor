# Email Monitor Tool

This script monitors a Gmail account for emails matching a specific keyword and automatically opens the first link found in the email body in your default web browser.

## Features

- Connects to Gmail via IMAP using an App Password.
- Monitors for incoming emails with a specific keyword in the subject or body (case-insensitive).
- Extracts the first HTTP/HTTPS link from the email body.
- Opens the extracted link in the default web browser.
- Polls for new emails at a configurable interval.
- Logs actions and errors to the console.
- Designed to be lightweight and run on Windows and Mac.

## Prerequisites

- Python 3.x
- An active Gmail account with IMAP enabled.
- A Gmail App Password.

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
    *   Under "Select device", choose "Other (Custom name)" and give it a name (e.g., "EmailMonitorScript").
    *   Click "Generate".
    *   A 16-character password will be displayed. **Copy this password.** This is your App Password. You won't see it again.
    *   Click "Done".

3.  **Configure the Script:**
    *   Open the `config.py` file in a text editor.
    *   Update the following fields:
        *   `EMAIL_ACCOUNT`: Set this to your Gmail address (e.g., `'your_email@gmail.com'`).
        *   `APP_PASSWORD`: Set this to the 16-character App Password you generated in the previous step (e.g., `'abcdefghijklmnop'`).
        *   `KEYWORD`: Set this to the specific keyword you want to search for in email subjects or bodies (e.g., `'Project Update'`). The search is case-insensitive.
        *   `POLL_INTERVAL_SECONDS` (Optional): Adjust the polling interval if needed (default is 30 seconds).
        *   `MAILBOX` (Optional): Specify a different mailbox if you don't want to monitor "INBOX" (e.g., `'MyLabel'`).
    *   Save the `config.py` file.

## Running the Script

1.  Open a terminal or command prompt.
2.  Navigate to the directory where you saved the `email_monitor.py` and `config.py` files.
    ```bash
    cd path/to/EmailMonitor
    ```
3.  Run the script using Python:
    ```bash
    python email_monitor.py
    ```
4.  The script will start monitoring your Gmail account. You will see log messages in the terminal.

## Stopping the Script

-   Press `Ctrl+C` in the terminal where the script is running.

## How it Works

1.  **Login:** The script logs into your Gmail account using the IMAP protocol with the credentials provided in `config.py`.
2.  **Search:** It periodically searches the specified mailbox (default: INBOX) for emails that either:
    *   Are unread.
    *   Contain the specified `KEYWORD` in their subject or body.
    The search is case-insensitive.
3.  **Fetch & Parse:** If matching emails are found, the script fetches them.
4.  **Keyword Verification & Link Extraction:** For each fetched email:
    *   It re-verifies if the `KEYWORD` is present in the decoded subject or body.
    *   It searches for the first URL (starting with `http://` or `https://`) in the email's body (plaintext or HTML parts, excluding attachments).
5.  **Open Link:** If a link is found in an email that also contains the keyword, the script opens this link in your system's default web browser.
6.  **Mark as Read:** After processing an email (either by opening a link or by confirming it contained the keyword but no link), the script marks the email as "read" (\\Seen flag) on the server to avoid reprocessing it in future checks.
7.  **Loop:** The script waits for the configured `POLL_INTERVAL_SECONDS` and then repeats the process.

## Troubleshooting

*   **Login Failed:**
    *   Double-check your `EMAIL_ACCOUNT` and `APP_PASSWORD` in `config.py`.
    *   Ensure IMAP is enabled in your Gmail settings.
    *   Verify that the App Password is correct and hasn't been revoked.
    *   Check your internet connection.
*   **No Emails Found:**
    *   Ensure the `KEYWORD` in `config.py` is correct and matches the expected emails.
    *   Check if the emails you are expecting are in the correct `MAILBOX`.
    *   Make sure the target emails are not already marked as read if you are testing repeatedly.
*   **Link Not Opening:**
    *   The script extracts the *first* link found. If there are multiple links, ensure the desired one is the first, or modify the link extraction logic in `email_monitor.py`.
    *   Some complex HTML emails might have links formatted in a way the basic regex doesn't catch. The current regex `https?://[^\s\"'<>\[\]]+` is fairly general but might need adjustment for specific edge cases.
*   **Character Encoding Issues:**
    *   The script attempts to decode email subjects and bodies using common encodings (UTF-8, Latin-1). If you encounter issues with specific emails, the decoding logic might need to be enhanced.

## Security Considerations

*   **App Password:** Using an App Password is more secure than storing your main Google account password. You can revoke App Passwords at any time from your Google Account settings without affecting your main password.
*   **Local Execution:** This script runs entirely on your local machine. Your credentials are stored locally in `config.py` and are only used to communicate directly with Google's IMAP servers.
*   **Keyword Specificity:** Use a specific keyword to avoid processing unintended emails.

## Platform Compatibility

-   **Windows:** Tested and works.
-   **macOS:** Tested and works.
-   **Linux:** Should work, as Python and its standard libraries are cross-platform. `webbrowser.open()` behavior might vary slightly depending on the desktop environment.

## Disclaimer

This tool is provided as-is. Always be cautious when running scripts that access your email account. Ensure you understand what the script does before running it.
