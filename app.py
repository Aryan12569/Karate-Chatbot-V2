from flask import Flask, request, jsonify
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

# --- Google Sheets Setup ---
try:
    creds_dict = json.loads(os.environ['GOOGLE_CREDS_JSON'])
except Exception:
    raise ValueError("Invalid GOOGLE_CREDS_JSON. Paste full JSON.")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)

SHEET_NAME = "Subscribers"
sheet = gc.open(SHEET_NAME).sheet1

if sheet.row_count == 0:
    sheet.append_row(["Timestamp", "Name", "Contact", "WhatsApp ID", "Intent"])

# --- Helper functions ---
def format_row(name, contact, whatsapp_id, intent):
    return [datetime.now().strftime("%Y-%m-%d %H:%M"), name, contact, whatsapp_id, intent]

def keyword_answer(message):
    """
    Return answer based on keywords in the message.
    Can add multiple phrases per answer.
    """
    msg = message.lower()
    responses = {
        "location": ["where is the location", "where are you located", "address"],
        "contact": ["contact", "phone number", "call"],
        "about": ["about us", "who are you", "karate info"],
        "programs": ["programs", "courses", "classes"],
        "schedule": ["class schedule", "timing", "when are classes"],
        "membership": ["membership", "fees", "pricing"]
    }
    answers = {
        "location": "We are located at Muscat City Center, Oman.",
        "contact": "You can reach us at +968 1234 5678.",
        "about": "Karate Centre Muscat offers world-class karate training for all ages.",
        "programs": "We offer Beginner, Intermediate, and Advanced Karate Programs.",
        "schedule": "Classes run Monday to Friday, 5 PM to 8 PM.",
        "membership": "Membership starts at OMR 25/month."
    }
    for key, keywords in responses.items():
        if any(k in msg for k in keywords):
            return answers[key]
    return "Sorry, I didn't understand. You can ask about Location, Programs, Schedule, Membership, or Contact."

# --- Routes ---
@app.route("/api/leads", methods=["GET"])
def get_leads():
    try:
        data = sheet.get_all_records()
        return jsonify({"success": True, "leads": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/register", methods=["POST"])
def register_user():
    """
    JSON: { "name": "Aryan", "contact": "+96878505509", "whatsapp_id": "96878505509", "intent": "register_now" }
    """
    data = request.get_json()
    required_fields = ["name", "contact", "whatsapp_id", "intent"]
    if not all(field in data for field in required_fields):
        return jsonify({"success": False, "error": "Missing fields"}), 400

    sheet.append_row(format_row(data["name"], data["contact"], data["whatsapp_id"], data["intent"]))
    return jsonify({"success": True, "message": "User registered successfully"})

@app.route("/api/message", methods=["POST"])
def send_message():
    """
    JSON: { "segment": "register_now"/"register_later", "message_type": "offer"/"event", "message_text": "..." }
    """
    data = request.get_json()
    segment = data.get("segment")
    message_text = data.get("message_text")
    if not segment or not message_text:
        return jsonify({"success": False, "error": "Missing segment or message_text"}), 400

    leads = sheet.get_all_records()
    recipients = [lead for lead in leads if lead["Intent"].lower() == segment]
    # Here integrate with WhatsApp API
    sent_count = len(recipients)
    return jsonify({"success": True, "sent_count": sent_count, "message": message_text})

@app.route("/api/answer", methods=["POST"])
def answer_message():
    """
    JSON: { "message": "User's text" }
    """
    data = request.get_json()
    msg = data.get("message")
    if not msg:
        return jsonify({"success": False, "error": "Missing message"}), 400
    answer = keyword_answer(msg)
    return jsonify({"success": True, "answer": answer})

if __name__ == "__main__":
    app.run(debug=True)
