import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import boto3
from twilio.rest import Client

# ------------------- CONFIG -------------------
app = Flask(__name__)

# Cloudflare R2 (S3 compatible)
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET = os.getenv("R2_BUCKET")

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY
)

# Twilio WhatsApp
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_WHATSAPP = os.getenv("TWILIO_WHATSAPP")  # e.g. "whatsapp:+14155238886"

# ------------------- ROUTES -------------------

@app.route("/")
def language():
    return render_template("language.html")

@app.route("/index/<lang>")
def index(lang):
    return render_template("index.html", lang=lang)

@app.route("/register", methods=["POST"])
def register():
    try:
        phone = request.form.get("phone")
        whatsapp = request.form.get("whatsapp")
        secondary = request.form.get("secondary")

        if not phone or not whatsapp:
            return jsonify({"status": "error", "message": "Phone and WhatsApp are required"}), 400

        photos = request.files.getlist("photos")
        uploaded = []

        for idx, file in enumerate(photos):
            if file and file.filename:  # ✅ skip empty slots
                ext = os.path.splitext(file.filename)[1] or ".jpg"
                filename = f"p{idx+1}{ext}"
                key = f"Registration/{phone}/{filename}"
                s3.upload_fileobj(file, R2_BUCKET, key)
                uploaded.append(filename)

        # ✅ WhatsApp confirmation
        if TWILIO_SID and TWILIO_AUTH and TWILIO_WHATSAPP:
            client = Client(TWILIO_SID, TWILIO_AUTH)
            msg = f"✅ Registration successful!\n\nPhone: {phone}\nUploaded: {len(uploaded)} photos.\n\nReopen portal: https://people-registration-r2-thumbs.onrender.com"
            client.messages.create(
                from_=TWILIO_WHATSAPP,
                body=msg,
                to=f"whatsapp:+{whatsapp}"
            )

        return jsonify({"status": "success", "message": "Registration complete", "photos": uploaded})

    except Exception as e:
        app.logger.error(f"Registration error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/report_missing", methods=["GET", "POST"])
def report_missing():
    if request.method == "GET":
        return render_template("report_missing.html")

    try:
        phone = request.form.get("phone")
        whatsapp = request.form.get("whatsapp")
        missing_code = request.form.get("missing_code")

        if not phone or not missing_code:
            return jsonify({"status": "error", "message": "Phone and missing code are required"}), 400

        # Copy file from registration to missing folder
        src_key = f"Registration/{phone}/{missing_code}"
        dst_key = f"Missing/{phone}/{missing_code}"

        copy_source = {"Bucket": R2_BUCKET, "Key": src_key}
        s3.copy(copy_source, R2_BUCKET, dst_key)

        return jsonify({"status": "success", "message": f"{missing_code} reported missing"})

    except Exception as e:
        app.logger.error(f"Missing report error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/board")
def board():
    # TODO: List missing reports from R2
    return render_template("board.html")


# ------------------- MAIN -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
