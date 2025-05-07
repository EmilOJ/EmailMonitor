"""
Email Monitor Configuration
--------------------------
This file contains the settings for the EmailMonitor application.

When setting up:
1. Replace the placeholder values with your actual credentials
2. Make sure to obtain an App Password for Gmail to use with this application
   (https://support.google.com/accounts/answer/185833)
"""

# Gmail IMAP settings
IMAP_SERVER = 'imap.gmail.com'
EMAIL_ACCOUNT = 'emil.johansen@gmail.com'
APP_PASSWORD = 'rahx ovtl opkx oqcs'

# Email search criteria
KEYWORD = 'test123'

# Monitoring settings
POLL_INTERVAL_SECONDS = 5

# Mailbox to monitor
MAILBOX = "Inbox"
