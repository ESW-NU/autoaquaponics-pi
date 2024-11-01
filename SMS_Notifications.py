import os
import smtplib
import time
import phonenumbers
from phonenumbers import carrier
from phonenumbers.phonenumberutil import number_type
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Firebase
service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
cred = credentials.Certificate(service_account_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Email configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# SMS Gateway Domains
CARRIER_GATEWAYS = {
    'T-Mobile': '@tmomail.net',
    'Cricket': '@mms.cricketwireless.net',
    'Cricket-Alt': '@sms.cricketwireless.net',
    'AT&T': '@txt.att.net',
    'Verizon': '@vtext.com',
    'Sprint': '@messaging.sprintpcs.com',
    'Boost Mobile': '@sms.myboostmobile.com',
    'Metro PCS': '@mymetropcs.com',
    'U.S. Cellular': '@email.uscc.net',
    'Virgin Mobile': '@vmobl.com',
    'Republic Wireless': '@text.republicwireless.com',
    'Google Fi': '@msg.fi.google.com',
    'Xfinity Mobile': '@vtext.com',
    'Ting': '@message.ting.com',
    'Consumer Cellular': '@mailmymobile.net',
    'Simple Mobile': '@smtext.com',
    'Mint Mobile': '@tmomail.net',
    'Red Pocket': '@vtext.com',
    'TracFone': '@mmst5.tracfone.com',
    'Straight Talk': '@vtext.com',
    'Page Plus': '@vtext.com'
}

def format_phone_number(phone_number):
    """
    Format phone number to include country code if not present.
    Expects a string of digits like "3125932138"
    """
    if not phone_number.startswith('+'):
        if phone_number.startswith('1'):
            phone_number = '+' + phone_number
        else:
            phone_number = '+1' + phone_number
    return phone_number

def detect_carrier(phone_number):
    """
    Detect the carrier for a given phone number using the phonenumbers library.
    Returns None if carrier cannot be determined.
    """
    try:
        formatted_number = format_phone_number(phone_number)
        parsed_number = phonenumbers.parse(formatted_number)
        if number_type(parsed_number) == phonenumbers.PhoneNumberType.MOBILE:
            carrier_name = carrier.name_for_number(parsed_number, "en")
            print(f"Detected carrier: {carrier_name} for number: {formatted_number}")
            return carrier_name
        else:
            print(f"Number {formatted_number} is not a mobile number")
            return None
    except Exception as e:
        print(f"Error detecting carrier for {formatted_number}: {str(e)}")
        return None

def get_sms_gateway_address(phone_number, carrier_name=None):
    """
    Get multiple SMS gateway addresses for a phone number.
    Returns a list of gateway addresses to try.
    """
    clean_number = ''.join(filter(str.isdigit, phone_number))
    
    if carrier_name == 'T-Mobile':
        print(f"Using T-Mobile gateways for {clean_number}")
        return [
            f"{clean_number}@tmomail.net",
            f"{clean_number}@vtext.com",  # Try Verizon's gateway as backup
            f"{clean_number}@txt.att.net"  # Try AT&T's gateway as backup
        ]
    elif carrier_name == 'Cricket':
        print(f"Using Cricket gateways for {clean_number}")
        return [
            f"{clean_number}@mms.cricketwireless.net",
            f"{clean_number}@sms.cricketwireless.net"
        ]
    
    # Default fallback gateways for unknown carriers
    print(f"No specific carrier gateway found for {carrier_name}, trying all gateways")
    return [
        f"{clean_number}@tmomail.net",
        f"{clean_number}@vtext.com",
        f"{clean_number}@txt.att.net",
        f"{clean_number}@mms.cricketwireless.net",
        f"{clean_number}@sms.cricketwireless.net"
    ]

def send_sms_via_email(recipient_number, message, carrier_name=None):
    """
    Send an SMS through email gateway with multiple gateway attempts.
    Returns True if any gateway succeeds, False if all fail.
    """
    gateway_addresses = get_sms_gateway_address(recipient_number, carrier_name)
    if not gateway_addresses:
        print(f"No gateway addresses found for {recipient_number}")
        return False
        
    print(f"Attempting to send to {recipient_number} via {carrier_name or 'multiple gateways'}")
    
    for gateway_address in gateway_addresses:
        try:
            email_message = MIMEMultipart()
            email_message["From"] = SENDER_EMAIL
            email_message["To"] = gateway_address
            email_message["Subject"] = "Aquaponics Alert"
            email_message.attach(MIMEText(message, "plain"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(email_message)
                used_gateway = gateway_address.split('@')[1]
                print(f"Successfully sent to {recipient_number} via {used_gateway}")
                return True
                
        except Exception as e:
            print(f"Failed to send to {recipient_number} via {gateway_address}: {str(e)}")
            continue
    
    return False

def get_tolerances():
    """
    Retrieve tolerances from Firebase.
    Returns a dictionary of tolerances or empty dict if none found.
    """
    tolerances = {}
    tolerances_ref = db.collection('tolerances')
    docs = tolerances_ref.stream()
    for doc in docs:
        tolerances[doc.id] = doc.to_dict()
    if tolerances:
        print(f"Retrieved tolerances: {tolerances}")
        return tolerances
    else:
        print("No tolerances found in Firebase")
        return {}

def check_tolerances(sensor_data, tolerances):
    """
    Check if sensor data is within tolerances.
    Returns a list of alert messages for out-of-range values.
    """
    alerts = []
    fields_to_check = ['TDS', 'air_temp', 'distance', 'humidity', 'pH', 'water_temp']
    
    for field in fields_to_check:
        if field in sensor_data and field in tolerances:
            value = sensor_data[field]
            tolerance_data = tolerances[field]
            min_val = tolerance_data.get('min')
            max_val = tolerance_data.get('max')
            if min_val is not None and max_val is not None:
                if value < min_val or value > max_val:
                    alerts.append(f"{field} is out of range: {value} (safe range: {min_val}-{max_val})")
            elif min_val is not None and value < min_val:
                alerts.append(f"{field} is below minimum: {value} (minimum: {min_val})")
            elif max_val is not None and value > max_val:
                alerts.append(f"{field} is above maximum: {value} (maximum: {max_val})")
        elif field in sensor_data and field not in tolerances:
            print(f"Warning: No tolerance defined for {field}")
    
    print(f"Alerts generated: {alerts}")
    return alerts

def get_notification_recipients():
    """
    Retrieve users who have opted in for SMS notifications.
    Returns a list of recipient dictionaries with number and carrier info.
    """
    users_ref = db.collection('users')
    query = users_ref.where(filter=firestore.FieldFilter("sms_notifications", "==", True))
    recipients = []
    for user in query.stream():
        user_data = user.to_dict()
        if 'phoneNumber' in user_data:
            # Add debug logging
            print(f"Found user with phone: {user_data['phoneNumber']}")
            print(f"Carrier info: {user_data.get('carrier')}")
            phone_info = {
                'number': user_data['phoneNumber'],
                'carrier': user_data.get('carrier')
            }
            recipients.append(phone_info)
            print(f"Added recipient: {phone_info['number']} with carrier: {phone_info['carrier']}")
    print(f"Total recipients found: {len(recipients)}")
    return recipients

def handle_sensor_update(doc_snapshot, changes, read_time):
    """
    Handle real-time updates to sensor data.
    Processes updates and sends notifications if needed.
    """
    print("\n--- New Sensor Update ---")
    
    if not doc_snapshot:
        print("No snapshot data received")
        return
        
    most_recent = max(doc_snapshot, 
                     key=lambda x: x.to_dict().get('unix_time', 0))
    sensor_data = most_recent.to_dict()
    print(f"Processing sensor data: {sensor_data}")
    
    tolerances = get_tolerances()
    if not tolerances:
        print("No tolerances defined")
        return

    alerts = check_tolerances(sensor_data, tolerances)
    if alerts:
        recipients = get_notification_recipients()
        message = "Aquaponics Alert:\n" + "\n".join(alerts[:2])
        
        for i, recipient in enumerate(recipients):
            if i > 0:  # Add delay between recipients
                time.sleep(2)
            print(f"\nSending alert to {recipient['number']}")
            send_sms_via_email(recipient['number'], message, recipient.get('carrier'))
    else:
        print("No alerts generated for this update")

def listen_for_sensor_updates():
    """
    Set up a real-time listener for sensor data updates.
    """
    stats_ref = db.collection('stats')
    query = stats_ref.order_by("unix_time", direction=firestore.Query.DESCENDING).limit(1)
    query.on_snapshot(handle_sensor_update)
    print("Listener set up successfully")

def add_test_data(db):
    """
    Add test data to Firestore to simulate out-of-range readings.
    """
    test_data = {
        "TDS": 1000,
        "air_temp": 35,
        "distance": 50,
        "humidity": 80,
        "pH": 7,
        "water_temp": 25,
        "unix_time": int(time.time())
    }
    db.collection('stats').add(test_data)
    print(f"Test data added: {test_data}")

def send_test_sms():
    """
    Send a test message to all recipients.
    """
    recipients = get_notification_recipients()
    test_message = "Aquaponics test message"
    
    for recipient in recipients:
        print(f"\nTrying test message to {recipient['number']}")
        success = send_sms_via_email(recipient['number'], test_message, recipient.get('carrier'))
        print(f"Test message {'sent' if success else 'failed'}\n")

def main():
    """
    Main function to start the real-time listener and run tests.
    """
    print("Starting real-time monitoring of sensor data...")
    
    # Verify email configuration
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
        print("Email credentials verified successfully")
    except Exception as e:
        print(f"Error verifying email credentials: {str(e)}")
        return

    # First set up the listener
    listen_for_sensor_updates()
    
    # Add test data first
    print("\n--- Adding Test Data ---")
    time.sleep(2)  # Short delay to ensure listener is ready
    add_test_data(db)
    
    # Then send a test message
    print("\n--- Sending Test Message ---")
    time.sleep(2)  # Short delay to let test data process
    test_message = "Aquaponics System Test Message"
    recipients = get_notification_recipients()
    for recipient in recipients:
        print(f"\nSending test to {recipient['number']}")
        send_sms_via_email(recipient['number'], test_message, recipient.get('carrier'))

    # Keep the main thread alive
    try:
        while True:
            time.sleep(10)
            print("Still monitoring...")
    except KeyboardInterrupt:
        print("Stopping the monitoring process...")

if __name__ == "__main__":
    main()