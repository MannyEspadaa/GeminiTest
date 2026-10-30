import os
import hashlib
import secrets
import re
from datetime import datetime
from app.database import get_db

OFFICIAL_DOMAINS = ['.edu', 'official.edu', 'university.edu', 'esports.edu', 'stockton.edu']

def is_official_email(email: str) -> bool:
    if not email or '@' not in email:
        return False
    parts = email.strip().lower().split('@')
    if len(parts) != 2:
        return False
    domain = parts[1]
    # Check if domain ends with .edu or matches any allowed official domain
    if domain.endswith('.edu'):
        return True
    for official in OFFICIAL_DOMAINS:
        if domain == official or domain.endswith('.' + official):
            return True
    return False

def hash_password(password: str, salt: str = None) -> tuple:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hashed, salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    expected_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(expected_hash, password_hash)

def register_user(full_name: str, username: str, email: str, password: str, db_path=None) -> dict:
    if not full_name or not full_name.strip():
        return {"success": False, "error": "Full name is required."}
    if not username or not username.strip():
        return {"success": False, "error": "Username is required."}
    if not email or not email.strip():
        return {"success": False, "error": "Official email is required."}
    if not password or len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    clean_email = email.strip().lower()
    clean_username = username.strip()
    clean_full_name = full_name.strip()

    if not is_official_email(clean_email):
        return {"success": False, "error": "A valid official institutional (.edu) email address is required."}

    conn = get_db(db_path)
    cur = conn.cursor()

    # Check for existing email
    cur.execute("SELECT id FROM users WHERE LOWER(email) = ?", (clean_email,))
    if cur.fetchone():
        conn.close()
        return {"success": False, "error": "An account with this email address already exists."}

    # Check for existing username
    cur.execute("SELECT id FROM users WHERE LOWER(username) = ?", (clean_username.lower(),))
    if cur.fetchone():
        conn.close()
        return {"success": False, "error": "This username is already taken."}

    pwd_hash, pwd_salt = hash_password(password)
    verification_token = secrets.token_urlsafe(16)

    cur.execute("""
        INSERT INTO users (full_name, username, email, password_hash, password_salt, is_verified, verification_token, status)
        VALUES (?, ?, ?, ?, ?, 0, ?, 'active')
    """, (clean_full_name, clean_username, clean_email, pwd_hash, pwd_salt, verification_token))
    
    user_id = cur.lastrowid
    
    # Base role is 'user'
    cur.execute("INSERT INTO user_roles (user_id, role) VALUES (?, 'user')", (user_id,))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "user_id": user_id,
        "email": clean_email,
        "verification_token": verification_token,
        "message": "Account created. Please verify your email using the verification token."
    }

def verify_email(token: str, db_path=None) -> dict:
    if not token or not token.strip():
        return {"success": False, "error": "Verification token is required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, email, is_verified FROM users WHERE verification_token = ?", (token.strip(),))
    user = cur.fetchone()
    if not user:
        conn.close()
        return {"success": False, "error": "Invalid verification token."}

    cur.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user["id"],))
    conn.commit()
    conn.close()

    return {"success": True, "message": "Email successfully verified. You may now log in.", "user_id": user["id"]}

def authenticate_user(username_or_email: str, password: str, db_path=None) -> dict:
    if not username_or_email or not password:
        return {"success": False, "error": "Username/email and password are required."}

    conn = get_db(db_path)
    cur = conn.cursor()
    target = username_or_email.strip().lower()
    cur.execute("""
        SELECT id, full_name, username, email, password_hash, password_salt, is_verified, status
        FROM users
        WHERE LOWER(username) = ? OR LOWER(email) = ?
    """, (target, target))
    user = cur.fetchone()

    if not user:
        conn.close()
        return {"success": False, "error": "Invalid username/email or password."}

    if user["status"] == "suspended":
        conn.close()
        return {"success": False, "error": "This account is currently suspended. Please contact an administrator."}

    if user["status"] == "deactivated":
        conn.close()
        return {"success": False, "error": "This account has been deactivated."}

    if not user["is_verified"]:
        conn.close()
        return {"success": False, "error": "Please verify your email before logging in."}

    if not verify_password(password, user["password_hash"], user["password_salt"]):
        conn.close()
        return {"success": False, "error": "Invalid username/email or password."}

    # Generate session token
    session_token = secrets.token_hex(24)
    cur.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (session_token, user["id"]))
    
    # Retrieve roles
    cur.execute("SELECT role FROM user_roles WHERE user_id = ?", (user["id"],))
    roles = [r["role"] for r in cur.fetchall()]

    conn.commit()
    conn.close()

    return {
        "success": True,
        "token": session_token,
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "username": user["username"],
            "email": user["email"],
            "roles": roles,
            "status": user["status"]
        }
    }

def get_current_user_from_token(token: str, db_path=None) -> dict:
    if not token:
        return None
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.full_name, u.username, u.email, u.status, u.discord_username, u.created_at
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    user = cur.fetchone()
    if not user:
        conn.close()
        return None

    if user["status"] in ("suspended", "deactivated"):
        conn.close()
        return None

    cur.execute("SELECT role FROM user_roles WHERE user_id = ?", (user["id"],))
    roles = [r["role"] for r in cur.fetchall()]

    # Also check if player or community member dynamically based on memberships
    cur.execute("SELECT COUNT(*) as count FROM game_rosters WHERE user_id = ?", (user["id"],))
    roster_count = cur.fetchone()["count"]
    if roster_count > 0 and 'community_member' not in roles:
        roles.append('community_member')

    cur.execute("SELECT COUNT(*) as count FROM team_members WHERE user_id = ?", (user["id"],))
    team_count = cur.fetchone()["count"]
    if team_count > 0 and 'player' not in roles:
        roles.append('player')
        if 'community_member' not in roles:
            roles.append('community_member')

    # Get assigned games for game manager
    cur.execute("SELECT game_id FROM game_manager_assignments WHERE user_id = ?", (user["id"],))
    assigned_games = [r["game_id"] for r in cur.fetchall()]

    conn.close()
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "username": user["username"],
        "email": user["email"],
        "status": user["status"],
        "discord_username": user["discord_username"],
        "roles": roles,
        "assigned_games": assigned_games
    }

def has_role_permission(user: dict, required_role: str) -> bool:
    if not user:
        return False
    roles = user.get("roles", [])
    if "admin" in roles:
        return True
    
    # Hierarchy check
    hierarchy = {
        "user": 1,
        "community_member": 2,
        "player": 3,
        "game_manager": 4,
        "admin": 5
    }
    required_level = hierarchy.get(required_role, 1)
    
    # A user has permission if any of their roles meets or exceeds the required level
    max_user_level = max([hierarchy.get(r, 0) for r in roles] or [0])
    return max_user_level >= required_level

def end_session(token: str, db_path=None):
    if not token:
        return
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
