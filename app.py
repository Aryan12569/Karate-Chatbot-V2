from flask import Flask, request, jsonify
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# ----------------------
# Google Sheets Setup
# ----------------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
creds_json = {
    # Paste your google_creds_json here
}
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

SHEET_NAME = "Subscribers"
try:
    sheet = client.open(SHEET_NAME).sheet1
except:
    sheet = client.create(SHEET_NAME).sheet1
    sheet.append_row(["Timestamp", "Name", "Contact", "WhatsApp ID", "Intent"])

# ----------------------
# WhatsApp Bot Utilities
# ----------------------
def send_text_message(wa_id, text):
    """Placeholder function for sending WhatsApp messages via your API."""
    # Integrate with your WhatsApp API here
    print(f"Sent to {wa_id}: {text}")

# ----------------------
# Keyword Responses
# ----------------------
KEYWORDS_RESPONSES = {
    "location": [
        ["where", "location"], ["where", "located"], ["address"], ["gym", "location"]
    ],
    "timings": [
        ["timing"], ["hours"], ["open"], ["close"], ["schedule"]
    ],
    "about": [
        ["about"], ["information"], ["info"], ["karate", "info"]
    ],
    "programs": [
        ["program"], ["classes"], ["courses"]
    ],
    "membership": [
        ["membership"], ["fees"], ["price"], ["cost"]
    ],
    "contact": [
        ["contact"], ["phone"], ["number"], ["reach"]
    ],
    "schedule": [
        ["schedule"], ["class", "time"], ["class", "schedule"]
    ]
}

RESPONSES = {
    "location": "Our Karate Center is located at 123 Karate St, Muscat, Oman.",
    "timings": "We are open Mon-Sat from 6:00 AM to 9:00 PM.",
    "about": "KarateBot is your smart assistant for all our karate classes and programs.",
    "programs": "We offer Kids, Teens, and Adults karate programs. Visit our schedule for details.",
    "membership": "Monthly membership is 25 OMR. Discounts available for siblings and referrals.",
    "contact": "You can reach us at +968 1234 5678 or WhatsApp us directly.",
    "schedule": "Classes are scheduled in the mornings (6-8 AM) and evenings (6-9 PM)."
}

def get_response_from_message(message_text):
    message_lower = message_text.lower()
    for key, keyword_lists in KEYWORDS_RESPONSES.items():
        for keywords in keyword_lists:
            if all(k in message_lower for k in keywords):
                return RESPONSES[key]
    return None

# ----------------------
# WhatsApp Webhook Endpoint
# ----------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    wa_id = data.get("wa_id")
    message = data.get("message", "").strip()
    buttons_payload = data.get("button_payload", None)

    # Check if it's a button payload
    if buttons_payload:
        if buttons_payload == "register_now":
            send_text_message(wa_id, "Please provide your Name and Contact number. We'll record your registration now.")
            return jsonify({"status": "ok"})
        elif buttons_payload == "register_later":
            sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                              "-", "-", wa_id, "Register Later"])
            send_text_message(wa_id, "No worries! We will send you special offers and updates. Contact us anytime.")
            return jsonify({"status": "ok"})

    # Check for registration format
    if "|" in message or " " in message:
        # Extract Name and Contact
        parts = message.replace("|", " ").split()
        name = " ".join(parts[:-1])
        contact = parts[-1]
        sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                          name, contact, wa_id, "Register Now"])
        send_text_message(wa_id, f"Thank you {name}! Your registration is recorded. Contact +968 1234 5678 for further info.")
        return jsonify({"status": "registered"})

    # Keyword-based response
    response = get_response_from_message(message)
    if response:
        send_text_message(wa_id, response)
    else:
        # Send default options menu
        menu = ("Hello! Please choose an option:\n"
                "1. About Us\n2. Programs\n3. Class Schedule\n"
                "4. Membership\n5. Contact\n6. Location\n"
                "Or ask a question and I'll try to answer.")
        send_text_message(wa_id, menu)
    return jsonify({"status": "ok"})

# ----------------------
# Dashboard API Endpoints
# ----------------------
@app.route("/api/leads", methods=["GET"])
def api_leads():
    all_data = sheet.get_all_records()
    return jsonify(all_data)

@app.route("/api/broadcast", methods=["POST"])
def api_broadcast():
    data = request.get_json()
    segment = data.get("segment", "all")
    message = data.get("message", "")
    all_data = sheet.get_all_records()
    for row in all_data:
        intent = row.get("Intent", "")
        if segment == "all" or (segment=="register_now" and intent=="Register Now") or (segment=="register_later" and intent=="Register Later"):
            send_text_message(row.get("WhatsApp ID", ""), message)
    return jsonify({"status": "Broadcast sent"})

# ----------------------
# Run Flask App
# ----------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
