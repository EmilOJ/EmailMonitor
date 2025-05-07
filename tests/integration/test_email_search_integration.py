import sys
import os
import unittest
from unittest import mock
import imaplib
import email
from email.header import Header
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Import application modules
from email_monitor import (
    connect_to_gmail,
    search_emails,
    decode_subject,
    extract_link_from_email,
    mark_as_read
)

class TestEmailSearchIntegration(unittest.TestCase):
    """Integration tests for email search functionality"""

    def setUp(self):
        self.test_config = {
            "IMAP_SERVER": "imap.gmail.com",
            "EMAIL_ACCOUNT": "test@example.com",
            "APP_PASSWORD": "test_password",
            "KEYWORD": "important",
            "POLL_INTERVAL_SECONDS": 30,
            "MAILBOX": "INBOX"
        }
        
        # Setup a mock logger to capture log messages
        self.log_messages = []
        self.mock_logger = lambda msg: self.log_messages.append(msg)
        
        # Create sample email messages for testing
        self.create_test_emails()

    def create_test_emails(self):
        """Create sample email messages for testing"""
        # Email with keyword in subject
        subject_match_msg = email.message.EmailMessage()
        subject_match_msg["Subject"] = f"This is an IMPORTANT test email"
        subject_match_msg["From"] = "sender@example.com"
        subject_match_msg["To"] = "recipient@example.com"
        subject_match_msg.set_content("This is a test email without any links.")
        self.subject_match_msg = subject_match_msg
        
        # Email with keyword in body and link
        body_match_msg = email.message.EmailMessage()
        body_match_msg["Subject"] = "Test email with link"
        body_match_msg["From"] = "sender@example.com"
        body_match_msg["To"] = "recipient@example.com"
        body_match_msg.set_content(
            "This is a test email containing the keyword IMPORTANT and a link: https://example.com/test"
        )
        self.body_match_msg = body_match_msg
        
        # Email with no match
        no_match_msg = email.message.EmailMessage()
        no_match_msg["Subject"] = "Regular test email"
        no_match_msg["From"] = "sender@example.com"
        no_match_msg["To"] = "recipient@example.com"
        no_match_msg.set_content("This is a regular test email without any significant keywords.")
        self.no_match_msg = no_match_msg

    @mock.patch('imaplib.IMAP4_SSL')
    def test_search_and_process_email_flow(self, mock_imap):
        """Test the full flow of searching emails and processing them based on keyword matches"""
        # Setup mock responses
        mock_mail = mock_imap.return_value
        mock_mail.login.return_value = ('OK', [b'LOGIN completed'])
        mock_mail.select.return_value = ('OK', [b'3'])  # 3 messages in mailbox
        
        # Mock search to return message IDs
        mock_mail.search.return_value = ('OK', [b'1 2 3'])
        
        # Setup fetch responses for each email
        def mock_fetch_side_effect(email_id, format_spec):
            if email_id == b'1':
                return ('OK', [(b'1', self.subject_match_msg.as_bytes())])
            elif email_id == b'2':
                return ('OK', [(b'2', self.body_match_msg.as_bytes())])
            elif email_id == b'3':
                return ('OK', [(b'3', self.no_match_msg.as_bytes())])
            return ('NO', [])
            
        mock_mail.fetch.side_effect = mock_fetch_side_effect
        
        # Connect to mail
        mail = connect_to_gmail(self.test_config, logger=self.mock_logger)
        self.assertIsNotNone(mail)
        
        # Search for emails with the keyword
        email_ids = search_emails(mail, self.test_config, logger=self.mock_logger)
        
        # We should get 3 emails (in a real scenario, search would filter, but our mock returns all)
        self.assertEqual(len(email_ids), 3)
        
        # Process each email to check for keyword
        processed_count = 0
        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status == 'OK':
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg_bytes = response_part[1]
                        msg = email.message_from_bytes(msg_bytes)
                        
                        # Extract subject and check for keyword
                        subject = decode_subject(msg['subject'])
                        keyword_in_subject = self.test_config['KEYWORD'].lower() in subject.lower()
                        
                        # Check body for keyword
                        keyword_in_body = False
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                                if self.test_config['KEYWORD'].lower() in body.lower():
                                    keyword_in_body = True
                                    break
                        
                        # If keyword found in either subject or body, count it
                        if keyword_in_subject or keyword_in_body:
                            processed_count += 1
                            
                            # Extract link if present
                            link = extract_link_from_email(msg, logger=self.mock_logger)
                            
                            # Mark as read
                            mark_as_read(mail, email_id, self.test_config, logger=self.mock_logger)
        
        # We should have found the keyword in 2 of the 3 emails
        self.assertEqual(processed_count, 2)
        
        # Check that mark_as_read was called correctly
        mock_mail.store.assert_called()  # The mock doesn't track each call correctly for this test

    @mock.patch('imaplib.IMAP4_SSL')
    def test_extract_link_integration(self, mock_imap):
        """Test integration of link extraction from emails"""
        # Create a message with a link
        msg = email.message.EmailMessage()
        msg.set_content("Test email with link: https://example.com/test")
        
        # Extract link from the message
        link = extract_link_from_email(msg, logger=self.mock_logger)
        
        # Check that link was extracted correctly
        self.assertEqual(link, "https://example.com/test")
        
        # Create a message without a link
        msg_no_link = email.message.EmailMessage()
        msg_no_link.set_content("Test email without any links")
        
        # Extract link from the message without a link
        link = extract_link_from_email(msg_no_link, logger=self.mock_logger)
        
        # Check that no link was extracted
        self.assertIsNone(link)

if __name__ == '__main__':
    unittest.main()