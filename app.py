import os
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

from resume_parser import extract_text_from_pdf
from ollama_client import analyze_resume
from prompts import ats_prompt

UPLOAD_FOLDER = "uploads"

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["resume"]
        filename = secure_filename(file.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(path)

        resume_text = extract_text_from_pdf(path)
        prompt = ats_prompt(resume_text)
        result = analyze_resume(prompt)

        return render_template("result.html", result=result)

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
