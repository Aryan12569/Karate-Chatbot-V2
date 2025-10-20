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

def send_whatsapp_message(to, message):
    """Send WhatsApp message via Meta API - SIMPLIFIED VERSION"""
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
        
        # Simple text message - NO BUTTONS for broadcast
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_to,
            "type": "text",
            "text": {
                "body": message
            }
        }

        logger.info(f"📤 Sending broadcast to: {clean_to}")
        logger.info(f"Message: {message[:50]}...")
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response_data = response.json()
        
        if response.status_code == 200:
            logger.info(f"✅ Broadcast sent successfully to {clean_to}")
            return True
        else:
            error_message = response_data.get('error', {}).get('message', 'Unknown error')
            logger.error(f"❌ Broadcast failed for {clean_to}: {error_message}")
            return False
        
    except Exception as e:
        logger.error(f"🚨 Broadcast error for {to}: {str(e)}")
        return False

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
    """Handle incoming WhatsApp messages"""
    try:
        data = request.get_json()
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return jsonify({"status": "no_message"})
            
        message = messages[0]
        phone_number = message["from"]
        
        # Handle interactive button clicks
        if "interactive" in message:
            button_id = message["interactive"]["button_reply"]["id"]
            logger.info(f"Button clicked: {button_id} by {phone_number}")
            
            if button_id == "register_later":
                if sheet:
                    add_lead_to_sheet("Pending", "Pending", "Register Later", phone_number)
                return jsonify({"status": "register_later_saved"})
            
            return jsonify({"status": "button_handled"})
        
        # Handle text messages
        if "text" in message:
            text = message["text"]["body"].strip()
            
            # Send welcome message for any text
            send_whatsapp_message(phone_number, 
                "International Karate Centre – Al Maabelah\n\n"
                "Welcome. Select an option.\n\n"
                "Excellence • Discipline • Respect")
            
            return jsonify({"status": "welcome_sent"})
        
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
        "sheets_available": sheet is not None
    }
    return jsonify(status)

# ==============================
# RUN APPLICATION
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)