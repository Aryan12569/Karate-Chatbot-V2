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
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
SHEET_NAME = os.environ.get("SHEET_NAME", "Subscribers")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

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
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")
        sheet.append_row([timestamp, name, contact, whatsapp_id, intent])
        logger.info(f"Added lead to sheet: {name}, {contact}, {intent}")
        return True
    except Exception as e:
        logger.error(f"Failed to add lead to sheet: {str(e)}")
        return False

def send_whatsapp_message(to, message, interactive_data=None):
    """Send WhatsApp message via Meta API"""
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
        
        if interactive_data:
            # Interactive message (List or Buttons)
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_to,
                "type": "interactive",
                "interactive": interactive_data
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
    interactive_data = {
        "type": "button",
        "body": {
            "text": "Oman Karate Centre\n\nWelcome. Select an option.\n\nExcellence • Discipline • Respect"
        },
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {
                        "id": "view_options",
                        "title": "View Options"
                    }
                }
            ]
        }
    }
    
    send_whatsapp_message(to, "", interactive_data)

def send_main_options_list(to):
    """Send ALL options in one list"""
    interactive_data = {
        "type": "list",
        "header": {
            "type": "text",
            "text": "Oman Karate Centre"
        },
        "body": {
            "text": "Choose an option to learn more:"
        },
        "action": {
            "button": "View Options",
            "sections": [
                {
                    "title": "Centre Information",
                    "rows": [
                        {
                            "id": "about_us",
                            "title": "About Us",
                            "description": "Our mission and values"
                        },
                        {
                            "id": "programs", 
                            "title": "Programs",
                            "description": "Training programs for all ages"
                        },
                        {
                            "id": "schedule",
                            "title": "Schedule", 
                            "description": "Class timings and batches"
                        },
                        {
                            "id": "membership",
                            "title": "Membership",
                            "description": "Fees and discount information"
                        }
                    ]
                },
                {
                    "title": "Contact & Registration",
                    "rows": [
                        {
                            "id": "location",
                            "title": "Location",
                            "description": "Our address and directions"
                        },
                        {
                            "id": "contact",
                            "title": "Contact",
                            "description": "Get in touch with us"
                        },
                        {
                            "id": "offers",
                            "title": "Offers",
                            "description": "Current promotions"
                        },
                        {
                            "id": "events",
                            "title": "Events",
                            "description": "Upcoming activities"
                        },
                        {
                            "id": "register",
                            "title": "Register", 
                            "description": "Join Oman Karate Centre"
                        }
                    ]
                }
            ]
        }
    }
    
    send_whatsapp_message(to, "", interactive_data)

def send_registration_options(to):
    """Send registration options"""
    interactive_data = {
        "type": "list",
        "header": {
            "type": "text",
            "text": "Registration"
        },
        "body": {
            "text": "Choose your registration option:"
        },
        "action": {
            "button": "Register",
            "sections": [
                {
                    "title": "Enrollment Options",
                    "rows": [
                        {
                            "id": "register_now",
                            "title": "Register Now", 
                            "description": "Complete registration immediately"
                        },
                        {
                            "id": "register_later",
                            "title": "Register Later",
                            "description": "Get updates and offers later"
                        }
                    ]
                }
            ]
        }
    }
    
    send_whatsapp_message(to, "", interactive_data)

