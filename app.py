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
            # Interactive message with buttons (MAX 3 BUTTONS ALLOWED)
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
                        "buttons": buttons[:3]  # Only take first 3 buttons max
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
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"WhatsApp API error {response.status_code}: {response.text}")
            return False
            
        logger.info(f"WhatsApp message sent successfully to {to}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {str(e)}")
        return False

def send_welcome_message(to):
    """Send initial welcome message with ONE Get Started button"""
    buttons = [
        {
            "type": "reply",
            "reply": {"id": "get_started", "title": "🚀 Get Started"}
        }
    ]
    
    welcome_message = """👋 *Welcome to Oman Karate Centre!*

I'm your virtual assistant. Ready to begin your martial arts journey?"""
    
    send_whatsapp_message(to, welcome_message, buttons)

def send_main_menu(to):
    """Send the main interactive menu with 3 buttons (WhatsApp limit)"""
    buttons = [
        {
            "type": "reply",
            "reply": {"id": "about_programs", "title": "🥋 About & Programs"}
        },
        {
            "type": "reply", 
            "reply": {"id": "schedule_fees", "title": "🕒 Schedule & Fees"}
        },
        {
            "type": "reply",
            "reply": {"id": "register_contact", "title": "📝 Register Now"}
        }
    ]
    
    menu_message = """*KarateBot Main Menu*

Choose an option to learn more:"""
    
    send_whatsapp_message(to, menu_message, buttons)

def send_secondary_menu(to):
    """Send secondary menu with more options"""
    buttons = [
        {
            "type": "reply",
            "reply": {"id": "location", "title": "📍 Location"}
        },
        {
            "type": "reply",
            "reply": {"id": "contact_info", "title": "☎️ Contact"}
        },
        {
            "type": "reply",
            "reply": {"id": "back_to_main", "title": "🔙 Main Menu"}
        }
    ]
    
    menu_message = """*More Options*

What would you like to know?"""
    
    send_whatsapp_message(to, menu_message, buttons)

def send_registration_menu(to):
    """Send registration options with 2 buttons"""
    buttons = [
        {
            "type": "reply",
            "reply": {"id": "register_now", "title": "✅ Register Now"}
        },
        {
            "type": "reply",
            "reply": {"id": "register_later", "title": "⏰ Later"}
        }
    ]
    
    message = "📝 *Registration Options*\n\nReady to join our karate family?"
    
    send_whatsapp_message(to, message, buttons)

def handle_button_click(button_id, phone_number):
    """Handle button click responses"""
    responses = {
        # Welcome button
        "get_started": lambda: send_main_menu(phone_number),
        
        # Main menu buttons
        "about_programs": """🥋 *About Oman Karate Centre*

We build discipline, strength, and confidence through traditional karate training.

💪 *Programs Offered:*
• Kids Karate (Age 5-12)
• Teens Karate (13-17) 
• Adults Karate (18+)
• Self Defense Classes
• Black Belt Training
• Competitive Training""",

        "schedule_fees": """🕒 *Class Schedule*
• Monday-Friday: 4 PM - 8 PM
• Saturday: 9 AM - 1 PM
• Sunday: Closed

💰 *Membership Info*
• Registration: 10 OMR
• Monthly: 25 OMR  
• 3-Month: 65 OMR (Save 10 OMR)
• Family Discounts Available!
• Free Trial Class!""",

        "register_contact": lambda: send_registration_menu(phone_number),
        
        # Secondary menu buttons
        "location": """📍 *Our Location*

Oman Karate Centre
Near Sultan Qaboos Sports Complex
Muscat, Oman

https://maps.google.com/?q=Oman+Karate+Centre+Muscat""",

        "contact_info": """☎️ *Contact Us*

• Phone: +968 9123 4567
• WhatsApp: +968 9123 4567  
• Email: oman.karate.centre@gmail.com
• Instagram: @OmanKarateCentre""",

        "back_to_main": lambda: send_main_menu(phone_number),
        
        # Registration buttons
        "register_now": "✅ *Registration - Step 1*\n\nPlease send your *Full Name* and *Phone Number*:\n\nExample: Ali Ahmed | 91234567\n\nOr simply: Ali Ahmed 91234567",
        
        "register_later": "⏰ *We'll Be in Touch!*\n\nWe've saved your interest! We'll contact you soon about our next session.\n\nFor immediate questions, call: +968 9123 4567"
    }
    
    response = responses.get(button_id)
    
    if callable(response):
        response()  # Execute the function
        return None
    elif response:
        send_whatsapp_message(phone_number, response)
        
        # After certain responses, show next menu
        if button_id in ["about_programs", "schedule_fees"]:
            send_secondary_menu(phone_number)
            
        return response
    else:
        send_whatsapp_message(phone_number, "Sorry, I didn't understand that option. Please try again.")
        return None

