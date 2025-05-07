import imaplib
import email
from email.header import decode_header
import webbrowser
import time
import re
import os
import sys

def _console_log_message(message):
    """Default logger: Prints a message with a timestamp to the console."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")

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
        logger("Please check your email, app password, and IMAP settings.")
        logger("Ensure IMAP is enabled in your Gmail settings and you are using a valid App Password.")
        return None
    except (OSError, imaplib.socket.gaierror) as e: # Catch network errors more broadly
        logger(f"Network error: Could not connect to {app_config['IMAP_SERVER']}. Details: {e}")
        return None
    except Exception as e:
        logger(f"An unexpected error occurred during login: {e}")
        return None

def decode_subject(subject):
    """Decodes email subject to handle different charsets."""
    decoded_parts = decode_header(subject)
    decoded_subject_str = ''
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                decoded_subject_str += part.decode(charset or 'utf-8')
            except UnicodeDecodeError:
                decoded_subject_str += part.decode('latin-1', errors='replace') # Fallback
        else:
            decoded_subject_str += part
    return decoded_subject_str

def search_emails(mail, app_config, logger=_console_log_message):
    """Searches for emails with a specific keyword in subject or body."""
    keyword = app_config['KEYWORD']
    mailbox = app_config.get('MAILBOX', "INBOX")
    try:
        logger(f"Selecting mailbox: '{mailbox}'")
        status, messages = mail.select(mailbox)
        if status != 'OK':
            logger(f"Error selecting mailbox {mailbox}: {status}")
            return []

        # IMAP search is case-insensitive by default for most servers including Gmail
        # Using a single, comprehensive search query.
        # Note: Complex keywords with quotes might need careful handling.
        search_criteria = f'(OR (UNSEEN SUBJECT "{keyword}" BODY "{keyword}") (SUBJECT "{keyword}" BODY "{keyword}"))'
        logger(f"Searching with criteria: {search_criteria}")
        
        status, email_ids_data = mail.search(None, search_criteria)

        if status != 'OK':
            logger(f"Error searching emails: {status}")
            return []

        email_ids = email_ids_data[0].split()
        if email_ids:
            logger(f"Found {len(email_ids)} email(s) matching search criteria.")
        else:
            logger("No emails found matching search criteria.")
        return email_ids
    except Exception as e:
        logger(f"Error searching emails: {e}")
        return []

def extract_link_from_email(msg_data, logger=_console_log_message): # msg_data is an email.message.Message object
    """Extracts the first HTTP/HTTPS link from the email body."""
    for part in msg_data.walk():
        content_type = part.get_content_type()
        content_disposition = str(part.get("Content-Disposition"))

        if "attachment" not in content_disposition:
            if content_type == "text/plain" or content_type == "text/html":
                try:
                    body = part.get_payload(decode=True).decode()
                except UnicodeDecodeError:
                    try:
                        body = part.get_payload(decode=True).decode('latin-1', errors='replace')
                    except Exception as e_decode:
                        logger(f"Could not decode email part (type {content_type}): {e_decode}")
                        continue 
                
                url_match = re.search(r'https?://[^\s"\'<>\[\]]+', body)
                if url_match:
                    return url_match.group(0)
    return None

def mark_as_read(mail, email_id, app_config, logger=_console_log_message):
    """Marks an email as read (seen)."""
    mailbox = app_config.get('MAILBOX', "INBOX")
    try:
        # mail.select(mailbox) # select should already be done by search_emails or before calling this
        mail.store(email_id, '+FLAGS', '\\Seen')
        logger(f"Marked email ID {email_id.decode() if isinstance(email_id, bytes) else email_id} as read in {mailbox}.")
    except Exception as e:
        logger(f"Error marking email ID {email_id.decode() if isinstance(email_id, bytes) else email_id} as read: {e}")

def open_link_in_browser(link, logger=_console_log_message):
    """Opens a link in the default web browser."""
    try:
        webbrowser.open(link, new=2)
        logger(f"Successfully opened link: {link}")
    except Exception as e:
        logger(f"Error opening link {link} in browser: {e}")

def main():
    # This main function is for standalone execution of email_monitor.py
    # It will use the config.py file directly and _console_log_message.
    try:
        import config as config_module
    except ImportError:
        _console_log_message("Error: Configuration file (config.py) not found.")
        _console_log_message("Please ensure config.py exists and contains your Gmail credentials and settings.")
        sys.exit(1)

    # Create a dictionary from the config module for consistent access by functions
    current_config_dict = {
        key: getattr(config_module, key) 
        for key in dir(config_module) 
        if not key.startswith('_') and hasattr(config_module, key)
    }
    # Ensure all required keys are present with defaults if necessary
    current_config_dict.setdefault("IMAP_SERVER", "imap.gmail.com")
    current_config_dict.setdefault("MAILBOX", "INBOX")
    current_config_dict.setdefault("POLL_INTERVAL_SECONDS", 30)


    if not current_config_dict.get("EMAIL_ACCOUNT") or current_config_dict["EMAIL_ACCOUNT"] == 'YOUR_EMAIL@gmail.com':
        _console_log_message("CRITICAL: Please set your EMAIL_ACCOUNT in config.py")
        sys.exit(1)
    if not current_config_dict.get("APP_PASSWORD") or current_config_dict["APP_PASSWORD"] == 'YOUR_APP_PASSWORD':
        _console_log_message("CRITICAL: Please set your APP_PASSWORD in config.py")
        sys.exit(1)
    if not current_config_dict.get("KEYWORD") or current_config_dict["KEYWORD"] == 'your_specific_keyword':
        _console_log_message("CRITICAL: Please set your KEYWORD in config.py")
        sys.exit(1)

    _console_log_message("Email Monitor Script (Standalone) - Starting up...")
    _console_log_message(f"Monitoring for emails with keyword: '{current_config_dict['KEYWORD']}'")
    _console_log_message(f"Polling interval: {current_config_dict['POLL_INTERVAL_SECONDS']} seconds.")
    _console_log_message("Press Ctrl+C to stop the script.")

    processed_email_ids = set()

    try:
        while True:
            mail = connect_to_gmail(current_config_dict, _console_log_message)
            if not mail:
                _console_log_message(f"Failed to connect. Retrying in {current_config_dict['POLL_INTERVAL_SECONDS']} seconds...")
                time.sleep(current_config_dict['POLL_INTERVAL_SECONDS'])
                continue

            try:
                email_ids = search_emails(mail, current_config_dict, _console_log_message)

                if not email_ids:
                    _console_log_message(f"No new emails found. Waiting...")
                else:
                    _console_log_message(f"Found {len(email_ids)} email(s) potentially matching.")

                for e_id in reversed(email_ids): 
                    if e_id in processed_email_ids:
                        continue

                    status, msg_data_raw = mail.fetch(e_id, '(RFC822)')
                    if status == 'OK':
                        for response_part in msg_data_raw:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                subject = decode_subject(msg['subject'])
                                from_ = msg.get('From')
                                _console_log_message(f"Processing ID {e_id.decode()}: From: {from_}, Subject: {subject}")

                                keyword_in_subject = current_config_dict['KEYWORD'].lower() in subject.lower()
                                link = None
                                keyword_in_body = False
                                
                                for part in msg.walk():
                                    if part.get_content_type() in ["text/plain", "text/html"] and "attachment" not in str(part.get("Content-Disposition")):
                                        try:
                                            body_part_content = part.get_payload(decode=True).decode()
                                        except UnicodeDecodeError:
                                            try: body_part_content = part.get_payload(decode=True).decode('latin-1', errors='replace')
                                            except: continue
                                        
                                        if current_config_dict['KEYWORD'].lower() in body_part_content.lower():
                                            keyword_in_body = True
                                        
                                        if not link:
                                            # Pass logger to extract_link_from_email
                                            extracted_url = extract_link_from_email(msg, _console_log_message)
                                            if extracted_url: link = extracted_url
                                        
                                        if link and keyword_in_body: break
                                
                                if keyword_in_subject or keyword_in_body:
                                    if link:
                                        _console_log_message(f"Found link in email ID {e_id.decode()}: {link}")
                                        open_link_in_browser(link, _console_log_message)
                                        mark_as_read(mail, e_id, current_config_dict, _console_log_message)
                                        processed_email_ids.add(e_id)
                                    else:
                                        _console_log_message(f"Keyword found in email ID {e_id.decode()}, but no link extracted.")
                                        mark_as_read(mail, e_id, current_config_dict, _console_log_message)
                                        processed_email_ids.add(e_id)
                                else:
                                    _console_log_message(f"Keyword not found in ID {e_id.decode()} after fetch. Skipping.")
                                    processed_email_ids.add(e_id)
                    else:
                        _console_log_message(f"Failed to fetch email ID {e_id.decode()}")
            except Exception as e_loop:
                _console_log_message(f"An error occurred during email processing loop: {e_loop}")
            finally:
                if mail:
                    try:
                        mail.close()
                        mail.logout()
                        _console_log_message("Logged out from Gmail.")
                    except Exception as e_logout:
                        _console_log_message(f"Error during logout: {e_logout}")
            
            _console_log_message(f"Waiting for {current_config_dict['POLL_INTERVAL_SECONDS']} seconds...")
            time.sleep(current_config_dict['POLL_INTERVAL_SECONDS'])

    except KeyboardInterrupt:
        _console_log_message("Script interrupted by user. Exiting...")
    except Exception as e_critical:
        _console_log_message(f"An unexpected critical error occurred: {e_critical}")
    finally:
        _console_log_message("Email Monitor Script (Standalone) - Shutting down.")
        sys.exit(0)

if __name__ == "__main__":
    main()