def handle_interaction(interaction_id, phone_number):
    """Handle list and button interactions"""
    responses = {
        # Welcome button
        "view_options": lambda: send_main_options_list(phone_number),
        
        # Main list options - USING YOUR EXACT CONTENT
        "about_us": """About Us

Oman Karate Centre is dedicated to teaching traditional karate for all ages.
Our mission is to build discipline, confidence, and strength in every student through expert-led training.
Certified instructors, safe environment, and a legacy of excellence.""",

        "programs": """Programs

We offer programs for all age groups:

Kids Karate (Age 5+)

Teens & Adults Karate

Black Belt Training

Self Defense Sessions

Every program focuses on fitness, technique, and character development.""",

        "schedule": """Schedule

Class Timings:
Weekdays: 5:00 PM – 8:00 PM
Weekends: 10:00 AM – 1:00 PM

Classes are divided by age and skill level. Contact us to confirm your batch.""",

        "membership": """Membership

Membership Details:

Registration Fee: 10 OMR

Monthly Fee: 25 OMR

Family & Group Discounts available

Flexible plans designed for long-term training and growth.""",

        "location": """Location

Address:
Oman Karate Centre
Near Sultan Qaboos Sports Complex, Muscat

Google Maps: https://maps.app.goo.gl/jcdQoP7ZnuPot1wK9""",

        "contact": """Contact

Contact Information:
WhatsApp: +968 9123 4567
Email: oman.karate.centre@gmail.com

Feel free to reach out for schedules, trial classes, or general queries.""",

        "offers": """Offers

Current Offers:
No active promotions at the moment.
Stay tuned for seasonal discounts and referral bonuses.""",

        "events": """Events

Upcoming Events:

Karate Belt Grading – December 2025

Annual Tournament – February 2026

Keep training — we'll share event updates soon!""",

        "register": lambda: send_registration_options(phone_number),
        
        # Registration options
        "register_now": """Register Now

Please reply with your Name and Contact Number in this format:

Name | Contact
Example: Ahmed | +96891234567

Our team will reach out to confirm your registration shortly.""",
        
        "register_later": """Register Later

Got it! We'll reach out to you later with our latest offers and class details.
Thank you for your interest in Oman Karate Centre."""
    }
    
    response = responses.get(interaction_id)
    
    if callable(response):
        response()  # Execute the function
        return None
    elif response:
        send_whatsapp_message(phone_number, response)
        # DON'T show main menu again after each selection
        return response
    else:
        send_whatsapp_message(phone_number, "Sorry, I didn't understand that option. Please select 'View Options' to see available choices.")
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
    """Handle incoming WhatsApp messages and interactions"""
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
        
        # Check if it's an interactive message (list or button)
        if "interactive" in message:
            interactive_data = message["interactive"]
            interactive_type = interactive_data["type"]
            
            if interactive_type == "list_reply":
                # Handle list selection
                list_reply = interactive_data["list_reply"]
                option_id = list_reply["id"]
                option_title = list_reply["title"]
                
                logger.info(f"List option selected: {option_id} - {option_title} by {phone_number}")
                
                # Handle registration actions
                if option_id == "register_later":
                    if sheet:
                        add_lead_to_sheet("Pending", "Pending", "Register Later", phone_number)
                    send_whatsapp_message(phone_number, "Thank you! We've noted your interest and will contact you with updates and offers.")
                    return jsonify({"status": "register_later_saved"})
                
                # Handle other list selections
                handle_interaction(option_id, phone_number)
                return jsonify({"status": "list_handled"})
            
            elif interactive_type == "button_reply":
                # Handle button click
                button_reply = interactive_data["button_reply"]
                button_id = button_reply["id"]
                button_title = button_reply["title"]
                
                logger.info(f"Button clicked: {button_id} - {button_title} by {phone_number}")
                handle_interaction(button_id, phone_number)
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
                        
                        send_whatsapp_message(phone_number, 
                            f"Registration Received!\n\n"
                            f"Thank you {name}! We have received your registration.\n\n"
                            f"Name: {name}\n"
                            f"Contact: {contact}\n\n"
                            f"Our team will contact you within 24 hours to complete your enrollment.\n\n"
                            f"For immediate assistance: +968 9123 4567")
                        return jsonify({"status": "registered"})
                    
                except Exception as e:
                    logger.error(f"Registration parsing error: {str(e)}")
                    send_whatsapp_message(phone_number, 
                        "Please send your information as:\n\n"
                        "Name | Phone Number\n\n"
                        "Example: Ahmed | 91234567\n\n"
                        "Or: Ahmed 91234567")
                    return jsonify({"status": "registration_error"})
            
            # If no specific match, send welcome message (ONLY ONCE)
            send_welcome_message(phone_number)
            return jsonify({"status": "fallback_welcome_sent"})
        
        return jsonify({"status": "unhandled_message_type"})
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================
# DASHBOARD ENDPOINTS - FIXED BROADCAST
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
    """Send broadcast messages - FIXED VERSION"""
    try:
        data = request.get_json()
        logger.info(f"📨 Received broadcast request")
        
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
        logger.info(f"📊 Found {len(all_records)} total records")
        
        target_leads = []
        
        for row in all_records:
            # Try different column name variations
            whatsapp_id = (
                str(row.get("WhatsApp ID", "")).strip() or 
                str(row.get("WhatsAppID", "")).strip() or
                str(row.get("whatsapp_id", "")).strip() or
                str(row.get("WhatsApp", "")).strip() or
                str(row.get("Phone", "")).strip() or
                str(row.get("Contact", "")).strip()
            )
            
            intent = (
                str(row.get("Intent", "")).strip() or
                str(row.get("intent", "")).strip() or
                str(row.get("Status", "")).strip()
            )
            
            name = (
                str(row.get("Name", "")).strip() or
                str(row.get("name", "")).strip()
            )
            
            # Skip if no WhatsApp ID
            if not whatsapp_id or whatsapp_id.lower() in ["pending", "none", "null", ""]:
                continue
                
            # Check segment filter
            if (segment == "all" or
                (segment == "register_now" and "register now" in intent.lower()) or
                (segment == "register_later" and "register later" in intent.lower())):
                
                # Clean phone number
                clean_whatsapp_id = ''.join(filter(str.isdigit, whatsapp_id))
                
                # Add Oman country code if missing
                if clean_whatsapp_id:
                    if not clean_whatsapp_id.startswith('968'):
                        if clean_whatsapp_id.startswith('9') and len(clean_whatsapp_id) == 8:
                            clean_whatsapp_id = '968' + clean_whatsapp_id
                        else:
                            clean_whatsapp_id = '968' + clean_whatsapp_id.lstrip('0')
                    
                    # Only add if we have a valid-looking number
                    if len(clean_whatsapp_id) >= 11:
                        target_leads.append({
                            "whatsapp_id": clean_whatsapp_id,
                            "name": name,
                            "intent": intent
                        })
        
        logger.info(f"🎯 Targeting {len(target_leads)} recipients")
        
        if len(target_leads) == 0:
            return jsonify({
                "status": "no_recipients", 
                "sent": 0,
                "failed": 0,
                "total_recipients": 0,
                "message": "No valid recipients found. Check if you have WhatsApp numbers in your Google Sheets."
            })
        
        # Send messages
        sent_count = 0
        failed_count = 0
        
        for i, lead in enumerate(target_leads):
            try:
                # Add delay to avoid rate limiting
                if i > 0:
                    time.sleep(3)
                
                # Personalize message
                personalized_message = message
                if lead["name"] and lead["name"] not in ["", "Pending", "Unknown", "None"]:
                    personalized_message = f"Hello {lead['name']}!\n\n{message}"
                
                logger.info(f"📤 Sending to {lead['whatsapp_id']}")
                
                # Send the message
                success = send_whatsapp_message(lead["whatsapp_id"], personalized_message)
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error sending to {lead['whatsapp_id']}: {str(e)}")
        
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
        logger.error(f"Broadcast error: {str(e)}")
        return jsonify({"error": f"Broadcast failed: {str(e)}"}), 500

