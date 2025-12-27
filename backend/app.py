from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import smtplib
from email.mime.text import MIMEText
import os
from waitress import serve

BASE_URL = os.getenv("BASE_URL", "https://polyhouse-qqiy.onrender.com")


# ================= FLASK SETUP =================
app = Flask(__name__, static_folder='../frontend', static_url_path='/')
CORS(app)

# ================= DATABASE ====================
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://polyhouse:12345@cluster0.alfrvs9.mongodb.net/?appName=Cluster0"
)

client = MongoClient(MONGO_URI)
db = client["sensors"]
temp_collection = db["temperature_data"]
relay_collection = db["relay_control"]
users_collection = db["users"]

print("✅ MongoDB Connected")

# ================= TIMEZONE ====================
IST = timezone(timedelta(hours=5, minutes=30))

# ================= EMAIL CONFIG =================
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
ADMIN_EMAIL = "bhargavkola53@gmail.com"

def send_email(to, subject, message):
    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        print("📧 Email sent")
    except Exception as e:
        print("❌ Email error:", e)

# ================= FRONTEND ====================
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('../frontend', path)

# ================= HEALTH ======================
@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

# ================= SENSOR APIs =================
@app.route('/sensors/data', methods=['POST'])
def save_temp():
    try:
        data = request.get_json(force=True)
        temperature = data.get("temperature")

        if temperature is None:
            return jsonify({"error": "Temperature missing"}), 400

        temperature = float(temperature)
        now = datetime.now(timezone.utc)

        # Save temperature
        temp_collection.insert_one({
            "temperature": temperature,
            "timestamp": now
        })

        # ================= AUTO / MANUAL LOGIC =================
        relay2 = relay_collection.find_one({"device": "relay2"}) or {}
        relay3 = relay_collection.find_one({"device": "relay3"}) or {}

        relay2_mode = relay2.get("mode", "AUTO")
        relay3_mode = relay3.get("mode", "AUTO")

        exhaust_state = relay2.get("state", "OFF")
        sprinkler_state = relay3.get("state", "OFF")

        # AUTO control only if mode = AUTO
        if relay2_mode == "AUTO" or relay3_mode == "AUTO":

            if temperature > 28:
                exhaust_state = "ON"
                sprinkler_state = "ON"

            elif temperature > 25:
                exhaust_state = "ON"
                sprinkler_state = "OFF"

            else:
                exhaust_state = "OFF"
                sprinkler_state = "OFF"

            if relay2_mode == "AUTO":
                relay_collection.update_one(
                    {"device": "relay2"},
                    {"$set": {
                        "state": exhaust_state,
                        "timestamp": now
                    }},
                    upsert=True
                )

            if relay3_mode == "AUTO":
                relay_collection.update_one(
                    {"device": "relay3"},
                    {"$set": {
                        "state": sprinkler_state,
                        "timestamp": now
                    }},
                    upsert=True
                )

        return jsonify({
            "message": "Temperature processed",
            "temperature": temperature,
            "relay2": exhaust_state,
            "relay3": sprinkler_state
        }), 200

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500

# ================= SENSOR APIs =================
@app.route('/sensors/data', methods=['GET'])
def get_all_temp():
    data = list(
        temp_collection.find({}, {"_id": 0})
        .sort("timestamp", -1)
    )

    result = []
    for d in data:
        result.append({
            "waterTemperature": d.get("temperature"),
            "timestamp": d["timestamp"]
                .astimezone(IST)
                .strftime("%Y-%m-%d %H:%M:%S")
        })

    return jsonify(result), 200

@app.route('/sensors/latest', methods=['GET'])
def latest_temp():
    d = temp_collection.find_one(sort=[("timestamp", -1)])
    if not d:
        return jsonify({"waterTemperature": None}), 404

    return jsonify({
        "waterTemperature": d["temperature"],
        "timestamp": d["timestamp"].astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")
    })

# ================= RELAY APIs ==================
@app.route('/sensors/control/<device>', methods=['POST'])
def set_relay(device):
    data = request.get_json(force=True)
    state = data.get("state", "").upper()
    mode = data.get("mode", "MANUAL").upper()

    if state not in ["ON", "OFF"]:
        return jsonify({"error": "Invalid state"}), 400

    if mode not in ["AUTO", "MANUAL"]:
        mode = "MANUAL"

    relay_collection.update_one(
        {"device": device},
        {"$set": {
            "state": state,
            "mode": mode,
            "timestamp": datetime.now(timezone.utc)
        }},
        upsert=True
    )

    return jsonify({
        "message": f"{device} set to {state}",
        "mode": mode
    }), 200

@app.route('/sensors/control/<device>', methods=['GET'])
def get_relay(device):
    r = relay_collection.find_one({"device": device})

    if not r:
        return jsonify({
            "device": device,
            "state": "OFF",
            "mode": "AUTO"
        }), 200

    return jsonify({
        "device": device,
        "state": r.get("state", "OFF"),
        "mode": r.get("mode", "AUTO"),
        "timestamp": r["timestamp"].astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")
    })


# ================= AUTH ========================
@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json(force=True)
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not all([name, email, password]):
            return jsonify({"message": "All fields required"}), 400

        if users_collection.find_one({"email": email}):
            return jsonify({"message": "Email already exists"}), 409

        created_time = datetime.now(timezone.utc)

        users_collection.insert_one({
            "name": name,
            "email": email,
            "password": password,
            "status": "PENDING",
            "createdAt": created_time
        })

        review_link = f"{BASE_URL}/admin/review?email={email}"

        # ✅ EMAIL SHOULD NEVER BREAK SIGNUP
        try:
            if SMTP_EMAIL and SMTP_PASSWORD:
                send_email(
                    ADMIN_EMAIL,
                    "New User Approval Request",
                    f"""
New user signup request

Name: {name}
Email: {email}
Signup Time: {created_time.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S')}

Review user (Approve / Reject):
{review_link}
"""
                )
            else:
                print("⚠️ SMTP not configured, skipping email")
        except Exception as mail_err:
            print("⚠️ Email failed, but signup continues:", mail_err)

        return jsonify({
            "message": "Signup successful. Await admin approval."
        }), 201

    except Exception as e:
        print("❌ Signup error:", e)
        return jsonify({"message": "Internal server error"}), 500



@app.route('/admin/review')
def review_page():
    return send_from_directory('../frontend', 'admin-review.html')

@app.route('/admin/approve')
def approve():
    email = request.args.get("email")

    users_collection.update_one(
        {"email": email},
        {"$set": {
            "status": "APPROVED",
            "approvedAt": datetime.now(timezone.utc)
        }}
    )

    send_email(email, "Account Approved", "Your account is approved.")
    return "✅ User approved"

@app.route('/admin/reject')
def reject():
    email = request.args.get("email")

    users_collection.update_one(
        {"email": email},
        {"$set": {
            "status": "REJECTED",
            "rejectedAt": datetime.now(timezone.utc)
        }}
    )

    send_email(email, "Account Rejected", "Your signup request was rejected.")
    return "❌ User rejected"


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(force=True)
    email = data.get("email")
    password = data.get("password")

    user = users_collection.find_one({"email": email})

    if not user or user.get("password") != password:
        return jsonify({"message": "Invalid credentials"}), 401

    status = user.get("status", "PENDING")  # 🔥 SAFE ACCESS

    if status != "APPROVED":
        return jsonify({
            "verified": False,
            "message": "Your account is awaiting admin approval."
        }), 403

    return jsonify({
        "verified": True,
        "token": "dummy-token"
    }), 200


# ================= RUN =========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Server running on {port}")
    serve(app, host="0.0.0.0", port=port)
