from flask import Flask, request, jsonify
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import requests
import logging
import time

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
    """Send WhatsApp message via Meta API with interactive buttons"""
    try:
        # Clean the phone number
        clean_to = ''.join(filter(str.isdigit, str(to)))
        
        # Ensure proper format for WhatsApp API
        if not clean_to.startswith('968') and len(clean_to) >= 8:
            if clean_to.startswith('9'):
                clean_to = '968' + clean_to
            else:
                clean_to = '968' + clean_to.lstrip('0')
        
        url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        if buttons:
            # Interactive message with buttons (MAX 3 BUTTONS ALLOWED)
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_to,
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
                "to": clean_to,
                "type": "text",
                "text": {
                    "body": message
                }
            }

        logger.info(f"Sending WhatsApp message to {clean_to}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response_data = response.json()
        
        if response.status_code == 200:
            logger.info(f"✅ WhatsApp message sent successfully to {clean_to}")
            return True
        else:
            error_message = response_data.get('error', {}).get('message', 'Unknown error')
            logger.error(f"❌ WhatsApp API error {response.status_code}: {error_message} for {clean_to}")
            return False
        
    except Exception as e:
        logger.error(f"🚨 Failed to send WhatsApp message to {to}: {str(e)}")
        return False

def send_welcome_message(to):
    """Send initial welcome message with ONE View Options button"""
    buttons = [
        {
            "type": "reply",
            "reply": {"id": "view_options", "title": "View Options"}
        }
    ]
    
    welcome_message = """International Karate Centre – Al Maabelah

Welcome. Select an option.

Excellence • Discipline • Respect"""
    
    send_whatsapp_message(to, welcome_message, buttons)

def send_main_options_menu(to):
    """Send ALL options in main menu"""
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
            "reply": {"id": "membership", "title": "💰 Membership"}
        },
        {
            "type": "reply",
            "reply": {"id": "contact_location", "title": "📍 Contact & Location"}
        },
        {
            "type": "reply",
            "reply": {"id": "registration", "title": "📝 Registration"}
        }
    ]
    
    menu_message = """*Main Menu*

Choose an option to learn more:"""
    
    # WhatsApp only allows 3 buttons, so we need to split into multiple messages
    # First send message with first 3 buttons
    send_whatsapp_message(to, menu_message, buttons[:3])
    
    # Then send second message with remaining 2 buttons
    time.sleep(1)
    send_whatsapp_message(to, "More options:", buttons[3:])

def send_registration_menu(to):
    """Send registration options"""
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
    
    message = "*Registration*\n\nReady to join International Karate Centre?"
    
    send_whatsapp_message(to, message, buttons)

def handle_button_click(button_id, phone_number):
    """Handle button click responses"""
    responses = {
        # Welcome button
        "view_options": lambda: send_main_options_menu(phone_number),
        
        # Main menu buttons
        "about_us": """*About International Karate Centre – Al Maabelah*

🥋 *Our Mission:*
To develop discipline, strength, and character through traditional karate training in a supportive community.

🏆 *What Makes Us Unique:*
• International certified instructors
• Traditional Japanese karate style
• Modern training facilities
• Focus on personal development
• Competitive training programs

We believe in Excellence, Discipline, and Respect in every student.""",

        "programs": """*Programs Offered*

💪 *Kids Karate (Ages 5-12)*
• Foundation skills development
• Discipline and focus training
• Fun, engaging classes
• Belt progression system

👦 *Teens Karate (Ages 13-17)*
• Advanced technique training
• Self-defense skills
• Leadership development
• Competition preparation

👨‍🎓 *Adults Karate (18+)*
• Traditional karate training
• Self-defense mastery
• Fitness and conditioning
• Black belt pathway

🥊 *Special Programs:*
• Self Defense Classes
• Black Belt Training
• Competitive Training
• Private Lessons""",

        "membership": """*Membership & Fees*

💰 *Membership Options:*
• *Registration Fee:* 10 OMR
• *Monthly Training:* 25 OMR
• *3-Month Package:* 65 OMR (Save 10 OMR)
• *6-Month Package:* 120 OMR (Save 30 OMR)

🎁 *Special Offers:*
• Family Discounts Available
• Sibling Discounts
• Free Trial Class
• No hidden fees

⏰ *Payment Options:*
• Cash
• Bank Transfer
• Monthly Installments""",

        "contact_location": """*Contact & Location*

📍 *Our Location:*
International Karate Centre
Al Maabelah, Muscat
Oman

🗺️ *Google Maps:*
https://maps.google.com/?q=International+Karate+Centre+Al+Maabelah

📞 *Contact Information:*
• Phone: +968 9123 4567
• WhatsApp: +968 9123 4567
• Email: ikc.maabelah@gmail.com
• Instagram: @IKC_Maabelah

🕒 *Office Hours:*
• Sunday-Thursday: 8 AM - 8 PM
• Friday: 2 PM - 6 PM
• Saturday: 9 AM - 1 PM""",

        "registration": lambda: send_registration_menu(phone_number),
        
        # Registration buttons
        "register_now": """✅ *Registration - Step 1*

To register, please send us your:
• *Full Name*
• *Phone Number*

📝 *Format:*
Ali Ahmed | 91234567
*OR*
Ali Ahmed 91234567

We'll contact you within 24 hours to complete your registration!""",
        
        "register_later": """⏰ *We'll Be in Touch!*

Thank you for your interest in International Karate Centre!

We've saved your contact and will reach out to you soon with more information about our programs and next available sessions.

For immediate assistance, call us at: +968 9123 4567

*Excellence • Discipline • Respect*"""
    }
    
    response = responses.get(button_id)
    
    if callable(response):
        response()  # Execute the function
        return None
    elif response:
        send_whatsapp_message(phone_number, response)
        
        # After showing any option, show main menu again
        time.sleep(1)
        send_main_options_menu(phone_number)
            
        return response
    else:
        send_whatsapp_message(phone_number, "Sorry, I didn't understand that option. Please try 'View Options' to see available choices.")
        return None

