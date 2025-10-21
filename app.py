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
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")
        # Make sure we're saving the actual WhatsApp ID, not "Pending"
        sheet.append_row([timestamp, name, contact, whatsapp_id, intent])
        logger.info(f"Added lead to sheet: {name}, {contact}, {intent}, WhatsApp: {whatsapp_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to add lead to sheet: {str(e)}")
        return False

def send_whatsapp_message(to, message, interactive_data=None):
    """Send WhatsApp message via Meta API with better error handling"""
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
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_to,
                "type": "interactive",
                "interactive": interactive_data
            }
        else:
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
            error_code = response_data.get('error', {}).get('code', 'Unknown')
            
            # Handle specific errors
            if error_code == 131030:
                logger.warning(f"⚠️ Number {clean_to} not in allowed list. Add it to Meta Business Account.")
                return False
            elif error_code == 131031:
                logger.warning(f"⚠️ Rate limit hit for {clean_to}. Waiting before retry.")
                time.sleep(2)
                return False
            else:
                logger.error(f"❌ WhatsApp API error {response.status_code} (Code: {error_code}): {error_message} for {clean_to}")
                return False
        
    except Exception as e:
        logger.error(f"🚨 Failed to send WhatsApp message to {to}: {str(e)}")
        return False

def send_whatsapp_template_message(to, message, name):
    """Send WhatsApp message using approved template for 24h+ conversations"""
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
        
        # Use a generic utility template
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_to,
            "type": "template",
            "template": {
                "name": "karate_announcement",
                "language": {
                    "code": "en"
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "text": name if name and name not in ["", "Pending"] else "Student"
                            },
                            {
                                "type": "text", 
                                "text": message[:200]
                            }
                        ]
                    }
                ]
            }
        }

        logger.info(f"Attempting template message to {clean_to}")
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response_data = response.json()
        
        if response.status_code == 200:
            logger.info(f"✅ WhatsApp template message sent successfully to {clean_to}")
            return True
        else:
            error_message = response_data.get('error', {}).get('message', 'Unknown error')
            logger.warning(f"⚠️ Template message failed {response.status_code}: {error_message} for {clean_to}")
            return False
        
    except Exception as e:
        logger.error(f"🚨 Failed to send WhatsApp template message to {to}: {str(e)}")
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
        
        # Main list options
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
        response()
        return None
    elif response:
        send_whatsapp_message(phone_number, response)
        return response
    else:
        send_whatsapp_message(phone_number, "Sorry, I didn't understand that option. Please select 'View Options' to see available choices.")
        return None

# ==============================
# BROADCAST HELPER FUNCTIONS
# ==============================

def extract_whatsapp_id(row):
    """Extract WhatsApp ID from row with multiple field name support"""
    field_names = ["WhatsApp ID", "WhatsAppID", "whatsapp_id", "WhatsApp", "Phone", "Contact", "Mobile"]
    for field in field_names:
        if field in row and row[field]:
            value = str(row[field]).strip()
            if value and value.lower() not in ["pending", "none", "null", ""]:
                return value
    return None

def extract_intent(row):
    """Extract intent from row"""
    field_names = ["Intent", "intent", "Status", "status"]
    for field in field_names:
        if field in row and row[field]:
            return str(row[field]).strip()
    return ""

def extract_name(row):
    """Extract name from row"""
    field_names = ["Name", "name", "Full Name", "full_name"]
    for field in field_names:
        if field in row and row[field]:
            name = str(row[field]).strip()
            if name and name.lower() not in ["pending", "unknown", "none"]:
                return name
    return ""

def is_valid_whatsapp_number(number):
    """Check if number looks like a valid WhatsApp number"""
    if not number:
        return False
    clean = ''.join(filter(str.isdigit, str(number)))
    return len(clean) >= 8

def clean_whatsapp_number(number):
    """Clean and format WhatsApp number"""
    if not number:
        return None
    
    clean_number = ''.join(filter(str.isdigit, str(number)))
    
    if not clean_number:
        return None
        
    # Handle Oman numbers specifically
    if not clean_number.startswith('968'):
        if clean_number.startswith('9') and len(clean_number) == 8:
            clean_number = '968' + clean_number
        else:
            clean_number = '968' + clean_number.lstrip('0')
    
    # Final validation
    if len(clean_number) >= 11 and clean_number.startswith('968'):
        return clean_number
    
    return None

