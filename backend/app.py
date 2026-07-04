from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from dotenv import load_dotenv
import json
import os
import sys
import subprocess
import urllib.request
import uuid
import webbrowser
import threading
from functools import wraps
from io import BytesIO
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

from database import (
    test_connection,
    save_bill,
    get_all_bills,
    get_recent_bills,
    get_dashboard_stats,
    delete_bill,
    ensure_users_table,
    get_user_by_username,
    create_user
)

from ocr import scan_bill
from predictor import predict


# =========================================================
# APP SETUP
# =========================================================
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# In local dev, app.py lives in backend/ and frontend/ is a sibling
# directory (../frontend). In the Docker image, the Dockerfile copies
# backend/'s contents directly into /app and frontend/ into /app/frontend,
# so app.py and frontend/ end up in the SAME directory instead.
# Check both locations so this works in either layout.
_FRONTEND_CANDIDATES = [
    os.path.join(BASE_DIR, "frontend"),
    os.path.abspath(os.path.join(BASE_DIR, os.pardir, "frontend")),
]
FRONTEND_FOLDER = next(
    (path for path in _FRONTEND_CANDIDATES if os.path.isdir(path)),
    _FRONTEND_CANDIDATES[-1],
)

app = Flask(
    __name__,
    static_folder=FRONTEND_FOLDER,
    static_url_path=""
)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret")
app.config["SESSION_COOKIE_HTTPONLY"] = True
CORS(app)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    os.getenv("UPLOAD_FOLDER", "uploads")
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = int(
    os.getenv("MAX_FILE_SIZE_MB", 10)
) * 1024 * 1024


def ensure_default_user():
    default_username = os.getenv("DEFAULT_ADMIN_USER", "admin")
    default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "billwise123")

    if not default_username or not default_password:
        return

    try:
        user = get_user_by_username(default_username)
        if user:
            return

        password_hash = generate_password_hash(default_password)
        create_user(default_username, password_hash)
        print("Default admin user created:", default_username)
    except Exception as error:
        print("Unable to create default user:", error)


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("username"):
            return func(*args, **kwargs)
        return jsonify({"error": "Authentication required."}), 401
    return wrapper


# Ensure auth tables exist before requests are handled
ensure_users_table()
ensure_default_user()


ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"
}


# =========================================================
# HELPER FUNCTIONS
# =========================================================
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_uploaded_image(file):
    """
    Saves an uploaded image in uploads folder.
    Converts all supported images to JPG.
    Returns saved filename.
    """

    if not file or file.filename == "":
        raise ValueError("No image selected")

    if not allowed_file(file.filename):
        raise ValueError(
            "Only PNG, JPG, JPEG, GIF, BMP, TIFF and WEBP images are allowed"
        )

    file.stream.seek(0)
    file_bytes = file.read()

    if not file_bytes:
        raise ValueError("Selected image is empty")

    max_size = app.config["MAX_CONTENT_LENGTH"]

    if len(file_bytes) > max_size:
        raise ValueError("Image is too large. Maximum allowed size is 10 MB")

    try:
        image = Image.open(BytesIO(file_bytes))
        image.load()
        image = image.convert("RGB")

    except Exception as primary_error:
        print("Primary image open error:", primary_error)

        try:
            parser = ImageFile.Parser()
            parser.feed(file_bytes)
            image = parser.close()
            image.load()
            image = image.convert("RGB")
        except Exception as parser_error:
            print("Parser image open error:", parser_error)
            raise ValueError(
                "Unable to read this image. Please upload a valid bill image. "
                "If the file is already an image, try a different JPG/PNG file."
            )

    # Cap dimensions before saving. Modern phone cameras routinely shoot
    # 3000-4000px+ photos; there's no OCR benefit beyond ~2000px on the
    # long edge, and every extra pixel costs disk I/O, decode time, and
    # memory - all of which matter a lot on a slow/free hosting tier.
    MAX_DIMENSION = 2000
    if max(image.size) > MAX_DIMENSION:
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    saved_name = f"{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        saved_name
    )

    image.save(save_path, "JPEG", quality=90)

    print("Image saved successfully:", save_path)

    return saved_name, save_path


def fetch_exchange_rate(from_currency: str, to_currency: str = "USD"):
    try:
        url = (
            f"https://api.exchangerate.host/convert?from={from_currency}"
            f"&to={to_currency}&amount=1"
        )
        with urllib.request.urlopen(url, timeout=4) as response:
            data = json.load(response)

        rate = data.get("info", {}).get("rate")
        return float(rate) if rate else None

    except Exception as error:
        print("Currency conversion API error:", error)
        return None


def convert_amount(amount, currency: str, target_currency: str = "USD"):
    try:
        rate = fetch_exchange_rate(currency.upper(), target_currency.upper())
        if rate is None:
            return None
        return float(amount) * rate
    except Exception as error:
        print("Currency conversion error:", error)
        return None