def get_keywords_response(message):
    """Return keyword-based automated responses (fallback)"""
    msg = message.lower()

    if any(k in msg for k in ["about", "who are you", "your centre", "about us"]):
        return """*About International Karate Centre – Al Maabelah*

We develop discipline, strength, and character through traditional karate training. Reply with 'View Options' for more details."""

    elif any(k in msg for k in ["program", "classes", "courses", "programs"]):
        return """*Programs:* Kids, Teens, Adults karate, Self Defense, and Black Belt training. Reply with 'View Options' for full program details."""

    elif any(k in msg for k in ["membership", "fees", "price", "cost"]):
        return """*Membership:* Registration 10 OMR, Monthly 25 OMR. Reply with 'View Options' for complete pricing."""

    elif any(k in msg for k in ["contact", "call", "reach", "whatsapp", "phone", "location", "where", "address"]):
        return """*Contact:* +968 9123 4567 | Al Maabelah, Muscat. Reply with 'View Options' for full contact details."""

    elif any(k in msg for k in ["register", "join", "sign up", "enroll"]):
        send_registration_menu("dummy")
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
        logger.info(f"Received webhook: {json.dumps(data, indent=2)}")
        
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
                    send_whatsapp_message(phone_number, "✅ Thank you! We've saved your interest and will contact you soon about our programs.")
                    return jsonify({"status": "register_later_saved"})
                
                # Handle other button clicks
                handle_button_click(button_id, phone_number)
                return jsonify({"status": "button_handled"})
        
        # Handle text messages (fallback)
        if "text" in message:
            text = message["text"]["body"].strip()
            logger.info(f"Text message received: {text} from {phone_number}")
            
            # Check for greeting or any message to show welcome
            if text.lower() in ["hi", "hello", "hey", "start", "menu", "options"]:
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
                        
                        send_whatsapp_message(phone_number, 
                            f"✅ *Registration Received!*\n\n"
                            f"Thank you {name}! We have received your registration for International Karate Centre.\n\n"
                            f"• Name: {name}\n"
                            f"• Contact: {contact}\n\n"
                            f"Our team will contact you within 24 hours to complete your enrollment.\n\n"
                            f"For immediate assistance: +968 9123 4567\n\n"
                            f"*Excellence • Discipline • Respect*")
                        return jsonify({"status": "registered"})
                    
                except Exception as e:
                    logger.error(f"Registration parsing error: {str(e)}")
                    send_whatsapp_message(phone_number, 
                        "⚠️ *Registration Format*\n\n"
                        "Please send: *Full Name | Phone Number*\n\n"
                        "Example: Ali Ahmed | 91234567\n\n"
                        "Or: Ali Ahmed 91234567")
                    return jsonify({"status": "registration_error"})
            
            # Check for keyword-based responses
            response = get_keywords_response(text)
            if response:
                send_whatsapp_message(phone_number, response)
                return jsonify({"status": "keyword_response_sent"})
            
            # If no specific match, send welcome message
            send_welcome_message(phone_number)
            return jsonify({"status": "fallback_welcome_sent"})
        
        return jsonify({"status": "unhandled_message_type"})
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================
# DASHBOARD ENDPOINTS - WORKING BROADCAST
# ==============================

