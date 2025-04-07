import firebase_admin
from firebase_admin import credentials, db

# Path to your JSON file
cred = credentials.Certificate("C:/Barnaba/Telegram Bot/firebase_config.json")

# Initialize with your actual URL
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://telegrambotdb-1895e-default-rtdb.firebaseio.com/"
})