def scan_image_and_predict(image_path, filename):
    """
    Runs OCR and category prediction.
    Always returns JSON-safe values.
    """

    print("\n========== STARTING OCR ==========")
    print("Image path:", image_path)

    result = scan_bill(image_path)

    print("OCR RESULT:", result)

    extracted_text = result.get("extracted_text", "")
    shop_name = result.get("shop_name", "Unknown")
    bill_date = result.get("bill_date", "")
    amount = result.get("amount", None)
    currency = result.get("currency", "INR")

    # NOTE: USD conversion used to call an external exchange-rate API
    # (fetch_exchange_rate -> urlopen, up to a 4s timeout) synchronously
    # on every single scan, even though the frontend never displays this
    # value. That network round trip was the single biggest contributor
    # to "slow" scans. It is now skipped during scanning entirely - OCR
    # results return immediately.
    converted_amount_usd = None
    converted_amount_usd_formatted = None

    # Category prediction
    try:
        prediction = predict(f"{shop_name} {extracted_text}")

        print("PREDICTION RESULT:", prediction)

        if isinstance(prediction, dict):
            category = prediction.get("category", "Other")
            confidence = prediction.get("confidence", 0)
        else:
            category = "Other"
            confidence = 0

    except Exception as prediction_error:
        print("Prediction error:", prediction_error)

        category = "Other"
        confidence = 0

    # Make confidence JSON safe
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0.0

    # Make amount JSON safe
    try:
        if amount is not None:
            amount = float(amount)
    except (ValueError, TypeError):
        amount = None

    response = {
        "success": True,
        "filename": filename,
        "shop_name": shop_name or "Unknown",
        "bill_date": bill_date or "",
        "amount": amount,
        "amount_found": amount is not None,
        "currency": currency or "INR",
        "converted_amount_usd": converted_amount_usd,
        "converted_amount_usd_formatted": converted_amount_usd_formatted,
        "extracted_text": extracted_text or "",
        "category": category or "Other",
        "confidence": confidence
    }

    print("RETURNING RESPONSE:", response)
    print("==================================\n")

    return response


# =========================================================
# BASIC ROUTES
# =========================================================
@app.route("/")
def home():
    return app.send_static_file("login.html")


@app.route("/api/health", methods=["GET"])
def health():
    try:
        db_ok = test_connection()

        return jsonify({
            "status": "ok",
            "version": "1.0.0",
            "database": "connected" if db_ok else "error"
        })

    except Exception as error:
        print("Health check error:", error)

        return jsonify({
            "status": "error",
            "database": "error",
            "error": str(error)
        }), 500


# =========================================================
# OLD UPLOAD ROUTE
# This supports old frontend flow:
# POST /api/upload -> returns filename
# =========================================================
@app.route("/api/upload", methods=["POST"])
def upload_bill():
    try:
        print("\n========== UPLOAD REQUEST ==========")

        if "bill_image" not in request.files:
            return jsonify({
                "error": "No file received. Expected field name: bill_image"
            }), 400

        file = request.files["bill_image"]

        filename, _ = save_uploaded_image(file)

        return jsonify({
            "success": True,
            "message": "Image uploaded successfully",
            "filename": filename
        }), 200

    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 400

    except Exception as error:
        print("Upload error:", error)

        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# SCAN ROUTE
#
# Supports BOTH:
#
# NEW FRONTEND:
# FormData with bill_image directly
#
# OLD FRONTEND:
# JSON { "filename": "abc.jpg" }
# =========================================================
@app.route("/api/scan", methods=["POST"])
def scan():
    try:
        print("\n========== SCAN REQUEST RECEIVED ==========")
        print("Content-Type:", request.content_type)

        # -------------------------------------------------
        # METHOD 1: Current frontend sends image directly
        # -------------------------------------------------
        if "bill_image" in request.files:
            file = request.files["bill_image"]

            print("Direct image received:", file.filename)

            filename, image_path = save_uploaded_image(file)

            print("Calling scan_image_and_predict()...")

            response = scan_image_and_predict(
                image_path,
                filename
            )

            print("Returned from scan_image_and_predict()")
            print(response)

            return jsonify(response), 200

        # -------------------------------------------------
        # METHOD 2: Old frontend sends filename as JSON
        # -------------------------------------------------
        data = request.get_json(silent=True) or {}

        filename = data.get("filename", "")

        if not filename:
            return jsonify({
                "error": (
                    "No bill image received. Send bill_image as FormData "
                    "or filename as JSON."
                )
            }), 400

        filename = secure_filename(filename)

        image_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        if not os.path.exists(image_path):
            return jsonify({
                "error": f"File not found: {filename}"
            }), 404

        print("Calling scan_image_and_predict()...")

        response = scan_image_and_predict(
            image_path,
            filename
        )

        print("Returned from scan_image_and_predict()")
        print(response)

        return jsonify(response), 200

    except ValueError as error:
        print("Scan validation error:", error)

        return jsonify({
            "error": str(error)
        }), 400

    except Exception as error:
        print("\n========== SCAN BACKEND ERROR ==========")
        print(error)
        print("========================================\n")

        return jsonify({
            "error": str(error)
        }), 500

