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

def send_whatsapp_message(to, message, interactive_data=None):
    """Send WhatsApp message via Meta API with interactive list/buttons"""
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
    """Send initial welcome message with ONE button that opens list"""
    interactive_data = {
        "type": "button",
        "body": {
            "text": "🌟 *International Karate Centre – Al Maabelah*\n\nWelcome to your martial arts journey! 🥋\n\n*Excellence • Discipline • Respect*"
        },
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {
                        "id": "view_options",
                        "title": "🚀 Explore Options"
                    }
                }
            ]
        }
    }
    
    send_whatsapp_message(to, "", interactive_data)

def send_main_options_list(to):
    """Send the main options as a LIST (popup with dark background)"""
    interactive_data = {
        "type": "list",
        "body": {
            "text": "🎯 *What would you like to know?*\n\nChoose an option below to explore International Karate Centre:"
        },
        "action": {
            "button": "📋 Main Menu",
            "sections": [
                {
                    "title": "🏫 Centre Information",
                    "rows": [
                        {
                            "id": "about_us",
                            "title": "🥋 About Our Centre",
                            "description": "Our mission, values & what makes us unique"
                        },
                        {
                            "id": "programs", 
                            "title": "💪 Training Programs",
                            "description": "Kids, Teens, Adults & Specialized classes"
                        },
                        {
                            "id": "membership",
                            "title": "💰 Membership & Fees", 
                            "description": "Pricing, packages & special offers"
                        }
                    ]
                },
                {
                    "title": "📍 Contact & Registration",
                    "rows": [
                        {
                            "id": "contact_location",
                            "title": "📞 Contact & Location",
                            "description": "Find us, call us, visit us"
                        },
                        {
                            "id": "registration",
                            "title": "🎯 Start Your Journey", 
                            "description": "Register now or get more information"
                        }
                    ]
                }
            ]
        }
    }
    
    send_whatsapp_message(to, "", interactive_data)

def send_registration_options(to):
    """Send registration options as a LIST"""
    interactive_data = {
        "type": "list", 
        "body": {
            "text": "🎯 *Ready to Begin Your Karate Journey?*\n\nChoose your registration option:"
        },
        "action": {
            "button": "📝 Registration",
            "sections": [
                {
                    "title": "🎓 Enrollment Options",
                    "rows": [
                        {
                            "id": "register_now",
                            "title": "✅ Register Now", 
                            "description": "Complete your registration immediately"
                        },
                        {
                            "id": "register_later",
                            "title": "⏰ Get More Info",
                            "description": "Receive information & follow-up call"
                        }
                    ]
                }
            ]
        }
    }
    
    send_whatsapp_message(to, "", interactive_data)

