import os
from flask import Flask, render_template, request, jsonify
import boto3
from botocore.client import Config
from twilio.rest import Client
import traceback

app = Flask(__name__)

# ----------------------------
# Cloudflare R2 Setup
# ----------------------------
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

# ----------------------------
# Twilio WhatsApp Setup
# ----------------------------
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_WHATSAPP = os.getenv("TWILIO_WHATSAPP")

twilio_client = None
if TWILIO_SID and TWILIO_AUTH:
    twilio_client = Client(TWILIO_SID, TWILIO_AUTH)


@app.route("/")
def language():
    return render_template("language.html")


@app.route("/index/<lang>")
def index(lang):
    return render_template("index.html", lang=lang)


@app.route("/missing")
def missing():
    # Temporary placeholder until missing.html exists
    try:
        return render_template("missing.html")
    except:
        return "<h2>Missing report page coming soon...</h2>"


@app.route("/notifications")
def notifications():
    return render_template("notifications.html", reports=[])


# ----------------------------
# Registration Upload
# ----------------------------
@app.route("/submit_registration", methods=["POST"])
def submit_registration():
    try:
        # Fallback field handling
        mobile = request.form.get("mobile") or request.form.get("mobileNumber")
        whatsapp = request.form.get("whatsapp") or request.form.get("whatsappNumber")
        secondary = request.form.get("secondary") or request.form.get("secondaryContact")

        if not mobile or not whatsapp:
            return jsonify({"status": "error", "message": "Mobile and WhatsApp are required"}), 400

        folder = f"Registration/{mobile}/"

        # Save uploaded photos
        incoming_files = request.files.getlist("photos") or request.files.getlist("photos[]")
        for idx, file in enumerate(incoming_files):
            if file:
                ext = os.path.splitext(file.filename)[1] or ".jpg"
                filename = f"p{idx+1}{ext}"
                s3.upload_fileobj(file, R2_BUCKET, folder + filename)

        # WhatsApp confirmation
        if twilio_client:
            try:
                twilio_client.messages.create(
                    from_=f"whatsapp:{TWILIO_WHATSAPP}",
                    to=f"whatsapp:{whatsapp}",
                    body=f"✅ Registration successful!\nReopen: https://{request.host}/index/en",
                )
            except Exception as twilio_err:
                print("Twilio error:", twilio_err)

        return jsonify({"status": "success"})

    except Exception as e:
        print("Registration error:", e)
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------
# Missing Report
# ----------------------------
@app.route("/submit_missing", methods=["POST"])
def submit_missing():
    try:
        phone = request.form.get("mobile") or request.form.get("mobileNumber")
        whatsapp = request.form.get("whatsapp") or request.form.get("whatsappNumber")
        member_code = request.form.get("member_code")
        description = request.form.get("description", "")

        if not phone or not whatsapp or not member_code:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        reg_folder = f"Registration/{phone}/"
        miss_folder = f"Missing/{phone}/"

        # Copy missing member photo
        objects = s3.list_objects_v2(Bucket=R2_BUCKET, Prefix=reg_folder)
        if "Contents" in objects:
            for obj in objects["Contents"]:
                if obj["Key"].endswith(member_code):
                    copy_source = {"Bucket": R2_BUCKET, "Key": obj["Key"]}
                    s3.copy(copy_source, R2_BUCKET, miss_folder + member_code)

        # Save description
        desc_key = miss_folder + member_code.replace(".", "_") + ".txt"
        s3.put_object(Bucket=R2_BUCKET, Key=desc_key, Body=description)

        return jsonify({"status": "success"})

    except Exception as e:
        print("Missing report error:", e)
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
