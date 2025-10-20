from flask import Flask, request, jsonify
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import requests

app = Flask(__name__)

# ==============================
# CONFIGURATION
# ==============================
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "KARATEB0T")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
SHEET_NAME = os.environ.get("SHEET_NAME", "Subscribers")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")  # Meta WhatsApp phone ID

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ==============================
# HELPER FUNCTIONS
# ==============================

def add_lead_to_sheet(name, contact, intent, whatsapp_id):
    """Add user entry to Google Sheet"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([timestamp, name, contact, whatsapp_id, intent])

def send_whatsapp_message(to, message, buttons=None):
    """Send WhatsApp message via Meta API with optional interactive buttons"""
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to
    }

    if buttons:
        payload.update({
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": message},
                "action": {"buttons": [{"type": "reply", "reply": {"id": b["id"], "title": b["title"]}} for b in buttons]}
            }
        })
    else:
        payload.update({"type": "text", "text": {"body": message}})

    requests.post(url, headers=headers, json=payload)

def get_keywords_response(message):
    """Return keyword-based automated responses with multiple phrasings"""
    msg = message.lower()

    if any(k in msg for k in ["about", "who are you", "your centre"]):
        return "🥋 *About Us:*\nWe are Oman Karate Centre, building discipline, strength, and confidence."

    elif any(k in msg for k in ["program", "classes", "courses"]):
        return "📅 *Programs Offered:*\n- Kids Karate (Age 5+)\n- Teens & Adults Karate\n- Self Defense\n- Black Belt Training"

    elif any(k in msg for k in ["schedule", "timing", "class time"]):
        return "🕒 *Class Schedule:*\nWeekdays: 5 PM - 8 PM\nWeekends: 10 AM - 1 PM"

    elif any(k in msg for k in ["membership", "fees", "price", "cost"]):
        return "💰 *Membership Info:*\nRegistration Fee: 10 OMR\nMonthly Fee: 25 OMR\nDiscounts available!"

    elif any(k in msg for k in ["contact", "call", "reach", "whatsapp"]):
        return "📞 *Contact Us:*\nPhone: +968 9123 4567\nEmail: oman.karate.centre@gmail.com"

    elif any(k in msg for k in ["location", "where", "address", "place"]):
        return "📍 *Location:*\nOman Karate Centre\nNear Sultan Qaboos Sports Complex, Muscat."

    elif any(k in msg for k in ["offers", "discount", "promo"]):
        return "🎁 *Current Offers:*\nRegister now to get 10% off your first month!\nReply YES to claim."

    elif any(k in msg for k in ["events", "seminar", "camp", "tournament"]):
        return "📣 *Upcoming Events:*\n- Karate Summer Camp: 25th June\n- Annual Karate Tournament: 15th July"

    return None

# ==============================
# WEBHOOK ENDPOINTS
# ==============================

@app.route("/webhook", methods=["GET"])
def verify():
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
        interactive = message.get("interactive", {})
    except KeyError:
        return jsonify({"status": "ignored"})

    # Check if interactive button pressed
    if interactive:
        reply_id = interactive.get("button_reply", {}).get("id")
        if reply_id == "register_now":
            send_whatsapp_message(phone_number, "✅ Please reply with your *Name* and *Phone Number* in any format. We'll register you now.")
        elif reply_id == "register_later":
            add_lead_to_sheet("Pending", "Pending", "Register Later", phone_number)
            send_whatsapp_message(phone_number, "⏰ You will be reminded about our next session soon!")
        return jsonify({"status": "button_handled"})

    # Check keyword responses
    response = get_keywords_response(text)
    if response:
        send_whatsapp_message(phone_number, response)
        return jsonify({"status": "keyword_response_sent"})

    # Check registration entry
    if "|" in text or any(char.isdigit() for char in text):
        try:
            # Simple split: assume Name | Contact or just Name Contact
            parts = [p.strip() for p in text.replace("|", " ").split()]
            name = parts[0]
            contact = parts[-1]
            add_lead_to_sheet(name, contact, "Register Now", phone_number)
            send_whatsapp_message(phone_number, f"✅ Thanks {name}! You are now registered. Our team will contact you shortly.")
            return jsonify({"status": "registered"})
        except Exception:
            send_whatsapp_message(phone_number, "⚠️ Unable to register. Please enter *Name* and *Phone Number* correctly.")

    # If nothing matches, send main menu
    buttons = [
        {"id": "register_now", "title": "Register Now"},
        {"id": "register_later", "title": "Register Later"}
    ]
    menu_text = "👋 Hi! I’m *KarateBot*, your virtual assistant. Choose an option below or type your query:\n- About Us\n- Programs\n- Schedule\n- Membership\n- Contact\n- Location\n- Offers\n- Events"
    send_whatsapp_message(phone_number, menu_text, buttons=buttons)

    return jsonify({"status": "success"})

# ==============================
# DASHBOARD ENDPOINTS
# ==============================

@app.route("/api/leads", methods=["GET"])
def get_leads():
    """Return all leads for dashboard"""
    return jsonify(sheet.get_all_records())

@app.route("/api/broadcast", methods=["POST"])
def broadcast():
    """Send custom message to selected segment"""
    data = request.get_json()
    segment = data.get("segment")  # "register_now" or "register_later"
    message = data.get("message", "")
    records = sheet.get_all_records()
    for row in records:
        if (segment == "register_now" and row["Intent"] == "Register Now") or \
           (segment == "register_later" and row["Intent"] == "Register Later") or \
           segment == "all":
            send_whatsapp_message(row["WhatsApp ID"], message)
    return jsonify({"status": "broadcast_sent"})

# ==============================
# ROOT
# ==============================

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "KarateBot Backend Active", "time": str(datetime.datetime.now())})

# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
