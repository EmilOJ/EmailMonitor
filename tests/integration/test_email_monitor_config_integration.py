import sys
import os
import unittest
from unittest import mock
import imaplib
from pathlib import Path

# Add the parent directory to sys.path to import the application modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Import application modules
import email_monitor
from email_monitor import connect_to_gmail, search_emails

class TestEmailMonitorConfigIntegration(unittest.TestCase):
    """Integration tests for the email monitor and config integration"""

    def setUp(self):
        self.test_config = {
            "IMAP_SERVER": "imap.gmail.com",
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "test_password",
            "KEYWORD": "test_keyword",
            "POLL_INTERVAL_SECONDS": 30,
            "MAILBOX": "INBOX"
        }
        
        # Setup a mock logger to capture log messages
        self.log_messages = []
        self.mock_logger = lambda msg: self.log_messages.append(msg)

    @mock.patch('imaplib.IMAP4_SSL')
    def test_connect_to_gmail_with_config(self, mock_imap):
        """Test that connect_to_gmail correctly uses the configuration"""
        # Setup mock IMAP connection
        mock_imap.return_value.login.return_value = ('OK', [b'LOGIN completed'])
        
        # Connect using our test config
        mail = connect_to_gmail(self.test_config, logger=self.mock_logger)
        
        # Check that the connection was made with the correct parameters
        mock_imap.assert_called_once_with(self.test_config['IMAP_SERVER'])
        mock_imap.return_value.login.assert_called_once_with(
            self.test_config['EMAIL_ACCOUNT'], 
            self.test_config['APP_PASSWORD']
        )
        
        # Check that the connection was successful
        self.assertIsNotNone(mail)
        
        # Verify log messages
        self.assertTrue(any(self.test_config['IMAP_SERVER'] in msg for msg in self.log_messages))
        self.assertTrue(any(self.test_config['EMAIL_ACCOUNT'] in msg for msg in self.log_messages))

    @mock.patch('imaplib.IMAP4_SSL')
    def test_connect_to_gmail_error_handling(self, mock_imap):
        """Test error handling when connection fails"""
        # Setup mock to raise an IMAP4 error
        mock_imap.return_value.login.side_effect = imaplib.IMAP4.error("Login failed")
        
        # Connect should return None when login fails
        mail = connect_to_gmail(self.test_config, logger=self.mock_logger)
        self.assertIsNone(mail)
        
        # Check proper error logging
        self.assertTrue(any("IMAP login failed" in msg for msg in self.log_messages))
        
    @mock.patch('imaplib.IMAP4_SSL')
    def test_search_emails_with_config(self, mock_imap):
        """Test that search_emails correctly uses the configuration"""
        # Setup mock responses
        mock_imap.return_value.select.return_value = ('OK', [b'1'])
        mock_imap.return_value.search.return_value = ('OK', [b'1 2 3'])
        
        # Connect using our test config
        mail = mock_imap.return_value
        email_ids = search_emails(mail, self.test_config, logger=self.mock_logger)
        
        # Check that search was called with the correct keyword
        search_call_args = mock_imap.return_value.search.call_args[0]
        self.assertIn(self.test_config['KEYWORD'], str(search_call_args[1]))
        
        # Check that the email IDs were returned correctly
        self.assertEqual(email_ids, [b'1', b'2', b'3'])
        
        # Verify log messages
        self.assertTrue(any(self.test_config['MAILBOX'] in msg for msg in self.log_messages))

if __name__ == '__main__':
    unittest.main()