def handle_list_selection(button_id, phone_number):
    """Handle list selection responses"""
    responses = {
        # Welcome button
        "view_options": lambda: send_main_options_list(phone_number),
        
        # Main list options
        "about_us": """🏫 *About International Karate Centre – Al Maabelah*

🌟 *Our Mission:*
To cultivate excellence, discipline, and respect through authentic karate training in a world-class facility.

🎯 *What Sets Us Apart:*
• 🥋 Internationally Certified Master Instructors
• 🇯🇵 Authentic Japanese Karate Style  
• 🏆 Modern, State-of-the-Art Dojo
• 📈 Personalized Progress Tracking
• 🏅 Competitive Team Training

💫 *Our Values:*
Excellence in technique, Discipline in practice, Respect for all.

*Begin your journey to black belt excellence!* 🥋""",

        "programs": """💪 *Comprehensive Training Programs*

👶 *Little Dragons (Ages 5-7)*
• 🤸 Fundamental movement skills
• 🧠 Focus & attention development  
• 🎯 Basic self-defense techniques
• 🎮 Fun, game-based learning

👦 *Junior Warriors (Ages 8-12)*  
• 🥋 Traditional kata & kumite
• 🛡️ Practical self-defense skills
• 🏆 Belt ranking system
• 🤝 Teamwork & leadership

🧑 *Youth Champions (Ages 13-17)*
• ⚡ Advanced technique mastery
• 🥊 Competitive training
• 💪 Strength & conditioning
• 🎓 Leadership development

👨‍🎓 *Adult Excellence (18+)*
• 🥋 Complete karate curriculum  
• 🧘 Mental discipline & focus
• 💥 Real-world self defense
• 🏅 Black belt pathway

🌟 *Specialized Programs:*
• 🥊 Elite Competition Training
• 🛡️ Women's Self-Defense
• 👨‍👩‍👧‍👦 Family Karate Classes
• 🎯 Private 1-on-1 Coaching""",

        "membership": """💰 *Membership & Investment*

🎫 *Registration Fee:* 10 OMR
*(Includes official karate uniform & welcome kit)*

💳 *Monthly Training Plans:*
• 🥋 *Standard Membership:* 25 OMR
  (2 classes per week)
  
• ⭐ *Premium Membership:* 35 OMR  
  (Unlimited classes + Saturday training)

• 👨‍👩‍👧‍👦 *Family Package:* 60 OMR
  (2 family members, save 15%)

🎁 *Commitment Packages (Save More!):*
• 📅 *3-Month Package:* 65 OMR (Save 10 OMR)
• 🗓️ *6-Month Package:* 120 OMR (Save 30 OMR) 
• 🌟 *Annual Elite:* 220 OMR (Save 80 OMR)

💎 *Special Offers:*
• 🆓 *FREE Trial Class* for new students
• 👥 *Referral Discounts* available
• 🎓 *Sibling Discounts* (15% off)
• 🏆 *No hidden fees or contracts*

💸 *Flexible Payment Options:*
• 💰 Cash • 🏦 Bank Transfer • 💳 Card
• 📱 Mobile Payment • 🗓️ Monthly Installments""",

        "contact_location": """📍 *Find & Contact Us*

🏢 *Our Location:*
International Karate Centre
Al Maabelah Commercial Street
Muscat, Oman

🗺️ *Get Directions:*
https://maps.google.com/?q=International+Karate+Centre+Al+Maabelah

📞 *Direct Contact:*
• 📱 WhatsApp: +968 9123 4567
• 📞 Phone: +968 9123 4567  
• 📧 Email: ikc.maabelah@gmail.com
• 📷 Instagram: @IKC_Maabelah

🕒 *Training Hours:*
• 🗓️ Sunday - Thursday: 4:00 PM - 9:00 PM
• 🗓️ Friday: 3:00 PM - 7:00 PM  
• 🗓️ Saturday: 9:00 AM - 1:00 PM

🏢 *Office Hours:*
• 🗓️ Sunday - Thursday: 9:00 AM - 8:00 PM
• 🗓️ Friday: 2:00 PM - 6:00 PM

🎯 *Visit us for a FREE trial class!*""",

        "registration": lambda: send_registration_options(phone_number),
        
        # Registration options
        "register_now": """✅ *Registration Process - Step 1*

🎯 *To complete your registration, please provide:*

👤 *Full Name*
📱 *Phone Number*

📝 *You can send it in any format:*
• Ali Ahmed | 91234567
• Ali Ahmed 91234567  
• Name: Ali Ahmed, Phone: 91234567

⏰ *What Happens Next:*
1. We'll contact you within 24 hours
2. Schedule your FREE trial class  
3. Complete enrollment paperwork
4. Receive your official uniform
5. Begin your karate journey!

🏆 *Welcome to the IKC family!*""",
        
        "register_later": """⏰ *More Information Request*

📧 *We'll Send You:*
• 📋 Complete program details
• 🗓️ Current class schedules  
- 💰 Detailed pricing packages
• 🎯 Special offers & discounts
• 📞 Personal follow-up call

📱 *Next Steps:*
1. We'll WhatsApp you detailed info
2. Schedule a centre tour if desired
3. Answer any questions you have
4. Help choose the perfect program

🌟 *No pressure - just information!*

📞 *For immediate questions:*
+968 9123 4567

*Your martial arts journey starts with curiosity!* 🥋"""
    }
    
    response = responses.get(button_id)
    
    if callable(response):
        response()  # Execute the function
        return None
    elif response:
        send_whatsapp_message(phone_number, response)
        
        # After showing information, show main options again
        time.sleep(2)
        send_main_options_list(phone_number)
            
        return response
    else:
        send_whatsapp_message(phone_number, "❌ *Option Not Recognized*\n\nPlease select '🚀 Explore Options' to see available choices.")
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
        
        # Check if it's an interactive message (list or button)
        if "interactive" in message:
            interactive_data = message["interactive"]
            
            # Handle list replies
            if interactive_data["type"] == "list_reply":
                button_id = interactive_data["list_reply"]["id"]
                logger.info(f"List option selected: {button_id} by {phone_number}")
                
                # Handle registration actions
                if button_id == "register_later":
                    if sheet:
                        add_lead_to_sheet("Pending", "Pending", "Register Later", phone_number)
                    send_whatsapp_message(phone_number, "✅ *Interest Registered!*\n\nWe've saved your details and will contact you soon with more information about our programs!\n\n📞 For immediate questions: +968 9123 4567")
                    return jsonify({"status": "register_later_saved"})
                
                # Handle other list selections
                handle_list_selection(button_id, phone_number)
                return jsonify({"status": "list_handled"})
            
            # Handle button replies
            elif interactive_data["type"] == "button_reply":
                button_id = interactive_data["button_reply"]["id"]
                logger.info(f"Button clicked: {button_id} by {phone_number}")
                handle_list_selection(button_id, phone_number)
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
                            f"🎉 *Registration Confirmed!*\n\n"
                            f"Welcome to the IKC family, {name}! \n\n"
                            f"✅ *Registration Details:*\n"
                            f"• 👤 Name: {name}\n"
                            f"• 📱 Contact: {contact}\n\n"
                            f"⏰ *What's Next:*\n"
                            f"• We'll contact you within 24 hours\n"
                            f"• Schedule your FREE trial class\n"  
                            f"• Complete your enrollment\n"
                            f"• Receive your official uniform\n\n"
                            f"📞 *Immediate Assistance:*\n"
                            f"+968 9123 4567\n\n"
                            f"🌟 *Your black belt journey begins now!* 🥋")
                        return jsonify({"status": "registered"})
                    
                except Exception as e:
                    logger.error(f"Registration parsing error: {str(e)}")
                    send_whatsapp_message(phone_number, 
                        "❌ *Registration Format Issue*\n\n"
                        "Please send your information as:\n\n"
                        "👤 *Full Name* | 📱 *Phone Number*\n\n"
                        "📝 *Examples:*\n"
                        "• Ali Ahmed | 91234567\n"  
                        "• Ali Ahmed 91234567\n"
                        "• Name: Ali Ahmed, Phone: 91234567\n\n"
                        "We'll get you registered immediately! ✅")
                    return jsonify({"status": "registration_error"})
            
            # If no specific match, send welcome message
            send_welcome_message(phone_number)
            return jsonify({"status": "fallback_welcome_sent"})
        
        return jsonify({"status": "unhandled_message_type"})
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================
# DASHBOARD ENDPOINTS (Keep the same as before)
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
    """Send broadcast messages - DEBUGGED VERSION"""
    try:
        # Get the JSON data from request
        data = request.get_json()
        logger.info(f"📨 Received broadcast request: {json.dumps(data)}")
        
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
            # Safely get values - FIXED: Use proper column names
            whatsapp_id = str(row.get("WhatsApp ID", "")).strip()
            intent = str(row.get("Intent", "")).strip()
            name = str(row.get("Name", "")).strip()
            
            logger.info(f"Processing lead: {name} - {whatsapp_id} - {intent}")
            
            # Skip if no WhatsApp ID or it's empty
            if not whatsapp_id or whatsapp_id.lower() in ["pending", "none", "null", ""]:
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
                    elif len(clean_whatsapp_id) >= 8:
                        clean_whatsapp_id = '968' + clean_whatsapp_id.lstrip('0')
                
                # Only add if we have a valid-looking number
                if clean_whatsapp_id and len(clean_whatsapp_id) >= 11:
                    target_leads.append({
                        "whatsapp_id": clean_whatsapp_id,
                        "name": name,
                        "intent": intent,
                        "original_id": whatsapp_id
                    })
                    logger.info(f"✅ Added to broadcast: {clean_whatsapp_id}")
                else:
                    logger.warning(f"❌ Invalid WhatsApp ID: {whatsapp_id} -> {clean_whatsapp_id}")
        
        logger.info(f"🎯 Targeting {len(target_leads)} recipients for broadcast")
        
        if len(target_leads) == 0:
            return jsonify({
                "status": "no_recipients", 
                "sent": 0,
                "failed": 0,
                "total_recipients": 0,
                "message": "No valid recipients found for the selected segment"
            })
        
        # Send messages with delays
        sent_count = 0
        failed_count = 0
        failed_numbers = []
        
        for i, lead in enumerate(target_leads):
            try:
                # Add delay to avoid rate limiting (3 seconds between messages)
                if i > 0:
                    time.sleep(3)
                
                # Personalize message
                personalized_message = message
                if lead["name"] and lead["name"] not in ["", "Pending", "Unknown", "None"]:
                    personalized_message = f"Hello {lead['name']}! 👋\n\n{message}"
                
                logger.info(f"📤 Sending to {lead['whatsapp_id']} ({lead['name']})")
                
                # Send the message - USE SIMPLE TEXT MESSAGE FOR BROADCAST
                success = send_whatsapp_message(lead["whatsapp_id"], personalized_message)
                
                if success:
                    sent_count += 1
                    logger.info(f"✅ [{i+1}/{len(target_leads)}] Sent to {lead['whatsapp_id']}")
                else:
                    failed_count += 1
                    failed_numbers.append(lead['whatsapp_id'])
                    logger.error(f"❌ [{i+1}/{len(target_leads)}] Failed for {lead['whatsapp_id']}")
                    
            except Exception as e:
                failed_count += 1
                failed_numbers.append(lead['whatsapp_id'])
                logger.error(f"🚨 Error sending to {lead['whatsapp_id']}: {str(e)}")
        
        # Return results
        result = {
            "status": "broadcast_completed",
            "sent": sent_count,
            "failed": failed_count,
            "total_recipients": len(target_leads),
            "failed_numbers": failed_numbers,
            "message": f"Broadcast completed: {sent_count} sent, {failed_count} failed out of {len(target_leads)} total recipients"
        }
        
        logger.info(f"📬 Broadcast result: {result}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"💥 Broadcast error: {str(e)}")
        return jsonify({"error": f"Broadcast failed: {str(e)}"}), 500

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
            "interactive_lists": True,
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