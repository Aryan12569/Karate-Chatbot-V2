import os
import json
import requests
from flask import Flask, request, jsonify
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# -----------------------
# WhatsApp & Admin Config
# -----------------------
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
ADMIN_WA_ID = os.environ.get("ADMIN_WA_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "KARATEB0T")

# -----------------------
# Google Sheets Setup
# -----------------------
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON")
SHEET_NAME = os.environ.get("SHEET_NAME", "KarateBotLeads")

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(GOOGLE_CREDS_JSON), scope)
gc = gspread.authorize(creds)
sheet = gc.open(SHEET_NAME).sheet1

# -----------------------
# Helpers
# -----------------------
def send_request(url, payload):
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        return resp
    except Exception as e:
        print("[whatsapp] request error:", e)
        return None

def send_text_message(to, text):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    payload = {"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text}}
    send_request(url, payload)

def save_to_sheet(wa_id, name, contact, intent):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet.append_row([timestamp, name, contact, wa_id, intent])

# -----------------------
# Webhook verification
# -----------------------
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

# -----------------------
# Incoming webhook
# -----------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            messages = change.get("value", {}).get("messages", [])
            if messages:
                for msg in messages:
                    wa_id = msg.get("from")
                    mtype = msg.get("type")
                    if mtype == "text":
                        text = msg.get("text", {}).get("body", "").lower()
                        handle_text(wa_id, text)
                    elif mtype == "interactive":
                        interactive = msg.get("interactive", {})
                        itype = interactive.get("type")
                        if itype in ["button_reply", "list_reply"]:
                            reply_id = interactive.get(itype, {}).get("id")
                            handle_interactive(wa_id, reply_id)
    return jsonify({"status": "ok"}), 200

# -----------------------
# Process Text & Interactive Messages
# -----------------------
def handle_text(wa_id, text):
    if any(k in text for k in ["hi","hello","menu"]):
        send_main_menu(wa_id)
    elif "offer" in text:
        send_offer_demo(wa_id)
    elif "event" in text:
        send_event_demo(wa_id)
    elif any(k in text for k in ["signup","register","book"]):
        send_text_message(wa_id,"Thank you! Our team will contact you shortly.")
    else:
        # Keyword based auto-answer
        if "location" in text:
            send_text_message(wa_id,"📍 We are at Al Maabelah. Maps: https://maps.app.goo.gl/jcdQoP7ZnuPot1wK9")
        elif "timing" in text or "hours" in text:
            send_text_message(wa_id,"🕘 Open Mon-Fri: 5PM-9PM, Sat: 10AM-12PM, Sun: Closed")
        elif "fees" in text or "price" in text:
            send_text_message(wa_id,"💳 Monthly: 15 OMR, Quarterly: 40 OMR, Yearly: 140 OMR")
        else:
            send_text_message(wa_id,"Thank you for contacting International Karate Centre – Al Maabelah.\nType *menu* to view options.")

def handle_interactive(wa_id, reply_id):
    mapping = {
        "register_now": lambda: register_user(wa_id, "now"),
        "register_later": lambda: register_user(wa_id, "later"),
        "offers": lambda: send_offer_demo(wa_id),
        "events": lambda: send_event_demo(wa_id)
    }
    if reply_id in mapping:
        mapping[reply_id]()

def register_user(wa_id, intent_type):
    # Ask for name & contact for Register Now
    if intent_type == "now":
        send_text_message(wa_id,"Please provide your full name and contact number in this format:\nName | Contact")
    else:
        # Register Later
        save_to_sheet(wa_id,"","", "Register Later")
        send_text_message(wa_id,"You are registered for future offers! We'll notify you soon.")

# -----------------------
# Send Interactive Menus
# -----------------------
def send_main_menu(wa_id):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text","text":"🥋 International Karate Centre – Al Maabelah"},
            "body": {"text":"Welcome. Select an option."},
            "footer": {"text":"Excellence • Discipline • Respect"},
            "action": {
                "button": "View Options",
                "sections": [{
                    "title":"Main Menu",
                    "rows":[
                        {"id":"offers","title":"🏷 Offers","description":"Current promotions"},
                        {"id":"events","title":"🎟 Events","description":"Upcoming tournaments"},
                        {"id":"register_now","title":"📝 Register Now","description":"Provide details now"},
                        {"id":"register_later","title":"⏰ Register Later","description":"Receive offers later"}
                    ]
                }]
            }
        }
    }
    send_request(url, payload)

def send_offer_demo(wa_id):
    send_text_message(wa_id,"🏷 Enroll before 15 Oct 2025: 25% off first 3 months + free uniform!")

def send_event_demo(wa_id):
    send_text_message(wa_id,"🎟 Inter-Dojo Championship on 20 Oct 2025. Categories: Kids/Juniors/Adults.")

# -----------------------
# Run Flask
# -----------------------
if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)

@app.route("/api/leads", methods=["GET"])
def get_leads():
    records = sheet.get_all_records()
    return jsonify(records)

@app.route("/api/broadcast", methods=["POST"])
def broadcast():
    data = request.get_json()
    segment = data.get("segment")
    message = data.get("message")

    leads = sheet.get_all_records()
    for lead in leads:
        if segment == "All" or lead["Intent"] == segment:
            send_text_message(lead["WhatsApp ID"], message)
    return jsonify({"status": "success"})

