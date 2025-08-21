import os
import io
from typing import List, Dict, Optional

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from twilio.rest import Client as TwilioClient


# ==================================================
# Flask setup
# ==================================================
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB


# ==================================================
# Cloudflare R2 (S3 compatible)
# ==================================================
R2_BUCKET = os.getenv("R2_BUCKET")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)


# ==================================================
# Twilio WhatsApp
# ==================================================
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_WHATSAPP = os.getenv("TWILIO_WHATSAPP")  # e.g., 'whatsapp:+14155238886' or '+14155238886'
SITE_URL = os.getenv("SITE_URL", "")

twilio_client: Optional[TwilioClient] = None
if TWILIO_SID and TWILIO_AUTH:
    twilio_client = TwilioClient(TWILIO_SID, TWILIO_AUTH)


# ==================================================
# Helpers
# ==================================================
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

def normalize_sender(sender: str) -> str:
    """Ensure 'whatsapp:' prefix on sender if missing."""
    if not sender:
        return ""
    return sender if sender.startswith("whatsapp:") else f"whatsapp:{sender}"

def normalize_recipient(number: str) -> str:
    """Ensure recipient is in whatsapp:+<country><number> format if possible."""
    if not number:
        return ""
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"

def file_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    return ext if ext in ALLOWED_IMAGE_EXTS else ".jpg"

def key_name_phone_folder(prefix: str, phone: str) -> str:
    # Very light sanitization for folder naming
    phone_safe = "".join(ch for ch in (phone or "") if ch.isdigit() or ch in "+")
    return f"{prefix}/{phone_safe}/"

