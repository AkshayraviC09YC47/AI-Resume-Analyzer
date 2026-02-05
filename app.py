import os
import sqlite3
import jwt
import datetime
from flask import Flask, render_template, request, redirect, url_for, make_response
from werkzeug.utils import secure_filename

from resume_parser import extract_text_from_pdf
from ollama_client import analyze_resume
from prompts import ats_prompt

app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-jwt-key"

UPLOAD_FOLDER = "uploads"
DB_PATH = "database.db"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def ensure_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resume_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            filename TEXT,
            result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES ('admin','admin')"
    )

    conn.commit()
    conn.close()


def get_db():
    ensure_db()
    return sqlite3.connect(DB_PATH)

def generate_jwt(username):
    payload = {
        "sub": username,
        "iat": datetime.datetime.now(datetime.UTC),
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=30)
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

def verify_jwt(token):
    try:
        return jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("index.html", error="Username and password required")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE username=? AND password=?",
            (username, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            token = generate_jwt(username)
            resp = make_response(redirect(url_for("dashboard")))
            resp.set_cookie("token", token, httponly=True, samesite="Lax")
            return resp

        return render_template("index.html", error="Invalid credentials")

    return render_template("index.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    token = request.cookies.get("token")
    payload = verify_jwt(token) if token else None

    if not payload:
        return redirect(url_for("login"))

    if request.method == "POST":
        file = request.files["resume"]
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        resume_text = extract_text_from_pdf(path)
        result = analyze_resume(ats_prompt(resume_text))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO resume_history (username, filename, result) VALUES (?,?,?)",
            (payload["sub"], filename, result)
        )
        conn.commit()
        conn.close()

        return render_template("dashboard.html", result=result, payload=payload)

    return render_template("dashboard.html", payload=payload)

@app.route("/history")
def history():
    token = request.cookies.get("token")
    payload = verify_jwt(token) if token else None

    if not payload:
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, filename, result, created_at FROM resume_history WHERE username=? ORDER BY created_at DESC",
        (payload["sub"],)
    )
    rows = cursor.fetchall()
    conn.close()

    return render_template("history.html", payload=payload, history=rows)

@app.route("/history/delete/<int:rid>", methods=["POST"])
def delete_history(rid):
    token = request.cookies.get("token")
    payload = verify_jwt(token) if token else None

    if not payload:
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM resume_history WHERE id=? AND username=?",
        (rid, payload["sub"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("history"))

from flask import Response
import json
import requests

@app.route("/analyze-stream", methods=["POST"])
def analyze_stream():
    token = request.cookies.get("token")
    payload = verify_jwt(token) if token else None
    if not payload:
        return "", 401

    file = request.files["resume"]
    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    resume_text = extract_text_from_pdf(path)
    prompt = ats_prompt(resume_text)

    def stream():
        url = "http://localhost:11434/api/generate"
        data = {
            "model": "deepseek-r1:1.5b",
            "prompt": prompt,
            "stream": True
        }

        r = requests.post(url, json=data, stream=True)
        final_output = []

        for line in r.iter_lines():
            if line:
                chunk = json.loads(line.decode())
                if "response" in chunk:
                    text = chunk["response"]
                    final_output.append(text)
                    yield text

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO resume_history (username, filename, result) VALUES (?,?,?)",
            (payload["sub"], filename, "".join(final_output))
        )
        conn.commit()
        conn.close()

    return Response(stream(), mimetype="text/event-stream")

@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("login")))
    resp.delete_cookie("token")
    return resp

if __name__ == "__main__":
    app.run(host="192.168.1.20", port=1221, debug=True)

