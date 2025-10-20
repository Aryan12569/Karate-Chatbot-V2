from flask import Flask, request, jsonify
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

app = Flask(__name__)

# ==============================
# CONFIGURATION
# ==============================
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "KARATEB0T")
WHATSAPP_TOKEN = os.environ.get("ACCESS_TOKEN")
SHEET_NAME = os.environ.get("SHEET_NAME", "Subscribers")

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1


# ==============================
# HELPER FUNCTIONS
# ==============================

def add_lead_to_sheet(name, contact, intent):
    """Add user entry to Google Sheet"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([timestamp, name, contact, intent])


def get_keywords_response(message):
    """Return keyword-based automated responses"""
    msg = message.lower()

    if any(k in msg for k in ["about", "who are you", "your centre"]):
        return "🥋 *About Us:*\nWe are Oman Karate Centre, dedicated to building discipline, strength, and confidence through traditional karate training."

    elif any(k in msg for k in ["program", "classes", "courses"]):
        return "📅 *Programs Offered:*\n- Kids Karate (Age 5+)\n- Teens & Adults Karate\n- Self Defense Classes\n- Black Belt Training"

    elif any(k in msg for k in ["schedule", "timing", "class time"]):
        return "🕒 *Class Schedule:*\nWeekdays: 5 PM - 8 PM\nWeekends: 10 AM - 1 PM"

    elif any(k in msg for k in ["membership", "fees", "price", "cost"]):
        return "💰 *Membership Info:*\nRegistration Fee: 10 OMR\nMonthly Fee: 25 OMR\nFamily & group discounts available!"

    elif any(k in msg for k in ["contact", "call", "reach", "whatsapp"]):
        return "📞 *Contact Us:*\nPhone: +968 9123 4567\nEmail: oman.karate.centre@gmail.com"

    elif any(k in msg for k in ["location", "where", "address", "place"]):
        return "📍 *Location:*\nOman Karate Centre\nNear Sultan Qaboos Sports Complex, Muscat."

    elif "register now" in msg:
        return "✅ Great! Please reply with your *Name* and *Phone Number* in this format:\n\nName | Contact\nExample: Ahmed | +96891234567"

    elif "register later" in msg:
        return "⏰ No problem! We’ll remind you about our next session later. Thank you!"

    return None


# ==============================
# WHATSAPP WEBHOOK ENDPOINTS
# ==============================

@app.route("/webhook", methods=["GET"])
def verify_token():
    """Webhook verification for Meta"""
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Verification token mismatch", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming WhatsApp messages"""
    data = request.get_json()

    try:
        message = data["entry"][0]["changes"][0]["value"]["messages"][0]
        phone_number = message["from"]
        text = message.get("text", {}).get("body", "").strip()
    except KeyError:
        return jsonify({"status": "ignored"})

    response = get_keywords_response(text)

    if response:
        send_whatsapp_message(phone_number, response)

    elif "|" in text:
        try:
            name, contact = [x.strip() for x in text.split("|")]
            add_lead_to_sheet(name, contact, "Register Now")
            send_whatsapp_message(phone_number, f"✅ Thanks {name}! You’ve been registered successfully.\nWe’ll contact you soon.")
        except Exception as e:
            send_whatsapp_message(phone_number, "⚠️ Please enter details correctly.\nExample: Ahmed | +96891234567")

    else:
        send_whatsapp_message(phone_number, "👋 Hi! I’m *KarateBot*, your virtual assistant.\nType any of the following:\n- About Us\n- Programs\n- Schedule\n- Membership\n- Contact\n- Location\nOr type *Register Now* to join our classes!")

    return jsonify({"status": "success"})


def send_whatsapp_message(to, message):
    """Send WhatsApp message via Meta API"""
    import requests
    url = f"https://graph.facebook.com/v17.0/{os.environ.get('PHONE_NUMBER_ID')}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    requests.post(url, headers=headers, json=payload)


# ==============================
# DASHBOARD ENDPOINT
# ==============================

@app.route("/api/leads", methods=["GET"])
def get_leads():
    """Return all leads for the dashboard"""
    data = sheet.get_all_records()
    return jsonify(data)


# ==============================
# ROOT ENDPOINT
# ==============================

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "KarateBot Backend Active", "time": str(datetime.datetime.now())})


# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