def should_include_lead(segment, intent, name):
    """Check if lead should be included based on segment"""
    intent_lower = intent.lower() if intent else ""
    
    if segment == "all":
        return True
    elif segment == "register_now":
        return "register now" in intent_lower
    elif segment == "register_later":
        return "register later" in intent_lower
    return False

def personalize_message(message, name):
    """Personalize message with name"""
    if name and name not in ["", "Pending", "Unknown", "None"]:
        return f"Hello {name}!\n\n{message}"
    return message

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
                
                # Handle registration actions - FIXED: Save actual phone number instead of "Pending"
                if option_id == "register_later":
                    if sheet:
                        # Save with actual WhatsApp number instead of "Pending"
                        add_lead_to_sheet("Pending", phone_number, "Register Later", phone_number)
                    send_whatsapp_message(phone_number, "Thank you! We've noted your interest and will contact you with updates and offers.")
                    return jsonify({"status": "register_later_saved"})
                
                if option_id == "register_now":
                    # For register now, prompt for name and contact
                    send_whatsapp_message(phone_number, 
                        "Register Now\n\nPlease reply with your Name and Contact Number in this format:\n\n"
                        "Name | Contact\nExample: Ahmed | +96891234567\n\n"
                        "Our team will reach out to confirm your registration shortly.")
                    return jsonify({"status": "register_now_prompt"})
                
                # Handle other list selections
                handle_interaction(option_id, phone_number)
                return jsonify({"status": "list_handled"})
            
            elif interactive_type == "button_reply":
                # Handle button click
                button_reply = interactive_data["button_reply"]
                button_id = button_reply["id"]
                button_title = button_reply["title"]
                
                logger.info(f"Button clicked: {button_id} - {button_title} by {phone_number}")
                
                # Handle view_options button
                if button_id == "view_options":
                    send_main_options_list(phone_number)
                    return jsonify({"status": "view_options_sent"})
                
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
# DASHBOARD ENDPOINTS
# ==============================

@app.route("/api/leads", methods=["GET"])
def get_leads():
    """Return all leads for dashboard"""
    try:
        if sheet:
            all_data = sheet.get_all_records()
            valid_leads = []
            
            for row in all_data:
                processed_row = {}
                for key, value in row.items():
                    processed_row[key] = str(value) if value is not None else ""
                
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
    """Send broadcast messages with better data handling"""
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
        
        all_records = sheet.get_all_records()
        logger.info(f"📊 Found {len(all_records)} total records")
        
        target_leads = []
        
        for row in all_records:
            whatsapp_id = extract_whatsapp_id(row)
            intent = extract_intent(row)
            name = extract_name(row)
            
            if not whatsapp_id or not is_valid_whatsapp_number(whatsapp_id):
                continue
                
            clean_whatsapp_id = clean_whatsapp_number(whatsapp_id)
            if not clean_whatsapp_id:
                continue
                
            if should_include_lead(segment, intent, name):
                target_leads.append({
                    "whatsapp_id": clean_whatsapp_id,
                    "name": name,
                    "intent": intent,
                    "original_data": row
                })
        
        logger.info(f"🎯 Targeting {len(target_leads)} recipients for segment '{segment}'")
        
        if len(target_leads) == 0:
            return jsonify({
                "status": "no_recipients", 
                "sent": 0,
                "failed": 0,
                "total_recipients": 0,
                "debug_info": {
                    "total_records": len(all_records),
                    "segment": segment,
                    "message": "No valid recipients found. Check if you have WhatsApp numbers and correct intent values in Google Sheets."
                }
            })
        
        sent_count = 0
        failed_count = 0
        failed_details = []
        
        for i, lead in enumerate(target_leads):
            try:
                if i > 0:
                    time.sleep(3)
                
                personalized_message = personalize_message(message, lead["name"])
                
                logger.info(f"📤 Sending to {lead['whatsapp_id']} - {lead['name']}")
                
                success = send_whatsapp_message(lead["whatsapp_id"], personalized_message)
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    failed_details.append({
                        "number": lead["whatsapp_id"],
                        "name": lead["name"],
                        "intent": lead["intent"],
                        "reason": "WhatsApp API rejected message - may need to add number to allowed list"
                    })
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error sending to {lead['whatsapp_id']}: {str(e)}")
                failed_details.append({
                    "number": lead["whatsapp_id"],
                    "name": lead["name"],
                    "intent": lead["intent"],
                    "reason": str(e)
                })
        
        result = {
            "status": "broadcast_completed",
            "sent": sent_count,
            "failed": failed_count,
            "total_recipients": len(target_leads),
            "segment": segment,
            "failed_details": failed_details[:10],
            "message": f"Broadcast completed: {sent_count} sent, {failed_count} failed for segment '{segment}'"
        }
        
        logger.info(f"📬 Broadcast result: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Broadcast error: {str(e)}")
        return jsonify({"error": f"Broadcast failed: {str(e)}"}), 500