@app.route("/api/debug-data", methods=["GET"])
def debug_data():
    """Debug endpoint to check leads data"""
    try:
        if not sheet:
            return jsonify({"error": "Sheets not available"})
        
        all_records = sheet.get_all_records()
        column_names = list(all_records[0].keys()) if all_records else []
        
        processed_data = []
        valid_count = 0
        
        for i, row in enumerate(all_records):
            whatsapp_id = (
                str(row.get("WhatsApp ID", "")).strip() or 
                str(row.get("WhatsAppID", "")).strip() or
                str(row.get("whatsapp_id", "")).strip() or
                str(row.get("WhatsApp", "")).strip()
            )
            
            # Clean and validate
            clean_whatsapp_id = ''.join(filter(str.isdigit, whatsapp_id))
            if clean_whatsapp_id and not clean_whatsapp_id.startswith('968'):
                if clean_whatsapp_id.startswith('9') and len(clean_whatsapp_id) == 8:
                    clean_whatsapp_id = '968' + clean_whatsapp_id
                else:
                    clean_whatsapp_id = '968' + clean_whatsapp_id.lstrip('0')
            
            is_valid = len(clean_whatsapp_id) >= 11 if clean_whatsapp_id else False
            if is_valid:
                valid_count += 1
            
            processed_data.append({
                "row": i + 1,
                "original_whatsapp_id": whatsapp_id,
                "clean_whatsapp_id": clean_whatsapp_id,
                "name": str(row.get("Name", "")),
                "intent": str(row.get("Intent", "")),
                "valid": is_valid
            })
        
        return jsonify({
            "column_names": column_names,
            "total_records": len(all_records),
            "valid_whatsapp_numbers": valid_count,
            "data": processed_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

# ==============================
# HEALTH CHECK
# ==============================

@app.route("/", methods=["GET"])
def home():
    status = {
        "status": "Oman Karate Centre WhatsApp API Active",
        "timestamp": str(datetime.datetime.now()),
        "whatsapp_configured": bool(WHATSAPP_TOKEN and WHATSAPP_PHONE_ID),
        "sheets_available": sheet is not None
    }
    return jsonify(status)

# ==============================
# RUN APPLICATION
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)