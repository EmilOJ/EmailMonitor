import unittest
from unittest.mock import MagicMock, patch, call
import email.message
import imaplib

# Add the parent directory to the Python path to allow importing email_monitor
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from email_monitor import (
    connect_to_gmail,
    search_emails,
    decode_subject,
    extract_link_from_email,
    open_link_in_browser,
    mark_as_read
)

# Basic config for tests
TEST_CONFIG = {
    "IMAP_SERVER": "imap.gmail.com",
    "EMAIL_ACCOUNT": "test@example.com",
    "APP_PASSWORD": "password",
    "KEYWORD": "test_keyword",
    "POLL_INTERVAL_SECONDS": 30,
    "MAILBOX": "INBOX"
}

class TestEmailMonitorFunctions(unittest.TestCase):

    def test_decode_subject_simple(self):
        subject = "Simple Subject"
        self.assertEqual(decode_subject(subject), "Simple Subject")

    def test_decode_subject_encoded(self):
        # Simulate an email.header.Header object for an encoded subject
        mock_header = email.header.make_header([("Hello World", "utf-8")])
        self.assertEqual(decode_subject(str(mock_header)), "Hello World")

        mock_header_iso = email.header.make_header([("Héllo Test", "iso-8859-1")])
        self.assertEqual(decode_subject(str(mock_header_iso)), "Héllo Test")
        
        mock_header_multiple = email.header.make_header([("Part1", "utf-8"), (" Part2", "iso-8859-1")])
        self.assertEqual(decode_subject(str(mock_header_multiple)), "Part1 Part2")

    def test_decode_subject_none(self):
        self.assertEqual(decode_subject(None), "")

    @patch('webbrowser.open_new_tab')
    def test_open_link_in_browser(self, mock_open_new_tab):
        logger_mock = MagicMock()
        link = "http://example.com"
        open_link_in_browser(link, logger=logger_mock)
        mock_open_new_tab.assert_called_once_with(link)
        logger_mock.assert_called_once_with(f"Opened link in browser: {link}")

    @patch('webbrowser.open_new_tab', side_effect=Exception("Browser error"))
    def test_open_link_in_browser_error(self, mock_open_new_tab):
        logger_mock = MagicMock()
        link = "http://example.com"
        open_link_in_browser(link, logger=logger_mock)
        mock_open_new_tab.assert_called_once_with(link)
        logger_mock.assert_any_call(f"Opened link in browser: {link}") # Original attempt log
        logger_mock.assert_any_call(f"Error opening link http://example.com: Browser error")


    def test_extract_link_from_email_simple_html(self):
        logger_mock = MagicMock()
        msg = email.message.Message()
        msg.set_payload([email.message.Message()]) # Make it multipart
        html_part = email.message.Message()
        html_part.set_content_type("text/html")
        html_part.set_payload("<html><body><a href=\"http://example.com/link1\">Link</a></body></html>", charset="utf-8")
        
        text_part = email.message.Message()
        text_part.set_content_type("text/plain")
        text_part.set_payload("Some text with no link.", charset="utf-8")

        msg.set_payload([text_part, html_part]) # Order can matter

        link = extract_link_from_email(msg, logger=logger_mock)
        self.assertEqual(link, "http://example.com/link1")
        logger_mock.assert_not_called() # No logging for successful simple extraction

    def test_extract_link_from_email_plain_text_first_link(self):
        logger_mock = MagicMock()
        msg = email.message.Message()
        msg.set_payload("This is a test email with a link: https://www.google.com and another http://example.com", charset="utf-8")
        msg.set_content_type("text/plain")
        
        link = extract_link_from_email(msg, logger=logger_mock)
        self.assertEqual(link, "https://www.google.com") # Should get the first one
        logger_mock.assert_not_called()

    def test_extract_link_from_email_no_link(self):
        logger_mock = MagicMock()
        msg = email.message.Message()
        msg.set_payload("This email has no links.", charset="utf-8")
        msg.set_content_type("text/plain")
        link = extract_link_from_email(msg, logger=logger_mock)
        self.assertIsNone(link)
        logger_mock.assert_not_called()

    def test_extract_link_from_email_complex_html_body(self):
        logger_mock = MagicMock()
        msg = email.message.Message()
        msg.set_payload([email.message.Message()]) # Multipart
        html_body = """
        <html><body>
        <p>Some text</p>
        <a href='http://example.com/path?query=val'>Click here</a>
        <p>More text <a href=\"https://another.link.org\">Another</a></p>
        </body></html>
        """
        html_part = email.message.Message()
        html_part.set_content_type("text/html")
        html_part.set_payload(html_body, charset="utf-8")
        msg.set_payload([html_part])

        link = extract_link_from_email(msg, logger=logger_mock)
        self.assertEqual(link, "http://example.com/path?query=val") # First link found
        logger_mock.assert_not_called()

    def test_extract_link_from_email_with_base_tag(self):
        logger_mock = MagicMock()
        msg = email.message.Message()
        msg.set_payload([email.message.Message()]) # Multipart
        html_body = """
        <html><head><base href=\"http://base.com/\"></head>
        <body><a href=\"relative/path\">Link</a></body></html>
        """
        html_part = email.message.Message()
        html_part.set_content_type("text/html")
        html_part.set_payload(html_body, charset="utf-8")
        msg.set_payload([html_part])

        link = extract_link_from_email(msg, logger=logger_mock)
        self.assertEqual(link, "http://base.com/relative/path")
        logger_mock.assert_not_called()
        
    def test_extract_link_from_email_non_multipart_with_link_in_payload(self):
        logger_mock = MagicMock()
        msg = email.message.Message()
        msg.set_content_type("text/plain")
        payload_content = "Hello, check this link: http://example.com/test_link"
        msg.set_payload(payload_content, charset="utf-8")

        link = extract_link_from_email(msg, logger=logger_mock)
        self.assertEqual(link, "http://example.com/test_link")
        logger_mock.assert_not_called()

    def test_extract_link_from_email_bad_html(self):
        logger_mock = MagicMock()
        msg = email.message.Message()
        msg.set_payload([email.message.Message()])
        html_part = email.message.Message()
        html_part.set_content_type("text/html")
        # Malformed HTML, but link might still be extractable by regex
        html_part.set_payload("<html><body><a hre=\"malformed.com/link\">Link</a> <a href=\"http://good.link\">Good</a></body></html>", charset="utf-8")
        msg.set_payload([html_part])
        link = extract_link_from_email(msg, logger=logger_mock)
        self.assertEqual(link, "http://good.link") # Regex should find the valid one
        logger_mock.assert_not_called() # No specific logging for this case in current code

    @patch('imaplib.IMAP4_SSL')
    def test_connect_to_gmail_success(self, mock_imap_constructor):
        logger_mock = MagicMock()
        mock_mail_instance = MagicMock()
        mock_mail_instance.login.return_value = ('OK', [b'Login successful'])
        mock_mail_instance.select.return_value = ('OK', [b'Mailbox selected'])
        mock_imap_constructor.return_value = mock_mail_instance

        mail = connect_to_gmail(TEST_CONFIG, logger=logger_mock)

        self.assertIsNotNone(mail)
        mock_imap_constructor.assert_called_once_with(TEST_CONFIG["IMAP_SERVER"])
        mock_mail_instance.login.assert_called_once_with(TEST_CONFIG["EMAIL_ACCOUNT"], TEST_CONFIG["APP_PASSWORD"])
        mock_mail_instance.select.assert_called_once_with(TEST_CONFIG["MAILBOX"])
        logger_mock.assert_any_call(f"Connecting to {TEST_CONFIG['IMAP_SERVER']}...")
        logger_mock.assert_any_call(f"Logging in as {TEST_CONFIG['EMAIL_ACCOUNT']}...")
        logger_mock.assert_any_call(f"Selecting mailbox {TEST_CONFIG['MAILBOX']}...")
        logger_mock.assert_any_call("Connection successful.")

    @patch('imaplib.IMAP4_SSL')
    def test_connect_to_gmail_login_failure(self, mock_imap_constructor):
        logger_mock = MagicMock()
        mock_mail_instance = MagicMock()
        mock_mail_instance.login.side_effect = imaplib.IMAP4.error("Login failed")
        mock_imap_constructor.return_value = mock_mail_instance

        mail = connect_to_gmail(TEST_CONFIG, logger=logger_mock)

        self.assertIsNone(mail)
        logger_mock.assert_any_call(f"Connecting to {TEST_CONFIG['IMAP_SERVER']}...")
        logger_mock.assert_any_call(f"Logging in as {TEST_CONFIG['EMAIL_ACCOUNT']}...")
        logger_mock.assert_any_call("IMAP login failed: Login failed")
        mock_mail_instance.shutdown.assert_called_once() # Check if shutdown is called on error

    @patch('imaplib.IMAP4_SSL')
    def test_connect_to_gmail_select_failure(self, mock_imap_constructor):
        logger_mock = MagicMock()
        mock_mail_instance = MagicMock()
        mock_mail_instance.login.return_value = ('OK', [b'Login successful'])
        mock_mail_instance.select.side_effect = imaplib.IMAP4.error("Select failed")
        mock_imap_constructor.return_value = mock_mail_instance

        mail = connect_to_gmail(TEST_CONFIG, logger=logger_mock)

        self.assertIsNone(mail)
        logger_mock.assert_any_call(f"Selecting mailbox {TEST_CONFIG['MAILBOX']}...")
        logger_mock.assert_any_call("Failed to select mailbox INBOX: Select failed")
        mock_mail_instance.close.assert_called_once()
        mock_mail_instance.logout.assert_called_once()

    @patch('imaplib.IMAP4_SSL', side_effect=Exception("Connection error"))
    def test_connect_to_gmail_connection_error(self, mock_imap_constructor):
        logger_mock = MagicMock()
        mail = connect_to_gmail(TEST_CONFIG, logger=logger_mock)
        self.assertIsNone(mail)
        logger_mock.assert_any_call(f"Connecting to {TEST_CONFIG['IMAP_SERVER']}...")
        logger_mock.assert_any_call("Failed to connect to IMAP server: Connection error")

    def test_search_emails_success(self):
        logger_mock = MagicMock()
        mock_mail = MagicMock()
        mock_mail.search.return_value = ('OK', [b'1 2 3'])
        
        config_with_keyword = TEST_CONFIG.copy()
        config_with_keyword["KEYWORD"] = "urgent"

        ids = search_emails(mock_mail, config_with_keyword, logger=logger_mock)
        
        self.assertEqual(ids, [b'1', b'2', b'3'])
        expected_search_criteria = f'(UNSEEN TEXT "{config_with_keyword["KEYWORD"]}")'
        mock_mail.search.assert_called_once_with(None, expected_search_criteria)
        logger_mock.assert_called_once_with(f"Searching for emails with criteria: {expected_search_criteria}")

    def test_search_emails_no_keyword(self):
        logger_mock = MagicMock()
        mock_mail = MagicMock()
        mock_mail.search.return_value = ('OK', [b'4 5'])

        config_no_keyword = TEST_CONFIG.copy()
        config_no_keyword["KEYWORD"] = "" # No keyword

        ids = search_emails(mock_mail, config_no_keyword, logger=logger_mock)
        self.assertEqual(ids, [b'4', b'5'])
        expected_search_criteria = '(UNSEEN)' # Only UNSEEN if no keyword
        mock_mail.search.assert_called_once_with(None, expected_search_criteria)
        logger_mock.assert_called_once_with(f"Searching for emails with criteria: {expected_search_criteria}")

    def test_search_emails_api_error(self):
        logger_mock = MagicMock()
        mock_mail = MagicMock()
        mock_mail.search.return_value = ('NO', [b'Error in search'])
        
        ids = search_emails(mock_mail, TEST_CONFIG, logger=logger_mock)
        
        self.assertEqual(ids, [])
        logger_mock.assert_any_call(f"Email search failed: Error in search")

    def test_search_emails_exception(self):
        logger_mock = MagicMock()
        mock_mail = MagicMock()
        mock_mail.search.side_effect = imaplib.IMAP4.error("IMAP crashed")

        ids = search_emails(mock_mail, TEST_CONFIG, logger=logger_mock)
        self.assertEqual(ids, [])
        logger_mock.assert_any_call(f"Error searching emails: IMAP crashed")

    def test_mark_as_read_success(self):
        logger_mock = MagicMock()
        mock_mail = MagicMock()
        mock_mail.store.return_value = ('OK', [b'Flags updated'])
        email_id = b'123'
        
        mark_as_read(mock_mail, email_id, TEST_CONFIG, logger=logger_mock)
        
        mock_mail.store.assert_called_once_with(email_id, '+FLAGS', '\Seen')
        logger_mock.assert_called_once_with(f"Marked email ID {email_id.decode()} as read.")

    def test_mark_as_read_failure(self):
        logger_mock = MagicMock()
        mock_mail = MagicMock()
        mock_mail.store.return_value = ('NO', [b'Failed to update flags'])
        email_id = b'123'

        mark_as_read(mock_mail, email_id, TEST_CONFIG, logger=logger_mock)

        mock_mail.store.assert_called_once_with(email_id, '+FLAGS', '\Seen')
        logger_mock.assert_called_once_with(f"Failed to mark email ID {email_id.decode()} as read. Response: ([b'Failed to update flags'],)")

    def test_mark_as_read_exception(self):
        logger_mock = MagicMock()
        mock_mail = MagicMock()
        mock_mail.store.side_effect = imaplib.IMAP4.error("Store command failed")
        email_id = b'123'

        mark_as_read(mock_mail, email_id, TEST_CONFIG, logger=logger_mock)

        mock_mail.store.assert_called_once_with(email_id, '+FLAGS', '\Seen')
        logger_mock.assert_called_once_with(f"Error marking email ID {email_id.decode()} as read: Store command failed")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