# =========================================================
# PREDICT CATEGORY ONLY
# =========================================================
@app.route("/api/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        confirm_password = (data.get("confirm_password") or "").strip()

        if not username or not password or not confirm_password:
            return jsonify({"error": "Username, password, and confirmation are required."}), 400

        if password != confirm_password:
            return jsonify({"error": "Passwords do not match."}), 400

        if get_user_by_username(username):
            return jsonify({"error": "Username already exists."}), 400

        password_hash = generate_password_hash(password)
        create_user(username, password_hash)

        session["username"] = username
        return jsonify({"success": True, "username": username}), 201

    except Exception as error:
        print("Signup error:", error)
        return jsonify({"error": str(error)}), 500


@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        if not username or not password:
            return jsonify({"error": "Username and password are required."}), 400

        user = get_user_by_username(username)
        if not user:
            return jsonify({"error": "Invalid username or password."}), 401

        if not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid username or password."}), 401

        session["username"] = username
        return jsonify({"success": True, "username": username}), 200

    except Exception as error:
        print("Login error:", error)
        return jsonify({"error": str(error)}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    return jsonify({"success": True, "message": "Logged out."}), 200


@app.route("/api/predict", methods=["POST"])
def predict_only():
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")

        result = predict(text)

        return jsonify(result)

    except Exception as error:
        print("Predict error:", error)

        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# SAVE BILL TO DATABASE
# =========================================================
@app.route("/api/save", methods=["POST"])
@login_required
def save():
    try:
        data = request.get_json(silent=True) or {}

        image_name = data.get("image_name", "")
        shop_name = data.get("shop_name", "Unknown")
        bill_date = data.get("bill_date", "")
        amount = data.get("amount", 0)
        extracted_text = data.get("extracted_text", "")
        category = data.get("category", "Other")
        confidence = data.get("confidence", 0.0)

        if not image_name:
            return jsonify({
                "error": "image_name is required"
            }), 400

        try:
            amount = float(amount) if amount else 0.0
        except (ValueError, TypeError):
            amount = 0.0

        try:
            confidence = float(confidence) if confidence else 0.0
        except (ValueError, TypeError):
            confidence = 0.0

        bill_id = save_bill(
            image_name,
            shop_name,
            bill_date,
            amount,
            extracted_text,
            category,
            confidence
        )

        return jsonify({
            "success": True,
            "message": "Bill saved successfully",
            "id": bill_id
        }), 200

    except Exception as error:
        print("Save bill error:", error)

        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# VIEW UPLOADED IMAGE
# =========================================================
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# =========================================================
# BILL HISTORY
# =========================================================
@app.route("/api/bills", methods=["GET"])
@login_required
def list_bills():
    try:
        bills = get_all_bills(
            search=request.args.get("search", ""),
            category=request.args.get("category", "")
        )

        for bill in bills:
            bill["amount"] = float(bill.get("amount", 0) or 0)
            bill["confidence"] = float(
                bill.get("confidence", 0) or 0
            )

            if bill.get("created_at"):
                bill["created_at"] = str(bill["created_at"])

        return jsonify({
            "bills": bills
        })

    except Exception as error:
        print("List bills error:", error)

        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# DELETE BILL
# =========================================================
@app.route("/api/bills/<int:bill_id>", methods=["DELETE"])
@login_required
def remove_bill(bill_id):
    try:
        deleted = delete_bill(bill_id)

        if deleted:
            return jsonify({
                "success": True,
                "message": "Bill deleted"
            })

        return jsonify({
            "error": "Bill not found"
        }), 404

    except Exception as error:
        print("Delete bill error:", error)

        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# DASHBOARD
# =========================================================
@app.route("/api/dashboard", methods=["GET"])
@login_required
def dashboard():
    try:
        stats = get_dashboard_stats()

        stats["total_spending"] = float(
            stats.get("total_spending", 0) or 0
        )

        stats["this_month_spending"] = float(
            stats.get("this_month_spending", 0) or 0
        )

        for item in stats.get("category_spending", []):
            # Your database is returning amount, not total.
            # This ensures dashboard charts get both values.
            value = item.get("total", item.get("amount", 0))
            item["total"] = float(value or 0)

        for item in stats.get("monthly_spending", []):
            value = item.get("total", item.get("amount", 0))
            item["total"] = float(value or 0)

        for bill in stats.get("recent_bills", []):
            bill["amount"] = float(bill.get("amount", 0) or 0)

            if bill.get("created_at"):
                bill["created_at"] = str(bill["created_at"])

        return jsonify(stats)

    except Exception as error:
        print("Dashboard error:", error)

        return jsonify({
            "error": str(error)
        }), 500


# =========================================================
# START SERVER
# =========================================================
def open_browser(url):
    try:
        if sys.platform.startswith("win"):
            subprocess.run(["cmd", "/c", "start", "", url], check=False)
        else:
            webbrowser.open(url, new=2)
    except Exception as error:
        print("Unable to open browser automatically:", error)


if __name__ == "__main__":
    url = "http://127.0.0.1:5000"

    print("\n========================================")
    print("BillWise AI Backend Started")
    print("Backend URL:")
    print(url)
    print("========================================\n")
    print("Click the URL above to open the app in your browser.")

    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.0, open_browser, args=(url,)).start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )