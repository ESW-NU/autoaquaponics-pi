import os
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
cred = credentials.Certificate(service_account_path)
firebase_admin.initialize_app(cred)
db = firestore.client()