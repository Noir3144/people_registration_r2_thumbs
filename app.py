import os
import boto3
from flask import Flask, render_template, request, redirect, url_for, session
from twilio.rest import Client
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "devkey")

# --- Cloudflare R2 setup ---
s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT"),
    aws_access_key_id=os.getenv("S3_KEY"),
    aws_secret_access_key=os.getenv("S3_SECRET"),
    region_name=os.getenv("S3_REGION", "auto"),
)
BUCKET = os.getenv("S3_BUCKET", "people-registration")

# --- Twilio setup ---
twilio_sid = os.getenv("TWILIO_SID")
twilio_auth = os.getenv("TWILIO_AUTH")
twilio_whatsapp = os.getenv("TWILIO_WHATSAPP")
twilio_client = Client(twilio_sid, twilio_auth)

SITE_URL = os.getenv("SITE_URL", "https://people-registration-r2-thumbs.onrender.com")

# ---------------- Routes ----------------
@app.route("/")
def language():
    return render_template("language.html")

@app.route("/set_language/<lang>")
def set_language(lang):
    session["lang"] = lang
    return redirect(url_for("index"))

@app.route("/index")
def index():
    return render_template("index.html", lang=session.get("lang", "English"))

@app.route("/register", methods=["POST"])
def register():
    mobile = request.form.get("mobile")
    whatsapp = request.form.get("whatsapp")
    secondary = request.form.get("secondary")
    folder = f"Registration/{mobile}/"

    # Save up to 20 uploaded photos
    for i in range(1, 21):
        file = request.files.get(f"photo{i}")
        if file and file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
            filename = f"p{i}.{ext}"
            key = folder + filename
            s3.upload_fileobj(file, BUCKET, key)

    # Send WhatsApp confirmation
    try:
        twilio_client.messages.create(
            from_=twilio_whatsapp,
            body=f"✅ Registration successful!\nReopen portal: {SITE_URL}",
            to=f"whatsapp:+91{whatsapp}"
        )
    except Exception as e:
        print("Twilio error:", e)

    return "✅ Registration successful!"

@app.route("/report", methods=["GET", "POST"])
def report():
    if request.method == "POST":
        mobile = request.form.get("mobile")
        whatsapp = request.form.get("whatsapp")
        member_code = request.form.get("missing")
        desc = request.form.get("desc", "")

        src_key = f"Registration/{mobile}/{member_code}.jpg"
        dst_folder = f"Missing/{mobile}/"
        dst_key = dst_folder + f"{member_code}.jpg"
        txt_key = dst_folder + f"{member_code}.txt"

        # Copy the missing member photo to Missing/
        try:
            s3.copy_object(Bucket=BUCKET, CopySource={"Bucket": BUCKET, "Key": src_key}, Key=dst_key)
            s3.put_object(Bucket=BUCKET, Key=txt_key, Body=desc.encode("utf-8"))
        except Exception as e:
            return f"Error: {e}"

        return "🚨 Missing report filed!"
    return render_template("report.html")

@app.route("/board")
def board():
    reports = []
    try:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix="Missing/")
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].endswith(".txt"):
                    phone = obj["Key"].split("/")[1]
                    member_code = obj["Key"].split("/")[-1].replace(".txt", "")
                    desc = s3.get_object(Bucket=BUCKET, Key=obj["Key"])["Body"].read().decode("utf-8")
                    reports.append({"phone": phone, "code": member_code, "desc": desc})
    except Exception as e:
        print("Board error:", e)

    return render_template("board.html", reports=reports)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
