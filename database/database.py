import sqlite3
import os
from config_module.config import DB_PATH

def ensure_db():
    """Initialize database with required tables and default admin user."""
    # Ensure the database directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resume_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            filename TEXT NOT NULL,
            result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    """)

    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES ('admin', 'admin')"
    )

    conn.commit()
    conn.close()


def get_db():
    """Get database connection with row factory enabled."""
    ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_resume_to_history(username, filename, result):
    """Save resume analysis to history."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO resume_history (username, filename, result) VALUES (?, ?, ?)",
            (username, filename, result)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving to history: {e}")
        return False


def get_user_by_credentials(username, password):
    """Get user by username and password."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username FROM users WHERE username=? AND password=?",
        (username, password)
    )
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_history(username):
    """Get resume history for a specific user."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, filename, result, created_at FROM resume_history WHERE username=? ORDER BY created_at DESC",
        (username,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_user_history_entry(entry_id, username):
    """Delete a specific resume history entry for a user."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM resume_history WHERE id=? AND username=?",
        (entry_id, username)
    )
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return affected_rows > 0