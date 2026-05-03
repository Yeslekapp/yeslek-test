# ---------------------------
# Telnyx Service
# ---------------------------

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
TELNYX_PHONE_NUMBER = os.getenv("TELNYX_PHONE_NUMBER")


def send_sms(to_number: str, message: str):
    url = "https://api.telnyx.com/v2/messages"

    headers = {
        "Authorization": f"Bearer {TELNYX_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "from": TELNYX_PHONE_NUMBER,
        "to": to_number,
        "text": message,
    }

    response = requests.post(url, json=payload, headers=headers)

    return response.json()