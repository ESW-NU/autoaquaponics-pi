import os
import requests
from logs import register_logger

slack_logger = register_logger("logs/slack.log", "SlackSender")

# Slack configuration
SLACK_MESSAGE_ENDPOINT = os.getenv('SLACK_MESSAGE_ENDPOINT')

def send_slack_message(text):
    """Send a message to the configured Slack channel."""
    myobj = {"text": text}
    try:
        requests.post(SLACK_MESSAGE_ENDPOINT, json=myobj)
        slack_logger.info("Slack message sent successfully")
        return True
    except Exception as e:
        slack_logger.warning(f"Failed to send Slack message: {e}")
        return False