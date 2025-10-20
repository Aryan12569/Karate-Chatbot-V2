from flask import Flask, request, jsonify
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import requests
import logging

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
        
        if buttons:
            # Interactive message with buttons
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": message
                    },
                    "action": {
                        "buttons": buttons
                    }
                }
            }
        else:
            # Simple text message
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {
                    "body": message
                }
            }

        logger.info(f"Sending WhatsApp message to {to}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"WhatsApp API error {response.status_code}: {response.text}")
            return False
            
        response_data = response.json()
        logger.info(f"WhatsApp API response: {response_data}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {str(e)}")
        return False

def get_keywords_response(message):
    """Return keyword-based automated responses (fallback)"""
    msg = message.lower()

    if any(k in msg for k in ["about", "who are you", "your centre", "about us"]):
        return "🥋 *About Us:*\nWe are Oman Karate Centre, building discipline, strength, and confidence through traditional karate training."

    elif any(k in msg for k in ["program", "classes", "courses", "programs"]):
        return "💪 *Programs Offered:*\n• Kids Karate (Age 5-12)\n• Teens Karate (13-17)\n• Adults Karate (18+)\n• Self Defense Classes\n• Black Belt Training\n• Competitive Training"

    elif any(k in msg for k in ["schedule", "timing", "class time", "hours"]):
        return "🕒 *Class Schedule:*\n• Monday-Friday: 4 PM - 8 PM\n• Saturday: 9 AM - 1 PM\n• Sunday: Closed\n\n*Weekend Batches:*\n• Saturday: 9 AM - 1 PM"

    elif any(k in msg for k in ["membership", "fees", "price", "cost", "fee"]):
        return "💰 *Membership Info:*\n• Registration Fee: 10 OMR\n• Monthly Fee: 25 OMR\n• 3-Month Package: 65 OMR (Save 10 OMR)\n• Family Discounts Available!\n• Free Trial Class Available"

    elif any(k in msg for k in ["location", "where", "address", "place"]):
        return "📍 *Location:*\nOman Karate Centre\nNear Sultan Qaboos Sports Complex\nMuscat, Oman\n\nhttps://maps.google.com/?q=Oman+Karate+Centre+Muscat"

    elif any(k in msg for k in ["contact", "call", "reach", "whatsapp", "phone"]):
        return "☎️ *Contact Us:*\n• Phone: +968 9123 4567\n• WhatsApp: +968 9123 4567\n• Email: oman.karate.centre@gmail.com\n• Instagram: @OmanKarateCentre"

    elif any(k in msg for k in ["offers", "discount", "promo", "offer"]):
        return "🎁 *Current Offers:*\nNo offers currently. Stay tuned for exciting promotions and discounts!"

    elif any(k in msg for k in ["events", "seminar", "camp", "tournament", "competition"]):
        return "🗓️ *Upcoming Events:*\nUpcoming events will be shared soon! Follow us for updates."

    elif any(k in msg for k in ["register", "join", "sign up", "enroll"]):
        return None  # This will be handled by the calling function

    return None

def send_main_menu(to):
    """Send the main interactive menu with buttons"""
    buttons = [
        {
            "type": "reply",
            "reply": {"id": "about_us", "title": "🥋 About Us"}
        },
        {
            "type": "reply", 
            "reply": {"id": "programs", "title": "💪 Programs"}
        },
        {
            "type": "reply",
            "reply": {"id": "schedule", "title": "🕒 Schedule"}
        },
        {
            "type": "reply",
            "reply": {"id": "membership", "title": "💰 Membership"}
        },
        {
            "type": "reply",
            "reply": {"id": "location", "title": "📍 Location"}
        },
        {
            "type": "reply",
            "reply": {"id": "contact", "title": "☎️ Contact"}
        },
        {
            "type": "reply",
            "reply": {"id": "offers", "title": "🎁 Offers"}
        },
        {
            "type": "reply",
            "reply": {"id": "events", "title": "🗓️ Events"}
        },
        {
            "type": "reply",
            "reply": {"id": "register", "title": "📝 Register"}
        }
    ]
    
    welcome_message = """👋 *Welcome to Oman Karate Centre!*

I'm your virtual assistant. Choose an option below to get information:"""
    
    send_whatsapp_message(to, welcome_message, buttons)

def send_registration_menu(to):
    """Send registration options with buttons"""
    buttons = [
        {
            "type": "reply",
            "reply": {"id": "register_now", "title": "✅ Register Now"}
        },
        {
            "type": "reply",
            "reply": {"id": "register_later", "title": "⏰ Register Later"}
        }
    ]
    
    message = "📝 *Registration Options:*\n\nPlease choose your preferred registration option:"
    
    send_whatsapp_message(to, message, buttons)

def handle_button_click(button_id, phone_number):
    """Handle button click responses"""
    responses = {
        "about_us": "🥋 *About Us:*\nWe are Oman Karate Centre, building discipline, strength, and confidence through traditional karate training.",
        
        "programs": "💪 *Programs Offered:*\n• Kids Karate (Age 5-12)\n• Teens Karate (13-17)\n• Adults Karate (18+)\n• Self Defense Classes\n• Black Belt Training\n• Competitive Training",
        
        "schedule": "🕒 *Class Schedule:*\n• Monday-Friday: 4 PM - 8 PM\n• Saturday: 9 AM - 1 PM\n• Sunday: Closed\n\n*Weekend Batches:*\n• Saturday: 9 AM - 1 PM",
        
        "membership": "💰 *Membership Info:*\n• Registration Fee: 10 OMR\n• Monthly Fee: 25 OMR\n• 3-Month Package: 65 OMR (Save 10 OMR)\n• Family Discounts Available!\n• Free Trial Class Available",
        
        "location": "📍 *Location:*\nOman Karate Centre\nNear Sultan Qaboos Sports Complex\nMuscat, Oman\n\nhttps://maps.google.com/?q=Oman+Karate+Centre+Muscat",
        
        "contact": "☎️ *Contact Us:*\n• Phone: +968 9123 4567\n• WhatsApp: +968 9123 4567\n• Email: oman.karate.centre@gmail.com\n• Instagram: @OmanKarateCentre",
        
        "offers": "🎁 *Current Offers:*\nNo offers currently. Stay tuned for exciting promotions and discounts!",
        
        "events": "🗓️ *Upcoming Events:*\nUpcoming events will be shared soon! Follow us for updates.",
        
        "register": lambda: send_registration_menu(phone_number),
        
        "register_now": "✅ *Registration - Step 1:*\nPlease reply with your *Full Name* and *Phone Number* in this format:\n\nJohn Smith | 91234567\n\nOr simply: John Smith 91234567",
        
        "register_later": "⏰ *Registration Later:*\nWe've noted your interest! We'll remind you about our next session soon. Feel free to contact us anytime at +968 9123 4567."
    }
    
    response = responses.get(button_id)
    
    if callable(response):
        response()  # Execute the function (for register button)
        return None
    elif response:
        send_whatsapp_message(phone_number, response)
        return response
    else:
        send_whatsapp_message(phone_number, "Sorry, I didn't understand that option. Please try again.")
        return None

# ==============================
# CORS HEADERS (Manual Implementation)
# ==============================

@app.after_request
def after_request(response):
    """Add CORS headers to all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

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
    else:
        logger.warning("Webhook verification failed: token mismatch")
        return "Verification token mismatch", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming WhatsApp messages and button clicks"""
    try:
        data = request.get_json()
        logger.info(f"Received webhook data: {json.dumps(data)}")
        
        # Extract message details
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return jsonify({"status": "no_message"})
            
        message = messages[0]
        phone_number = message["from"]
        
        # Check if it's an interactive button click
        if "interactive" in message:
            interactive_data = message["interactive"]
            if "button_reply" in interactive_data:
                button_id = interactive_data["button_reply"]["id"]
                logger.info(f"Button clicked: {button_id} by {phone_number}")
                
                # Handle registration actions
                if button_id == "register_later":
                    if sheet:
                        add_lead_to_sheet("Pending", "Pending", "Register Later", phone_number)
                    send_whatsapp_message(phone_number, "✅ Thank you! We've saved your interest and will contact you soon about our next session.")
                    return jsonify({"status": "register_later_saved"})
                
                # Handle other button clicks
                handle_button_click(button_id, phone_number)
                return jsonify({"status": "button_handled"})
        
        # Handle text messages (fallback)
        if "text" in message:
            text = message["text"]["body"].strip()
            logger.info(f"Text message received: {text} from {phone_number}")
            
            # Check for greeting or any message to show main menu
            if text.lower() in ["hi", "hello", "hey", "start", "menu"]:
                send_main_menu(phone_number)
                return jsonify({"status": "main_menu_sent"})
            
            # Check for registration data (name and contact)
            if any(char.isdigit() for char in text) and len(text.split()) >= 2:
                try:
                    # Parse name and contact (supports "Name | Contact" or "Name Contact")
                    parts = [p.strip() for p in text.replace("|", " ").split() if p.strip()]
                    if len(parts) >= 2:
                        name = ' '.join(parts[:-1])  # All except last part as name
                        contact = parts[-1]  # Last part as contact
                        
                        if sheet:
                            add_lead_to_sheet(name, contact, "Register Now", phone_number)
                        
                        send_whatsapp_message(phone_number, f"✅ *Registration Successful!*\n\nThank you {name}! You are now registered with Oman Karate Centre.\n\n• Name: {name}\n• Contact: {contact}\n\nOur team will contact you within 24 hours to complete your registration.\n\nFor immediate assistance, call: +968 9123 4567")
                        return jsonify({"status": "registered"})
                    
                except Exception as e:
                    logger.error(f"Registration parsing error: {str(e)}")
                    send_whatsapp_message(phone_number, "⚠️ *Registration Failed*\n\nPlease send your information in this format:\n\n*First Name Last Name | Phone Number*\n\nExample: Ali Ahmed | 91234567")
                    return jsonify({"status": "registration_error"})
            
            # Check for keyword-based responses
            response = get_keywords_response(text)
            if response:
                send_whatsapp_message(phone_number, response)
                return jsonify({"status": "keyword_response_sent"})
            
            # If no specific match, send main menu
            send_main_menu(phone_number)
            return jsonify({"status": "fallback_menu_sent"})
        
        return jsonify({"status": "unhandled_message_type"})
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================
# DASHBOARD ENDPOINTS
# ==============================

@app.route("/api/leads", methods=["GET"])
def get_leads():
    """Return all leads for dashboard"""
    try:
        if sheet:
            # Get all records and filter out empty rows
            all_data = sheet.get_all_records()
            
            # Filter out empty rows and rows with no meaningful data
            valid_leads = []
            for row in all_data:
                # Check if row has at least one non-empty field (excluding timestamp)
                has_data = any([
                    row.get('Name', '').strip(),
                    row.get('Contact', '').strip(), 
                    row.get('WhatsApp ID', '').strip(),
                    row.get('Intent', '').strip()
                ])
                
                if has_data:
                    valid_leads.append(row)
            
            logger.info(f"Returning {len(valid_leads)} valid leads out of {len(all_data)} total rows")
            return jsonify(valid_leads)
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
        segment = data.get("segment", "all")
        message = data.get("message", "")
        
        if not sheet:
            return jsonify({"error": "Google Sheets not available"}), 500
            
        records = sheet.get_all_records()
        sent_count = 0
        
        for row in records:
            if (segment == "all" or
                (segment == "register_now" and row.get("Intent") == "Register Now") or
                (segment == "register_later" and row.get("Intent") == "Register Later")):
                
                whatsapp_id = row.get("WhatsApp ID")
                if whatsapp_id:
                    send_whatsapp_message(whatsapp_id, message)
                    sent_count += 1
        
        return jsonify({"status": "broadcast_sent", "recipients": sent_count})
    except Exception as e:
        logger.error(f"Error in broadcast: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ==============================
# HEALTH CHECK
# ==============================

@app.route("/", methods=["GET"])
def home():
    status = {
        "status": "KarateBot WhatsApp API Active",
        "timestamp": str(datetime.datetime.now()),
        "whatsapp_configured": bool(WHATSAPP_TOKEN and WHATSAPP_PHONE_ID),
        "sheets_available": sheet is not None,
        "interactive_buttons": True
    }
    return jsonify(status)

# ==============================
# RUN APPLICATION
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)