
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import boto3
from botocore.config import Config
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- S3 Client Setup (Cloudflare R2 / AWS S3 compatible) ---
s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT"),
    aws_access_key_id=os.getenv("S3_KEY"),
    aws_secret_access_key=os.getenv("S3_SECRET"),
    region_name=os.getenv("S3_REGION","auto"),
    config=Config(signature_version="s3v4")
)
BUCKET = os.getenv("S3_BUCKET")
URL_EXPIRY = int(os.getenv("S3_URL_EXPIRY", "3600"))  # seconds

MAX_PICS = 20
VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

def safe_ext(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext if ext in VALID_EXTS else ".jpeg"

def save_to_s3(file, folder, filename):
    key = f"{folder}/{filename}"
    s3.upload_fileobj(file, BUCKET, key)
    return key

def presign(key):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=URL_EXPIRY
    )

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/register', methods=['POST'])
def register():
    phone = (request.form.get('phone') or '').strip()
    whatsapp = (request.form.get('whatsapp') or '').strip()
    secondary = (request.form.get('secondary') or '').strip()

    photos = request.files.getlist("family_photos")

    # Enforce max 20 and rename to p1..p20 preserving/normalizing extension
    for idx, f in enumerate(photos[:MAX_PICS], start=1):
        if not f or not getattr(f, "filename", ""):
            continue
        ext = safe_ext(f.filename)
        filename = f"p{idx}{ext}"
        save_to_s3(f, f"Registration/{phone}", filename)

    return redirect(url_for('index'))

@app.route('/report', methods=['GET','POST'])
def report():
    if request.method == 'POST':
        phone = (request.form.get('phone') or '').strip()
        whatsapp = (request.form.get('whatsapp') or '').strip()
        missing_code = (request.form.get('missing_code') or '').strip().lower()  # e.g., p2
        desc = (request.form.get('description') or '')

        # Try possible extensions (we saved normalized but allow any valid ext)
        src_key = None
        for ext in [".jpeg", ".jpg", ".png", ".webp"]:
            candidate = f"Registration/{phone}/{missing_code}{ext}"
            try:
                s3.head_object(Bucket=BUCKET, Key=candidate)
                src_key = candidate
                break
            except Exception:
                continue

        if not src_key:
            # fall back: assume .jpeg
            src_key = f"Registration/{phone}/{missing_code}.jpeg"

        dst_key = f"MissingReport/{phone}/{missing_code}.jpeg"
        copy_source = {'Bucket': BUCKET, 'Key': src_key}
        s3.copy(copy_source, BUCKET, dst_key)

        if desc:
            s3.put_object(Bucket=BUCKET, Key=f"MissingReport/{phone}/{missing_code}.txt", Body=desc.encode())

        return redirect(url_for('index'))
    return render_template("report.html")

@app.route('/notifications')
def notifications():
    prefix = "MissingReport/"
    items = []
    continuation = None
    while True:
        kwargs = dict(Bucket=BUCKET, Prefix=prefix, MaxKeys=1000)
        if continuation:
            kwargs["ContinuationToken"] = continuation
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get('Contents', []):
            key = obj['Key']
            if key.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                parts = key.split("/")
                if len(parts) >= 3:
                    phone = parts[1]
                    filename = parts[2]
                    items.append({
                        "phone": phone,
                        "file": filename,
                        "timestamp": obj['LastModified'].isoformat(),
                        "url": presign(key)
                    })
        if resp.get("IsTruncated"):
            continuation = resp.get("NextContinuationToken")
        else:
            break
    # Newest first
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify(items)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
