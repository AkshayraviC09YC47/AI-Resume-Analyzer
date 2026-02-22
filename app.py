import os
import json
import requests
from flask import Flask, render_template, request, redirect, url_for, make_response, Response
from werkzeug.utils import secure_filename

from resume_parser import extract_text_from_pdf
from ollama_client import analyze_resume
from prompts import ats_prompt
from config import SECRET_KEY, UPLOAD_FOLDER, DB_PATH, SERVER_IP, SERVER_PORT, OLLAMA_URL, OLLAMA_MODEL
from database import ensure_db, save_resume_to_history, get_user_by_credentials, get_user_history, delete_user_history_entry
from auth import generate_jwt, verify_jwt, get_current_user

# Flask app configuration
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database on startup
ensure_db()

ALLOWED_EXTENSIONS = {'pdf'}


# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# =====================================================================
# ROUTES
# =====================================================================

@app.route("/", methods=["GET", "POST"])
def login():
    """Handle user login."""
    # Check if user is already logged in
    payload = get_current_user()
    if payload:
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            return render_template("index.html", error="Username and password required")

        user = get_user_by_credentials(username, password)

        if user:
            token = generate_jwt(username)
            resp = make_response(redirect(url_for("dashboard")))
            resp.set_cookie("token", token, httponly=True, samesite="Lax", max_age=1800)
            return resp

        return render_template("index.html", error="Invalid credentials")

    return render_template("index.html")


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """Handle resume upload and analysis."""
    payload = get_current_user()
    if not payload:
        return redirect(url_for("login"))

    if request.method == "POST":
        # Validate file upload
        if 'resume' not in request.files:
            return render_template("dashboard.html", 
                                 error="No file uploaded", 
                                 payload=payload)
        
        file = request.files["resume"]
        
        if file.filename == '':
            return render_template("dashboard.html", 
                                 error="No file selected", 
                                 payload=payload)
        
        if not allowed_file(file.filename):
            return render_template("dashboard.html", 
                                 error="Only PDF files are allowed", 
                                 payload=payload)

        try:
            # Save and process file
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            # Extract and analyze
            resume_text = extract_text_from_pdf(filepath)
            result = analyze_resume(ats_prompt(resume_text))

            # Save to history
            save_resume_to_history(payload["sub"], filename, result)

            return render_template("dashboard.html", result=result, payload=payload)
        
        except Exception as e:
            print(f"Error processing resume: {e}")
            return render_template("dashboard.html", 
                                 error="Error processing resume. Please try again.", 
                                 payload=payload)

    return render_template("dashboard.html", payload=payload)


@app.route("/history")
def history():
    """Display user's resume analysis history."""
    payload = get_current_user()
    if not payload:
        return redirect(url_for("login"))

    rows = get_user_history(payload["sub"])
    return render_template("history.html", payload=payload, history=rows)


@app.route("/history/delete/<int:rid>", methods=["POST"])
def delete_history(rid):
    """Delete a specific resume history entry."""
    payload = get_current_user()
    if not payload:
        return redirect(url_for("login"))

    delete_user_history_entry(rid, payload["sub"])
    return redirect(url_for("history"))


@app.route("/analyze-stream", methods=["POST"])
def analyze_stream():
    """Stream resume analysis results in real-time."""
    payload = get_current_user()
    if not payload:
        return Response("Unauthorized", status=401)

    # Validate file upload
    if 'resume' not in request.files:
        return Response("No file uploaded", status=400)
    
    file = request.files["resume"]
    
    if file.filename == '' or not allowed_file(file.filename):
        return Response("Invalid file", status=400)

    try:
        # Save and process file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        resume_text = extract_text_from_pdf(filepath)
        prompt = ats_prompt(resume_text)

        def stream():
            """Generator function for streaming response."""
            data = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True
            }

            try:
                r = requests.post(OLLAMA_URL, json=data, stream=True, timeout=60)
                r.raise_for_status()
                
                final_output = []

                for line in r.iter_lines():
                    if line:
                        chunk = json.loads(line.decode())
                        if "response" in chunk:
                            text = chunk["response"]
                            final_output.append(text)
                            yield text

                # Save complete result to history
                save_resume_to_history(payload["sub"], filename, "".join(final_output))

            except requests.RequestException as e:
                print(f"Error streaming from Ollama: {e}")
                yield f"Error: {str(e)}"

        return Response(stream(), mimetype="text/event-stream")
    
    except Exception as e:
        print(f"Error in analyze_stream: {e}")
        return Response(f"Error: {str(e)}", status=500)


@app.route("/logout")
def logout():
    """Handle user logout."""
    resp = make_response(redirect(url_for("login")))
    resp.delete_cookie("token")
    return resp


# =====================================================================
# ERROR HANDLERS
# =====================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template("500.html"), 500


# =====================================================================
# MAIN
# =====================================================================

if __name__ == "__main__":
    print(f"[*] Starting server on {SERVER_IP}:{SERVER_PORT}")
    
    try:
        from waitress import serve
        print("[*] Using Waitress production server")
        serve(app, host=SERVER_IP, port=SERVER_PORT)
    except ImportError:
        print("[!] Waitress not found, falling back to Flask dev server")
        print("[!] WARNING: Dev server should not be used in production")
        app.run(host=SERVER_IP, port=SERVER_PORT, debug=False)
