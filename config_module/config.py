import os
import socket
from dotenv import load_dotenv

load_dotenv()

def get_local_ip():
    """Get the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

SECRET_KEY = os.getenv("SECRET_KEY")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
DB_PATH = os.getenv("DB_PATH", "database/database.db")
SERVER_IP = os.getenv("SERVER_IP") or get_local_ip()
SERVER_PORT = int(os.getenv("SERVER_PORT", 1221))
OLLAMA_URL = os.getenv("OLLAMA_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")