def list_s3(prefix: str) -> List[Dict]:
    objs: List[Dict] = []
    continuation = None
    while True:
        kwargs = {"Bucket": R2_BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if continuation:
            kwargs["ContinuationToken"] = continuation
        resp = s3.list_objects_v2(**kwargs)
        for item in resp.get("Contents", []):
            objs.append(item)
        if resp.get("IsTruncated"):
            continuation = resp.get("NextContinuationToken")
        else:
            break
    return objs

def read_text_object(key: str) -> str:
    try:
        obj = s3.get_object(Bucket=R2_BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8", errors="ignore")
    except ClientError:
        return ""


# ==================================================
# Routes: pages
# ==================================================
@app.route("/")
def home():
    return render_template("language.html")

@app.route("/index/<lang>")
def index(lang: str):
    return render_template("index.html", lang=lang)

@app.route("/missing")
def missing():
    return render_template("missing.html")

@app.route("/notifications")
def notifications():
    """Build a lightweight board by listing Missing/<phone>/ and grouping pN.* & pN.txt"""
    reports = []
    base_prefix = "Missing/"
    try:
        objects = list_s3(base_prefix)
        # Organize by phone + member code
        for obj in objects:
            key = obj["Key"]  # e.g., Missing/+919406210551/p2.jpg or p2_txt.txt
            parts = key.split("/")
            if len(parts) != 3:
                continue
            _, phone, filename = parts
            # Only consider image files named like pN.ext
            if not filename.startswith("p"):
                continue
            name_no_ext, ext = os.path.splitext(filename)
            if ext.lower() not in ALLOWED_IMAGE_EXTS:
                # could be a .txt description attached to same member
                continue
            desc_key = f"Missing/{phone}/{name_no_ext}.txt"
            reports.append({
                "phone": phone,
                "code": name_no_ext,  # 'p2'
                "desc": read_text_object(desc_key),
            })
    except Exception as e:
        print("Error loading board:", e)
    return render_template("notifications.html", reports=reports)


# ==================================================
# API: registration
# ==================================================
@app.route("/submit_registration", methods=["POST"])
def submit_registration():
    try:
        phone = (request.form.get("mobile") or "").strip()
        whatsapp = (request.form.get("whatsapp") or "").strip()
        secondary = (request.form.get("secondary") or "").strip()

        if not phone or not whatsapp:
            return jsonify({"status": "error", "message": "Mobile and WhatsApp are required."}), 400

        # Pull all incoming images under a single "photos" field
        incoming_files = request.files.getlist("photos")
        if not incoming_files:
            return jsonify({"status": "error", "message": "At least one photo is required."}), 400

        if len(incoming_files) > 20:
            return jsonify({"status": "error", "message": "Maximum 20 photos allowed."}), 400

        folder = key_name_phone_folder("Registration", phone)

        # Save each as p1.ext, p2.ext, ...
        for idx, f in enumerate(incoming_files, start=1):
            if not f or not getattr(f, "filename", None):
                continue
            ext = file_ext(f.filename)
            key = f"{folder}p{idx}{ext}"
            s3.upload_fileobj(f, R2_BUCKET, key)

        # Send WhatsApp confirmation (optional)
        if twilio_client and TWILIO_WHATSAPP:
            try:
                twilio_client.messages.create(
                    from_=normalize_sender(TWILIO_WHATSAPP),
                    to=normalize_recipient(whatsapp),
                    body=(
                        "✅ Registration successful!\n"
                        f"📞 Mobile: {phone}\n"
                        f"🔗 Reopen portal: {SITE_URL or f'https://{request.host}/'}"
                    ),
                )
            except Exception as tw_err:
                print("Twilio error:", tw_err)

        return jsonify({"status": "success", "message": "Registration completed."})
    except Exception as e:
        print("Registration error:", e)
        return jsonify({"status": "error", "message": "Server error during registration."}), 500


# ==================================================
# API: missing report
# ==================================================
@app.route("/submit_missing", methods=["POST"])
def submit_missing():
    """
    Input:
      - mobile (phone used at registration)
      - whatsapp
      - member_code (e.g., 'p2' OR 'p2.jpg'—we normalize to 'p2')
      - description (optional)
    Action:
      - find Registration/<phone>/p2.<ext>
      - copy to Missing/<phone>/p2.<ext>
      - write Missing/<phone>/p2.txt with description
    """
    try:
        phone = (request.form.get("mobile") or "").strip()
        whatsapp = (request.form.get("whatsapp") or "").strip()
        code_raw = (request.form.get("member_code") or "").strip().lower()
        description = (request.form.get("description") or "").strip()

        if not phone or not whatsapp or not code_raw:
            return jsonify({"status": "error", "message": "All fields are required."}), 400

        # Normalize member code to 'pN'
        # Accept 'p2' or 'p2.jpg' etc; we strip extension for matching
        member_code = code_raw.split(".")[0]  # 'p2'
        reg_folder = key_name_phone_folder("Registration", phone)
        miss_folder = key_name_phone_folder("Missing", phone)

        # Find a key in Registration/<phone>/ that starts with 'pN.' (any allowed ext)
        objects = list_s3(reg_folder)
        target_key = None
        for obj in objects:
            key = obj["Key"]  # e.g., Registration/+9194.../p2.jpg
            name = key.split("/")[-1]  # p2.jpg
            if not name.lower().startswith(member_code + "."):
                continue
            # Only accept allowed image extensions
            if os.path.splitext(name)[1].lower() in ALLOWED_IMAGE_EXTS:
                target_key = key
                break

        if not target_key:
            return jsonify({"status": "error", "message": "Member photo not found for the provided code."}), 404

        # Copy to Missing/<phone> with the same file name
        filename = target_key.split("/")[-1]  # p2.jpg
        copy_dest = f"{miss_folder}{filename}"
        try:
            s3.copy({"Bucket": R2_BUCKET, "Key": target_key}, R2_BUCKET, copy_dest)
        except ClientError as ce:
            print("Copy error:", ce)
            return jsonify({"status": "error", "message": "Unable to copy photo to Missing folder."}), 500

        # Write / overwrite description as p2.txt
        desc_key = f"{miss_folder}{member_code}.txt"
        try:
            s3.put_object(Bucket=R2_BUCKET, Key=desc_key, Body=description.encode("utf-8"))
        except ClientError as ce:
            print("Put description error:", ce)
            # Non-fatal; continue

        return jsonify({"status": "success", "message": "Missing report submitted."})
    except Exception as e:
        print("Missing report error:", e)
        return jsonify({"status": "error", "message": "Server error during missing report."}), 500


# ==================================================
# Main
# ==================================================
if __name__ == "__main__":
    # For local debugging; in Render you will run via gunicorn
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
