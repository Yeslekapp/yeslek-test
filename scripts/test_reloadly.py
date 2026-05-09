# ---------------------------
# scripts/test_reloadly.py
# ---------------------------

import sys
from pathlib import Path

import requests

# ---------------------------
# Project root
# ---------------------------

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# ---------------------------
# Reloadly imports
# ---------------------------

from services.reloadly.auth_service import get_reloadly_token

# ---------------------------
# Test operator
# ---------------------------

OPERATOR_ID = 1249

# ---------------------------
# Token
# ---------------------------

token = get_reloadly_token()

if not token:
    raise RuntimeError("Reloadly token not found")

# ---------------------------
# Request
# ---------------------------

url = f"https://topups.reloadly.com/operators/{OPERATOR_ID}"

headers = {
    "Accept": "application/com.reloadly.topups-v1+json",
    "Authorization": f"Bearer {token}",
}

# ---------------------------
# API call
# ---------------------------

response = requests.get(
    url,
    headers=headers,
    timeout=20,
)

# ---------------------------
# Output
# ---------------------------

print("\n==============================")
print("RELOADLY TEST")
print("==============================")

print("STATUS:", response.status_code)

try:
    data = response.json()
except Exception:
    data = response.text

print("\nRESPONSE:")
print(data)

# ---------------------------
# Fixed amounts
# ---------------------------

if isinstance(data, dict):

    fixed_amounts = data.get("fixedAmounts") or []
    descriptions = data.get("fixedAmountsDescriptions") or {}

    print("\n==============================")
    print("FORFAITS")
    print("==============================")

    if not fixed_amounts:
        print("Aucun forfait trouvé")

    for amount in fixed_amounts:

        desc = (
            descriptions.get(str(amount))
            or descriptions.get(f"{float(amount):.2f}")
            or ""
        )

        print(f"{amount} -> {desc}")