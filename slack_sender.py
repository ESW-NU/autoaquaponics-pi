import os
import requests
from logs import register_logger

slack_logger = register_logger("logs/slack.log", "SlackSender")

def send_slack_message(text):
    """Send a message to the configured Slack channel."""
    endpoint = os.getenv('SLACK_MESSAGE_ENDPOINT')
    slack_logger.debug(f"Sending slack message to {endpoint}: {text}")
    myobj = {"text": text}
    try:
        requests.post(endpoint, json=myobj)
        slack_logger.debug("Slack message sent successfully")
        return True
    except Exception as e:
        slack_logger.error(f"Failed to send Slack message: {e}")
        return False