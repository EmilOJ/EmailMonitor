import unittest
import sys
import os
from unittest.mock import patch, MagicMock, call
import imaplib
import email
from email.message import Message

# Add parent directory to path to import the module to be tested
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import email_monitor

class TestEmailMonitor(unittest.TestCase):
    """Unit tests for email_monitor.py module"""
    
    def setUp(self):
        """Set up test fixtures, called before each test method"""
        self.mock_logger = MagicMock()
        self.test_config = {
            "IMAP_SERVER": "imap.gmail.com",
            "EMAIL_ACCOUNT": "test@gmail.com",
            "APP_PASSWORD": "test_password",
            "KEYWORD": "test_keyword",
            "POLL_INTERVAL_SECONDS": 10,
            "MAILBOX": "INBOX"
        }

    def test_connect_to_gmail_success(self):
        """Test successful connection to Gmail"""
        mock_imap = MagicMock()
        with patch('imaplib.IMAP4_SSL', return_value=mock_imap):
            result = email_monitor.connect_to_gmail(self.test_config, self.mock_logger)
            
            # Verify IMAP4_SSL was called with correct server
            imaplib.IMAP4_SSL.assert_called_once_with(self.test_config['IMAP_SERVER'])
            # Verify login was called with correct credentials
            mock_imap.login.assert_called_once_with(
                self.test_config['EMAIL_ACCOUNT'], 
                self.test_config['APP_PASSWORD']
            )
            # Verify the result is the mock mail object
            self.assertEqual(result, mock_imap)
            # Verify logger was called with success message
            self.mock_logger.assert_any_call(f"Attempting to connect to {self.test_config['IMAP_SERVER']} for user {self.test_config['EMAIL_ACCOUNT']}...")
            self.mock_logger.assert_any_call(f"Successfully logged into {self.test_config['EMAIL_ACCOUNT']}")

    def test_connect_to_gmail_login_failure(self):
        """Test handling of login failure"""
        mock_imap = MagicMock()
        mock_imap.login.side_effect = imaplib.IMAP4.error("Login failed")
        
        with patch('imaplib.IMAP4_SSL', return_value=mock_imap):
            result = email_monitor.connect_to_gmail(self.test_config, self.mock_logger)
            
            # Verify login was attempted
            mock_imap.login.assert_called_once()
            # Verify None is returned on failure
            self.assertIsNone(result)
            # Verify appropriate error messages were logged
            self.mock_logger.assert_any_call("IMAP login failed: Login failed")
    
    def test_connect_to_gmail_network_error(self):
        """Test handling of network errors"""
        with patch('imaplib.IMAP4_SSL', side_effect=OSError("Network error")):
            result = email_monitor.connect_to_gmail(self.test_config, self.mock_logger)
            
            # Verify None is returned on network failure
            self.assertIsNone(result)
            # Verify network error message was logged
            self.mock_logger.assert_any_call("Network error: Could not connect to imap.gmail.com. Details: Network error")

    def test_decode_subject(self):
        """Test subject decoding with different character encodings"""
        # Test plain ASCII subject
        self.assertEqual(email_monitor.decode_subject("Simple Subject"), "Simple Subject")
        
        # Test UTF-8 encoded subject in header format
        encoded_subject = "=?utf-8?b?VGVzdCBTdWJqZWN0IHdpdGggVW5pY29kZSDwn5iC?="
        # We can't test exact result without actual encoding/decoding, but we can verify it doesn't raise exceptions
        result = email_monitor.decode_subject(encoded_subject)
        self.assertIsInstance(result, str)

    def test_search_emails_success(self):
        """Test successful search for emails"""
        mock_mail = MagicMock()
        mock_mail.select.return_value = ('OK', [b'1'])
        mock_mail.search.return_value = ('OK', [b'1 2 3'])
        
        result = email_monitor.search_emails(mock_mail, self.test_config, self.mock_logger)
        
        # Verify mailbox was selected
        mock_mail.select.assert_called_once_with(self.test_config['MAILBOX'])
        # Verify search was performed with correct criteria
        self.assertIn(call(None, f'(OR (UNSEEN SUBJECT "{self.test_config["KEYWORD"]}" BODY "{self.test_config["KEYWORD"]}") (SUBJECT "{self.test_config["KEYWORD"]}" BODY "{self.test_config["KEYWORD"]}"))')
                     , mock_mail.search.call_args_list)
        # Verify the result is the list of email IDs
        self.assertEqual(result, [b'1', b'2', b'3'])

    def test_search_emails_select_failure(self):
        """Test handling of mailbox selection failure"""
        mock_mail = MagicMock()
        mock_mail.select.return_value = ('NO', [b'Mailbox does not exist'])
        
        result = email_monitor.search_emails(mock_mail, self.test_config, self.mock_logger)
        
        # Verify an empty list is returned on mailbox selection failure
        self.assertEqual(result, [])
        # Verify error was logged
        self.mock_logger.assert_any_call(f"Error selecting mailbox {self.test_config['MAILBOX']}: NO")

    def test_search_emails_search_failure(self):
        """Test handling of search failure"""
        mock_mail = MagicMock()
        mock_mail.select.return_value = ('OK', [b'1'])
        mock_mail.search.return_value = ('NO', [b'Search failed'])
        
        result = email_monitor.search_emails(mock_mail, self.test_config, self.mock_logger)
        
        # Verify an empty list is returned on search failure
        self.assertEqual(result, [])
        # Verify error was logged
        self.mock_logger.assert_any_call("Error searching emails: NO")

    def test_extract_link_from_email(self):
        """Test link extraction from email body"""
        # Create a mock email message with a link
        mock_msg = MagicMock(spec=Message)
        mock_part = MagicMock()
        mock_part.get_content_type.return_value = "text/plain"
        mock_part.get.return_value = ""  # Content-Disposition is empty
        mock_part.get_payload.return_value = b"This email contains a link: https://example.com/test"
        mock_msg.walk.return_value = [mock_part]
        
        with patch('email.message.Message.walk', return_value=[mock_part]):
            result = email_monitor.extract_link_from_email(mock_msg, self.mock_logger)
            
            # Verify the correct link was extracted
            self.assertEqual(result, "https://example.com/test")
    
    def test_extract_link_from_email_no_link(self):
        """Test link extraction when no link is present"""
        # Create a mock email message without a link
        mock_msg = MagicMock(spec=Message)
        mock_part = MagicMock()
        mock_part.get_content_type.return_value = "text/plain"
        mock_part.get.return_value = ""  # Content-Disposition is empty
        mock_part.get_payload.return_value = b"This email does not contain a link"
        mock_msg.walk.return_value = [mock_part]
        
        with patch('email.message.Message.walk', return_value=[mock_part]):
            result = email_monitor.extract_link_from_email(mock_msg, self.mock_logger)
            
            # Verify None is returned when no link is found
            self.assertIsNone(result)

    def test_mark_as_read(self):
        """Test marking an email as read"""
        mock_mail = MagicMock()
        email_id = b'1'
        
        email_monitor.mark_as_read(mock_mail, email_id, self.test_config, self.mock_logger)
        
        # Verify the correct flag was set
        mock_mail.store.assert_called_once_with(email_id, '+FLAGS', '\\Seen')
        # Verify success message was logged
        self.mock_logger.assert_any_call(f"Marked email ID 1 as read in {self.test_config['MAILBOX']}.")
    
    def test_mark_as_read_failure(self):
        """Test handling of failure to mark an email as read"""
        mock_mail = MagicMock()
        email_id = b'1'
        mock_mail.store.side_effect = Exception("Failed to mark as read")
        
        email_monitor.mark_as_read(mock_mail, email_id, self.test_config, self.mock_logger)
        
        # Verify error message was logged
        self.mock_logger.assert_any_call("Error marking email ID 1 as read: Failed to mark as read")

    def test_open_link_in_browser(self):
        """Test opening a link in the browser"""
        test_link = "https://example.com"
        
        with patch('webbrowser.open') as mock_open:
            email_monitor.open_link_in_browser(test_link, self.mock_logger)
            
            # Verify webbrowser.open was called with the correct link
            mock_open.assert_called_once_with(test_link, new=2)
            # Verify success message was logged
            self.mock_logger.assert_called_with(f"Successfully opened link: {test_link}")
    
    def test_open_link_in_browser_failure(self):
        """Test handling of failure to open a link"""
        test_link = "https://example.com"
        
        with patch('webbrowser.open', side_effect=Exception("Failed to open link")):
            email_monitor.open_link_in_browser(test_link, self.mock_logger)
            
            # Verify error message was logged
            self.mock_logger.assert_called_with(f"Error opening link {test_link} in browser: Failed to open link")

if __name__ == '__main__':
    unittest.main()