@app.route("/api/debug-leads", methods=["GET"])
def debug_leads():
    """Debug endpoint to check leads data"""
    try:
        if not sheet:
            return jsonify({"error": "Google Sheets not available"}), 500
        
        all_records = sheet.get_all_records()
        processed_data = []
        
        for i, row in enumerate(all_records):
            whatsapp_id = extract_whatsapp_id(row)
            intent = extract_intent(row)
            name = extract_name(row)
            
            clean_whatsapp_id = clean_whatsapp_number(whatsapp_id)
            is_valid = len(clean_whatsapp_id) >= 11 if clean_whatsapp_id else False
            is_register_later = "register later" in intent.lower() if intent else False
            is_register_now = "register now" in intent.lower() if intent else False
            
            processed_data.append({
                "row": i + 2,
                "name": name,
                "original_whatsapp": whatsapp_id,
                "cleaned_whatsapp": clean_whatsapp_id,
                "intent": intent,
                "is_valid": is_valid,
                "is_register_later": is_register_later,
                "is_register_now": is_register_now
            })
        
        register_later_count = len([x for x in processed_data if x["is_register_later"]])
        register_now_count = len([x for x in processed_data if x["is_register_now"]])
        valid_numbers_count = len([x for x in processed_data if x["is_valid"]])
        
        return jsonify({
            "total_records": len(all_records),
            "register_later_count": register_later_count,
            "register_now_count": register_now_count,
            "valid_whatsapp_numbers": valid_numbers_count,
            "data": processed_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cleanup-data", methods=["POST"])
def cleanup_data():
    """Cleanup existing data - fix Register Later users with 'Pending' contact"""
    try:
        if not sheet:
            return jsonify({"error": "Google Sheets not available"}), 500
        
        all_records = sheet.get_all_records()
        updated_count = 0
        
        for i, row in enumerate(all_records):
            intent = extract_intent(row)
            contact = extract_whatsapp_id(row)  # Using same function to get contact
            whatsapp_id = extract_whatsapp_id(row)
            
            # Fix Register Later users who have 'Pending' as contact but have WhatsApp ID
            if (intent and "register later" in intent.lower() and 
                contact and contact.lower() == "pending" and 
                whatsapp_id and whatsapp_id.lower() != "pending" and 
                is_valid_whatsapp_number(whatsapp_id)):
                
                # Update the Contact field with the WhatsApp ID
                sheet.update_cell(i+2, 3, whatsapp_id)  # +2 because of header row, 3 is Contact column
                updated_count += 1
                logger.info(f"Updated row {i+2}: Contact = {whatsapp_id}")
        
        return jsonify({
            "status": "cleanup_completed",
            "updated_records": updated_count,
            "message": f"Successfully updated {updated_count} records"
        })
        
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    status = {
        "status": "Oman Karate Centre WhatsApp API Active",
        "timestamp": str(datetime.datetime.now()),
        "whatsapp_configured": bool(WHATSAPP_TOKEN and WHATSAPP_PHONE_ID),
        "sheets_available": sheet is not None,
        "version": "2.1"
    }
    return jsonify(status)

# ==============================
# RUN APPLICATION
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)