@app.route("/api/leads", methods=["GET"])
def get_leads():
    """Return all leads for dashboard"""
    try:
        if sheet:
            all_data = sheet.get_all_records()
            valid_leads = []
            
            for row in all_data:
                # Convert all values to strings safely
                processed_row = {}
                for key, value in row.items():
                    processed_row[key] = str(value) if value is not None else ""
                
                # Check if row has meaningful data
                has_data = any([
                    processed_row.get('Name', ''),
                    processed_row.get('Contact', ''), 
                    processed_row.get('WhatsApp ID', ''),
                    processed_row.get('Intent', '')
                ])
                
                if has_data:
                    valid_leads.append(processed_row)
            
            logger.info(f"✅ Returning {len(valid_leads)} valid leads")
            return jsonify(valid_leads)
        else:
            return jsonify({"error": "Google Sheets not available"}), 500
    except Exception as e:
        logger.error(f"Error getting leads: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/broadcast", methods=["POST"])
def broadcast():
    """Send broadcast messages - WORKING VERSION"""
    try:
        # Get the JSON data from request
        data = request.get_json()
        logger.info(f"📨 Received broadcast request: {data}")
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        segment = data.get("segment", "all")
        message = data.get("message", "").strip()
        
        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400
            
        if not sheet:
            return jsonify({"error": "Google Sheets not available"}), 500
        
        # Get all records from Google Sheets
        all_records = sheet.get_all_records()
        logger.info(f"📊 Found {len(all_records)} total records in sheet")
        
        target_leads = []
        
        for row in all_records:
            # Safely get values
            whatsapp_id = str(row.get("WhatsApp ID", "")).strip()
            intent = str(row.get("Intent", "")).strip()
            name = str(row.get("Name", "")).strip()
            
            # Skip if no WhatsApp ID or it's "Pending"
            if not whatsapp_id or whatsapp_id.lower() == "pending":
                continue
                
            # Check segment filter
            if (segment == "all" or
                (segment == "register_now" and intent == "Register Now") or
                (segment == "register_later" and intent == "Register Later")):
                
                # Clean and format phone number
                clean_whatsapp_id = ''.join(filter(str.isdigit, whatsapp_id))
                
                # Add Oman country code if missing
                if clean_whatsapp_id and not clean_whatsapp_id.startswith('968'):
                    if clean_whatsapp_id.startswith('9') and len(clean_whatsapp_id) == 8:
                        clean_whatsapp_id = '968' + clean_whatsapp_id
                    else:
                        clean_whatsapp_id = '968' + clean_whatsapp_id.lstrip('0')
                
                # Only add if we have a valid-looking number
                if clean_whatsapp_id and len(clean_whatsapp_id) >= 11:
                    target_leads.append({
                        "whatsapp_id": clean_whatsapp_id,
                        "name": name,
                        "intent": intent
                    })
        
        logger.info(f"🎯 Targeting {len(target_leads)} recipients for broadcast")
        
        # Send messages with delays
        sent_count = 0
        failed_count = 0
        
        for i, lead in enumerate(target_leads):
            try:
                # Add delay to avoid rate limiting (2 seconds between messages)
                if i > 0:
                    time.sleep(2)
                
                # Personalize message
                personalized_message = message
                if lead["name"] and lead["name"] not in ["", "Pending", "Unknown"]:
                    personalized_message = f"Hello {lead['name']}! 👋\n\n{message}"
                
                # Send the message
                success = send_whatsapp_message(lead["whatsapp_id"], personalized_message)
                
                if success:
                    sent_count += 1
                    logger.info(f"✅ [{i+1}/{len(target_leads)}] Sent to {lead['whatsapp_id']}")
                else:
                    failed_count += 1
                    logger.error(f"❌ [{i+1}/{len(target_leads)}] Failed for {lead['whatsapp_id']}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"🚨 Error sending to {lead['whatsapp_id']}: {str(e)}")
        
        # Return results
        result = {
            "status": "broadcast_completed",
            "sent": sent_count,
            "failed": failed_count,
            "total_recipients": len(target_leads),
            "message": f"Broadcast completed: {sent_count} sent, {failed_count} failed"
        }
        
        logger.info(f"📬 Broadcast result: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"💥 Broadcast error: {str(e)}")
        return jsonify({"error": f"Broadcast failed: {str(e)}"}), 500

# ==============================
# HEALTH CHECK
# ==============================

@app.route("/", methods=["GET"])
def home():
    status = {
        "status": "International Karate Centre WhatsApp API Active",
        "timestamp": str(datetime.datetime.now()),
        "whatsapp_configured": bool(WHATSAPP_TOKEN and WHATSAPP_PHONE_ID),
        "sheets_available": sheet is not None,
        "features": {
            "interactive_buttons": True,
            "broadcast_messages": True,
            "google_sheets_integration": True
        }
    }
    return jsonify(status)

# ==============================
# RUN APPLICATION
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)