import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "deepseek-r1:1.5b"

def analyze_resume(prompt):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": True
    }

    response = requests.post(OLLAMA_URL, json=payload, stream=True)
    response.raise_for_status()

    final_output = []

    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode("utf-8"))
            if "response" in data:
                final_output.append(data["response"])

    return "".join(final_output)