def get_keywords_response(message):
    """Return keyword-based automated responses (fallback)"""
    msg = message.lower()

    if any(k in msg for k in ["about", "who are you", "your centre", "about us", "program", "classes", "courses"]):
        return "🥋 *About Us & Programs*\n\nWe are Oman Karate Centre, building discipline through traditional karate.\n\n*Programs:* Kids, Teens, Adults, Self Defense, Black Belt Training"

    elif any(k in msg for k in ["schedule", "timing", "class time", "hours", "membership", "fees", "price", "cost"]):
        return "🕒 *Schedule:* Mon-Fri 4-8PM, Sat 9AM-1PM\n💰 *Fees:* Reg 10 OMR, Monthly 25 OMR, 3-Month 65 OMR"

    elif any(k in msg for k in ["location", "where", "address", "place"]):
        return "📍 Near Sultan Qaboos Sports Complex, Muscat\nhttps://maps.google.com/?q=Oman+Karate+Centre+Muscat"

    elif any(k in msg for k in ["contact", "call", "reach", "whatsapp", "phone"]):
        return "☎️ *Contact:* +968 9123 4567 (Call/WhatsApp)\n📧 oman.karate.centre@gmail.com"

    elif any(k in msg for k in ["register", "join", "sign up", "enroll"]):
        send_registration_menu("dummy")  # This will be handled by actual phone number in context
        return None

    return None

# ==============================
# CORS HEADERS
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
                    send_whatsapp_message(phone_number, "✅ Thank you! We've saved your interest and will contact you soon.")
                    return jsonify({"status": "register_later_saved"})
                
                # Handle other button clicks
                handle_button_click(button_id, phone_number)
                return jsonify({"status": "button_handled"})
        
        # Handle text messages (fallback)
        if "text" in message:
            text = message["text"]["body"].strip()
            logger.info(f"Text message received: {text} from {phone_number}")
            
            # Check for greeting or any message to show welcome
            if text.lower() in ["hi", "hello", "hey", "start", "menu"]:
                send_welcome_message(phone_number)
                return jsonify({"status": "welcome_sent"})
            
            # Check for registration data (name and contact)
            if any(char.isdigit() for char in text) and len(text.split()) >= 2:
                try:
                    # Parse name and contact
                    parts = [p.strip() for p in text.replace("|", " ").split() if p.strip()]
                    if len(parts) >= 2:
                        name = ' '.join(parts[:-1])
                        contact = parts[-1]
                        
                        if sheet:
                            add_lead_to_sheet(name, contact, "Register Now", phone_number)
                        
                        send_whatsapp_message(phone_number, f"✅ *Registration Successful!*\n\nThank you {name}! You are now registered.\n\n• Name: {name}\n• Contact: {contact}\n\nWe'll contact you within 24 hours.\n\nCall: +968 9123 4567")
                        return jsonify({"status": "registered"})
                    
                except Exception as e:
                    logger.error(f"Registration parsing error: {str(e)}")
                    send_whatsapp_message(phone_number, "⚠️ Please send: *Name | Phone Number*\nExample: Ali Ahmed | 91234567")
                    return jsonify({"status": "registration_error"})
            
            # Check for keyword-based responses
            response = get_keywords_response(text)
            if response:
                send_whatsapp_message(phone_number, response)
                # After keyword response, show main menu
                send_main_menu(phone_number)
                return jsonify({"status": "keyword_response_sent"})
            
            # If no specific match, send welcome message
            send_welcome_message(phone_number)
            return jsonify({"status": "fallback_welcome_sent"})
        
        return jsonify({"status": "unhandled_message_type"})
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================
# DASHBOARD ENDPOINTS
# ==============================

@app.route("/api/leads", methods=["GET"])
def get_leads():
    """Return all leads for dashboard - FIXED integer strip error"""
    try:
        if sheet:
            # Get all records and safely process them
            all_data = sheet.get_all_records()
            
            valid_leads = []
            for row in all_data:
                # Safely convert all values to strings before stripping
                processed_row = {}
                for key, value in row.items():
                    if value is None:
                        processed_row[key] = ''
                    else:
                        processed_row[key] = str(value).strip()
                
                # Check if row has meaningful data (not just empty strings)
                has_data = any([
                    processed_row.get('Name', ''),
                    processed_row.get('Contact', ''), 
                    processed_row.get('WhatsApp ID', ''),
                    processed_row.get('Intent', '')
                ])
                
                if has_data:
                    valid_leads.append(processed_row)
            
            logger.info(f"Returning {len(valid_leads)} valid leads")
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
                    send_whatsapp_message(str(whatsapp_id), message)
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