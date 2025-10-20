from flask import Flask, request, jsonify
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import requests
import logging
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ==============================
# CONFIGURATION
# ==============================
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "KARATEB0T")
WHATSAPP_TOKEN = os.environ.get("ACCESS_TOKEN")
SHEET_NAME = os.environ.get("SHEET_NAME", "Subscribers")
WHATSAPP_PHONE_ID = os.environ.get("PHONE_NUMBER_ID")

# Validate required environment variables
missing_vars = []
if not WHATSAPP_TOKEN:
    missing_vars.append("WHATSAPP_TOKEN")
if not WHATSAPP_PHONE_ID:
    missing_vars.append("WHATSAPP_PHONE_ID")
if not os.environ.get("GOOGLE_CREDS_JSON"):
    missing_vars.append("GOOGLE_CREDS_JSON")

if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")

# Google Sheets setup
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    logger.info("Google Sheets initialized successfully")
except Exception as e:
    logger.error(f"Google Sheets initialization failed: {str(e)}")
    sheet = None

# ==============================
# HELPER FUNCTIONS
# ==============================

def add_lead_to_sheet(name, contact, intent, whatsapp_id):
    """Add user entry to Google Sheet"""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, name, contact, whatsapp_id, intent])
        logger.info(f"Added lead to sheet: {name}, {contact}, {intent}")
        return True
    except Exception as e:
        logger.error(f"Failed to add lead to sheet: {str(e)}")
        return False

def send_whatsapp_message(to, message, buttons=None):
    """Send WhatsApp message via Meta API with optional interactive buttons"""
    try:
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

        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Message sent to {to}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send WhatsApp message: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending message: {str(e)}")
        return False

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

def process_webhook_data(webhook_data):
    """Process webhook data in background thread"""
    try:
        logger.info(f"Processing webhook data: {json.dumps(webhook_data, indent=2)}")
        
        # Extract message details
        try:
            message = webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]
            phone_number = message["from"]
            text = message.get("text", {}).get("body", "").strip()
            interactive = message.get("interactive", {})
            logger.info(f"Processing message from {phone_number}: {text}")
        except (KeyError, IndexError) as e:
            logger.warning(f"No message found in webhook: {str(e)}")
            return

        # Check if interactive button pressed
        if interactive:
            reply_id = interactive.get("button_reply", {}).get("id")
            logger.info(f"Button pressed: {reply_id}")
            if reply_id == "register_now":
                send_whatsapp_message(phone_number, "✅ Please reply with your *Name* and *Phone Number* in any format. We'll register you now.")
            elif reply_id == "register_later":
                if sheet:
                    add_lead_to_sheet("Pending", "Pending", "Register Later", phone_number)
                send_whatsapp_message(phone_number, "⏰ You will be reminded about our next session soon!")
            return

        # Check keyword responses
        response = get_keywords_response(text)
        if response:
            send_whatsapp_message(phone_number, response)
            return

        # Check registration entry
        if text and ("|" in text or any(char.isdigit() for char in text)):
            try:
                # Simple split: assume Name | Contact or just Name Contact
                parts = [p.strip() for p in text.replace("|", " ").split()]
                if len(parts) >= 2:
                    name = parts[0]
                    contact = parts[-1]
                    if sheet:
                        add_lead_to_sheet(name, contact, "Register Now", phone_number)
                    send_whatsapp_message(phone_number, f"✅ Thanks {name}! You are now registered. Our team will contact you shortly.")
                    return
                else:
                    raise ValueError("Not enough parts")
            except Exception as e:
                logger.error(f"Registration parsing error: {str(e)}")
                send_whatsapp_message(phone_number, "⚠️ Unable to register. Please enter *Name* and *Phone Number* correctly.")
                return

        # If nothing matches, send main menu
        buttons = [
            {"id": "register_now", "title": "Register Now"},
            {"id": "register_later", "title": "Register Later"}
        ]
        menu_text = "👋 Hi! I'm *KarateBot*, your virtual assistant. Choose an option below or type your query:\n- About Us\n- Programs\n- Schedule\n- Membership\n- Contact\n- Location\n- Offers\n- Events"
        send_whatsapp_message(phone_number, menu_text, buttons=buttons)

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")

# ==============================
# WEBHOOK ENDPOINTS
# ==============================

@app.route("/webhook", methods=["GET"])
def verify():
    """Webhook verification for Meta"""
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    logger.info(f"Verification attempt with token: {token}")
    if token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return challenge
    logger.warning("Webhook verification failed: token mismatch")
    return "Verification token mismatch", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming WhatsApp messages"""
    logger.info("Received webhook POST request")
    
    try:
        # Get the JSON data while still in request context
        webhook_data = request.get_json()
        
        # Process in background thread to avoid timeout
        Thread(target=process_webhook_data, args=(webhook_data,)).start()
        
        logger.info("Webhook processing started in background")
        return jsonify({"status": "processing"}), 200
        
    except Exception as e:
        logger.error(f"Error handling webhook request: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================
# DASHBOARD ENDPOINTS
# ==============================

@app.route("/api/leads", methods=["GET"])
def get_leads():
    """Return all leads for dashboard"""
    try:
        if sheet:
            return jsonify(sheet.get_all_records())
        else:
            return jsonify({"error": "Google Sheets not available"}), 500
    except Exception as e:
        logger.error(f"Error getting leads: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/broadcast", methods=["POST"])
def broadcast():
    """Send custom message to selected segment"""
    try:
        data = request.get_json()
        segment = data.get("segment")  # "register_now" or "register_later"
        message = data.get("message", "")
        
        if not sheet:
            return jsonify({"error": "Google Sheets not available"}), 500
            
        records = sheet.get_all_records()
        for row in records:
            if (segment == "register_now" and row["Intent"] == "Register Now") or \
               (segment == "register_later" and row["Intent"] == "Register Later") or \
               segment == "all":
                send_whatsapp_message(row["WhatsApp ID"], message)
        return jsonify({"status": "broadcast_sent"})
    except Exception as e:
        logger.error(f"Error in broadcast: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ==============================
# ROOT
# ==============================

@app.route("/", methods=["GET"])
def home():
    status = {
        "status": "KarateBot Backend Active", 
        "time": str(datetime.datetime.now()),
        "whatsapp_token_set": bool(WHATSAPP_TOKEN),
        "phone_id_set": bool(WHATSAPP_PHONE_ID),
        "sheets_available": sheet is not None
    }
    return jsonify(status)

# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)