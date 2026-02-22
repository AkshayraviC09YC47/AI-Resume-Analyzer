import jwt
import datetime
from flask import request
from config_module.config import SECRET_KEY


def generate_jwt(username):
    """Generate JWT token for authenticated user."""
    payload = {
        "sub": username,
        "iat": datetime.datetime.now(datetime.UTC),
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_jwt(token):
    """Verify and decode JWT token."""
    if not token:
        return None
    
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user():
    """Get current authenticated user from request cookies."""
    token = request.cookies.get("token")
    return verify_jwt(token)