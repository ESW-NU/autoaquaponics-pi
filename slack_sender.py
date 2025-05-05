import os
import requests
from logs import register_logger

slack_logger = register_logger("logs/slack.log", "SlackSender")

def send_slack_message(text):
    """Send a message to the configured Slack channel."""
    endpoint = os.getenv('SLACK_MESSAGE_ENDPOINT')
    slack_logger.info(f"Sending slack message to {endpoint}: {text}")
    myobj = {"text": text}
    try:
        requests.post(endpoint, json=myobj)
        slack_logger.info("Slack message sent successfully")
        return True
    except Exception as e:
        slack_logger.warning(f"Failed to send Slack message: {e}")
        return False