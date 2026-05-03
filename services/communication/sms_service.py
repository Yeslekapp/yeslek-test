# ---------------------------
# SMS Service (Telnyx API direct)
# ---------------------------

import os
import requests


class SMSService:

    @staticmethod
    def send_sms(to_number: str, message: str) -> dict:

        api_key = os.getenv("TELNYX_API_KEY")
        sender = os.getenv("TELNYX_SMS_FROM")

        if not api_key:
            raise RuntimeError("TELNYX_API_KEY not configured")

        if not sender:
            raise RuntimeError("TELNYX_SMS_FROM not configured")

        if not to_number.startswith("+"):
            raise ValueError("Invalid phone format")

        print("SENDING SMS TO:", to_number)

        url = "https://api.telnyx.com/v2/messages"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": sender,
            "to": to_number,
            "text": message
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)

            print("TELNYX RAW RESPONSE:", response.text)

            data = response.json()

            return {
                "success": response.status_code in [200, 201],
                "data": data
            }

        except Exception as e:
            print("TELNYX ERROR:", str(e))
            return {
                "success": False,
                "error": str(e)
            }