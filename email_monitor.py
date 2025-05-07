import imaplib
import email
from email.header import decode_header
import webbrowser
import time
import re
import os
import sys


# --- Logging Functions ---
def _console_log_message(message):
    """Default logger: Prints a message with a timestamp to the console."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")


# --- Email Connection Functions ---
def connect_to_gmail(app_config, logger=_console_log_message):
    """Connects to Gmail IMAP server and logs in."""
    try:
        logger(f"Attempting to connect to {app_config['IMAP_SERVER']} for user {app_config['EMAIL_ACCOUNT']}...")
        mail = imaplib.IMAP4_SSL(app_config['IMAP_SERVER'])
        mail.login(app_config['EMAIL_ACCOUNT'], app_config['APP_PASSWORD'])
        logger(f"Successfully logged into {app_config['EMAIL_ACCOUNT']}")
        return mail
    except imaplib.IMAP4.error as e:
        logger(f"IMAP login failed: {e}")
        logger("Check your email, app password, and IMAP settings.")
        return None
    except (OSError, imaplib.socket.gaierror) as e:
        logger(f"Network error: Could not connect to {app_config['IMAP_SERVER']}. Details: {e}")
        return None
    except Exception as e:
        logger(f"Unexpected error during login: {e}")
        return None


# --- Email Processing Functions ---
def decode_subject(subject):
    """Decodes email subject to handle different charsets."""
    if not subject:
        return ""
        
    decoded_parts = decode_header(subject)
    decoded_subject_str = ''
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                decoded_subject_str += part.decode(charset or 'utf-8')
            except UnicodeDecodeError:
                decoded_subject_str += part.decode('latin-1', errors='replace')
        else:
            decoded_subject_str += part
    return decoded_subject_str


def search_emails(mail, app_config, logger=_console_log_message):
    """Searches for emails with a specific keyword in subject or body."""
    keyword = app_config['KEYWORD']
    mailbox = app_config.get('MAILBOX', "Inbox")
    
    try:
        logger(f"Selecting mailbox: '{mailbox}'")
        status, messages = mail.select(mailbox)
        if status != 'OK':
            logger(f"Error selecting mailbox {mailbox}: {status}")
            return []

        # Search for unread emails with keyword in subject or body
        search_criteria = f'(OR (UNSEEN SUBJECT "{keyword}" BODY "{keyword}") (SUBJECT "{keyword}" BODY "{keyword}"))'
        logger(f"Searching with criteria: {search_criteria}")
        
        status, email_ids_data = mail.search(None, search_criteria)
        if status != 'OK':
            logger(f"Error searching emails: {status}")
            return []

        email_ids = email_ids_data[0].split()
        count = len(email_ids)
        if count:
            logger(f"Found {count} email(s) matching search criteria.")
        else:
            logger("No emails found matching search criteria.")
        return email_ids
    except Exception as e:
        logger(f"Error searching emails: {e}")
        return []


def extract_link_from_email(msg_data, logger=_console_log_message):
    """Extracts the first HTTP/HTTPS link from the email body."""
    for part in msg_data.walk():
        content_type = part.get_content_type()
        content_disposition = str(part.get("Content-Disposition"))

        if "attachment" not in content_disposition:
            if content_type in ("text/plain", "text/html"):
                try:
                    body = part.get_payload(decode=True).decode()
                except UnicodeDecodeError:
                    try:
                        body = part.get_payload(decode=True).decode('latin-1', errors='replace')
                    except Exception as e_decode:
                        logger(f"Could not decode email part ({content_type}): {e_decode}")
                        continue 
                
                url_match = re.search(r'https?://[^\s"\'<>\[\]]+', body)
                if url_match:
                    return url_match.group(0)
    return None


def mark_as_read(mail, email_id, app_config, logger=_console_log_message):
    """Marks an email as read (seen)."""
    mailbox = app_config.get('MAILBOX', "Inbox")
    try:
        mail.store(email_id, '+FLAGS', '\\Seen')
        id_str = email_id.decode() if isinstance(email_id, bytes) else email_id
        logger(f"Marked email ID {id_str} as read in {mailbox}.")
    except Exception as e:
        id_str = email_id.decode() if isinstance(email_id, bytes) else email_id
        logger(f"Error marking email ID {id_str} as read: {e}")


def open_link_in_browser(link, logger=_console_log_message):
    """Opens a link in the default web browser."""
    try:
        webbrowser.open(link, new=2)
        logger(f"Successfully opened link: {link}")
    except Exception as e:
        logger(f"Error opening link {link} in browser: {e}")


# --- Main Function ---
def main():
    """Standalone execution of email monitor script."""
    try:
        import config as config_module
    except ImportError:
        _console_log_message("Error: Configuration file (config.py) not found.")
        _console_log_message("Please ensure config.py exists with your Gmail credentials and settings.")
        sys.exit(1)

    # Create a dictionary from the config module
    current_config = {
        key: getattr(config_module, key) 
        for key in dir(config_module) 
        if not key.startswith('_') and hasattr(config_module, key)
    }
    
    # Set default values if missing
    current_config.setdefault("IMAP_SERVER", "imap.gmail.com")
    current_config.setdefault("MAILBOX", "Inbox")
    current_config.setdefault("POLL_INTERVAL_SECONDS", 30)

    # Validate required settings
    missing_settings = []
    if not current_config.get("EMAIL_ACCOUNT") or current_config["EMAIL_ACCOUNT"] == 'YOUR_EMAIL@gmail.com':
        missing_settings.append("EMAIL_ACCOUNT")
    if not current_config.get("APP_PASSWORD") or current_config["APP_PASSWORD"] == 'YOUR_APP_PASSWORD':
        missing_settings.append("APP_PASSWORD")
    if not current_config.get("KEYWORD") or current_config["KEYWORD"] == 'your_specific_keyword':
        missing_settings.append("KEYWORD")
    
    if missing_settings:
        _console_log_message(f"CRITICAL: Please set these values in config.py: {', '.join(missing_settings)}")
        sys.exit(1)

    _console_log_message("Email Monitor Script - Starting up...")
    _console_log_message(f"Monitoring for emails with keyword: '{current_config['KEYWORD']}'")
    _console_log_message(f"Polling interval: {current_config['POLL_INTERVAL_SECONDS']} seconds.")
    _console_log_message("Press Ctrl+C to stop the script.")

    processed_email_ids = set()

    try:
        monitor_emails(current_config, processed_email_ids)
    except KeyboardInterrupt:
        _console_log_message("Script interrupted by user. Exiting...")
    except Exception as e_critical:
        _console_log_message(f"An unexpected critical error occurred: {e_critical}")
    finally:
        _console_log_message("Email Monitor Script - Shutting down.")
        sys.exit(0)


def monitor_emails(config, processed_email_ids):
    """Core email monitoring loop."""
    while True:
        mail = None
        try:
            mail = connect_to_gmail(config, _console_log_message)
            if not mail:
                _console_log_message(f"Failed to connect. Retrying in {config['POLL_INTERVAL_SECONDS']} seconds...")
                time.sleep(config['POLL_INTERVAL_SECONDS'])
                continue

            email_ids = search_emails(mail, config, _console_log_message)
            if not email_ids:
                _console_log_message("No new emails found. Waiting...")
            
            for e_id in reversed(email_ids):
                if e_id in processed_email_ids:
                    continue

                process_email(mail, e_id, config, processed_email_ids)
                
        except Exception as e:
            _console_log_message(f"Error in monitoring loop: {e}")
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                    _console_log_message("Logged out from Gmail.")
                except Exception as e_logout:
                    _console_log_message(f"Error during logout: {e_logout}")
        
        _console_log_message(f"Waiting for {config['POLL_INTERVAL_SECONDS']} seconds...")
        time.sleep(config['POLL_INTERVAL_SECONDS'])


def process_email(mail, e_id, config, processed_email_ids):
    """Process a single email."""
    e_id_str = e_id.decode() if isinstance(e_id, bytes) else e_id
    status, msg_data_raw = mail.fetch(e_id, '(RFC822)')
    
    if status != 'OK':
        _console_log_message(f"Failed to fetch email ID {e_id_str}")
        return
        
    for response_part in msg_data_raw:
        if not isinstance(response_part, tuple):
            continue
            
        msg = email.message_from_bytes(response_part[1])
        subject = decode_subject(msg['subject'])
        from_ = msg.get('From')
        _console_log_message(f"Processing ID {e_id_str}: From: {from_}, Subject: {subject}")

        keyword_in_subject = config['KEYWORD'].lower() in subject.lower()
        link = None
        keyword_in_body = False
        
        for part in msg.walk():
            if part.get_content_type() in ["text/plain", "text/html"] and \
               "attachment" not in str(part.get("Content-Disposition")):
                body_content = get_decoded_content(part)
                if not body_content:
                    continue
                    
                if config['KEYWORD'].lower() in body_content.lower():
                    keyword_in_body = True
                
                if not link:
                    url = extract_link_from_email(msg, _console_log_message)
                    if url: 
                        link = url
                
                if link and keyword_in_body:
                    break
        
        if keyword_in_subject or keyword_in_body:
            if link:
                _console_log_message(f"Found link in email ID {e_id_str}: {link}")
                open_link_in_browser(link, _console_log_message)
                mark_as_read(mail, e_id, config, _console_log_message)
            else:
                _console_log_message(f"Keyword found in ID {e_id_str}, but no link extracted.")
                mark_as_read(mail, e_id, config, _console_log_message)
        else:
            _console_log_message(f"Keyword not found in ID {e_id_str} after fetch. Skipping.")
            
        processed_email_ids.add(e_id)


def get_decoded_content(part):
    """Helper to decode email content handling encoding issues."""
    try:
        return part.get_payload(decode=True).decode()
    except UnicodeDecodeError:
        try:
            return part.get_payload(decode=True).decode('latin-1', errors='replace')
        except Exception:
            return None


if __name__ == "__main__":
    main()
